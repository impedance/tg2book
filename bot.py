from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sys
import tempfile
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING, Any, Optional

from pyrogram import Client, filters as pyro_filters
from pyrogram.types import BotCommand

if TYPE_CHECKING:
    from pyrogram.types import Message

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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[_file_handler, _console_handler],
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Глушим многословные сетевые библиотеки
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)


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
# Admin filter (Pyrogram)
# ---------------------------------------------------------------------------


async def _is_admin_check(_, __, message: Message) -> bool:
    """Pyrogram filter: True only for the configured ADMIN_ID."""
    return bool(
        message.from_user and settings.ADMIN_ID and message.from_user.id == settings.ADMIN_ID
    )


is_admin = pyro_filters.create(_is_admin_check)


# ---------------------------------------------------------------------------
# Main bot class
# ---------------------------------------------------------------------------


class TelegramToEpub:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        # Producer-Consumer queue: unlimited capacity, single worker
        self.processing_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._sync_task: Optional[asyncio.Task] = None
        self._userbot: Optional[Client] = None
        self._bot: Optional[Client] = None
        # In-memory cache of monitored channels — avoid per-message DB hits
        self._monitored_channels_cache: dict = {"usernames": set(), "ids": set()}

    def __del__(self):
        try:
            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # In-memory cache helpers
    # ------------------------------------------------------------------

    async def _load_channels_cache(self) -> None:
        """Load monitored channels from DB into in-memory sets (called once on startup)."""
        from userbot_db import get_channels

        try:
            channels = await get_channels()
            usernames: set = set()
            ids: set = set()
            for ch in channels:
                ch_norm = ch.lstrip("@").lower()
                if ch_norm.lstrip("-").isdigit():
                    ids.add(ch_norm)
                else:
                    usernames.add(ch_norm)
            self._monitored_channels_cache = {"usernames": usernames, "ids": ids}
            logger.info(
                f"Кэш каналов загружен: {len(usernames)} username(s), {len(ids)} id(s)"
            )
        except Exception as e:
            logger.error(f"Не удалось загрузить кэш каналов из БД: {e}. Отслеживание отключено до перезапуска.")
            self._monitored_channels_cache = {"usernames": set(), "ids": set()}

    def _make_monitored_filter(self) -> Any:
        """Return a Pyrogram filter that passes only messages from monitored channels."""
        cache = self._monitored_channels_cache

        def _is_monitored(_, __, message) -> bool:  # type: ignore[return]
            chat = getattr(message, "chat", None)
            if chat is None:
                return False
            chat_id = str(getattr(chat, "id", ""))
            username = getattr(chat, "username", None)
            username_lc = username.lower() if username else ""
            return chat_id in cache["ids"] or username_lc in cache["usernames"]

        return pyro_filters.create(_is_monitored)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, bot_client: Client) -> None:
        """Initialize bot client, DB, userbot, and start background workers."""
        self._bot = bot_client

        # Init DB (WAL mode + table creation)
        from userbot_db import init_db
        await init_db()
        logger.info("Channel DB инициализирована")

        # Load channel cache
        await self._load_channels_cache()

        # Start queue worker
        self._worker_task = asyncio.create_task(self._channel_worker())
        logger.info("Queue worker started")

        # Register bot commands menu
        await bot_client.set_bot_commands([
            BotCommand("start", "Запустить бота"),
            BotCommand("help", "Справка по командам"),
            BotCommand("list_channels", "Список отслеживаемых каналов (Админ)"),
            BotCommand("add_channel", "Добавить канал (Админ)"),
            BotCommand("del_channel", "Удалить канал (Админ)"),
        ])
        logger.info("Bot commands menu updated")

    async def stop(self) -> None:
        """Gracefully stop background workers."""
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Queue worker stopped")

        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

    async def start_userbot(self, userbot_client: Client) -> None:
        """Initialize and register handlers on the Pyrogram userbot client."""
        self._userbot = userbot_client

        monitored_filter = self._make_monitored_filter()

        @userbot_client.on_message(pyro_filters.channel & monitored_filter)
        @userbot_client.on_edited_message(pyro_filters.channel & monitored_filter)
        async def _on_channel_message(client, message):
            await self._handle_channel_message(message, self._bot)

        # Принудительно кэшируем все диалоги, чтобы избежать "Peer id invalid"
        try:
            async for _ in userbot_client.get_dialogs():
                pass
            logger.info("Кэш диалогов юзербота успешно обновлен.")
        except Exception as e:
            logger.warning(f"Не удалось обновить кэш диалогов при старте: {e}")

        me = await userbot_client.get_me()
        logger.info(f"Pyrogram userbot запущен как @{me.username} (id={me.id})")

        # Запускаем фоновую синхронизацию диалогов
        self._sync_task = asyncio.create_task(self._dialogs_sync_worker())

    # ------------------------------------------------------------------
    # Dialogs background sync worker
    # ------------------------------------------------------------------

    async def _dialogs_sync_worker(self) -> None:
        """Фоновая задача для периодического обновления кэша диалогов."""
        while True:
            await asyncio.sleep(3600)  # раз в час
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

    async def _handle_channel_message(self, pyro_message: Any, bot_client: Any) -> None:
        """Called by Pyrogram when a message arrives in a monitored channel (pre-filtered)."""
        chat_username = getattr(pyro_message.chat, "username", None) or ""
        chat_id = str(getattr(pyro_message.chat, "id", ""))
        chat_title = getattr(pyro_message.chat, "title", None) or chat_username or "Unknown"

        text = pyro_message.text or pyro_message.caption or ""
        if not text:
            logger.debug(f"Канал '{chat_title}': сообщение без текста, пропускаем")
            return

        admin_id = settings.ADMIN_ID
        if not admin_id:
            logger.warning("ADMIN_ID не задан. Некуда отправить результат из канала.")
            return

        source_name = chat_title
        post_link = f"https://t.me/{chat_username}/{pyro_message.id}" if chat_username else ""

        item = _QueueItem(
            text=text,
            source_name=source_name,
            post_link=post_link,
            reply_chat_id=admin_id,
            bot=bot_client,
        )
        await self.processing_queue.put(item)
        logger.info(
            f"📥 Добавлено в очередь: {chat_title} (id={chat_id}), размер очереди={self.processing_queue.qsize()}"
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
            parse_mode="html",
            disable_web_page_preview=False,
        )
        logger.info(f"EPUB из канала '{item.source_name}' отправлен на admin {item.reply_chat_id}")

    # ------------------------------------------------------------------
    # Admin check helper
    # ------------------------------------------------------------------

    def _is_admin(self, user_id: int) -> bool:
        return settings.ADMIN_ID is not None and user_id == settings.ADMIN_ID

    # ------------------------------------------------------------------
    # Command handlers (Pyrogram)
    # ------------------------------------------------------------------

    async def cmd_start(self, client: Client, message: Message) -> None:
        """Handle /start command."""
        await message.reply(
            "Привет! Я могу конвертировать сообщения из Telegram в формат EPUB. "
            "Просто перешли мне сообщение, и я создам из него EPUB файл."
        )

    async def cmd_help(self, client: Client, message: Message) -> None:
        """Handle /help command."""
        text = (
            "Чтобы конвертировать сообщение в EPUB:\n"
            "1. Выберите сообщение, которое хотите конвертировать\n"
            "2. Перешлите его мне\n"
            "3. Я создам EPUB файл и отправлю его вам\n\n"
            "Команды управления каналами (только для администратора):\n"
            "/add_channel @username — добавить канал для отслеживания\n"
            "/del_channel @username — удалить канал\n"
            "/list_channels — список отслеживаемых каналов"
        )
        await message.reply(text)

    async def cmd_add_channel(self, client: Client, message: Message) -> None:
        """Handle /add_channel command (admin only)."""
        args = message.command[1:] if message.command else []
        if not args:
            await message.reply("Использование: /add_channel <@username или username>")
            return

        from userbot_db import add_channel as db_add_channel

        username = args[0].lstrip("@").lower()
        added = await db_add_channel(username)
        if added:
            if username.lstrip("-").isdigit():
                self._monitored_channels_cache["ids"].add(username)
            else:
                self._monitored_channels_cache["usernames"].add(username)
            await message.reply(f"✅ Канал @{username} добавлен в список отслеживания.")
        else:
            await message.reply(f"ℹ️ Канал @{username} уже в списке.")

    async def cmd_del_channel(self, client: Client, message: Message) -> None:
        """Handle /del_channel command (admin only)."""
        args = message.command[1:] if message.command else []
        if not args:
            await message.reply("Использование: /del_channel <@username или username>")
            return

        from userbot_db import remove_channel as db_remove_channel

        username = args[0].lstrip("@").lower()
        removed = await db_remove_channel(username)
        if removed:
            if username.lstrip("-").isdigit():
                self._monitored_channels_cache["ids"].discard(username)
            else:
                self._monitored_channels_cache["usernames"].discard(username)
            await message.reply(f"✅ Канал @{username} удалён из списка.")
        else:
            await message.reply(f"ℹ️ Канал @{username} не найден в списке.")

    async def cmd_list_channels(self, client: Client, message: Message) -> None:
        """Handle /list_channels command (admin only)."""
        from userbot_db import get_channels as db_get_channels

        channels = await db_get_channels()
        if not channels:
            await message.reply("Список отслеживаемых каналов пуст.")
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
            await message.reply(f"📋 Отслеживаемые каналы:\n{lines_str}")

    # ------------------------------------------------------------------
    # Message handler: forwarded messages & direct EPUB uploads (Pyrogram)
    # ------------------------------------------------------------------

    async def handle_message(self, client: Client, message: Message) -> None:
        """Handle incoming forwarded messages or plain text for EPUB conversion."""
        logger.info(f"Вход в handle_message: chat_id={message.chat.id}, message_id={message.id}")
        logger.debug(f"Полный объект сообщения: {message}")

        text_content = message.text or message.caption or ""
        
        forward_attrs = [
            "forward_date", "forward_from", "forward_from_chat",
            "forward_sender_name", "forward_origin"
        ]
        forward_values = {attr: getattr(message, attr, None) for attr in forward_attrs}
        logger.info(f"Атрибуты пересылки: {forward_values}")

        is_forwarded = any(val is not None for val in forward_values.values())
        logger.info(f"is_forwarded: {is_forwarded}, text_content_len: {len(text_content)}, has_document: {bool(message.document)}")

        if not message.document:
            if is_forwarded:
                if not text_content:
                    logger.info("Forwarded message does not contain text")
                    await message.reply(
                        "Пересланное сообщение не содержит текста. Пожалуйста, перешлите сообщение с текстом."
                    )
                    return
            elif not text_content:
                logger.info("Сообщение не содержит текста.")
                await message.reply(
                    "Сообщение не содержит текста. Пожалуйста, перешлите сообщение с текстом."
                )
                return

        if message.document:
            await self._process_uploaded_epub(client, message)
            return

        logger.info(f"Обработка сообщения от пользователя: {message.chat.id}")

        processing_msg = await message.reply("📚 Создаю EPUB файл...")

        try:
            logger.info("Попытка получить source_name")
            source_name = self._get_source_info(message)
            logger.info(f"source_name: {source_name}")
            
            logger.info("Попытка получить post_link")
            post_link = self._get_post_link(message)
            logger.info(f"post_link: {post_link}")

            summary_text = await epub_service.process_text_to_epub(
                text_content, source_name, post_link
            )

            await processing_msg.delete()
            await message.reply(
                summary_text, disable_web_page_preview=False, parse_mode="html"
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
            await message.reply(
                "❌ Извините, произошла ошибка при обработке вашего сообщения."
            )

    async def _process_uploaded_epub(self, client: Client, message: Message) -> None:
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
            await message.reply(
                "Сейчас поддерживаются только EPUB документы. Пожалуйста, отправьте файл с расширением .epub."
            )
            return

        logger.info("Обработка загруженного EPUB документа.")
        processing_msg = await message.reply("📚 Получен EPUB файл, подготавливаю отправку...")
        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp_file:
                temp_path = tmp_file.name

            # Скачиваем через Pyrogram
            temp_path = await client.download_media(message.document, file_name=temp_path)

            base_name = os.path.splitext(file_name)[0]
            safe_filename = sanitize_filename(base_name) or "document"
            send_filename = f"{safe_filename}.epub"

            source_name = self._get_source_info(message)
            clean_title = strip_emojis(base_name)
            clean_source = strip_emojis(source_name)

            post_link = self._get_post_link(message)

            if post_link:
                caption = f'<b><a href="{post_link}">{clean_title}</a></b>'
            else:
                caption = f"<b>{clean_title}</b>"

            if clean_source and clean_source != "Unknown Source":
                caption += f" {clean_source}"

            await processing_msg.delete()
            await message.reply_document(
                document=temp_path,
                file_name=send_filename,
                caption=caption,
                parse_mode="html",
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
            await message.reply("❌ Извините, произошла ошибка при обработке файла EPUB.")
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    logger.error("Не удалось удалить временный EPUB файл.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_source_info(self, message: Message) -> str:
        """Get the name of the channel or user forwarded from."""
        logger.info(f"Вызов _get_source_info для message_id={message.id}")
        if getattr(message, "forward_from_chat", None):
            title = message.forward_from_chat.title or "Channel"
            logger.info(f"Извлечен источник из forward_from_chat: {title}")
            return title
        elif getattr(message, "forward_from", None):
            name = getattr(message.forward_from, "first_name", "") or getattr(message.forward_from, "full_name", "") or "User"
            logger.info(f"Извлечен источник из forward_from: {name}")
            return name
        elif getattr(message, "forward_sender_name", None):
            logger.info(f"Извлечен источник из forward_sender_name: {message.forward_sender_name}")
            return message.forward_sender_name
            
        if getattr(message, "forward_origin", None):
            logger.info(f"Найден атрибут forward_origin: {message.forward_origin}, но он не обрабатывается!")

        logger.info("Источник не определен, возвращаем 'Unknown Source'")
        return "Unknown Source"

    def _get_post_link(self, message: Message) -> str:
        """Extract post link from a forwarded message."""
        logger.info(f"Вызов _get_post_link для message_id={message.id}")
        chat = getattr(message, "forward_from_chat", None)
        message_id = getattr(message, "forward_from_message_id", None)
        
        logger.info(f"Для post_link найдены: chat={chat}, message_id={message_id}")
        
        if chat and message_id and getattr(chat, "username", None):
            link = f"https://t.me/{chat.username}/{message_id}"
            logger.info(f"Сформирована ссылка: {link}")
            return link
            
        if getattr(message, "forward_origin", None):
            logger.info(f"Найден атрибут forward_origin при попытке создать ссылку: {message.forward_origin}")

        logger.info("Ссылка не сформирована")
        return ""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the bot using two Pyrogram clients in a single asyncio event loop."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN is not set")
        return

    if not settings.API_ID or not settings.API_HASH:
        logger.error("API_ID / API_HASH не заданы. Невозможно запустить Pyrogram.")
        return

    data_dir = os.environ.get("DATA_DIR", "data")
    os.makedirs(data_dir, exist_ok=True)
    session_name = os.path.join(data_dir, "userbot")

    # Bot client (по токену — для команд и общения с админом)
    bot_client = Client(
        name="bot",
        bot_token=token,
        api_id=settings.API_ID,
        api_hash=settings.API_HASH,
        workdir=data_dir,
    )

    # Userbot client (по сессии пользователя — для чтения каналов)
    userbot_kwargs: dict = dict(
        name="userbot",
        api_id=settings.API_ID,
        api_hash=settings.API_HASH,
        workdir=data_dir,
        no_updates=False,
    )
    if settings.USERBOT_SESSION_STRING:
        userbot_kwargs["session_string"] = settings.USERBOT_SESSION_STRING

    userbot_client = Client(**userbot_kwargs)

    converter = TelegramToEpub()



    async def run() -> None:
        # Регистрируем обработчики для bot_client внутри работающего event loop
        MessageHandler = __import__("pyrogram.handlers", fromlist=["MessageHandler"]).MessageHandler
        
        bot_client.add_handler(
            MessageHandler(converter.cmd_start, pyro_filters.command("start") & pyro_filters.private)
        )
        bot_client.add_handler(
            MessageHandler(converter.cmd_help, pyro_filters.command("help") & pyro_filters.private)
        )
        bot_client.add_handler(
            MessageHandler(converter.cmd_add_channel, pyro_filters.command("add_channel") & is_admin)
        )
        bot_client.add_handler(
            MessageHandler(converter.cmd_del_channel, pyro_filters.command("del_channel") & is_admin)
        )
        bot_client.add_handler(
            MessageHandler(converter.cmd_list_channels, pyro_filters.command("list_channels") & is_admin)
        )
        bot_client.add_handler(
            MessageHandler(
                converter.handle_message,
                pyro_filters.private & ~pyro_filters.command(
                    ["start", "help", "add_channel", "del_channel", "list_channels"]
                ),
            )
        )

        await bot_client.start()
        logger.info("Bot client запущен")

        await converter.start(bot_client)

        if settings.API_ID and settings.API_HASH:
            await userbot_client.start()
            await converter.start_userbot(userbot_client)
        else:
            logger.info(
                "Userbot не настроен (API_ID / API_HASH отсутствуют). "
                "Автопересылка из каналов отключена."
            )

        logger.info("Бот запущен. Ожидаем сообщений...")
        try:
            await asyncio.Event().wait()  # Ждём бесконечно
        finally:
            await converter.stop()
            if settings.API_ID and settings.API_HASH:
                try:
                    await userbot_client.stop()
                    logger.info("Pyrogram userbot остановлен")
                except Exception as e:
                    logger.error(f"Ошибка при остановке юзербота: {e}")
            await bot_client.stop()
            logger.info("Bot client остановлен")

    asyncio.run(run())


if __name__ == "__main__":
    main()
