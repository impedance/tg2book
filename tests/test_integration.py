import importlib.util as _ilu
import io
import pathlib as _pl
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _load_real_dropbox_module():
    spec = _ilu.spec_from_file_location(
        "dropbox_module_real",
        str(_pl.Path(__file__).parent.parent / "dropbox_module.py"),
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
