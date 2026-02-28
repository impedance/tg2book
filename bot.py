import asyncio
import logging
import os
import shutil
import sys
import tempfile
from logging.handlers import RotatingFileHandler
from typing import Any, List, Optional

from telegram import Message, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import settings
from services import epub_service
from utils.text_utils import sanitize_filename, strip_emojis

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


# Убеждаемся, что директория для логов существует
_log_dir = os.path.join("data", "logs")
os.makedirs(_log_dir, exist_ok=True)
_log_file = os.path.join(_log_dir, "bot.log")

# Настраиваем ротацию: макс 10 МБ на файл, храним 5 старых файлов
_file_handler = RotatingFileHandler(
    _log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_console_handler = logging.StreamHandler(sys.stdout)

# Задача 1: базовый уровень INFO — убирает отладочный шум от сторонних библиотек
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[_file_handler, _console_handler],
)

# Задача 3: внутренний логгер модуля остаётся на DEBUG для отладки нашей бизнес-логики
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Задача 2: явно глушим многословные сетевые библиотеки до WARNING
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Userbot (Pyrogram) — optional, only active when API_ID / API_HASH are set
# ---------------------------------------------------------------------------

_pyrogram_available = False
try:
    from pyrogram import Client as PyrogramClient
    from pyrogram import filters as pyro_filters

    _pyrogram_available = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Processing queue item
# ---------------------------------------------------------------------------


class _QueueItem:
    """Holds the data needed to process one message from a monitored channel."""

    def __init__(
        self,
        text: str,
        source_name: str,
        post_link: str,
        reply_chat_id: int,
        bot: Any,
    ):
        self.text = text
        self.source_name = source_name
        self.post_link = post_link
        self.reply_chat_id = reply_chat_id
        self.bot = bot


# ---------------------------------------------------------------------------
# Main bot class
# ---------------------------------------------------------------------------


