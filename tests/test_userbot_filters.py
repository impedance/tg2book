"""
Black-box tests for the userbot in-memory channel cache and custom Pyrogram filter.

Plan reference: docs/userbot_filtering_plan.md

Strategy:
  - The cache is populated via _load_channels_cache() and mutated by
    cmd_add_channel / cmd_del_channel (the same code paths the real bot uses).
  - The filter function itself is extracted by patching pyro_filters.create
    to be an identity (lambda f: f), so we get the raw Python predicate back
    and can call it directly in assertions.
  - No real network I/O; aiosqlite uses a tmp_path SQLite file.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is importable
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Stub out Pyrogram before importing bot (no real connection needed)
# ---------------------------------------------------------------------------


class _MockModule:
    pass


if "pyrogram" not in sys.modules:
    _pyro = _MockModule()
    _pyro.Client = MagicMock
    _pyro_filters = MagicMock()
    _pyro_filters.channel = MagicMock()
    _pyro.filters = _pyro_filters
    _pyro_types = MagicMock()
    _pyro_types.BotCommand = MagicMock
    _pyro.types = _pyro_types
    sys.modules["pyrogram"] = _pyro
    sys.modules["pyrogram.filters"] = _pyro_filters
    sys.modules["pyrogram.types"] = _pyro_types

from bot import TelegramToEpub  # noqa: E402,I001


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pyro_message(
    chat_id: int | None = None,
    username: str | None = None,
    text: str = "hello",
) -> MagicMock:
    """Build a minimal Pyrogram-like Message mock."""
    msg = MagicMock()
    if chat_id is None:
        msg.chat = None
    else:
        msg.chat = MagicMock()
        msg.chat.id = chat_id
        msg.chat.username = username
        msg.chat.title = username or str(chat_id)
    msg.text = text
    msg.caption = None
    msg.id = 1
    return msg


def _get_filter_func(converter: TelegramToEpub):
    """
    Extract the raw Python predicate from _make_monitored_filter().
    pyro_filters.create is patched to be an identity so the function
    comes back unwrapped.
    """
    import bot as _bot_module

    real_create = _bot_module.pyro_filters.create
    _bot_module.pyro_filters.create = lambda f: f
    try:
        return converter._make_monitored_filter()
    finally:
        _bot_module.pyro_filters.create = real_create


def _make_message(user_id: int = 42):
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.reply = AsyncMock()
    msg.command = []
    return msg


# ---------------------------------------------------------------------------
# Test 1 (план 2.2) — строгое игнорирование «чужого» канала (No False Positives)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_rejects_unknown_channel(tmp_path):
    """
    Фильтр должен вернуть False для канала, которого нет в кэше.
    Очередь должна оставаться пустой даже при прямом вызове handler-а.
    """
    import userbot_db

    original_path = userbot_db.DB_PATH
    userbot_db.DB_PATH = tmp_path / "test.sqlite"
    await userbot_db.init_db()
    # No channels added

    converter = TelegramToEpub()
    await converter._load_channels_cache()

    filt = _get_filter_func(converter)
    msg = _make_pyro_message(chat_id=-1009999999, username="random_trash")

    # Filter must return False
    assert filt(None, None, msg) is False

    assert converter.processing_queue.empty()

    userbot_db.DB_PATH = original_path


# ---------------------------------------------------------------------------
# Test 2 (план 2.3) — мгновенный подхват добавленного канала (Cache Sync)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_accepts_after_add_channel(tmp_path):
    """
    После успешного /add_channel:
      - Фильтр возвращает True для этого канала.
      - Очередь вырастает до 1 после прямого вызова handler-а.
    """
    import userbot_db

    original_path = userbot_db.DB_PATH
    userbot_db.DB_PATH = tmp_path / "test.sqlite"
    await userbot_db.init_db()

    converter = TelegramToEpub()
    await converter._load_channels_cache()

    # Admin adds channel via command
    msg = _make_message(user_id=42)
    msg.command = ["add_channel", "@testchannel"]
    client = MagicMock()

    with patch("bot.settings") as s:
        s.ADMIN_ID = 42
        await converter.cmd_add_channel(client, msg)

    call_text = msg.reply.call_args[0][0]
    assert "✅" in call_text

    # Filter must now return True (cache updated in-place)
    filt = _get_filter_func(converter)
    pyro_msg = _make_pyro_message(chat_id=-100111222, username="testchannel", text="First post!")
    assert filt(None, None, pyro_msg) is True

    # Handler should enqueue the message
    with patch("bot.settings") as s:
        s.ADMIN_ID = 42
        await converter._handle_channel_message(pyro_msg, MagicMock())

    assert converter.processing_queue.qsize() == 1
    item = converter.processing_queue.get_nowait()
    assert item.text == "First post!"
    assert item.reply_chat_id == 42

    userbot_db.DB_PATH = original_path


# ---------------------------------------------------------------------------
# Test 3 (план 2.4) — прекращение трекинга после удаления канала
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_rejects_after_del_channel(tmp_path):
    """
    После успешного /del_channel фильтр перестаёт пропускать сообщения.
    """
    import userbot_db

    original_path = userbot_db.DB_PATH
    userbot_db.DB_PATH = tmp_path / "test.sqlite"
    await userbot_db.init_db()
    await userbot_db.add_channel("testchannel")

    converter = TelegramToEpub()
    await converter._load_channels_cache()  # cache has "testchannel"

    filt = _get_filter_func(converter)
    pyro_msg = _make_pyro_message(chat_id=-100333444, username="testchannel", text="before")

    # Sanity: passes before deletion
    assert filt(None, None, pyro_msg) is True

    # Admin removes the channel
    msg = _make_message(user_id=42)
    msg.command = ["del_channel", "@testchannel"]
    client = MagicMock()

    with patch("bot.settings") as s:
        s.ADMIN_ID = 42
        await converter.cmd_del_channel(client, msg)

    call_text = msg.reply.call_args[0][0]
    assert "✅" in call_text

    # Filter must now return False (cache modified in-place; same filt object)
    assert filt(None, None, pyro_msg) is False

    # Queue must remain empty
    assert converter.processing_queue.empty()

    userbot_db.DB_PATH = original_path


# ---------------------------------------------------------------------------
# Test 4 — приватный канал через инвайт: резолв в числовой ID
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_accepts_private_channel_after_invite_resolve(tmp_path):
    """
    Если /add_channel получает инвайт-ссылку приватного канала, а юзербот
    может её разрешить в числовой chat.id, то в БД сохраняется именно ID и
    фильтр начинает пропускать сообщения даже без username.
    """
    import userbot_db

    original_path = userbot_db.DB_PATH
    userbot_db.DB_PATH = tmp_path / "test.sqlite"
    await userbot_db.init_db()

    converter = TelegramToEpub()
    await converter._load_channels_cache()

    # Attach a fake running userbot that can resolve invite links
    fake_userbot = MagicMock()
    fake_userbot.get_chat = AsyncMock()
    chat = MagicMock()
    chat.id = -100777888999
    chat.title = "Secret Channel"
    fake_userbot.get_chat.return_value = chat
    converter._userbot = fake_userbot

    # Admin adds channel via invite link
    msg = _make_message(user_id=42)
    msg.command = ["add_channel", "https://t.me/+AbCdEfGhIj"]
    client = MagicMock()

    with patch("bot.settings") as s:
        s.ADMIN_ID = 42
        await converter.cmd_add_channel(client, msg)

    channels = await userbot_db.get_channels()
    assert str(chat.id) in channels

    filt = _get_filter_func(converter)
    pyro_msg = _make_pyro_message(chat_id=chat.id, username=None, text="private post")
    assert filt(None, None, pyro_msg) is True

    call_text = msg.reply.call_args[0][0]
    assert "✅" in call_text

    userbot_db.DB_PATH = original_path


# ---------------------------------------------------------------------------
# Test 4 (план 2.5) — антихрупкость фильтра (Missing Attributes)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_is_antifragile(tmp_path):
    """
    Фильтр не должен падать с AttributeError на битых апдейтах:
      a) chat=None → False
      b) username=None, совпадение по ID → True + handler enqueues
      c) username=None, ID не совпал → False
    """
    import userbot_db

    original_path = userbot_db.DB_PATH
    userbot_db.DB_PATH = tmp_path / "test.sqlite"
    await userbot_db.init_db()
    await userbot_db.add_channel("-100444555")  # ID-only channel

    converter = TelegramToEpub()
    await converter._load_channels_cache()

    filt = _get_filter_func(converter)

    # a) chat=None — must not raise, must return False
    msg_no_chat = _make_pyro_message(chat_id=None)
    result = filt(None, None, msg_no_chat)
    assert result is False, "Filter must return False when chat is None"

    # b) username=None, ID matches → True
    msg_id_match = _make_pyro_message(chat_id=-100444555, username=None, text="ok")
    result = filt(None, None, msg_id_match)
    assert result is True, "Filter must match by numeric ID even without username"

    # Handler should enqueue when ID matches
    with patch("bot.settings") as s:
        s.ADMIN_ID = 42
        await converter._handle_channel_message(msg_id_match, MagicMock())
    assert converter.processing_queue.qsize() == 1

    # c) username=None, different ID → False
    msg_id_mismatch = _make_pyro_message(chat_id=-100000000, username=None, text="noise")
    result = filt(None, None, msg_id_mismatch)
    assert result is False

    userbot_db.DB_PATH = original_path
