import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from ebooklib import epub
import tempfile
import shutil
from datetime import datetime
import re

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramToEpub:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()

    def __del__(self):
        shutil.rmtree(self.temp_dir)

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
        """Create an EPUB file from the message content."""
        # Generate title from date and sender
        date_str = message.date.strftime("%Y-%m-%d %H:%M")
        sender = forwarded_from or "Unknown"
        title = f"Telegram Message - {date_str} - {sender}"
        # Clean title for filename
        clean_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        # Prepare content
        # ВСЕГДА используем format_message для форматирования текста
        content_text = self.format_message(message.text)
        content = f"""
        <h1>{title}</h1>
        <div class=\"message-content\">
            {content_text}
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
        # Add navigation
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        # Create spine
        book.spine = ['nav', c1]
        # Save the EPUB file
        epub_path = os.path.join(self.temp_dir, f'{clean_title}.epub')
        epub.write_epub(epub_path, book)
        return epub_path

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages."""
        message = update.message
        
        # Check if message is forwarded
        if not message.forward_origin:
            await message.reply_text(
                "Пожалуйста, перешлите мне сообщение, которое вы хотите конвертировать в EPUB."
            )
            return

        try:
            # Get sender info
            forwarded_from = None
            if message.forward_origin.type == "user":
                forwarded_from = message.forward_origin.sender_user.full_name or message.forward_origin.sender_user.username
            elif message.forward_origin.type == "chat":
                forwarded_from = message.forward_origin.sender_chat.title
            elif message.forward_origin.type == "hidden_user":
                forwarded_from = "Anonymous User"

            # Create EPUB
            epub_path = self.create_epub(message, forwarded_from)
            
            # Send EPUB file
            with open(epub_path, 'rb') as epub_file:
                await message.reply_document(
                    document=epub_file,
                    filename=f"message.epub",
                    caption="Вот ваш EPUB файл!"
                )
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await message.reply_text("Извините, произошла ошибка при обработке вашего сообщения.")

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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, converter.handle_message))

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()