class TelegramToEpub:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        # Producer-Consumer queue: capacity = unlimited, concurrency enforced by single worker
        self.processing_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._sync_task: Optional[asyncio.Task] = None
        self._userbot: Optional[Any] = None  # Pyrogram Client or None

    def __del__(self):
        try:
            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Lifecycle hooks (called by python-telegram-bot Application)
    # ------------------------------------------------------------------

    async def post_init(self, application: Application) -> None:
        """Start background worker and optionally the Pyrogram userbot."""
        # Start queue worker
        self._worker_task = asyncio.create_task(self._channel_worker())
        logger.info("Queue worker started")

        # Start Pyrogram userbot if credentials are configured
        if _pyrogram_available and settings.API_ID and settings.API_HASH:
            await self._start_userbot(application)
            if self._userbot:
                self._sync_task = asyncio.create_task(self._dialogs_sync_worker())
        else:
            logger.info(
                "Userbot не настроен (API_ID / API_HASH отсутствуют). "
                "Автопересылка из каналов отключена."
            )

    async def post_stop(self, application: Application) -> None:
        """Stop background worker and Pyrogram userbot gracefully."""
        # Stop queue worker
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Queue worker stopped")

        # Stop dialogs sync worker
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        # Stop Pyrogram userbot
        if self._userbot:
            try:
                await self._userbot.stop()
                logger.info("Pyrogram userbot stopped")
            except Exception as e:
                logger.error(f"Ошибка при остановке юзербота: {e}")

    # ------------------------------------------------------------------
    # Pyrogram userbot
    # ------------------------------------------------------------------

    async def _start_userbot(self, application: Application) -> None:
        """Initialize and start the Pyrogram client inside the current event loop."""
        import os
        from pathlib import Path

        data_dir = Path(os.environ.get("DATA_DIR", "data"))
        data_dir.mkdir(parents=True, exist_ok=True)
        session_name = str(data_dir / "userbot")

        if settings.USERBOT_SESSION_STRING:
            logger.info(f"Используем USERBOT_SESSION_STRING для авторизации. Сохраняем в {session_name}.session")
            self._userbot = PyrogramClient(
                session_name,
                session_string=settings.USERBOT_SESSION_STRING,
                api_id=settings.API_ID,
                api_hash=settings.API_HASH,
                no_updates=False,
            )
        else:
            logger.info(f"Используем файл сессии: {session_name}.session")
            self._userbot = PyrogramClient(
                session_name,
                api_id=settings.API_ID,
                api_hash=settings.API_HASH,
                no_updates=False,
            )

        @self._userbot.on_message()
        @self._userbot.on_edited_message()
        async def _log_all_messages(client, message):
            chat_title = message.chat.title if message.chat else "Private"
            chat_type = message.chat.type if message.chat else "Unknown"
            logger.debug(f"🔍 Юзербот видит сообщение в [{chat_type}] {chat_title}")
            # continue processing by falling through to other handlers
            message.continue_propagation()

        # Register the channel message handler on the Pyrogram client
        @self._userbot.on_message(pyro_filters.channel | pyro_filters.group)
        @self._userbot.on_edited_message(pyro_filters.channel | pyro_filters.group)
        async def _on_channel_message(client, message):
            await self._handle_channel_message(message, application.bot)

        await self._userbot.start()
        me = await self._userbot.get_me()
        logger.info(f"Pyrogram userbot запущен как @{me.username} (id={me.id})")

        # Принудительно кэшируем все диалоги, чтобы избежать ошибки "Peer id invalid"
        try:
            async for _ in self._userbot.get_dialogs():
                pass
            logger.info("Кэш диалогов юзербота успешно обновлен.")
        except Exception as e:
            logger.warning(f"Не удалось обновить кэш диалогов при старте: {e}")

    # ------------------------------------------------------------------
    # Dialogs background sync worker
    # ------------------------------------------------------------------

    async def _dialogs_sync_worker(self) -> None:
        """Фоновая задача для периодического обновления кэша диалогов."""
        while True:
            await asyncio.sleep(3600)  # Спим 1 час
            if self._userbot:
                try:
                    async for _ in self._userbot.get_dialogs():
                        pass
                    logger.debug("Фоновое обновление кэша диалогов завершено.")
                except Exception as e:
                    logger.debug(f"Ошибка при фоновом обновлении диалогов: {e}")

    # ------------------------------------------------------------------
    # Channel message handler (Pyrogram)
    # ------------------------------------------------------------------

    async def _handle_channel_message(self, pyro_message: Any, ptb_bot: Any) -> None:
        """Called by Pyrogram when a new message arrives in any channel."""
        from userbot_db import get_channels

        # Check if this channel is in our watchlist
        channels = await get_channels()
        
        chat_username = (pyro_message.chat.username or "").lower()
        chat_id = str(pyro_message.chat.id)
        chat_title = pyro_message.chat.title or "Unknown"
        
        logger.debug(
            f"📥 Юзербот поймал сообщение из канала:\n"
            f"   Название: {chat_title}\n"
            f"   Username: @{chat_username}\n"
            f"   ID: {chat_id}\n"
            f"   Текст/капча есть: {bool(pyro_message.text or pyro_message.caption)}\n"
            f"   База отслеживаемых: {channels}"
        )

        # A channel matches if any of the following is found in the DB:
        # 1. The exact username (without @, lowercased)
        # 2. The exact chat ID (e.g. "-100123456")
        # 3. An invite link (we check if it's in the DB, though invite links don't match username/id easily.
        #    Actually, if they added an invite link, we might not know the mapping unless we joined via it.
        #    For now, let's at least compare username and ID.
        
        is_monitored = False
        for ch in channels:
            ch_lower = ch.lower()
            if chat_username and chat_username == ch_lower:
                is_monitored = True
                break
            if chat_id == ch_lower:
                is_monitored = True
                break
            # Quick hack: if the user added "https://t.me/chat_username", match the username part
            if chat_username and chat_username in ch_lower:
                is_monitored = True
                break
                
        if not is_monitored:
            logger.debug(f"⏭️ Канал '{chat_title}' (id={chat_id}) не отслеживается, пропускаем.")
            return

        text = pyro_message.text or pyro_message.caption or ""
        if not text:
            logger.debug(f"Канал '{chat_title}': сообщение без текста, пропускаем")
            return

        admin_id = settings.ADMIN_ID
        if not admin_id:
            logger.warning("ADMIN_ID не задан. Некуда отправить результат из канала.")
            return

        source_name = pyro_message.chat.title or chat_username
        post_link = ""
        if pyro_message.chat.username:
            post_link = (
                f"https://t.me/{pyro_message.chat.username}/{pyro_message.id}"
            )

        item = _QueueItem(
            text=text,
            source_name=source_name,
            post_link=post_link,
            reply_chat_id=admin_id,
            bot=ptb_bot,
        )
        await self.processing_queue.put(item)
        logger.info(
            f"Сообщение из @{chat_username} помещено в очередь (size={self.processing_queue.qsize()})"
        )

    # ------------------------------------------------------------------
    # Background worker (Producer-Consumer, concurrency = 1)
    # ------------------------------------------------------------------

    async def _channel_worker(self) -> None:
        """Consumes _QueueItem objects one at a time, converts text → EPUB, sends to admin."""
        logger.info("Channel worker ожидает задачи...")
        while True:
            try:
                item: _QueueItem = await self.processing_queue.get()
                try:
                    await self._process_queue_item(item)
                except Exception as e:
                    logger.error(f"Ошибка обработки задачи из очереди: {e}")
                finally:
                    self.processing_queue.task_done()
            except asyncio.CancelledError:
                logger.info("Channel worker отменён, выходим")
                break

    async def _process_queue_item(self, item: _QueueItem) -> None:
        """Convert a channel message to EPUB and send it to the admin."""
        logger.info(f"Обработка из очереди: source={item.source_name!r}")
        summary_text = await epub_service.process_text_to_epub(
            item.text, item.source_name, item.post_link
        )
        await item.bot.send_message(
            chat_id=item.reply_chat_id,
            text=summary_text,
            parse_mode="HTML",
            disable_web_page_preview=False,
        )
        logger.info(f"EPUB из канала '{item.source_name}' отправлен на admin {item.reply_chat_id}")

    # ------------------------------------------------------------------
    # Helpers shared between PTB and Pyrogram paths
    # ------------------------------------------------------------------

    def get_first_link(self, message: Message) -> str:
        """Extract the first URL from message entities or caption entities, fallback to message link."""
        entities: List[Any] = list(message.entities or message.caption_entities or [])
        text = message.text or message.caption or ""

        for entity in entities:
            if entity.type == "text_link":
                return str(entity.url)
            if entity.type == "url":
                offset = entity.offset
                length = entity.length
                return str(text[offset : offset + length])

        return str(message.link or "")

    def get_source_info(self, message: Message) -> str:
        """Get the name of the channel or user forwarded from."""
        forward_origin = getattr(message, "forward_origin", None)
        if not forward_origin:
            return ""

        if forward_origin.type == "chat" and getattr(forward_origin, "sender_chat", None):
            return forward_origin.sender_chat.title or "Channel"
        elif forward_origin.type == "channel" and getattr(forward_origin, "chat", None):
            return forward_origin.chat.title or "Channel"
        elif forward_origin.type == "user" and getattr(forward_origin, "sender_user", None):
            return forward_origin.sender_user.full_name or "User"
        elif forward_origin.type == "hidden_user":
            return "Hidden User"

        return "Unknown Source"

    def get_message_text(self, message: Message) -> str:
        """Get text content from message.text or message.caption"""
        return message.text or message.caption or ""

    # ------------------------------------------------------------------
    # Admin-only check
    # ------------------------------------------------------------------

    def _is_admin(self, user_id: int) -> bool:
        return settings.ADMIN_ID is not None and user_id == settings.ADMIN_ID

    # ------------------------------------------------------------------
    # PTB command handlers
    # ------------------------------------------------------------------

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /start is issued."""
        if update.message:
            await update.message.reply_text(
                "Привет! Я могу конвертировать сообщения из Telegram в формат EPUB. "
                "Просто перешли мне сообщение, и я создам из него EPUB файл."
            )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /help is issued."""
        if update.message:
            await update.message.reply_text(
                "Чтобы конвертировать сообщение в EPUB:\n"
                "1. Выберите сообщение, которое хотите конвертировать\n"
                "2. Перешлите его мне\n"
                "3. Я создам EPUB файл и отправлю его вам\n\n"
                "Команды управления каналами (только для администратора):\n"
                "/add_channel @username — добавить канал для отслеживания\n"
                "/del_channel @username — удалить канал\n"
                "/list_channels — список отслеживаемых каналов"
            )

    async def add_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Add a channel to the monitored list (admin only)."""
        if not update.message:
            return
        if not self._is_admin(update.message.from_user.id):
            await update.message.reply_text("⛔ Команда доступна только администратору.")
            return

        if not context.args:
            await update.message.reply_text("Использование: /add_channel <@username или username>")
            return

        from userbot_db import add_channel as db_add_channel

        username = context.args[0].lstrip("@").lower()
        added = await db_add_channel(username)
        if added:
            await update.message.reply_text(f"✅ Канал @{username} добавлен в список отслеживания.")
        else:
            await update.message.reply_text(f"ℹ️ Канал @{username} уже в списке.")

    async def del_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Remove a channel from the monitored list (admin only)."""
        if not update.message:
            return
        if not self._is_admin(update.message.from_user.id):
            await update.message.reply_text("⛔ Команда доступна только администратору.")
            return

        if not context.args:
            await update.message.reply_text("Использование: /del_channel <@username или username>")
            return

        from userbot_db import remove_channel as db_remove_channel

        username = context.args[0].lstrip("@").lower()
        removed = await db_remove_channel(username)
        if removed:
            await update.message.reply_text(f"✅ Канал @{username} удалён из списка.")
        else:
            await update.message.reply_text(f"ℹ️ Канал @{username} не найден в списке.")

    async def list_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List all monitored channels (admin only)."""
        if not update.message:
            return
        if not self._is_admin(update.message.from_user.id):
            await update.message.reply_text("⛔ Команда доступна только администратору.")
            return

        from userbot_db import get_channels as db_get_channels

        channels = await db_get_channels()
        if not channels:
            await update.message.reply_text("Список отслеживаемых каналов пуст.")
        else:
            lines = []
            for ch in channels:
                if ch.startswith("http"):
                    lines.append(f"• {ch}")
                elif ch.startswith("-") or ch.isdigit():
                    lines.append(f"• {ch}")
                else:
                    lines.append(f"• @{ch}")
            lines_str = "\n".join(lines)
            await update.message.reply_text(f"📋 Отслеживаемые каналы:\n{lines_str}")

    # ------------------------------------------------------------------
    # PTB message handler (forwarded messages & direct EPUB uploads)
    # ------------------------------------------------------------------

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

        if message.document:
            await self._process_uploaded_epub(message, context)
            return

        logger.info(f"Обработка сообщения от пользователя: {message.chat.id}")

        if forward_origin:
            if forward_origin.type == "user" and forward_origin.sender_user:
                logger.info(
                    f"Переслано от пользователя: {forward_origin.sender_user.full_name or forward_origin.sender_user.username}"
                )
            elif forward_origin.type == "chat" and forward_origin.sender_chat:
                logger.info(f"Переслано из чата: {forward_origin.sender_chat.title}")
            elif forward_origin.type == "channel" and forward_origin.sender_chat:
                logger.info(f"Переслано из канала: {forward_origin.sender_chat.title}")
            elif forward_origin.type == "hidden_user":
                logger.info("Переслано от анонимного пользователя")

        processing_msg = await message.reply_text("📚 Создаю EPUB файл...")

        try:
            source_name = self.get_source_info(message)
            first_link = self.get_first_link(message)

            post_link = ""
            if (
                forward_origin
                and hasattr(forward_origin, "chat")
                and forward_origin.chat
                and forward_origin.message_id
            ):
                if forward_origin.chat.username:
                    post_link = f"https://t.me/{forward_origin.chat.username}/{forward_origin.message_id}"

            if not post_link:
                post_link = first_link

            summary_text = await epub_service.process_text_to_epub(
                text_content, source_name, post_link
            )

            await processing_msg.delete()
            await message.reply_text(
                summary_text, disable_web_page_preview=False, parse_mode="HTML"
            )

            try:
                await message.delete()
                logger.info("Исходное сообщение удалено")
            except Exception as e:
                logger.error(f"Не удалось удалить исходное сообщение: {e}")

        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await message.reply_text(
                "❌ Извините, произошла ошибка при обработке вашего сообщения."
            )

    async def _process_uploaded_epub(
        self, message: Message, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Process an uploaded EPUB document and forward it back with Dropbox sync."""
        document = message.document
        if not document:
            return

        file_name = document.file_name or "document.epub"
        is_epub = (document.mime_type == "application/epub+zip") or file_name.lower().endswith(
            ".epub"
        )

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
            safe_filename = sanitize_filename(base_name) or "document"
            send_filename = f"{safe_filename}.epub"

            forward_origin = getattr(message, "forward_origin", None)
            source_name = self.get_source_info(message)
            clean_title = strip_emojis(base_name)
            clean_source = strip_emojis(source_name)

            post_link = ""
            if (
                forward_origin
                and hasattr(forward_origin, "chat")
                and forward_origin.chat
                and forward_origin.message_id
            ):
                if forward_origin.chat.username:
                    post_link = (
                        f"https://t.me/{forward_origin.chat.username}/{forward_origin.message_id}"
                    )

            if post_link:
                caption = f'<b><a href="{post_link}">{clean_title}</a></b>'
            else:
                caption = f"<b>{clean_title}</b>"

            if clean_source and clean_source != "Unknown Source":
                caption += f" {clean_source}"

            await processing_msg.delete()
            with open(temp_path, "rb") as epub_file:
                await message.reply_document(
                    document=epub_file, filename=send_filename, caption=caption, parse_mode="HTML"
                )
            logger.info("EPUB документ отправлен пользователю.")

            dropbox_success = await epub_service.process_file_to_dropbox(temp_path, file_name)

            if dropbox_success:
                logger.info("Загрузка в Dropbox документа завершена успешно")
            else:
                logger.error("Загрузка в Dropbox документа не удалась")
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


