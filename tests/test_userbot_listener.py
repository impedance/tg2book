from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from userbot_listener import UserbotListener


@pytest.fixture
def listener():
    converter = MagicMock()
    converter.process_channel_post = AsyncMock(return_value=True)
    summary_target = MagicMock()
    summary_target.reply_text = AsyncMock()
    return UserbotListener(converter=converter, summary_target=summary_target)


def _build_event(
    text="Текст поста",
    username="testchannel",
    chat_id=-1001234567890,
    message_id=77,
    title="Test Channel",
):
    chat = SimpleNamespace(username=username, title=title)
    message = SimpleNamespace(message=text, id=message_id, chat=chat, chat_id=chat_id)
    return SimpleNamespace(message=message, chat=chat, chat_id=chat_id, is_channel=True, is_private=False, is_group=False)


def test_parse_channel_post_builds_metadata(listener):
    event = _build_event()

    post = listener.parse_channel_post(event)

    assert post is not None
    assert post.text_content == "Текст поста"
    assert post.source_name == "Test Channel"
    assert post.source_identifier == "testchannel"
    assert post.post_link == "https://t.me/testchannel/77"


@pytest.mark.asyncio
async def test_handle_new_message_skips_empty_posts(listener):
    event = _build_event(text="   ")

    success = await listener.handle_new_message(event)

    assert success is False
    listener.converter.process_channel_post.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_new_message_skips_private_chat_events(listener):
    event = _build_event(text="Личное сообщение")
    event.is_channel = False
    event.is_private = True

    success = await listener.handle_new_message(event)

    assert success is False
    listener.converter.process_channel_post.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_new_message_routes_to_converter(listener):
    event = _build_event(text="Пост для обработки", username="pubchan", message_id=101)

    success = await listener.handle_new_message(event)

    assert success is True
    listener.converter.process_channel_post.assert_awaited_once()
    kwargs = listener.converter.process_channel_post.await_args.kwargs
    assert kwargs["text_content"] == "Пост для обработки"
    assert kwargs["source_name"] == "Test Channel"
    assert kwargs["source_identifier"] == "pubchan"
    assert kwargs["post_link"] == "https://t.me/pubchan/101"
    assert kwargs["summary_target"] is listener.summary_target


@pytest.mark.asyncio
async def test_handle_new_message_unmonitored_or_failed_returns_false(listener):
    listener.converter.process_channel_post = AsyncMock(return_value=False)
    event = _build_event(username="unknownchan")

    success = await listener.handle_new_message(event)

    assert success is False
    listener.converter.process_channel_post.assert_awaited_once()
