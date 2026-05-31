import asyncio
import logging
import os
import re
import shutil
import sys
import tempfile

import channel_registry
import dropbox_module
from epub_functions import create_epub
from telegram import Update
from telegram.ext import Application, CommandHandler, ConversationHandler, ContextTypes, MessageHandler, filters

REAUTH_PHONE = 1
REAUTH_CODE = 2
REAUTH_2FA = 3


class HTTPRequestFilter(logging.Filter):
    def filter(self, record):
        # Фильтруем все HTTP запросы к Telegram API
        return "HTTP Request:" not in record.getMessage()

logging.basicConfig(
    stream=sys.stdout,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Применяем фильтр к различным логгерам, которые могут генерировать HTTP логи
http_filter = HTTPRequestFilter()
logger.addFilter(http_filter)
logging.getLogger('httpx').addFilter(http_filter)
logging.getLogger('urllib3').addFilter(http_filter)
logging.getLogger('telegram').addFilter(http_filter)
logging.getLogger().addFilter(http_filter)  # Корневой логгер

class TelegramToEpub:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.processing_semaphore = asyncio.Semaphore(1)

    def __del__(self):
        try:
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass

    def strip_emojis(self, text: str) -> str:
        """Removes emojis and other special characters from text."""
        if not text:
            return ""
        # Match anything that is NOT a basic character (simplified regex for now)
        # This matches common emoji ranges and some other symbols
        clean = re.sub(r'[^\w\s\-_.,()!?:;а-яёА-ЯЁ/]', '', text)
        # Also collapse multiple spaces
        return re.sub(r'\s+', ' ', clean).strip()

    def extract_title(self, text: str) -> str:
        """Берёт заголовок как первый абзац (до пустой строки)."""
        text = (text or "").strip()
        if not text:
            return "Untitled"
        paragraphs = re.split(r"\n\s*\n", text, maxsplit=1)
        title = (paragraphs[0] or "").strip()
        return title or "Untitled"

    def get_first_link(self, message) -> str:
        """Extract the first URL from message entities or caption entities, fallback to message link."""
        entities = message.entities or message.caption_entities or []
        text = message.text or message.caption or ""
        
        for entity in entities:
            if entity.type == 'text_link':
                return entity.url
            if entity.type == 'url':
                offset = entity.offset
                length = entity.length
                return text[offset:offset+length]
        
        # If no link found in text, try the message link (useful for public channels)
        return message.link or ""

    def get_source_info(self, message) -> str:
        """Get the name of the channel or user forwarded from."""
        forward_origin = getattr(message, "forward_origin", None)
        if not forward_origin:
            return ""
            
        if forward_origin.type == "chat" and forward_origin.sender_chat:
            return forward_origin.sender_chat.title or "Channel"
        elif forward_origin.type == "channel" and forward_origin.sender_chat:
            return forward_origin.sender_chat.title or "Channel"
        elif forward_origin.type == "user" and forward_origin.sender_user:
            return forward_origin.sender_user.full_name or "User"
        elif forward_origin.type == "hidden_user":
            return "Hidden User"
            
        return "Unknown Source"

    def get_message_text(self, message):
        """Get text content from message.text or message.caption"""
        return message.text or message.caption or ""

    def _log_forward_origin(self, forward_origin) -> None:
        """Log forwarded source details without changing message flow."""
        if not forward_origin:
            return

        if forward_origin.type == "user" and forward_origin.sender_user:
            logger.info(
                "Переслано от пользователя: %s",
                forward_origin.sender_user.full_name or forward_origin.sender_user.username,
            )
        elif forward_origin.type == "chat" and forward_origin.sender_chat:
            logger.info("Переслано из чата: %s", forward_origin.sender_chat.title)
        elif forward_origin.type == "channel" and forward_origin.sender_chat:
            logger.info("Переслано из канала: %s", forward_origin.sender_chat.title)
        elif forward_origin.type == "hidden_user":
            logger.info("Переслано от анонимного пользователя")

    def _build_forwarded_post_link(self, forward_origin, fallback_link: str) -> str:
        """Build a public Telegram link for forwarded posts when possible."""
        if (
            forward_origin
            and hasattr(forward_origin, "chat")
            and forward_origin.chat
            and forward_origin.message_id
            and forward_origin.chat.username
        ):
            return f"https://t.me/{forward_origin.chat.username}/{forward_origin.message_id}"
        return fallback_link or ""

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /start is issued."""
        await update.message.reply_text(
            'Привет! Я могу конвертировать сообщения из Telegram в формат EPUB. '
            'Просто перешли мне сообщение, и я создам из него EPUB файл.'
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /help is issued."""
        await update.message.reply_text(
            'Чтобы конвертировать сообщение в EPUB:\n'
            '1. Выберите сообщение, которое хотите конвертировать\n'
            '2. Перешлите его мне\n'
            '3. Я создам EPUB файл и отправлю его вам'
        )

    def _channel_db_path(self) -> str:
        return os.getenv("CHANNEL_REGISTRY_DB", channel_registry.DEFAULT_DB_PATH)

    def _get_admin_id(self):
        raw_admin_id = os.getenv("ADMIN_ID", "").strip()
        if not raw_admin_id:
            return None
        try:
            return int(raw_admin_id)
        except ValueError:
            logger.error("Некорректный ADMIN_ID: %s", raw_admin_id)
            return None

    async def _ensure_admin(self, message) -> bool:
        admin_id = self._get_admin_id()
        if admin_id is None:
            await message.reply_text("❌ ADMIN_ID не настроен. Добавьте ADMIN_ID в переменные окружения.")
            return False

        user_id = getattr(getattr(message, "from_user", None), "id", None)
        if user_id != admin_id:
            logger.warning(
                "ADMIN_CHECK_FAILED expected_admin_id=%s actual_user_id=%s",
                admin_id,
                user_id,
            )
            await message.reply_text("❌ Команда доступна только администратору.")
            return False
        return True

    async def add_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add a channel to monitored registry."""
        message = update.message
        if not message:
            return

        if not await self._ensure_admin(message):
            return

        if len(context.args) != 1:
            await message.reply_text("Использование: /add_channel <channel>")
            return

        channel_input = context.args[0]
        try:
            normalized = channel_registry.normalize_channel_identifier(channel_input)
            added = channel_registry.add_channel(normalized, self._channel_db_path())
        except ValueError:
            await message.reply_text("❌ Некорректный идентификатор канала.")
            return

        if added:
            await message.reply_text(f"✅ Канал добавлен: {normalized}")
        else:
            await message.reply_text(f"ℹ️ Канал уже есть в списке: {normalized}")

    async def del_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove a channel from monitored registry."""
        message = update.message
        if not message:
            return

        if not await self._ensure_admin(message):
            return

        if len(context.args) != 1:
            await message.reply_text("Использование: /del_channel <channel>")
            return

        channel_input = context.args[0]
        try:
            normalized = channel_registry.normalize_channel_identifier(channel_input)
            removed = channel_registry.remove_channel(normalized, self._channel_db_path())
        except ValueError:
            await message.reply_text("❌ Некорректный идентификатор канала.")
            return

        if removed:
            await message.reply_text(f"✅ Канал удалён: {normalized}")
        else:
            await message.reply_text(f"ℹ️ Канал не найден: {normalized}")

    async def list_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List monitored channels."""
        message = update.message
        if not message:
            return

        if not await self._ensure_admin(message):
            return

        channels = channel_registry.get_channels(self._channel_db_path())
        if not channels:
            await message.reply_text("Список каналов пуст.")
            return

        lines = "\n".join(f"- {item}" for item in channels)
        await message.reply_text(f"Отслеживаемые каналы:\n{lines}")

    def format_message(self, text):
        """
        Сохраняет структуру исходного текста, списки, абзацы.
        Все упоминания файлов .md подчёркивает (например, _plan.md_).
        Преобразует переносы строк в <br> и абзацы в <p> для корректного отображения в EPUB.
        """
        link_pattern = re.compile(r'\b[\w\-/]+\.md\b', re.IGNORECASE)
        def underline_md(match):
            return f"<u>{match.group(0)}</u>"
        # Разбиваем на абзацы по двойному переносу
        paragraphs = text.split('\n\n')
        formatted_paragraphs = []
        for para in paragraphs:
            # Подчёркиваем .md-ссылки и заменяем одиночные переносы на <br>
            para = link_pattern.sub(underline_md, para)
            para = para.replace('\n', '<br>')
            formatted_paragraphs.append(f'<p>{para}</p>')
        return '\n'.join(formatted_paragraphs)


    def sanitize_filename(self, title, max_words=4):
        """Create a safe filename from post title (limited to max_words)"""
        if not title or title == "Untitled":
            return "message"
        
        # Take first line or first sentence as filename
        clean_title = title.split('\n')[0].strip()
        if not clean_title:
            clean_title = title.strip()
        
        # Remove or replace unsafe characters
        clean_title = re.sub(r'[^\w\s\-_а-яё]', '', clean_title, flags=re.IGNORECASE)
        clean_title = re.sub(r'\s+', ' ', clean_title.strip())
        
        # Limit to max_words
        words = clean_title.split()
        if len(words) > max_words:
            words = words[:max_words]
        
        # Join with underscores
        clean_title = '_'.join(words)
        
        return clean_title if clean_title else "message"

    async def _process_text_to_dropbox(
        self,
        text_content: str,
        source_name: str,
        source_link: str,
        summary_target,
        source_message=None,
        delete_source_message: bool = False,
    ) -> bool:
        """Build EPUB from text, upload it to Dropbox and send summary reply."""
        processing_msg = await summary_target.reply_text("📚 Создаю EPUB файл...")

        try:
            full_text = text_content
            title = self.extract_title(full_text)
            content = self.format_message(full_text)
            safe_filename = self.sanitize_filename(title)

            with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp_file:
                epub_path = create_epub(title, source_name, content, tmp_file.name)

            if not os.path.exists(epub_path):
                logger.error(f"Файл не был создан: {epub_path}")
                await processing_msg.delete()
                await summary_target.reply_text("❌ Ошибка создания файла")
                return False

            logger.info(f"Инициируем загрузку в Dropbox: {epub_path}")
            dropbox_filename = f"{safe_filename}.epub"
            try:
                dropbox_success = dropbox_module.upload_to_dropbox(epub_path, dropbox_filename)
                if dropbox_success:
                    logger.info("Загрузка в Dropbox завершена успешно")
                else:
                    logger.error("Загрузка в Dropbox не удалась")
            except Exception as e:
                logger.error(f"Ошибка загрузки в Dropbox: {e}")

            try:
                os.remove(epub_path)
            except Exception as e:
                logger.error(f"Ошибка удаления временного файла: {e}")

            clean_title = self.strip_emojis(title)
            clean_source = self.strip_emojis(source_name)

            if source_link:
                summary_text = f'<b><a href="{source_link}">{clean_title}</a></b>'
            else:
                summary_text = f"<b>{clean_title}</b>"

            if clean_source and clean_source != "Unknown Source":
                if summary_text:
                    summary_text += f" {clean_source}"
                else:
                    summary_text = clean_source

            await processing_msg.delete()
            await summary_target.reply_text(
                summary_text,
                disable_web_page_preview=False,
                parse_mode="HTML",
            )

            if delete_source_message and source_message:
                try:
                    await source_message.delete()
                    logger.info("Исходное сообщение удалено")
                except Exception as e:
                    logger.error(f"Не удалось удалить исходное сообщение: {e}")

            return True
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await summary_target.reply_text("❌ Извините, произошла ошибка при обработке вашего сообщения.")
            return False

    async def process_channel_post(
        self,
        text_content: str,
        source_name: str,
        source_identifier: str,
        summary_target,
        post_link: str = "",
    ) -> bool:
        """Process a simulated/ingested channel post via shared EPUB+Dropbox pipeline."""
        if not summary_target:
            logger.error("Пропуск channel post: не указан summary target")
            return False

        if not text_content or not text_content.strip():
            logger.info("Пропуск channel post: текст отсутствует")
            return False

        try:
            normalized = channel_registry.normalize_channel_identifier(source_identifier)
        except ValueError:
            logger.info("Пропуск channel post: некорректный source_identifier")
            return False

        monitored_channels = set(channel_registry.get_channels(self._channel_db_path()))
        if normalized not in monitored_channels:
            logger.info(
                "CHANNEL_NOT_REGISTERED raw=%s normalized=%s monitored=%s",
                source_identifier,
                normalized,
                list(monitored_channels),
            )
            return False

        async with self.processing_semaphore:
            return await self._process_text_to_dropbox(
                text_content=text_content,
                source_name=source_name,
                source_link=post_link,
                summary_target=summary_target,
                source_message=None,
                delete_source_message=False,
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages."""
        message = update.message
        if not message:
            return

        text_content = self.get_message_text(message)
        forward_origin = getattr(message, "forward_origin", None)

        if not message.document:
            if forward_origin and forward_origin.type in ["user", "chat", "hidden_user", "channel"]:
                if not text_content:
                    logger.info("Forwarded message does not contain text")
                    await message.reply_text(
                        "Пересланное сообщение не содержит текста. Пожалуйста, перешлите сообщение с текстом."
                    )
                    return
            elif not text_content:
                logger.info("Сообщение не содержит текста.")
                await message.reply_text(
                    "Сообщение не содержит текста. Пожалуйста, перешлите сообщение с текстом."
                )
                return

        async with self.processing_semaphore:
            if message.document:
                await self._process_uploaded_epub(message, context)
                return

            logger.info(f"Обработка сообщения от пользователя: {message.chat.id}")
            self._log_forward_origin(forward_origin)
            source_name = self.get_source_info(message)
            link = self.get_first_link(message)
            post_link = self._build_forwarded_post_link(forward_origin, link)

            await self._process_text_to_dropbox(
                text_content=text_content,
                source_name=source_name,
                source_link=post_link,
                summary_target=message,
                source_message=message,
                delete_source_message=True,
            )

    async def _process_uploaded_epub(self, message, context):
        """Process an uploaded EPUB document and forward it back with Dropbox sync."""
        document = message.document
        if not document:
            return

        file_name = document.file_name or "document.epub"
        is_epub = (document.mime_type == "application/epub+zip") or file_name.lower().endswith(".epub")

        if not is_epub:
            logger.info("Получен неподдерживаемый тип документа.")
            await message.reply_text(
                "Сейчас поддерживаются только EPUB документы. Пожалуйста, отправьте файл с расширением .epub."
            )
            return

        logger.info("Обработка загруженного EPUB документа.")
        processing_msg = await message.reply_text("📚 Получен EPUB файл, подготавливаю отправку...")
        temp_path = None

        try:
            telegram_file = await context.bot.get_file(document.file_id)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp_file:
                temp_path = tmp_file.name

            await telegram_file.download_to_drive(custom_path=temp_path)

            base_name = os.path.splitext(file_name)[0]
            safe_filename = self.sanitize_filename(base_name) or "document"
            send_filename = f"{safe_filename}.epub"
            
            # Prepare caption
            forward_origin = getattr(message, "forward_origin", None)
            source_name = self.get_source_info(message)
            clean_title = self.strip_emojis(base_name)
            clean_source = self.strip_emojis(source_name)
            
            # Link for caption
            post_link = ""
            if forward_origin and hasattr(forward_origin, "chat") and forward_origin.chat and forward_origin.message_id:
                if forward_origin.chat.username:
                    post_link = f"https://t.me/{forward_origin.chat.username}/{forward_origin.message_id}"
            
            if post_link:
                caption = f'<b><a href="{post_link}">{clean_title}</a></b>'
            else:
                caption = f'<b>{clean_title}</b>'
            
            if clean_source and clean_source != "Unknown Source":
                caption += f" {clean_source}"

            await processing_msg.delete()
            with open(temp_path, "rb") as epub_file:
                await message.reply_document(
                    document=epub_file,
                    filename=send_filename,
                    caption=caption,
                    parse_mode='HTML'
                )
            logger.info("EPUB документ отправлен пользователю.")

            try:
                dropbox_filename = send_filename
                dropbox_module.upload_to_dropbox(temp_path, dropbox_filename)
                logger.info("EPUB документ загружен в Dropbox.")
            except Exception as e:
                logger.error(f"Ошибка при загрузке EPUB в Dropbox: {e}")
        except Exception as e:
            logger.error(f"Ошибка обработки входящего EPUB документа: {e}")
            try:
                await processing_msg.delete()
            except Exception:
                logger.error("Не удалось удалить сообщение о обработке (EPUB документ).")
            await message.reply_text("❌ Извините, произошла ошибка при обработке файла EPUB.")
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    logger.error("Не удалось удалить временный EPUB файл.")
    

async def _notify_admin(application, admin_id: int | None, text: str) -> None:
    if admin_id is None:
        return
    try:
        await application.bot.send_message(chat_id=admin_id, text=text)
    except Exception as e:
        logger.error("Не удалось уведомить админа: %s", e)


def _get_admin_id_from_env() -> int | None:
    raw = os.getenv("ADMIN_ID", "").strip()
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


async def reauth_start(update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return ConversationHandler.END

    admin_id = _get_admin_id_from_env()
    user_id = getattr(getattr(message, "from_user", None), "id", None)
    if admin_id is None or user_id != admin_id:
        await message.reply_text("❌ Команда доступна только администратору.")
        return ConversationHandler.END

    api_id_raw = os.getenv("API_ID", "").strip()
    api_hash = os.getenv("API_HASH", "").strip()
    session_name = os.getenv("USERBOT_SESSION", "tg2book_userbot").strip()

    if not api_id_raw or not api_hash:
        await message.reply_text("❌ Не заданы API_ID/API_HASH. Проверьте .env")
        return ConversationHandler.END

    phone = os.getenv("USERBOT_PHONE", "79296212402").strip()
    if not phone.startswith("+"):
        phone = "+" + phone

    # Используем временную сессию чтобы не конфликтовать с протухшей
    tmp_session = session_name + "_reauth_tmp"

    try:
        from telethon import TelegramClient
        api_id = int(api_id_raw)
        # Удаляем старый tmp если остался с прошлой попытки
        for ext in ("", ".session"):
            p = tmp_session + ext if not ext else tmp_session + ext
            try:
                os.remove(p)
            except FileNotFoundError:
                pass
        client = TelegramClient(tmp_session, api_id, api_hash)
        await client.connect()
        await client.send_code_request(phone)
        context.bot_data["reauth_client"] = client
        context.bot_data["reauth_session_name"] = session_name
        context.bot_data["reauth_tmp_session"] = tmp_session
        context.user_data["reauth_phone"] = phone
    except Exception as e:
        logger.error("reauth_start: ошибка инициализации: %s", e)
        await message.reply_text(f"❌ Ошибка: {e}")
        return ConversationHandler.END

    await message.reply_text(
        f"🔑 Код отправлен на {phone}.\n\n"
        "⚠️ ВАЖНО: введите код *с пробелами или дефисами между цифрами*, "
        "например `1 2 3 4 5` или `1-2-3-4-5`.\n\n"
        "Если ввести код слитно, Telegram распознает его как логин-код "
        "в сообщении и мгновенно аннулирует (ошибка «code expired»). "
        "Разделители это предотвращают.",
        parse_mode="Markdown",
    )
    return REAUTH_CODE


async def reauth_phone(update, context: ContextTypes.DEFAULT_TYPE):
    # Этот шаг больше не используется (телефон берётся из USERBOT_PHONE),
    # но оставлен для совместимости с ConversationHandler состоянием.
    message = update.message
    phone = (message.text or "").strip()
    client = context.bot_data.get("reauth_client")

    if not client:
        await message.reply_text("❌ Сессия реавторизации не найдена. Начните заново: /reauth")
        return ConversationHandler.END

    try:
        await client.send_code_request(phone)
        context.user_data["reauth_phone"] = phone
        await message.reply_text("🔑 Введите код из Telegram:")
        return REAUTH_CODE
    except Exception as e:
        logger.error("reauth_phone error: %s", e)
        await message.reply_text(f"❌ Ошибка отправки кода: {e}\nНачните заново: /reauth")
        await _cleanup_reauth_client(context)
        return ConversationHandler.END


async def reauth_code(update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    # Telegram аннулирует логин-код, если он проходит через сообщение слитно.
    # Просим вводить с разделителями и выкидываем всё кроме цифр.
    code = re.sub(r"\D", "", message.text or "")
    phone = context.user_data.get("reauth_phone", "")
    client = context.bot_data.get("reauth_client")

    if not client:
        await message.reply_text("❌ Сессия реавторизации не найдена. Начните заново: /reauth")
        return ConversationHandler.END

    if not code:
        await message.reply_text("❌ В сообщении нет цифр. Введите код, например `1 2 3 4 5`.")
        return REAUTH_CODE

    try:
        await client.sign_in(phone, code)
        await client.disconnect()
        _replace_session(context)
        context.bot_data.pop("reauth_client", None)
        context.user_data.pop("reauth_phone", None)
        restart_event = context.bot_data.get("restart_event")
        if restart_event:
            restart_event.set()
        await message.reply_text("✅ Переавторизация успешна! Userbot перезапускается...")
        logger.info("REAUTH_SUCCESS — userbot restart triggered")
        return ConversationHandler.END
    except Exception as e:
        if type(e).__name__ == "SessionPasswordNeededError":
            await message.reply_text("🔐 Введите пароль двухфакторной аутентификации:")
            return REAUTH_2FA
        logger.error("reauth_code error: %s", e)
        await message.reply_text(f"❌ Ошибка входа: {e}\nНачните заново: /reauth")
        await _cleanup_reauth_client(context)
        return ConversationHandler.END


async def reauth_2fa(update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    password = (message.text or "").strip()
    client = context.bot_data.get("reauth_client")

    if not client:
        await message.reply_text("❌ Сессия реавторизации не найдена. Начните заново: /reauth")
        return ConversationHandler.END

    try:
        await client.sign_in(password=password)
        await client.disconnect()
        _replace_session(context)
        context.bot_data.pop("reauth_client", None)
        context.user_data.pop("reauth_phone", None)
        restart_event = context.bot_data.get("restart_event")
        if restart_event:
            restart_event.set()
        await message.reply_text("✅ Переавторизация успешна! Userbot перезапускается...")
        logger.info("REAUTH_SUCCESS_2FA — userbot restart triggered")
        return ConversationHandler.END
    except Exception as e:
        logger.error("reauth_2fa error: %s", e)
        await message.reply_text(f"❌ Ошибка 2FA: {e}\nНачните заново: /reauth")
        await _cleanup_reauth_client(context)
        return ConversationHandler.END


async def reauth_cancel(update, context: ContextTypes.DEFAULT_TYPE):
    await _cleanup_reauth_client(context)
    if update.message:
        await update.message.reply_text("Реавторизация отменена.")
    return ConversationHandler.END


def _replace_session(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Перезаписывает основной session-файл временным после успешного reauth."""
    tmp = context.bot_data.pop("reauth_tmp_session", None)
    target = context.bot_data.pop("reauth_session_name", None)
    if not tmp or not target:
        return
    tmp_file = tmp + ".session"
    target_file = target + ".session"
    try:
        if os.path.exists(tmp_file):
            os.replace(tmp_file, target_file)
            logger.info("REAUTH session replaced: %s -> %s", tmp_file, target_file)
    except Exception as e:
        logger.error("REAUTH session replace failed: %s", e)


async def _cleanup_reauth_client(context: ContextTypes.DEFAULT_TYPE) -> None:
    client = context.bot_data.pop("reauth_client", None)
    context.user_data.pop("reauth_phone", None)
    if client:
        try:
            await client.disconnect()
        except Exception:
            pass


async def run_bot():
    """Start the combined bot and userbot."""
    from userbot_listener import run_userbot_listener

    # Get the token from environment variable
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
        return

    # Create the Application and pass it your bot's token
    application = Application.builder().token(token).build()

    # Create an instance of our converter
    converter = TelegramToEpub()

    # Add handlers
    application.add_handler(CommandHandler("start", converter.start))
    application.add_handler(CommandHandler("help", converter.help))
    application.add_handler(CommandHandler("add_channel", converter.add_channel))
    application.add_handler(CommandHandler("del_channel", converter.del_channel))
    application.add_handler(CommandHandler("list_channels", converter.list_channels))
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("reauth", reauth_start)],
        states={
            REAUTH_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reauth_phone)],
            REAUTH_CODE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, reauth_code)],
            REAUTH_2FA:   [MessageHandler(filters.TEXT & ~filters.COMMAND, reauth_2fa)],
        },
        fallbacks=[CommandHandler("cancel", reauth_cancel)],
    ))
    application.add_handler(MessageHandler(filters.ALL, converter.handle_message))

    async with application:
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logger.info("Bot API polling started.")

        # Optional Userbot consolidation
        api_id = os.getenv("API_ID")
        api_hash = os.getenv("API_HASH")
        if api_id and api_hash:
            admin_id = _get_admin_id_from_env()
            restart_event = asyncio.Event()
            application.bot_data["restart_event"] = restart_event

            retry_delay = 30
            max_delay = 1800
            while True:
                restart_event.clear()
                logger.info("Starting consolidated Userbot listener...")
                try:
                    await run_userbot_listener(converter=converter)
                    logger.warning("Userbot disconnected cleanly, restarting in %ds...", retry_delay)
                    retry_delay = 30
                except EOFError:
                    logger.error("Userbot needs re-authorization (EOF). Notifying admin.")
                    await _notify_admin(
                        application, admin_id,
                        "⚠️ Userbot: сессия протухла.\nИспользуй /reauth для переавторизации без SSH."
                    )
                    retry_delay = max_delay
                except Exception as e:
                    logger.error("Userbot listener failed: %s. Retry in %ds.", e, retry_delay)
                    retry_delay = min(retry_delay * 2, max_delay)

                try:
                    await asyncio.wait_for(restart_event.wait(), timeout=retry_delay)
                    logger.info("Userbot restart triggered manually, restarting now.")
                    retry_delay = 30
                except asyncio.TimeoutError:
                    pass
        else:
            logger.info("Userbot NOT configured (missing API_ID/HASH). Bot API only.")
            await asyncio.Event().wait()


def main():
    """Main entry point."""
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot shutdown by user.")

if __name__ == '__main__':
    main()
