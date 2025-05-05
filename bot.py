import re
import os
import logging
from telegram import Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from ebooklib import epub
from bs4 import BeautifulSoup
import requests

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Simple regex to detect URLs
URL_REGEX = re.compile(r'https?://\S+')
TELEGRAM_API_TOKEN = "7857271142:AAHBTN1yvpoKIIrrmdXyV691xxs-qZhR9g0"

def send_welcome(update, context):
    logging.info("Sending welcome message")
    context.bot.send_message(chat_id=update.effective_chat.id, text="Welcome! I'm your Telegram bot.")

def handle_link(update, context):
    url = URL_REGEX.search(update.message.text).group()
    try:
        logging.info(f"Handling link: {url}")
        post_content, images = download_telegram_post(url)
        epub_book = create_epub(post_content, images)
        epub.write_epub("post.epub", epub_book)
        with open("post.epub", "rb") as file:
            context.bot.send_document(chat_id=update.effective_chat.id, document=file)
        logging.info("EPUB file sent successfully")
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"An error occurred: {str(e)}")

def download_telegram_post(url):
    logging.info(f"Downloading post from: {url}")
    response = requests.get(url)
    response.raise_for_status()  # Raise an error for bad responses
    soup = BeautifulSoup(response.content, "html.parser")
    post_content = soup.get_text()
    images = []
    for img in soup.find_all("img"):
        image_url = img.get("src")
        if image_url:
            logging.info(f"Downloading image from: {image_url}")
            image_data = requests.get(image_url).content
            images.append((image_url.split("/")[-1], image_data))
    return post_content, images

def create_epub(content, images):
    logging.info("Creating EPUB file")
    book = epub.EpubBook()
    book.set_identifier('id123456')
    book.set_title('Telegram Post')
    book.set_language('en')
    book.add_author('Telegram Bot')
    
    # Add chapter
    c1 = epub.EpubHtml(title='Post Content', file_name='chap_01.xhtml', lang='en')
    soup = BeautifulSoup(content, "html.parser")
    sanitized_content = soup.prettify()
    c1.content = f'<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"><head><title>Post Content</title></head><body>{sanitized_content}</body></html>'
    c1.is_chapter = True
    c1.uid = 'chap_01'
    book.add_item(c1)
    logging.info(f"Sanitized content: {sanitized_content}")
    logging.info(f"Full HTML content: {c1.content}")

    # Ensure cover image is not added multiple times
    if 'cover.jpg' not in [item.file_name for item in book.get_items()]:
        cover_image = epub.EpubImage(file_name='cover.jpg', media_type='image/jpeg')
        with open('cover.jpg', 'rb') as img_file:
            cover_image.content = img_file.read()
        book.add_item(cover_image)
        book.set_cover('cover.jpg', cover_image.content)
    
    # Add images to the chapter
    for img_name, img_data in images:
        image_item = epub.EpubItem(file_name=f'images/{img_name}', media_type='image/jpeg', content=img_data)
        image_item.uid = f'image_{img_name}'
        book.add_item(image_item)
        c1.content += f'<img src="{image_item.file_name}"/>'
    
    # Define Table Of Contents
    book.toc = (epub.Link('chap_01.xhtml', 'Post Content', 'chap_01'), )
    
    # Add default NCX and NAV files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    # Define CSS style
    style = 'BODY {color: black;}'
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
    book.add_item(nav_css)
    
    # Add items to the spine
    book.spine = ['nav', c1]
    
    # Write the EPUB file
    epub.write_epub("post.epub", book)
    
    return book

def handle_message(update, context):
    """Handles incoming messages, checking for links or forwarded messages."""
    if update.message.forward_date:
        # Handle forwarded messages
        forwarded_message = update.message
        if forwarded_message.text:
            post_content = forwarded_message.text
            images = []
            for img in forwarded_message.photo:
                image_url = img.get_file().file_path
                logging.info(f"Downloading image from: {image_url}")
                image_data = requests.get(f"https://api.telegram.org/file/bot{TELEGRAM_API_TOKEN}/{image_url}").content
                images.append((image_url.split("/")[-1], image_data))
            epub_book = create_epub(post_content, images)
            epub.write_epub("post.epub", epub_book)
            with open("post.epub", "rb") as file:
                context.bot.send_document(chat_id=update.effective_chat.id, document=file)
            logging.info("EPUB file sent successfully")
        else:
            echo(update, context)
    elif update.message.text and URL_REGEX.search(update.message.text):
        handle_link(update, context)
    else:
        echo(update, context)

def echo(update, context):
    logging.info(f"Echoing message: {update.message.text}")
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"You said: {update.message.text}")

def main():
    logging.info("Starting bot")
    bot = Bot(token=TELEGRAM_API_TOKEN)
    updater = Updater(bot=bot)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", send_welcome))
    dp.add_handler(MessageHandler(Filters.text, handle_message))
    
    updater.start_polling()
    updater.idle()
    logging.info("Bot stopped")

if __name__ == '__main__':
    main()
