"""
Unit/integration tests for the userbot integration features:
- userbot_db channel management
- TelegramToEpub admin commands
- asyncio.Queue worker routing
"""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Minimal stubs so tests don't need an installed Telegram / Pyrogram package
# ---------------------------------------------------------------------------


class _MockModule:
    pass


if "telegram" not in sys.modules:
    _tg = _MockModule()
    _tg.Update = MagicMock
    _tg.Message = MagicMock
    _tg_ext = _MockModule()
    _tg_ext.Application = MagicMock
    _tg_ext.CommandHandler = MagicMock
    _tg_ext.MessageHandler = MagicMock
    _tg_ext.ContextTypes = MagicMock
    _tg_ext.ContextTypes.DEFAULT_TYPE = MagicMock
    _tg_ext.filters = MagicMock()
    _tg_ext.filters.ALL = MagicMock()
    sys.modules["telegram"] = _tg
    sys.modules["telegram.ext"] = _tg_ext

if "pyrogram" not in sys.modules:
    _pyro = _MockModule()
    _pyro.Client = MagicMock
    _pyro.filters = MagicMock()
    sys.modules["pyrogram"] = _pyro
    sys.modules["pyrogram.filters"] = _pyro.filters

from bot import TelegramToEpub, _QueueItem  # noqa: E402

# ===========================================================================
# Helpers
# ===========================================================================


def _make_update(user_id: int = 12345, text: str = "", document=None):
    update = MagicMock()
    update.message = MagicMock()
    update.message.from_user = MagicMock()
    update.message.from_user.id = user_id
    update.message.reply_text = AsyncMock()
    update.message.reply_document = AsyncMock()
    update.message.delete = AsyncMock()
    update.message.chat.id = user_id
    update.message.text = text or None
    update.message.caption = None
    update.message.document = document
    update.message.forward_origin = None
    return update


def _make_context(args=None):
    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.get_file = AsyncMock()
    ctx.args = args or []
    return ctx


# ===========================================================================
# userbot_db tests (in-memory via tmp path)
# ===========================================================================


@pytest.mark.asyncio
async def test_db_add_and_get(tmp_path):
    import userbot_db

    original_path = userbot_db.DB_PATH
    userbot_db.DB_PATH = tmp_path / "test.sqlite"
    try:
        await userbot_db.init_db()
        assert await userbot_db.add_channel("testchannel") is True
        assert await userbot_db.add_channel("@testchannel") is False  # duplicate
        channels = await userbot_db.get_channels()
        assert "testchannel" in channels
    finally:
        userbot_db.DB_PATH = original_path


@pytest.mark.asyncio
async def test_db_remove(tmp_path):
    import userbot_db

    original_path = userbot_db.DB_PATH
    userbot_db.DB_PATH = tmp_path / "test.sqlite"
    try:
        await userbot_db.init_db()
        await userbot_db.add_channel("mychannel")
        assert await userbot_db.remove_channel("mychannel") is True
        assert await userbot_db.remove_channel("mychannel") is False
        assert await userbot_db.get_channels() == []
    finally:
        userbot_db.DB_PATH = original_path


# ===========================================================================
# Admin guard tests
# ===========================================================================


