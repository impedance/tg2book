"""
Tests for tg2book bot.
"""

import importlib.util as _ilu
import pathlib as _pl


def _load_real_module(module_name, file_path):
    spec = _ilu.spec_from_file_location(
        module_name,
        str(_pl.Path(__file__).parent / file_path),
    )
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_real_dropbox_module():
    return _load_real_module("dropbox_module_real", "dropbox_module.py")


def _load_real_text_utils():
    return _load_real_module("text_utils_real", "utils/text_utils.py")


import io
import sys
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# GLOBAL MOCKS (Telegram only, as it's truly external and heavy)
# ---------------------------------------------------------------------------


class _MockModule:
    pass


if "telegram" not in sys.modules:
    _telegram_mock = _MockModule()
    _telegram_mock.Update = MagicMock
    _telegram_mock.Message = MagicMock
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

# We import the classes we want to test from the REAL bot.py
# but we need to ensure the imports inside bot.py don't fail or pull in light mocks
# when we want to test with real logic in integration tests.

from bot import TelegramToEpub
from epub_functions import _build_epub_zip, _render_svg_cover

# ===========================================================================
# Unit Tests
# ===========================================================================


class TestSvgCover:
    def test_returns_bytes(self):
        svg = _render_svg_cover("My Title", "My Author")
        assert isinstance(svg, bytes)
        assert b"<svg" in svg


class TestBuildEpubZip:
    def test_result_is_valid_zip(self):
        buf = io.BytesIO()
        _build_epub_zip(buf, title="T", author="A", content="C")
        assert zipfile.is_zipfile(io.BytesIO(buf.getvalue()))


class TestTelegramToEpub:
    @pytest.fixture
    def mock_update(self):
        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        update.message.reply_document = AsyncMock()
        update.message.delete = AsyncMock()
        update.message.chat.id = 12345
        update.message.text = None
        update.message.caption = None
        update.message.document = None
        update.message.forward_origin = None
        return update

    @pytest.fixture
    def mock_context(self):
        ctx = MagicMock()
        ctx.bot = MagicMock()
        ctx.bot.get_file = AsyncMock()
        return ctx

    @pytest.mark.asyncio
    @patch("services.epub_service.process_text_to_epub", new_callable=AsyncMock)
    async def test_handle_forwarded_message_success(self, mock_process, mock_update, mock_context):
        mock_update.message.text = "Hello"
        mock_update.message.forward_origin = MagicMock()
        mock_process.return_value = "<b>Done</b>"

        converter = TelegramToEpub()
        converter.processing_semaphore = AsyncMock()
        converter.processing_semaphore.__aenter__ = AsyncMock()
        converter.processing_semaphore.__aexit__ = AsyncMock()

        await converter.handle_message(mock_update, mock_context)
        assert mock_update.message.reply_text.called
        assert mock_update.message.delete.called

    @pytest.mark.asyncio
    @patch("services.epub_service.process_file_to_dropbox", new_callable=AsyncMock)
    async def test_handle_epub_document(self, mock_process, mock_update, mock_context):
        doc = MagicMock()
        doc.file_name = "test.epub"
        doc.mime_type = "application/epub+zip"
        mock_update.message.document = doc
        mock_process.return_value = True

        converter = TelegramToEpub()
        converter.processing_semaphore = AsyncMock()
        converter.processing_semaphore.__aenter__ = AsyncMock()
        converter.processing_semaphore.__aexit__ = AsyncMock()

        await converter.handle_message(mock_update, mock_context)
        assert mock_update.message.reply_document.called
        # Verify Dropbox upload service was also called (acceptance criteria 3.8)
        mock_process.assert_called_once()

    def test_extract_title(self):
        real_text_utils = _load_real_text_utils()
        assert real_text_utils.extract_title("Title\n\nBody") == "Title"
