import asyncio
import logging
import os
import tempfile

import dropbox_module
from epub_functions import create_epub
from utils.text_utils import extract_title, format_message, sanitize_filename

logger = logging.getLogger(__name__)

async def process_text_to_epub(text_content: str, source_name: str, first_link: str) -> str:
    """
    Process text content:
    1. Extract title and content
    2. Create EPUB file
    3. Upload to Dropbox
    4. Return summary text
    """
    title = extract_title(text_content)
    content = format_message(text_content)
    safe_filename = sanitize_filename(title)

    epub_path = None
    try:
        # Obtain a unique path
        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp_file:
            epub_path = tmp_file.name

        # Create EPUB in a thread to not block event loop
        epub_path = await asyncio.to_thread(
            create_epub, title, source_name, content, epub_path
        )

        if not os.path.exists(epub_path):
            logger.error(f"Файл не был создан: {epub_path}")
            return "❌ Ошибка создания файла"

        # Upload to Dropbox
        logger.info(f"Инициируем загрузку в Dropbox: {epub_path}")
        dropbox_filename = f"{safe_filename}.epub"

        # Upload in a thread
        await asyncio.to_thread(
            dropbox_module.upload_to_dropbox, epub_path, dropbox_filename
        )

        # Prepare summary text (using HTML for Telegram)
        post_link = first_link or ""
        if post_link:
            summary_text = f'<b><a href="{post_link}">{title}</a></b>'
        else:
            summary_text = f'<b>{title}</b>'

        if source_name and source_name != "Unknown Source":
             summary_text += f" {source_name}"

        return summary_text

    finally:
        # Guaranteed cleanup
        if epub_path and os.path.exists(epub_path):
            try:
                os.remove(epub_path)
            except Exception as e:
                logger.error(f"Ошибка удаления временного файла: {e}")

async def process_file_to_dropbox(temp_path: str, file_name: str) -> bool:
    """
    Upload an existing EPUB file to Dropbox.
    """
    try:
        base_name = os.path.splitext(file_name)[0]
        safe_filename = sanitize_filename(base_name) or "document"
        dropbox_filename = f"{safe_filename}.epub"

        logger.info(f"Инициируем загрузку документа в Dropbox: {temp_path}")
        success = await asyncio.to_thread(
            dropbox_module.upload_to_dropbox, temp_path, dropbox_filename
        )
        return success
    except Exception as e:
        logger.error(f"Ошибка при загрузке документа в Dropbox: {e}")
        return False
