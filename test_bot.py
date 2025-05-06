import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from datetime import datetime

# Mock modules we don't need to actually import
import sys
class MockModule:
    pass

mock_epub = MockModule()
mock_epub.EpubBook = MagicMock
mock_epub.EpubHtml = MagicMock
mock_epub.EpubNcx = MagicMock
mock_epub.EpubNav = MagicMock
mock_epub.write_epub = MagicMock()

sys.modules['ebooklib'] = MockModule()
sys.modules['ebooklib'].epub = mock_epub
sys.modules['telegram'] = MockModule()
sys.modules['telegram'].Update = MagicMock
sys.modules['telegram.ext'] = MockModule()
sys.modules['telegram.ext'].ContextTypes = MockModule()
sys.modules['telegram.ext'].ContextTypes.DEFAULT_TYPE = MagicMock

# Now import the bot module
from bot import TelegramToEpub

class TestTelegramToEpub:
    
    @pytest.fixture
    def converter(self):
        """Create a TelegramToEpub instance for testing."""
        return TelegramToEpub()
    
    @pytest.fixture
    def mock_update(self):
        """Create a mock Update object."""
        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = MagicMock()
        update.message.reply_document = MagicMock()
        return update
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock Context object."""
        return MagicMock()
    
    @pytest.fixture
    def mock_forward_from_user(self, mock_update):
        """Create a mock Update with forwarded message from user."""
        mock_update.message.forward_origin = MagicMock()
        mock_update.message.forward_origin.type = "user"
        mock_update.message.forward_origin.sender_user = MagicMock()
        mock_update.message.forward_origin.sender_user.full_name = "Test User"
        mock_update.message.forward_origin.sender_user.username = "testuser"
        mock_update.message.text = "Test message content"
        mock_update.message.text_html = "<p>Test message content</p>"
        mock_update.message.date = datetime.now()
        return mock_update
    
    @pytest.fixture
    def mock_forward_from_chat(self, mock_update):
        """Create a mock Update with forwarded message from chat."""
        mock_update.message.forward_origin = MagicMock()
        mock_update.message.forward_origin.type = "chat"
        mock_update.message.forward_origin.sender_chat = MagicMock()
        mock_update.message.forward_origin.sender_chat.title = "Test Chat"
        mock_update.message.text = "Test message content"
        mock_update.message.text_html = None
        mock_update.message.date = datetime.now()
        return mock_update
    
    @pytest.mark.asyncio
    async def test_start_command(self, converter, mock_update, mock_context):
        """Test the start command."""
        await converter.start(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()
        args, _ = mock_update.message.reply_text.call_args
        assert 'Привет!' in args[0]
    
    @pytest.mark.asyncio
    async def test_help_command(self, converter, mock_update, mock_context):
        """Test the help command."""
        await converter.help(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()
        args, _ = mock_update.message.reply_text.call_args
        assert 'Чтобы конвертировать сообщение в EPUB:' in args[0]
    
    def test_create_epub(self, converter):
        """Test the create_epub method."""
        # Setup a mock message
        message = MagicMock()
        message.date = datetime.now()
        message.text = "Test message content"
        message.text_html = "<p>Test message content</p>"
        
        # Test with a sender
        with patch('ebooklib.epub.write_epub') as mock_write_epub:
            epub_path = converter.create_epub(message, "Test Sender")
            assert mock_write_epub.called
            assert "Test Sender" in epub_path
            
        # Test without a sender
        with patch('ebooklib.epub.write_epub') as mock_write_epub:
            epub_path = converter.create_epub(message)
            assert mock_write_epub.called
            assert "Unknown" in epub_path
    
    @pytest.mark.asyncio
    async def test_handle_non_forwarded_message(self, converter, mock_update, mock_context):
        """Test handling a non-forwarded message."""
        mock_update.message.forward_origin = None
        
        await converter.handle_message(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        args, _ = mock_update.message.reply_text.call_args
        assert "Пожалуйста, перешлите мне сообщение" in args[0]
        mock_update.message.reply_document.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_forwarded_message_from_user(self, converter, mock_forward_from_user, mock_context):
        """Test handling a forwarded message from a user."""
        with patch.object(converter, 'create_epub', return_value='/tmp/test.epub'):
            with patch('builtins.open', MagicMock(return_value=MagicMock())):
                await converter.handle_message(mock_forward_from_user, mock_context)
                mock_forward_from_user.message.reply_document.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_forwarded_message_from_chat(self, converter, mock_forward_from_chat, mock_context):
        """Test handling a forwarded message from a chat."""
        with patch.object(converter, 'create_epub', return_value='/tmp/test.epub'):
            with patch('builtins.open', MagicMock(return_value=MagicMock())):
                await converter.handle_message(mock_forward_from_chat, mock_context)
                mock_forward_from_chat.message.reply_document.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_message_exception(self, converter, mock_forward_from_user, mock_context):
        """Test handling exceptions during message processing."""
        with patch.object(converter, 'create_epub', side_effect=Exception("Test error")):
            with patch('logging.Logger.error'):
                await converter.handle_message(mock_forward_from_user, mock_context)
                mock_forward_from_user.message.reply_text.assert_called_once()
                args, _ = mock_forward_from_user.message.reply_text.call_args
                assert "Извините, произошла ошибка" in args[0] 