import asyncio
import logging
import os
import shutil
import sys
import tempfile
from typing import Any, List

from telegram import Message, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import settings
from services import epub_service
from utils.text_utils import sanitize_filename, strip_emojis


class HTTPRequestFilter(logging.Filter):
    def filter(self, record):
        # Фильтруем все HTTP запросы к Telegram API
        return "HTTP Request:" not in record.getMessage()


logging.basicConfig(
    stream=sys.stdout,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Применяем фильтр к различным логгерам, которые могут генерировать HTTP логи
http_filter = HTTPRequestFilter()
logger.addFilter(http_filter)
logging.getLogger("httpx").addFilter(http_filter)
logging.getLogger("urllib3").addFilter(http_filter)
logging.getLogger("telegram").addFilter(http_filter)
logging.getLogger().addFilter(http_filter)  # Корневой логгер


class TelegramToEpub:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.processing_semaphore = asyncio.Semaphore(1)

    def __del__(self):
        try:
            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass

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

        # If no link found in text, try the message link (useful for public channels)
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
                "3. Я создам EPUB файл и отправлю его вам"
            )

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

        async with self.processing_semaphore:
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

                # Determine the post link to use
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

                # Send summary
                await processing_msg.delete()
                await message.reply_text(
                    summary_text, disable_web_page_preview=False, parse_mode="HTML"
                )

                # Delete original message
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
            finally:
                pass

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

            # Prepare caption
            forward_origin = getattr(message, "forward_origin", None)
            source_name = self.get_source_info(message)
            clean_title = strip_emojis(base_name)
            clean_source = strip_emojis(source_name)

            # Link for caption
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

            # Upload to Dropbox
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


def main() -> None:
    """Start the bot."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN is not set")
        return

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(token).build()

    # Create an instance of our converter
    converter = TelegramToEpub()

    # Add handlers
    application.add_handler(CommandHandler("start", converter.start))
    application.add_handler(CommandHandler("help", converter.help))
    application.add_handler(MessageHandler(filters.ALL, converter.handle_message))

    # Start the Bot
    application.run_polling()


if __name__ == "__main__":
    main()
