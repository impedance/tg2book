import os
import dropbox_module
import logging

class HTTPRequestFilter(logging.Filter):
    def filter(self, record):
        # Фильтруем все HTTP запросы к Telegram API
        return "HTTP Request:" not in record.getMessage()

logging.basicConfig(
    filename='bot.log',
    filemode='w',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Применяем фильтр к различным логгерам, которые могут генерировать HTTP логи
http_filter = HTTPRequestFilter()
logger.addFilter(http_filter)
logging.getLogger('httpx').addFilter(http_filter)
logging.getLogger('urllib3').addFilter(http_filter)
logging.getLogger('telegram').addFilter(http_filter)
logging.getLogger().addFilter(http_filter)  # Корневой логгер
from telegram import Update

logger.setLevel(logging.DEBUG)
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from ebooklib import epub
import tempfile
import shutil
from datetime import datetime
import re
import subprocess
import time
import threading
import requests
from epub_functions import create_epub

class TelegramToEpub:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()

    def __del__(self):
        shutil.rmtree(self.temp_dir)

    def get_message_text(self, message):
        """Get text content from message.text or message.caption"""
        return message.text or message.caption or ""

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


    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages."""
        message = update.message

        # Get text content from message.text or message.caption
        text_content = self.get_message_text(message)

        # Check if message contains text content
        if hasattr(message, 'forward_origin') and message.forward_origin:
            # Handle forwarded messages - check all supported types including channel
            if message.forward_origin.type in ["user", "chat", "hidden_user", "channel"]:
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

        logger.info(f"Обработка сообщения от пользователя: {message.chat.id}")

        if hasattr(message, 'forward_origin') and message.forward_origin:
            if message.forward_origin.type == "user" and message.forward_origin.sender_user:
                logger.info(f"Переслано от пользователя: {message.forward_origin.sender_user.full_name or message.forward_origin.sender_user.username}")
            elif message.forward_origin.type == "chat" and message.forward_origin.sender_chat:
                logger.info(f"Переслано из чата: {message.forward_origin.sender_chat.title}")
            elif message.forward_origin.type == "channel" and message.forward_origin.sender_chat:
                logger.info(f"Переслано из канала: {message.forward_origin.sender_chat.title}")
            elif message.forward_origin.type == "hidden_user":
                logger.info(f"Переслано от анонимного пользователя")
        
        # Optionally send a brief processing message
        processing_msg = await message.reply_text("📚 Создаю EPUB файл...")

        try:
            # Get sender info
            forwarded_from = None
            if hasattr(message, 'forward_origin') and message.forward_origin:
                if message.forward_origin.type == "user" and message.forward_origin.sender_user:
                    forwarded_from = message.forward_origin.sender_user.full_name or message.forward_origin.sender_user.username
                elif message.forward_origin.type in ["chat", "channel"] and message.forward_origin.sender_chat:
                    forwarded_from = message.forward_origin.sender_chat.title
                elif message.forward_origin.type == "hidden_user":
                    forwarded_from = "Anonymous User"
            else:
                forwarded_from = "Unknown"

            # Extract title and content from message
            title = message.text or message.caption or "Untitled"
            content = self.format_message(title)

            # Create EPUB
            with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp_file:
                epub_path = create_epub(title, forwarded_from, content, tmp_file.name)
            
            if not os.path.exists(epub_path):
                logger.error(f"Файл не был создан: {epub_path}")
                await processing_msg.delete()
                await message.reply_text("❌ Ошибка создания файла")
                return

            # Send EPUB file
            try:
                # Delete the processing message
                await processing_msg.delete()

                with open(epub_path, 'rb') as epub_file:
                    await message.reply_document(
                        document=epub_file,
                        filename=f"message.epub",
                        caption="📖 Ваш EPUB файл готов!"
                    )
                logger.info("EPUB файл отправлен")
            except Exception as e:
                logger.error(f"Ошибка при отправке EPUB файла: {e}")
                await message.reply_text("❌ Извините, произошла ошибка при отправке файла.")

            # Upload to Dropbox
            logger.info(f"Инициируем загрузку в Dropbox: {epub_path}")
            try:
                success = dropbox_module.upload_to_dropbox(epub_path)
                if success:
                    logger.info("Загрузка в Dropbox завершена успешно")
                else:
                    logger.error("Загрузка в Dropbox не удалась")
            except Exception as e:
                logger.error(f"Ошибка загрузки в Dropbox: {e}")

        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")
            try:
                await processing_msg.delete()
            except Exception:
                logger.error("Не удалось удалить сообщение о обработке")
                pass
            await message.reply_text("❌ Извините, произошла ошибка при обработке вашего сообщения.")
    

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
    application.add_handler(MessageHandler(filters.ALL, converter.handle_message))

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()