# ---------------------------------------------------------------------------
# DB init on startup
# ---------------------------------------------------------------------------


async def _init_db_on_startup(application: Application) -> None:
    """Ensure the SQLite channel database is initialized before the bot starts."""
    from userbot_db import init_db

    await init_db()
    logger.info("Channel DB инициализирована")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the bot."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN is not set")
        return

    converter = TelegramToEpub()

    # Chain DB init → converter startup into a single post_init callback
    async def _post_init(application: Application) -> None:
        await _init_db_on_startup(application)
        await converter.post_init(application)
        
        # Register bot commands automatically
        from telegram import BotCommand
        
        commands = [
            BotCommand("start", "Запустить бота"),
            BotCommand("help", "Справка по командам"),
            BotCommand("list_channels", "Список отслеживаемых каналов (Админ)"),
            BotCommand("add_channel", "Добавить канал (Админ)"),
            BotCommand("del_channel", "Удалить канал (Админ)"),
        ]
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands menu updated")

    application = (
        Application.builder()
        .token(token)
        .post_init(_post_init)
        .post_stop(converter.post_stop)
        .build()
    )

    # Handlers
    application.add_handler(CommandHandler("start", converter.start))
    application.add_handler(CommandHandler("help", converter.help))
    application.add_handler(CommandHandler("add_channel", converter.add_channel))
    application.add_handler(CommandHandler("del_channel", converter.del_channel))
    application.add_handler(CommandHandler("list_channels", converter.list_channels))
    application.add_handler(MessageHandler(filters.ALL, converter.handle_message))

    application.run_polling()




if __name__ == "__main__":
    main()
