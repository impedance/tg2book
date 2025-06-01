import os
import dropbox_module
import logging
logging.basicConfig(
    filename='bot.log',
    filemode='w',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)
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

    def create_epub(self, message, forwarded_from=None) -> str:
        """Create an EPUB file from the message text content."""
        # Get text content from message.text or message.caption
        text_content = self.get_message_text(message)
        
        # Generate title from date and sender
        date_str = message.date.strftime("%Y-%m-%d %H:%M")
        sender = forwarded_from or "Unknown"
        title = f"Telegram Message - {date_str} - {sender}"
        # Clean title for filename
        clean_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        
        # Prepare content from message text - without title header
        content = f"""
        <div class=\"message-content\">
            {self.format_message(text_content)}
        </div>
        """
        
        # Create EPUB
        book = epub.EpubBook()
        book.set_title(title)
        book.set_language('ru')
        
        # Add content
        c1 = epub.EpubHtml(title='Content', file_name='content.xhtml', lang='ru')
        c1.content = f'<html><body>{content}</body></html>'
        book.add_item(c1)
        
        # Add navigation (required by EPUB standard but not in spine)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        
        # Create spine - start directly with content, no navigation page
        book.spine = [c1]
        
        # Save the EPUB file
        os.makedirs("docs", exist_ok=True)
        date_str = message.date.strftime("%m-%d-%y_%H-%M-%S")
        epub_path = os.path.join("docs", f'msg-{date_str}.epub')
        epub.write_epub(epub_path, book)
        
        # Upload to Dropbox in a separate thread
        threading.Thread(target=dropbox_module.upload_to_dropbox, args=(epub_path,)).start()
        
        return epub_path

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

        logger.info(f"Начало обработки сообщения от пользователя: {message.chat.id}")
        
        # Log debug info but don't send to user
        logger.info(f"Message ID: {message.message_id}")
        logger.info(f"Text: {message.text or 'None'}")
        logger.info(f"Caption: {message.caption or 'None'}")

        if hasattr(message, 'forward_origin') and message.forward_origin:
            logger.info(f"Is Forwarded: True, Type: {message.forward_origin.type}")
            if message.forward_origin.type == "user" and message.forward_origin.sender_user:
                logger.info(f"Forwarded from User: {message.forward_origin.sender_user.full_name or message.forward_origin.sender_user.username}")
            elif message.forward_origin.type == "chat" and message.forward_origin.sender_chat:
                logger.info(f"Forwarded from Chat: {message.forward_origin.sender_chat.title}")
            elif message.forward_origin.type == "channel" and message.forward_origin.sender_chat:
                logger.info(f"Forwarded from Channel: {message.forward_origin.sender_chat.title}")
            elif message.forward_origin.type == "hidden_user":
                logger.info(f"Forwarded from: Anonymous User")
        else:
            pass
        
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

                logger.info(f"Тип forward_origin: {message.forward_origin.type}")
                if message.forward_origin.type == "user":
                    logger.info(f"sender_user: {message.forward_origin.sender_user}")
                elif message.forward_origin.type in ["chat", "channel"]:
                    logger.info(f"sender_chat: {message.forward_origin.sender_chat}")

                logger.info(f"Сообщение переслано от: {forwarded_from}")
            else:
                forwarded_from = "Unknown"

            # Create EPUB
            logger.info("Создание EPUB файла...")
            epub_path = self.create_epub(message, forwarded_from)
            logger.info(f"EPUB файл создан: {epub_path}")
            if os.path.exists(epub_path):
                logger.info(f"Файл существует по пути: {epub_path}")
            else:
                logger.error(f"Файл не существует по пути: {epub_path}")

            # Send EPUB file
            logger.info("Отправка EPUB файла пользователю...")
            try:
                # Delete the processing message
                await processing_msg.delete()

                logger.info(f"Opening EPUB file: {epub_path}")
                with open(epub_path, 'rb') as epub_file:
                    logger.info("EPUB file opened successfully.")
                    await message.reply_document(
                        document=epub_file,
                        filename=f"message.epub",
                        caption="📖 Ваш EPUB файл готов!"
                    )
                logger.info("EPUB файл успешно отправлен.")
            except Exception as e:
                logger.error(f"Ошибка при отправке EPUB файла: {e}")
                await message.reply_text("❌ Извините, произошла ошибка при отправке файла.")

            # Upload to Dropbox
            logger.info("Uploading EPUB file to Dropbox...")
            try:
                dropbox_module.upload_to_dropbox(epub_path)
                logger.info("EPUB file upload to Dropbox initiated.")
            except Exception as e:
                logger.error(f"Error initiating Dropbox upload: {e}")

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            try:
                await processing_msg.delete()
            except:
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
