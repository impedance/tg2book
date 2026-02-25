"""
Tests for tg2book bot.

Strategy:
- No ebooklib, no dropbox SDK, no subprocess.
- epub_functions now uses zipfile + SVG cover.
- dropbox_module now uses requests/urllib (HTTP-only, no subprocess).
- All external I/O (zipfile writes, HTTP calls) is mocked.
"""

import importlib.util as _ilu
import pathlib as _pl


def _load_real_dropbox_module():
    """Load dropbox_module directly from disk, bypassing sys.modules mock."""
    spec = _ilu.spec_from_file_location(
        "dropbox_module_real",
        str(_pl.Path(__file__).parent / "dropbox_module.py"),
    )
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

import io
import os
import sys
import tempfile
import zipfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Mock heavy / external modules BEFORE importing our code
# ---------------------------------------------------------------------------

class _MockModule:
    pass


# telegram
_telegram_mock = _MockModule()
_telegram_mock.Update = MagicMock

_telegram_ext_mock = _MockModule()
_telegram_ext_mock.Application = MagicMock
_telegram_ext_mock.CommandHandler = MagicMock
_telegram_ext_mock.MessageHandler = MagicMock
_telegram_ext_mock.ContextTypes = MagicMock
_telegram_ext_mock.ContextTypes.DEFAULT_TYPE = MagicMock
_telegram_ext_mock.filters = MagicMock()
_telegram_ext_mock.filters.ALL = MagicMock()

sys.modules["telegram"] = _telegram_mock
sys.modules["telegram.ext"] = _telegram_ext_mock

# dropbox_module – we provide a fully mocked version with controllable return values.
_dropbox_module_mock = MagicMock()
_dropbox_module_mock.upload_to_dropbox = MagicMock(return_value=True)
_dropbox_module_mock.refresh_access_token = MagicMock(return_value="test_token")
sys.modules["dropbox_module"] = _dropbox_module_mock

# ---------------------------------------------------------------------------
# Now safe to import our modules
# ---------------------------------------------------------------------------
from bot import TelegramToEpub  # noqa: E402
from epub_functions import (  # noqa: E402
    create_epub,
    _render_svg_cover,
    _build_epub_zip,
)


# ===========================================================================
# epub_functions tests (new pure-Python zipfile implementation)
# ===========================================================================

class TestSvgCover:
    """Tests for the SVG cover generator."""

    def test_returns_bytes(self):
        svg = _render_svg_cover("My Title", "My Author")
        assert isinstance(svg, bytes)

    def test_contains_title(self):
        svg = _render_svg_cover("Unique Title XYZ", "").decode("utf-8")
        assert "Unique Title XYZ" in svg

    def test_contains_author(self):
        svg = _render_svg_cover("Title", "Some Author Name").decode("utf-8")
        assert "Some Author Name" in svg

    def test_valid_svg_wrapper(self):
        svg = _render_svg_cover("T", "A").decode("utf-8")
        assert svg.strip().startswith("<svg")
        assert "</svg>" in svg

    def test_empty_author_no_crash(self):
        svg = _render_svg_cover("Title", "")
        assert len(svg) > 0

    def test_long_title_truncated_or_wrapped(self):
        long_title = "A" * 300
        svg = _render_svg_cover(long_title, "Author").decode("utf-8")
        # Should not blow up; SVG should still be valid
        assert "<svg" in svg

    def test_special_chars_escaped(self):
        svg = _render_svg_cover("<script>", "Author & Co").decode("utf-8")
        # Raw < and & must not appear unescaped in content (xml-safety)
        assert "<script>" not in svg
        # Either escaped or stripped – just must not crash
        assert "<svg" in svg


