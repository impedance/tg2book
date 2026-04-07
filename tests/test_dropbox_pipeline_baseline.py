import importlib
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module_from_file(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    sys.modules[module_name] = module
    return module


def _install_telegram_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    telegram_module = types.ModuleType("telegram")
    telegram_module.Update = object

    telegram_ext_module = types.ModuleType("telegram.ext")
    telegram_ext_module.Application = MagicMock
    telegram_ext_module.CommandHandler = MagicMock
    telegram_ext_module.ContextTypes = SimpleNamespace(DEFAULT_TYPE=object)
    telegram_ext_module.MessageHandler = MagicMock
    telegram_ext_module.filters = SimpleNamespace(ALL=object)

    monkeypatch.setitem(sys.modules, "telegram", telegram_module)
    monkeypatch.setitem(sys.modules, "telegram.ext", telegram_ext_module)


@pytest.fixture
def loaded_modules(monkeypatch: pytest.MonkeyPatch):
    # Make sure tests use real ebooklib + real modules from this repository.
    for name in ("bot", "dropbox_module", "epub_functions", "ebooklib", "ebooklib.epub"):
        sys.modules.pop(name, None)

    real_ebooklib = pytest.importorskip("ebooklib")
    monkeypatch.setitem(sys.modules, "ebooklib", real_ebooklib)
    monkeypatch.syspath_prepend(str(REPO_ROOT))
    _install_telegram_stubs(monkeypatch)

    dropbox_module = _load_module_from_file("dropbox_module", REPO_ROOT / "dropbox_module.py")
    bot_module = importlib.import_module("bot")
    bot_module = importlib.reload(bot_module)
    return bot_module, dropbox_module


def _mock_dropbox_http_success(monkeypatch: pytest.MonkeyPatch, dropbox_module):
    response = SimpleNamespace(status_code=200, json=lambda: {"access_token": "token-123"})
    monkeypatch.setattr(dropbox_module.requests, "post", lambda *args, **kwargs: response)


@pytest.mark.asyncio
async def test_text_message_uploads_generated_epub_bytes_to_dropbox(
    loaded_modules, monkeypatch: pytest.MonkeyPatch
):
    bot_module, dropbox_module = loaded_modules
    _mock_dropbox_http_success(monkeypatch, dropbox_module)

    captured = {}

    class FakePopen:
        def __init__(self, command, stdout=None, stderr=None):
            captured["command"] = command
            captured["uploaded_bytes"] = Path(command[2]).read_bytes()

        def communicate(self):
            return "Загрузка завершена успешно!".encode("utf-8"), b""

    monkeypatch.setattr(dropbox_module.subprocess, "Popen", FakePopen)

    converter = bot_module.TelegramToEpub()
    processing_msg = SimpleNamespace(delete=AsyncMock())
    message = MagicMock()
    message.chat = SimpleNamespace(id=42)
    message.text = "Заголовок\n\nТело поста"
    message.caption = None
    message.document = None
    message.entities = []
    message.caption_entities = []
    message.link = ""
    message.forward_origin = SimpleNamespace(
        type="user",
        sender_user=SimpleNamespace(full_name="Test User"),
        sender_chat=None,
        chat=None,
        message_id=None,
    )
    message.reply_text = AsyncMock(return_value=processing_msg)
    message.reply_document = AsyncMock()
    message.delete = AsyncMock()

    update = SimpleNamespace(message=message)
    context = SimpleNamespace()

    await converter.handle_message(update, context)

    assert captured["uploaded_bytes"].startswith(b"PK")
    assert len(captured["uploaded_bytes"]) > 100
    assert captured["command"][3].endswith(".epub")
    assert message.reply_text.await_count >= 2


@pytest.mark.asyncio
async def test_uploaded_epub_document_uploads_exact_original_bytes(
    loaded_modules, monkeypatch: pytest.MonkeyPatch
):
    bot_module, dropbox_module = loaded_modules
    _mock_dropbox_http_success(monkeypatch, dropbox_module)

    original_bytes = b"EPUB-DATA-12345"
    captured = {}

    class FakePopen:
        def __init__(self, command, stdout=None, stderr=None):
            captured["command"] = command
            captured["uploaded_bytes"] = Path(command[2]).read_bytes()

        def communicate(self):
            return "Успешно завершено!".encode("utf-8"), b""

    monkeypatch.setattr(dropbox_module.subprocess, "Popen", FakePopen)

    async def write_epub(custom_path=None):
        Path(custom_path).write_bytes(original_bytes)

    telegram_file = SimpleNamespace(download_to_drive=AsyncMock(side_effect=write_epub))
    context = SimpleNamespace(
        bot=SimpleNamespace(get_file=AsyncMock(return_value=telegram_file))
    )

    converter = bot_module.TelegramToEpub()
    processing_msg = SimpleNamespace(delete=AsyncMock())
    message = MagicMock()
    message.chat = SimpleNamespace(id=101)
    message.text = None
    message.caption = None
    message.entities = []
    message.caption_entities = []
    message.link = ""
    message.forward_origin = None
    message.document = SimpleNamespace(
        mime_type="application/epub+zip",
        file_name="Original File.epub",
        file_id="file-abc",
    )
    message.reply_text = AsyncMock(return_value=processing_msg)
    message.reply_document = AsyncMock()
    message.delete = AsyncMock()

    update = SimpleNamespace(message=message)

    await converter.handle_message(update, context)

    assert captured["uploaded_bytes"] == original_bytes
    assert captured["command"][3].endswith("Original_File.epub")
    message.reply_document.assert_awaited_once()


@pytest.mark.asyncio
async def test_dropbox_failure_is_logged_and_bot_stays_responsive(
    loaded_modules, monkeypatch: pytest.MonkeyPatch
):
    bot_module, dropbox_module = loaded_modules
    _mock_dropbox_http_success(monkeypatch, dropbox_module)

    class FakePopen:
        def __init__(self, command, stdout=None, stderr=None):
            self.command = command

        def communicate(self):
            return b"", b"forced upload error"

    monkeypatch.setattr(dropbox_module.subprocess, "Popen", FakePopen)
    error_mock = MagicMock()
    monkeypatch.setattr(bot_module.logger, "error", error_mock)

    converter = bot_module.TelegramToEpub()
    processing_msg = SimpleNamespace(delete=AsyncMock())
    message = MagicMock()
    message.chat = SimpleNamespace(id=55)
    message.text = "Тестовый пост"
    message.caption = None
    message.document = None
    message.entities = []
    message.caption_entities = []
    message.link = ""
    message.forward_origin = SimpleNamespace(
        type="user",
        sender_user=SimpleNamespace(full_name="Failure Test"),
        sender_chat=None,
        chat=None,
        message_id=None,
    )
    message.reply_text = AsyncMock(return_value=processing_msg)
    message.reply_document = AsyncMock()
    message.delete = AsyncMock()

    update = SimpleNamespace(message=message)
    context = SimpleNamespace()

    await converter.handle_message(update, context)

    assert message.reply_text.await_count >= 2
    assert any(
        "Загрузка в Dropbox не удалась" in str(call.args[0])
        for call in error_mock.call_args_list
    )
