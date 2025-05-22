import os
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
import dropbox


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
        # if not hasattr(message, 'forward_origin') or not message.forward_origin:
        #     logger.info("Сообщение не является пересланным.")
        #     await message.reply_text(
        #         "Пожалуйста, перешлите мне сообщение, которое вы хотите конвертировать в EPUB."
        #     )
        #     return
        # else:
        #     logger.info("Сообщение является пересланным.")

        # Check if message contains text
        if not message.text:
            logger.info("Сообщение не содержит текста.")
            await message.reply_text(
                "Сообщение не содержит текста. Пожалуйста, перешлите сообщение с текстом."
            )
            return

        logger.info(f"Начало обработки сообщения от пользователя: {message.chat.id}")

        reply_text = f"Получено сообщение:\n"
        reply_text += f"Chat ID: {message.chat.id}\n"
        reply_text += f"Message ID: {message.message_id}\n"
        reply_text += f"Text: {message.text}\n"

        if hasattr(message, 'forward_origin') and message.forward_origin:
            reply_text += f"Is Forwarded: True\n"
            reply_text += f"Forward Origin Type: {message.forward_origin.type}\n"
            if message.forward_origin.type == "user" and message.forward_origin.sender_user:
                reply_text += f"Forwarded from User: {message.forward_origin.sender_user.full_name or message.forward_origin.sender_user.username}\n"
            elif message.forward_origin.type == "chat" and message.forward_origin.sender_chat:
                reply_text += f"Forwarded from Chat: {message.forward_origin.sender_chat.title}\n"
            elif message.forward_origin.type == "hidden_user":
                reply_text += f"Forwarded from: Anonymous User\n"
        else:
            reply_text += f"Is Forwarded: False\n"

        await message.reply_text(reply_text)

        try:
            # Get sender info
            forwarded_from = None
            if hasattr(message, 'forward_origin') and message.forward_origin:
                if message.forward_origin.type == "user" and message.forward_origin.sender_user:
                    forwarded_from = message.forward_origin.sender_user.full_name or message.forward_origin.sender_user.username
                elif message.forward_origin.type == "chat" and message.forward_origin.sender_chat:
                    forwarded_from = message.forward_origin.sender_chat.title
                elif message.forward_origin.type == "hidden_user":
                    forwarded_from = "Anonymous User"

                logger.info(f"Тип forward_origin: {message.forward_origin.type}")
                if message.forward_origin.type == "user":
                    logger.info(f"sender_user: {message.forward_origin.sender_user}")
                elif message.forward_origin.type == "chat":
                    logger.info(f"sender_chat: {message.forward_origin.sender_chat}")

                logger.info(f"Сообщение переслано от: {forwarded_from}")
            else:
                logger.info("Сообщение не является пересланным.")
                forwarded_from = "Unknown"

            # Create EPUB
            logger.info("Создание EPUB файла...")
            epub_path = self.create_epub(message, forwarded_from)
            logger.info(f"EPUB файл создан: {epub_path}")
            if os.path.exists(epub_path):
                logger.info(f"Файл существует по пути: {epub_path}")
            else:
                logger.error(f"Файл не существует по пути: {epub_path}")

            # logger.info("Проверка токена Dropbox...")
            # # Get the Dropbox token from environment variable
            # dropbox_token = os.getenv('DROPBOX_TOKEN')
            # if not dropbox_token:
            #     logger.error("DROPBOX_TOKEN environment variable not set")
            #     await message.reply_text("Ошибка: Токен Dropbox не установлен.")
            #     return
            # logger.info("Токен Dropbox успешно загружен.")

            # # Upload EPUB file to Dropbox
            # logger.info("Попытка загрузки файла в Dropbox...")
            # try:
            #     dbx = dropbox.Dropbox(dropbox_token)
            #     logger.info("Клиент Dropbox инициализирован.")
            #     file_path = f'/All files/Apps/Dropbox PocketBook/from-bot/{message.date.strftime("%Y-%m-%d %H:%M")} - {forwarded_from}.epub'
            #     logger.info(f"Загрузка файла в Dropbox: {file_path}")
            #     with open(epub_path, 'rb') as f:
            #         dbx.files_upload(f.read(), file_path)
            #     logger.info("Файл успешно загружен в Dropbox!")
            #     await message.reply_text("Файл успешно загружен в Dropbox!")
            # except Exception as e:
            #     logger.error(f"Ошибка при загрузке в Dropbox: {e}")
            #     print(e)
            #     await message.reply_text("Извините, произошла ошибка при загрузке файла в Dropbox.")

            # Send EPUB file
            logger.info("Отправка EPUB файла пользователю...")
            try:
                with open(epub_path, 'rb') as epub_file:
                    await message.reply_document(
                        document=epub_file,
                        filename=f"message.epub",
                        caption="Вот ваш EPUB файл!"
                    )
                logger.info("EPUB файл успешно отправлен.")
            except Exception as e:
                logger.error(f"Ошибка при отправке EPUB файла: {e}")
                await message.reply_text("Извините, произошла ошибка при отправке файла.")
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

    # Get the Dropbox token from environment variable
    # dropbox_token = os.getenv('DROPBOX_TOKEN')
    # if not dropbox_token:
    #     logger.error("DROPBOX_TOKEN environment variable not set")
    #     # It's critical to exit if the Dropbox token is not set, as the bot will not function correctly.
    #     return

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