class TestBuildEpubZip:
    """Tests for _build_epub_zip (creates a valid ZIP/EPUB in memory)."""

    def _make_epub_bytes(self, title="Title", author="Author", content="<p>Hello</p>"):
        buf = io.BytesIO()
        _build_epub_zip(buf, title=title, author=author, content=content)
        buf.seek(0)
        return buf.read()

    def test_result_is_valid_zip(self):
        data = self._make_epub_bytes()
        assert zipfile.is_zipfile(io.BytesIO(data))

    def test_mimetype_entry_first(self):
        """EPUB spec: 'mimetype' must be the first file and uncompressed."""
        data = self._make_epub_bytes()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            assert names[0] == "mimetype"
            info = zf.getinfo("mimetype")
            assert info.compress_type == zipfile.ZIP_STORED
            assert zf.read("mimetype") == b"application/epub+zip"

    def test_required_files_present(self):
        data = self._make_epub_bytes()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
        assert "META-INF/container.xml" in names
        assert any("content.opf" in n for n in names), f"No content.opf found: {names}"
        assert any("content.xhtml" in n or "chapter" in n for n in names), f"No content in: {names}"

    def test_cover_svg_present(self):
        data = self._make_epub_bytes(title="CoverTest", author="Me")
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
        assert any("cover" in n for n in names), f"No cover entry found: {names}"

    def test_title_in_opf(self):
        data = self._make_epub_bytes(title="Special Title 123")
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            opf_names = [n for n in zf.namelist() if n.endswith(".opf")]
            assert opf_names
            opf_text = zf.read(opf_names[0]).decode("utf-8")
        assert "Special Title 123" in opf_text

    def test_author_in_opf(self):
        data = self._make_epub_bytes(author="Unique AuthorXYZ")
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            opf_names = [n for n in zf.namelist() if n.endswith(".opf")]
            opf_text = zf.read(opf_names[0]).decode("utf-8")
        assert "Unique AuthorXYZ" in opf_text

    def test_content_in_xhtml(self):
        data = self._make_epub_bytes(content="<p>TestContent789</p>")
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xhtml_names = [n for n in zf.namelist() if n.endswith(".xhtml")]
            assert xhtml_names
            xhtml_text = zf.read(xhtml_names[0]).decode("utf-8")
        assert "TestContent789" in xhtml_text


class TestCreateEpub:
    """Integration-level test for the public create_epub() function."""

    def test_creates_file_on_disk(self, tmp_path):
        out = str(tmp_path / "test.epub")
        result = create_epub("Title", "Author", "<p>content</p>", out)
        assert result == out
        assert os.path.exists(out)
        assert os.path.getsize(out) > 0

    def test_output_is_valid_epub_zip(self, tmp_path):
        out = str(tmp_path / "test.epub")
        create_epub("Title", "Author", "<p>content</p>", out)
        assert zipfile.is_zipfile(out)

    def test_empty_content_no_crash(self, tmp_path):
        out = str(tmp_path / "empty.epub")
        create_epub("", "", "", out)
        assert os.path.exists(out)

    def test_unicode_content(self, tmp_path):
        out = str(tmp_path / "unicode.epub")
        create_epub("Заголовок", "Автор", "<p>Текст на русском языке.</p>", out)
        assert zipfile.is_zipfile(out)

    def test_special_html_chars_in_title(self, tmp_path):
        """Title with HTML specials must not corrupt the OPF XML."""
        out = str(tmp_path / "special.epub")
        # Should not raise
        create_epub("<Title & 'Test'>", "Author", "<p>body</p>", out)
        assert zipfile.is_zipfile(out)


# ===========================================================================
# dropbox_module tests (now pure HTTP, no subprocess)
# ===========================================================================

