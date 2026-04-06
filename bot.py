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
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

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
            logger.info("Пропуск channel post: канал не зарегистрирован (%s)", normalized)
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
    

def main():
    """Start the bot."""
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
    application.add_handler(MessageHandler(filters.ALL, converter.handle_message))

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()
