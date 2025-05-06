import pytest
import sys
sys.path.append('../')
from unittest.mock import AsyncMock, patch
from telegram import Bot
import bot

@pytest.fixture
def mock_bot():
    bot = AsyncMock(spec=Bot)
    bot.send_message = AsyncMock()
    return bot

@pytest.fixture
def mock_update():
    update = AsyncMock()
    update.message = AsyncMock()
    update.message.chat.id = 12345
    return update

@pytest.mark.asyncio
async def test_send_welcome(mock_bot, mock_update):
    """Test the /start command handler"""
    mock_update.message.text = "/start"
    await bot.send_welcome(mock_update, mock_bot)
    mock_bot.send_message.assert_awaited_once_with(
        chat_id=12345,
        text="Welcome! I'm your Telegram bot."
    )

@pytest.mark.asyncio
async def test_handle_message_with_link(mock_bot, mock_update):
    """Test handling a message containing a link"""
    link = "https://t.me/telegram/123"
    mock_update.message.text = f"Check this out: {link}"
    # We expect handle_message to call handle_link which sends a specific message
    import bot
    from bot import handle_message # Import the new handler
    await bot.handle_message(mock_update, mock_bot)
    mock_bot.send_message.assert_awaited_once_with(
        chat_id=12345,
        text=f"Link received: Check this out: {link}"
    )


@pytest.mark.asyncio
async def test_echo_text_message(mock_bot, mock_update):
    """Test echoing text message"""
    mock_update.message.text = "Hello, Bot!"
    from bot import echo # Import echo as it's now called by handle_message
    await bot.echo(mock_update, mock_bot)
    mock_bot.send_message.assert_awaited_once_with(
        chat_id=12345,
        text="You said: !@#$%^&*()"
    )

@pytest.mark.asyncio
async def test_echo_special_characters(mock_bot, mock_update):
    """Test echoing message with special characters"""
    mock_update.message.text = "!@#$%^&*()"
    await echo(mock_update, mock_bot)
    mock_bot.send_message.assert_awaited_once_with(
        chat_id=12345,
        text="You said: !@#$%^&*()"
    )

@pytest.mark.asyncio
async def test_echo_emoji(mock_bot, mock_update):
    """Test echoing message with emoji"""
    mock_update.message.text = "😊 Hello!"
    await echo(mock_update, mock_bot)
    mock_bot.send_message.assert_awaited_once_with(
        chat_id=12345,
        text="You said: 😊 Hello!"
    )