class TestRefreshAccessToken:
    """Tests for the dropbox_module.refresh_access_token() HTTP call."""

    @patch.dict(
        os.environ,
        {
            "DROPBOX_REFRESH_TOKEN": "rtoken",
            "DROPBOX_APP_KEY": "appkey",
            "DROPBOX_APP_SECRET": "appsecret",
        },
    )
    def test_success_returns_token(self):
        dm = _load_real_dropbox_module()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "fresh_token_xyz"}

        with patch.object(dm.requests, "post", return_value=mock_resp) as mock_post:
            token = dm.refresh_access_token()

        assert token == "fresh_token_xyz"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "oauth2/token" in args[0]
        assert kwargs["data"]["grant_type"] == "refresh_token"

    @patch.dict(
        os.environ,
        {
            "DROPBOX_REFRESH_TOKEN": "rtoken",
            "DROPBOX_APP_KEY": "appkey",
            "DROPBOX_APP_SECRET": "appsecret",
        },
    )
    def test_failure_returns_none(self):
        dm = _load_real_dropbox_module()

        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch.object(dm.requests, "post", return_value=mock_resp):
            token = dm.refresh_access_token()

        assert token is None


class TestUploadToDropbox:
    """Tests for dropbox_module.upload_to_dropbox() – now uses HTTP, no subprocess."""

    def test_missing_file_returns_false(self):
        dm = _load_real_dropbox_module()
        result = dm.upload_to_dropbox("/nonexistent/path/file.epub")
        assert result is False

    def test_no_access_token_returns_false(self, tmp_path):
        dm = _load_real_dropbox_module()
        f = tmp_path / "test.epub"
        f.write_bytes(b"fakeepub")

        with patch.object(dm, "refresh_access_token", return_value=None):
            result = dm.upload_to_dropbox(str(f))
        assert result is False

    def test_successful_upload_returns_true(self, tmp_path):
        dm = _load_real_dropbox_module()
        f = tmp_path / "book.epub"
        f.write_bytes(b"fakeepubcontent")

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch.object(dm, "refresh_access_token", return_value="tok123"), \
             patch.object(dm.requests, "post", return_value=mock_resp) as mock_post:
            result = dm.upload_to_dropbox(str(f), "book.epub")

        assert result is True
        mock_post.assert_called_once()
        # Should hit content.dropboxapi.com/2/files/upload
        assert "dropboxapi.com" in mock_post.call_args[0][0]

    def test_api_error_returns_false(self, tmp_path):
        dm = _load_real_dropbox_module()
        f = tmp_path / "book.epub"
        f.write_bytes(b"fakeepubcontent")

        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_resp.text = "conflict"

        with patch.object(dm, "refresh_access_token", return_value="tok123"), \
             patch.object(dm.requests, "post", return_value=mock_resp):
            result = dm.upload_to_dropbox(str(f))
        assert result is False

    def test_network_exception_returns_false(self, tmp_path):
        dm = _load_real_dropbox_module()
        f = tmp_path / "book.epub"
        f.write_bytes(b"fakeepubcontent")

        with patch.object(dm, "refresh_access_token", return_value="tok123"), \
             patch.object(dm.requests, "post", side_effect=Exception("network error")):
            result = dm.upload_to_dropbox(str(f))
        assert result is False

    def test_no_subprocess_used(self, tmp_path):
        """Ensure subprocess is never called in upload_to_dropbox."""
        dm = _load_real_dropbox_module()
        f = tmp_path / "book.epub"
        f.write_bytes(b"fakeepubcontent")
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch.object(dm, "refresh_access_token", return_value="tok123"), \
             patch.object(dm.requests, "post", return_value=mock_resp), \
             patch("subprocess.Popen") as mock_popen:
            dm.upload_to_dropbox(str(f))
            mock_popen.assert_not_called()

    def test_custom_filename_used_in_header(self, tmp_path):
        """The custom filename should appear in Dropbox-API-Arg header path."""
        dm = _load_real_dropbox_module()
        f = tmp_path / "original.epub"
        f.write_bytes(b"epub")
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch.object(dm, "refresh_access_token", return_value="tok123"), \
             patch.object(dm.requests, "post", return_value=mock_resp) as mock_post:
            dm.upload_to_dropbox(str(f), custom_filename="my_custom_name.epub")

        _args, call_kwargs = mock_post.call_args
        headers = call_kwargs.get("headers", {})
        import json
        api_arg = json.loads(headers.get("Dropbox-API-Arg", "{}"))
        assert "my_custom_name.epub" in api_arg.get("path", "")