@pytest.mark.asyncio
async def test_add_channel_rejects_non_admin():
    converter = TelegramToEpub()
    update = _make_update(user_id=99999)
    context = _make_context(args=["somechannel"])

    with patch("bot.settings") as mock_settings:
        mock_settings.ADMIN_ID = 42
        await converter.add_channel(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "⛔" in call_text


@pytest.mark.asyncio
async def test_add_channel_admin_success(tmp_path):
    import userbot_db

    original_path = userbot_db.DB_PATH
    userbot_db.DB_PATH = tmp_path / "test.sqlite"
    await userbot_db.init_db()

    converter = TelegramToEpub()
    update = _make_update(user_id=42)
    context = _make_context(args=["@newchan"])

    with patch("bot.settings") as mock_settings:
        mock_settings.ADMIN_ID = 42
        await converter.add_channel(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "✅" in call_text
    assert "newchan" in call_text

    userbot_db.DB_PATH = original_path


@pytest.mark.asyncio
async def test_list_channels_empty(tmp_path):
    import userbot_db

    original_path = userbot_db.DB_PATH
    userbot_db.DB_PATH = tmp_path / "test.sqlite"
    await userbot_db.init_db()

    converter = TelegramToEpub()
    update = _make_update(user_id=42)
    context = _make_context()

    with patch("bot.settings") as mock_settings:
        mock_settings.ADMIN_ID = 42
        await converter.list_channels(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "пуст" in call_text

    userbot_db.DB_PATH = original_path


@pytest.mark.asyncio
async def test_del_channel_not_found(tmp_path):
    import userbot_db

    original_path = userbot_db.DB_PATH
    userbot_db.DB_PATH = tmp_path / "test.sqlite"
    await userbot_db.init_db()

    converter = TelegramToEpub()
    update = _make_update(user_id=42)
    context = _make_context(args=["ghost"])

    with patch("bot.settings") as mock_settings:
        mock_settings.ADMIN_ID = 42
        await converter.del_channel(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "ℹ️" in call_text

    userbot_db.DB_PATH = original_path


# ===========================================================================
# Queue worker tests
# ===========================================================================


@pytest.mark.asyncio
async def test_channel_worker_processes_item():
    """Worker should pop a QueueItem, call epub_service, and send result to admin."""
    converter = TelegramToEpub()

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    item = _QueueItem(
        text="Привет мир",
        source_name="TestChannel",
        post_link="https://t.me/testchannel/1",
        reply_chat_id=42,
        bot=mock_bot,
    )

    with patch("services.epub_service.process_text_to_epub", new_callable=AsyncMock) as mock_epub:
        mock_epub.return_value = "<b>Done</b>"

        await converter.processing_queue.put(item)

        # Run worker for a brief moment, then cancel it
        worker = asyncio.create_task(converter._channel_worker())
        await asyncio.sleep(0.1)
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass

    mock_epub.assert_called_once_with("Привет мир", "TestChannel", "https://t.me/testchannel/1")
    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args.kwargs["chat_id"] == 42


@pytest.mark.asyncio
async def test_handle_channel_message_enqueues_when_called_directly(tmp_path):
    """
    _handle_channel_message trusts the upstream Pyrogram filter and enqueues
    any message that reaches it. Filtering by channel membership is now done
    exclusively by the custom Pyrogram filter (tested in tests/test_userbot_filters.py).
    """
    import userbot_db

    original_path = userbot_db.DB_PATH
    userbot_db.DB_PATH = tmp_path / "test.sqlite"
    await userbot_db.init_db()

    converter = TelegramToEpub()

    pyro_msg = MagicMock()
    pyro_msg.chat.username = "somechannel"
    pyro_msg.chat.title = "Some Channel"
    pyro_msg.chat.id = -1009999999
    pyro_msg.text = "Some text"
    pyro_msg.caption = None
    pyro_msg.id = 1

    with patch("bot.settings") as mock_settings:
        mock_settings.ADMIN_ID = 42
        await converter._handle_channel_message(pyro_msg, MagicMock())

    # Handler enqueues unconditionally — filtering is the filter's job
    assert converter.processing_queue.qsize() == 1

    userbot_db.DB_PATH = original_path


@pytest.mark.asyncio
async def test_handle_channel_message_enqueues_known_channel(tmp_path):
    """Messages from monitored channels should be placed in the processing queue."""
    import userbot_db

    original_path = userbot_db.DB_PATH
    userbot_db.DB_PATH = tmp_path / "test.sqlite"
    await userbot_db.init_db()
    await userbot_db.add_channel("monitored")

    converter = TelegramToEpub()

    pyro_msg = MagicMock()
    pyro_msg.chat.username = "monitored"
    pyro_msg.chat.title = "Monitored Chan"
    pyro_msg.text = "Hello world"
    pyro_msg.caption = None
    pyro_msg.id = 999

    with patch("bot.settings") as mock_settings:
        mock_settings.ADMIN_ID = 42
        await converter._handle_channel_message(pyro_msg, MagicMock())

    assert converter.processing_queue.qsize() == 1
    queued: _QueueItem = converter.processing_queue.get_nowait()
    assert queued.text == "Hello world"
    assert queued.reply_chat_id == 42

    userbot_db.DB_PATH = original_path


# ===========================================================================
# Black-box test: userbot startup caches dialogs (anti-fragility guard)
# ===========================================================================


@pytest.mark.asyncio
async def test_userbot_starts_and_fetches_dialogs():
    """
    [Black-box test] Убедиться, что при запуске юзербота вызывается get_dialogs(),
    чтобы кэшировать peer_id и избежать 'ValueError: Peer id invalid'.
    """
    get_dialogs_called = False

    async def mock_get_dialogs():
        nonlocal get_dialogs_called
        get_dialogs_called = True
        yield MagicMock(chat=MagicMock(id=-100123456))

    with patch("bot.PyrogramClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance
        mock_instance.start = AsyncMock()
        mock_instance.get_me = AsyncMock(return_value=MagicMock(username="test", id=1))
        mock_instance.stop = AsyncMock()
        mock_instance.get_dialogs = mock_get_dialogs
        mock_instance.on_message = MagicMock(return_value=lambda f: f)
        mock_instance.on_edited_message = MagicMock(return_value=lambda f: f)

        converter = TelegramToEpub()
        app_mock = MagicMock()

        with patch("bot.settings") as mock_settings:
            mock_settings.API_ID = "123"
            mock_settings.API_HASH = "abc"
            mock_settings.USERBOT_SESSION_STRING = ""

            await converter._start_userbot(app_mock)

            mock_instance.start.assert_awaited_once()
            mock_instance.get_me.assert_awaited_once()
            assert get_dialogs_called, (
                "get_dialogs() должен вызываться при старте юзербота "
                "для предотвращения 'ValueError: Peer id invalid'"
            )
