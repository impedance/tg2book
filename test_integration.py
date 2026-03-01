import importlib.util as _ilu
import io
import pathlib as _pl
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _load_real_dropbox_module():
    spec = _ilu.spec_from_file_location(
        "dropbox_module_real",
        str(_pl.Path(__file__).parent / "dropbox_module.py"),
    )
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


from bot import TelegramToEpub


@pytest.fixture
def mock_message():
    message = MagicMock()

    processing_msg = MagicMock()
    processing_msg.delete = AsyncMock()
    message.reply_text = AsyncMock(return_value=processing_msg)
    message.reply = AsyncMock(return_value=processing_msg)

    message.reply_document = AsyncMock()
    message.delete = AsyncMock()
    message.chat = MagicMock()
    message.chat.id = 12345
    message.text = None
    message.caption = None
    message.document = None
    message.link = None
    message.forward_date = None
    message.forward_from = None
    message.forward_from_chat = None
    message.forward_sender_name = None
    message.forward_from_message_id = None
    return message


@pytest.fixture
def mock_client():
    client = MagicMock()
    return client


@pytest.mark.asyncio
async def test_full_pipeline_text_to_dropbox(mock_message, mock_client):
    """
    A true black-box integration test.
    It doesn't mock the internal file-generation (`create_epub`) logic.
    Instead, it gives the bot mock text and intercepts the final HTTP call to Dropbox.
    It asserts that the HTTP payload sent to Dropbox is indeed a valid EPUB ZIP file.
    """
    converter = TelegramToEpub()

    mock_message.text = (
        "Integration Architecture\n\nThis is a black-box test that verifies things "
        "end-to-end without tightly coupling to implementations."
    )

    real_dm = _load_real_dropbox_module()

    with (
        patch("services.epub_service.dropbox_module", real_dm),
        patch.object(real_dm, "refresh_access_token", return_value="fake_token"),
        patch.object(real_dm.requests, "post") as mock_post,
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        await converter.handle_message(mock_client, mock_message)

        # Verify Telegram replied with success summary
        assert mock_message.reply.call_count == 2
        last_call_args = mock_message.reply.call_args_list[-1][0]
        assert "Integration Architecture" in last_call_args[0]

        # Verify Dropbox HTTP Request
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "content.dropboxapi.com/2/files/upload" in args[0]

        # Verify the ZIP/EPUB uploaded
        epub_data = kwargs["data"]
        with zipfile.ZipFile(io.BytesIO(epub_data)) as zf:
            assert "mimetype" in zf.namelist()
            assert "OEBPS/content.opf" in zf.namelist()
            xhtml = zf.read("OEBPS/content.xhtml").decode("utf-8")
            assert "end-to-end without tightly coupling" in xhtml


@pytest.mark.asyncio
async def test_full_pipeline_document_to_dropbox(mock_message, mock_client):
    """
    Integration test for direct EPUB file upload.
    Verifies that the file is downloaded from Telegram and sent to Dropbox correctly
    without mocking the logic in between.
    """
    converter = TelegramToEpub()

    document = MagicMock()
    document.mime_type = "application/epub+zip"
    document.file_name = "User Book.epub"
    document.file_id = "doc-123"

    async def mock_download_media(media, file_name=None):
        with open(file_name, "wb") as f:
            f.write(b"fake_epub_content_bytes")
        return file_name

    mock_client.download_media = mock_download_media
    mock_message.document = document

    real_dm = _load_real_dropbox_module()

    with (
        patch("services.epub_service.dropbox_module", real_dm),
        patch.object(real_dm, "refresh_access_token", return_value="fake_token"),
        patch.object(real_dm.requests, "post") as mock_post,
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        await converter.handle_message(mock_client, mock_message)

        mock_message.reply_document.assert_called_once()

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "content.dropboxapi.com/2/files/upload" in args[0]
        assert kwargs["data"] == b"fake_epub_content_bytes"

        import json

        api_arg = json.loads(kwargs["headers"]["Dropbox-API-Arg"])
        assert "User_Book.epub" in api_arg["path"]


@pytest.mark.asyncio
async def test_full_pipeline_url_success(mock_message, mock_client):
    """
    Scenario 1: Successful URL parsing.
    The message contains a link. The bot should download the HTML,
    parse the title and content using BeautifulSoup, and create an EPUB
    based on the parsed article instead of just the message text.
    """
    converter = TelegramToEpub()

    # The message text contains a URL
    mock_message.text = "Check out this article! https://example.com/article"

    real_dm = _load_real_dropbox_module()

    # We mock requests to simulate website fetching, and Dropbox upload
    with (
        patch("services.epub_service.dropbox_module", real_dm),
        patch.object(real_dm, "refresh_access_token", return_value="fake_token"),
        patch.object(real_dm.requests, "post") as mock_dbx_post,
        patch("services.parser_service.requests.get") as mock_requests_get,
    ):
        mock_resp_dbx = MagicMock()
        mock_resp_dbx.status_code = 200
        mock_dbx_post.return_value = mock_resp_dbx

        # Mocking the website response
        mock_html_resp = MagicMock()
        mock_html_resp.status_code = 200
        mock_html_resp.content = b"<html><head><title>Awesome Article Title</title></head><body><p>This is the amazing content of the web article.</p></body></html>"
        mock_requests_get.return_value = mock_html_resp

        await converter.handle_message(mock_client, mock_message)

        # Requests should be called to fetch the URL
        mock_requests_get.assert_called_once_with("https://example.com/article", timeout=10)

        # Verify Dropbox HTTP Request was called and EPUB uploaded
        mock_dbx_post.assert_called_once()
        args, kwargs = mock_dbx_post.call_args
        
        # Verify the ZIP/EPUB uploaded contains the article content and title
        epub_data = kwargs["data"]
        with zipfile.ZipFile(io.BytesIO(epub_data)) as zf:
            xhtml = zf.read("OEBPS/content.xhtml").decode("utf-8")
            assert "This is the amazing content of the web article" in xhtml
            assert "Awesome Article Title" in xhtml


@pytest.mark.asyncio
async def test_full_pipeline_url_forwarded(mock_message, mock_client):
    """
    Scenario 2: Forwarded message with URL.
    The name of the original sender should also be extracted 
    via Pyrogram native attributes (forward_from_chat or similar).
    """
    converter = TelegramToEpub()

    mock_message.text = "https://example.com/forwarded"
    
    # Mocking a forwarded message in Pyrogram
    forward_from_chat = MagicMock()
    forward_from_chat.title = "Scientific Channel"
    mock_message.forward_from_chat = forward_from_chat

    real_dm = _load_real_dropbox_module()

    with (
        patch("services.epub_service.dropbox_module", real_dm),
        patch.object(real_dm, "refresh_access_token", return_value="fake_token"),
        patch.object(real_dm.requests, "post") as mock_dbx_post,
        patch("services.parser_service.requests.get") as mock_requests_get,
    ):
        mock_resp_dbx = MagicMock()
        mock_resp_dbx.status_code = 200
        mock_dbx_post.return_value = mock_resp_dbx

        mock_html_resp = MagicMock()
        mock_html_resp.status_code = 200
        mock_html_resp.content = b"<html><head><title>Forwarded Article</title></head><body><p>Text</p></body></html>"
        mock_requests_get.return_value = mock_html_resp

        await converter.handle_message(mock_client, mock_message)

        mock_requests_get.assert_called_once_with("https://example.com/forwarded", timeout=10)

        assert mock_message.reply.call_count >= 1
        last_call_args = mock_message.reply.call_args_list[-1][0]
        # Check if the generated message summary mentioned the source channel name
        assert "Scientific Channel" in last_call_args[0]


@pytest.mark.asyncio
async def test_full_pipeline_url_broken_fallback(mock_message, mock_client):
    """
    Scenario 3: Broken URL / 404 (Graceful Fallback).
    If requests gets a 404 or connection error, the bot shouldn't crash.
    It should fallback to generating EPUB from the raw text itself.
    """
    converter = TelegramToEpub()

    mock_message.text = "Here is a broken link https://example.com/404"

    real_dm = _load_real_dropbox_module()

    with (
        patch("services.epub_service.dropbox_module", real_dm),
        patch.object(real_dm, "refresh_access_token", return_value="fake_token"),
        patch.object(real_dm.requests, "post") as mock_dbx_post,
        patch("services.parser_service.requests.get") as mock_requests_get,
    ):
        mock_resp_dbx = MagicMock()
        mock_resp_dbx.status_code = 200
        mock_dbx_post.return_value = mock_resp_dbx

        # Mocking a 404 error
        mock_html_resp = MagicMock()
        mock_html_resp.status_code = 404
        mock_html_resp.raise_for_status.side_effect = Exception("404 Client Error")
        mock_requests_get.return_value = mock_html_resp

        await converter.handle_message(mock_client, mock_message)

        # Verify fallback: an EPUB was still created and uploaded with original text
        mock_dbx_post.assert_called_once()
        epub_data = mock_dbx_post.call_args[1]["data"]
        with zipfile.ZipFile(io.BytesIO(epub_data)) as zf:
            xhtml = zf.read("OEBPS/content.xhtml").decode("utf-8")
            assert "Here is a broken link" in xhtml