# ===========================================================================
# TelegramToEpub bot tests (unchanged logic, mocks updated)
# ===========================================================================

class TestTelegramToEpub:

    @pytest.fixture
    def converter(self):
        return TelegramToEpub()

    @pytest.fixture
    def mock_update(self):
        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        update.message.reply_document = AsyncMock()
        update.message.delete = AsyncMock()
        update.message.chat = MagicMock()
        update.message.chat.id = 12345
        update.message.text = None
        update.message.caption = None
        update.message.document = None
        update.message.date = datetime.now()
        update.message.entities = None
        update.message.caption_entities = None
        update.message.link = None
        return update

    @pytest.fixture
    def mock_context(self):
        ctx = MagicMock()
        ctx.bot = MagicMock()
        ctx.bot.get_file = AsyncMock()
        return ctx

    @pytest.fixture
    def mock_forwarded_message(self, mock_update):
        mock_update.message.forward_origin = MagicMock()
        mock_update.message.forward_origin.type = "user"
        mock_update.message.forward_origin.sender_user = MagicMock()
        mock_update.message.forward_origin.sender_user.full_name = "Test User"
        mock_update.message.text = "Test message content"
        return mock_update

    # --- utility methods ---

    def test_get_message_text(self, converter):
        message = MagicMock()
        message.text = "text"
        message.caption = None
        assert converter.get_message_text(message) == "text"

        message.text = None
        message.caption = "cap"
        assert converter.get_message_text(message) == "cap"

        message.text = "t"
        message.caption = "c"
        assert converter.get_message_text(message) == "t"

        message.text = None
        message.caption = None
        assert converter.get_message_text(message) == ""

    def test_extract_title_first_paragraph(self, converter):
        text = "First para\nline2\n\nSecond para"
        assert converter.extract_title(text) == "First para\nline2"

    def test_extract_title_empty(self, converter):
        assert converter.extract_title("") == "Untitled"
        assert converter.extract_title(None) == "Untitled"

    def test_format_message(self, converter):
        text = "This is a test\nwith newlines\n\nAnd paragraphs\nAnd file.md reference"
        formatted = converter.format_message(text)
        assert "<p>" in formatted
        assert "<br>" in formatted
        assert "<u>file.md</u>" in formatted

    def test_strip_emojis(self, converter):
        text = "Hello 🌍! 🗓️ Title 📖"
        assert converter.strip_emojis(text) == "Hello ! Title"

        text_cyr = "Привет 👋! Как дела? 😊"
        assert converter.strip_emojis(text_cyr) == "Привет ! Как дела?"

    def test_sanitize_filename(self, converter):
        assert converter.sanitize_filename("Hello World") == "Hello_World"
        assert converter.sanitize_filename("") == "message"
        assert converter.sanitize_filename("Untitled") == "message"
        # Limit to 4 words
        result = converter.sanitize_filename("One Two Three Four Five Six")
        assert "_".join(result.split("_")) == result
        assert len(result.split("_")) <= 4

    # --- async message handlers ---

    @pytest.mark.asyncio
    async def test_handle_message_no_text(self, converter, mock_update, mock_context):
        mock_update.message.forward_origin = None
        mock_update.message.text = None
        mock_update.message.caption = None

        await converter.handle_message(mock_update, mock_context)

        mock_update.message.reply_text.assert_called()
        args = mock_update.message.reply_text.call_args[0]
        assert "не содержит текста" in args[0]

    @pytest.mark.asyncio
    async def test_handle_forwarded_message_no_text(self, converter, mock_update, mock_context):
        mock_update.message.forward_origin = MagicMock()
        mock_update.message.forward_origin.type = "user"
        mock_update.message.text = None
        mock_update.message.caption = None

        await converter.handle_message(mock_update, mock_context)

        mock_update.message.reply_text.assert_called()
        args = mock_update.message.reply_text.call_args[0]
        assert "не содержит текста" in args[0]

    @pytest.mark.asyncio
    async def test_handle_forwarded_message_success(
        self, converter, mock_forwarded_message, mock_context
    ):
        processing_msg = MagicMock()
        processing_msg.delete = AsyncMock()
        mock_forwarded_message.message.reply_text = AsyncMock(return_value=processing_msg)

        with patch("bot.dropbox_module.upload_to_dropbox", return_value=True), \
             patch("bot.create_epub", return_value="/tmp/test.epub"), \
             patch("builtins.open", MagicMock()), \
             patch("os.path.exists", return_value=True), \
             patch("os.remove"):
            await converter.handle_message(mock_forwarded_message, mock_context)

        assert mock_forwarded_message.message.reply_text.call_count >= 2
        summary_call = mock_forwarded_message.message.reply_text.call_args_list[-1]
        assert "<b>" in summary_call[0][0]
        assert "Test User" in summary_call[0][0]
        assert summary_call[1]["parse_mode"] == "HTML"

    @pytest.mark.asyncio
    async def test_handle_message_title_is_first_paragraph(
        self, converter, mock_update, mock_context
    ):
        mock_update.message.forward_origin = MagicMock()
        mock_update.message.forward_origin.type = "user"
        mock_update.message.forward_origin.sender_user = MagicMock()
        mock_update.message.forward_origin.sender_user.full_name = "Test User"
        mock_update.message.text = "Заголовок\n\nТело поста"

        processing_msg = MagicMock()
        processing_msg.delete = AsyncMock()
        mock_update.message.reply_text = AsyncMock(return_value=processing_msg)

        with patch("bot.dropbox_module.upload_to_dropbox", return_value=True), \
             patch("bot.create_epub", return_value="/tmp/test.epub") as mock_create, \
             patch("builtins.open", MagicMock()), \
             patch("os.path.exists", return_value=True), \
             patch("os.remove"):
            await converter.handle_message(mock_update, mock_context)

        args, _kwargs = mock_create.call_args
        assert args[0] == "Заголовок"
        assert "Тело поста" in args[2]

    @pytest.mark.asyncio
    async def test_handle_message_with_caption(self, converter, mock_update, mock_context):
        mock_update.message.forward_origin = MagicMock()
        mock_update.message.forward_origin.type = "user"
        mock_update.message.forward_origin.sender_user = MagicMock()
        mock_update.message.forward_origin.sender_user.full_name = "Test User"
        mock_update.message.text = None
        mock_update.message.caption = "Test caption content"

        processing_msg = MagicMock()
        processing_msg.delete = AsyncMock()
        mock_update.message.reply_text = AsyncMock(return_value=processing_msg)

        with patch("bot.dropbox_module.upload_to_dropbox", return_value=True), \
             patch("bot.create_epub", return_value="/tmp/test.epub"), \
             patch("builtins.open", MagicMock()), \
             patch("os.path.exists", return_value=True), \
             patch("os.remove"):
            await converter.handle_message(mock_update, mock_context)

        assert mock_update.message.reply_text.call_count >= 2

    @pytest.mark.asyncio
    async def test_handle_message_exception(
        self, converter, mock_forwarded_message, mock_context
    ):
        processing_msg = MagicMock()
        processing_msg.delete = AsyncMock()
        mock_forwarded_message.message.reply_text = AsyncMock(return_value=processing_msg)

        with patch("bot.dropbox_module.upload_to_dropbox", return_value=True), \
             patch("bot.create_epub", side_effect=Exception("Test error")):
            await converter.handle_message(mock_forwarded_message, mock_context)

        processing_msg.delete.assert_called_once()
        assert mock_forwarded_message.message.reply_text.call_count == 2
        error_call = mock_forwarded_message.message.reply_text.call_args_list[1]
        assert "Извините, произошла ошибка" in error_call[0][0]

    @pytest.mark.asyncio
    async def test_handle_forwarded_from_channel(self, converter, mock_update, mock_context):
        mock_update.message.forward_origin = MagicMock()
        mock_update.message.forward_origin.type = "channel"
        mock_update.message.forward_origin.sender_chat = MagicMock()
        mock_update.message.forward_origin.sender_chat.title = "Test Channel"
        mock_update.message.text = "Test message"

        processing_msg = MagicMock()
        processing_msg.delete = AsyncMock()
        mock_update.message.reply_text = AsyncMock(return_value=processing_msg)

        with patch("bot.dropbox_module.upload_to_dropbox", return_value=True), \
             patch("bot.create_epub", return_value="/tmp/test.epub"), \
             patch("builtins.open", MagicMock()), \
             patch("os.path.exists", return_value=True), \
             patch("os.remove"):
            await converter.handle_message(mock_update, mock_context)

        assert mock_update.message.reply_text.call_count >= 2

    @pytest.mark.asyncio
    async def test_handle_epub_document(self, converter, mock_update, mock_context):
        """Direct EPUB uploads are forwarded without conversion."""
        processing_msg = MagicMock()
        processing_msg.delete = AsyncMock()
        mock_update.message.reply_text = AsyncMock(return_value=processing_msg)

        document = MagicMock()
        document.mime_type = "application/epub+zip"
        document.file_name = "My Book.epub"
        document.file_id = "file-id"
        mock_update.message.document = document
        mock_update.message.forward_origin = None

        file_mock = MagicMock()
        file_mock.download_to_drive = AsyncMock()
        mock_context.bot.get_file.return_value = file_mock

        with patch("bot.dropbox_module.upload_to_dropbox", return_value=True) as mock_upload, \
             patch("bot.create_epub") as mock_create:
            await converter.handle_message(mock_update, mock_context)

        mock_context.bot.get_file.assert_awaited_once_with("file-id")
        file_mock.download_to_drive.assert_awaited()
        mock_update.message.reply_document.assert_awaited_once()
        _args, kwargs = mock_update.message.reply_document.call_args
        assert kwargs["filename"] == "My_Book.epub"
        assert kwargs["parse_mode"] == "HTML"
        assert "My Book" in kwargs["caption"]
        assert "<b>" in kwargs["caption"]
        processing_msg.delete.assert_awaited_once()
        mock_upload.assert_called_once()
        assert mock_upload.call_args[0][1] == "My_Book.epub"
        mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_non_epub_document(self, converter, mock_update, mock_context):
        """Non-EPUB documents are rejected."""
        document = MagicMock()
        document.mime_type = "application/pdf"
        document.file_name = "report.pdf"
        document.file_id = "file-id"
        mock_update.message.document = document

        await converter.handle_message(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once()
        reply_text = mock_update.message.reply_text.call_args[0][0]
        assert "только EPUB" in reply_text
        mock_context.bot.get_file.assert_not_called()
        mock_update.message.reply_document.assert_not_called()


# ===========================================================================
# Integration tests for main()
# ===========================================================================

@patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"})
@patch("bot.Application")
def test_main_function(mock_application):
    from bot import main

    mock_app_instance = MagicMock()
    mock_application.builder.return_value.token.return_value.build.return_value = (
        mock_app_instance
    )

    with patch("bot.CommandHandler", new=MagicMock()), patch(
        "bot.MessageHandler", new=MagicMock()
    ):
        main()

    mock_app_instance.add_handler.assert_called()
    mock_app_instance.run_polling.assert_called_once()


@patch.dict(os.environ, {}, clear=True)
def test_main_function_no_token():
    from bot import main

    result = main()
    assert result is None
