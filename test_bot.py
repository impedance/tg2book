import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
import sys

# Mock external dependencies BEFORE importing bot
class MockModule:
    pass

# Mock telegram
telegram_mock = MockModule()
telegram_mock.Update = MagicMock

telegram_ext_mock = MockModule() 
telegram_ext_mock.Application = MagicMock
telegram_ext_mock.CommandHandler = MagicMock
telegram_ext_mock.MessageHandler = MagicMock
telegram_ext_mock.ContextTypes = MagicMock
telegram_ext_mock.ContextTypes.DEFAULT_TYPE = MagicMock

# Mock filters with ALL attribute
filters_mock = MagicMock()
filters_mock.ALL = MagicMock()
telegram_ext_mock.filters = filters_mock

sys.modules['telegram'] = telegram_mock
sys.modules['telegram.ext'] = telegram_ext_mock

# Mock ebooklib
mock_epub = MockModule()
mock_epub.EpubBook = MagicMock
mock_epub.EpubHtml = MagicMock
mock_epub.EpubNcx = MagicMock
mock_epub.EpubNav = MagicMock
mock_epub.write_epub = MagicMock()

ebooklib_mock = MockModule()
ebooklib_mock.epub = mock_epub
sys.modules['ebooklib'] = ebooklib_mock

# Mock dropbox
sys.modules['dropbox'] = MockModule()

# Now import bot module
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
        update.message.reply_text = AsyncMock()
        update.message.reply_document = AsyncMock()
        update.message.delete = AsyncMock()
        update.message.chat = MagicMock()
        update.message.chat.id = 12345
        update.message.text = None
        update.message.caption = None
        update.message.date = datetime.now()
        return update

    @pytest.fixture
    def mock_context(self):
        """Create a mock Context object."""
        return MagicMock()
    
    @pytest.fixture
    def mock_forwarded_message(self, mock_update):
        """Create a mock forwarded message."""
        mock_update.message.forward_origin = MagicMock()
        mock_update.message.forward_origin.type = "user"
        mock_update.message.forward_origin.sender_user = MagicMock()
        mock_update.message.forward_origin.sender_user.full_name = "Test User"
        mock_update.message.text = "Test message content"
        return mock_update

    # Test message text extraction
    def test_get_message_text(self, converter):
        """Test getting text from message."""
        message = MagicMock()
        
        # Test with text
        message.text = "Test text"
        message.caption = None
        assert converter.get_message_text(message) == "Test text"
        
        # Test with caption
        message.text = None
        message.caption = "Test caption"
        assert converter.get_message_text(message) == "Test caption"
        
        # Test with both
        message.text = "Test text"
        message.caption = "Test caption"
        assert converter.get_message_text(message) == "Test text"
        
        # Test with neither
        message.text = None
        message.caption = None
        assert converter.get_message_text(message) == ""

    # Test text formatting
    def test_format_message(self, converter):
        """Test message formatting."""
        text = "This is a test\nwith newlines\n\nAnd paragraphs\nAnd file.md reference"
        formatted = converter.format_message(text)
        
        assert '<p>' in formatted
        assert '<br>' in formatted
        assert '<u>file.md</u>' in formatted

    # Test EPUB creation
    @patch('bot.os.makedirs')
    @patch('bot.threading.Thread')
    def test_create_epub(self, mock_thread, mock_makedirs, converter):
        """Test EPUB file creation."""
        message = MagicMock()
        message.text = "Test message content"
        message.caption = None
        message.date = datetime.now()
        
        epub_path = converter.create_epub(message, "Test Sender")
        
        assert mock_epub.write_epub.called
        assert "docs" in epub_path
        assert epub_path.endswith('.epub')
        mock_thread.assert_called_once()

    # Test access token refresh
    @patch.dict(os.environ, {
        'DROPBOX_REFRESH_TOKEN': 'test_refresh_token',
        'DROPBOX_APP_KEY': 'test_app_key',
        'DROPBOX_APP_SECRET': 'test_app_secret'
    })
    @patch('bot.requests.post')
    def test_refresh_access_token(self, mock_post):
        """Test Dropbox access token refresh."""
        from bot import refresh_access_token
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "new_test_token"}
        mock_post.return_value = mock_response
        
        token = refresh_access_token()
        
        assert token == "new_test_token"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "oauth2/token" in args[0]
        assert kwargs['data']['grant_type'] == 'refresh_token'

    # Test message handling - no text
    @pytest.mark.asyncio
    async def test_handle_message_no_text(self, converter, mock_update, mock_context):
        """Test handling message without text."""
        mock_update.message.forward_origin = None
        mock_update.message.text = None
        mock_update.message.caption = None
        
        await converter.handle_message(mock_update, mock_context)
        
        # Should reply with error message
        mock_update.message.reply_text.assert_called()
        args = mock_update.message.reply_text.call_args[0]
        assert "не содержит текста" in args[0]

    # Test message handling - forwarded with no text
    @pytest.mark.asyncio
    async def test_handle_forwarded_message_no_text(self, converter, mock_update, mock_context):
        """Test handling forwarded message without text."""
        mock_update.message.forward_origin = MagicMock()
        mock_update.message.forward_origin.type = "user"
        mock_update.message.text = None
        mock_update.message.caption = None
        
        await converter.handle_message(mock_update, mock_context)
        
        # Should reply with error message
        mock_update.message.reply_text.assert_called()
        args = mock_update.message.reply_text.call_args[0]
        assert "не содержит текста" in args[0]

    # Test message handling - successful processing
    @pytest.mark.asyncio
    async def test_handle_forwarded_message_success(self, converter, mock_forwarded_message, mock_context):
        """Test successful handling of forwarded message."""
        with patch.object(converter, 'create_epub', return_value='/tmp/test.epub') as mock_create:
            with patch('builtins.open', MagicMock()):
                with patch('os.path.exists', return_value=True):
                    await converter.handle_message(mock_forwarded_message, mock_context)
                    
                    # Should create EPUB and send document
                    mock_create.assert_called_once()
                    mock_forwarded_message.message.reply_document.assert_called_once()

    # Test message handling - with caption instead of text
    @pytest.mark.asyncio
    async def test_handle_message_with_caption(self, converter, mock_update, mock_context):
        """Test handling message with caption instead of text."""
        mock_update.message.forward_origin = MagicMock()
        mock_update.message.forward_origin.type = "user"
        mock_update.message.forward_origin.sender_user = MagicMock()
        mock_update.message.forward_origin.sender_user.full_name = "Test User"
        mock_update.message.text = None
        mock_update.message.caption = "Test caption content"
        
        with patch.object(converter, 'create_epub', return_value='/tmp/test.epub'):
            with patch('builtins.open', MagicMock()):
                with patch('os.path.exists', return_value=True):
                    await converter.handle_message(mock_update, mock_context)
                    
                    mock_update.message.reply_document.assert_called_once()

    # Test message handling - exception
    @pytest.mark.asyncio
    async def test_handle_message_exception(self, converter, mock_forwarded_message, mock_context):
        """Test handling exceptions during message processing."""
        with patch.object(converter, 'create_epub', side_effect=Exception("Test error")):
            await converter.handle_message(mock_forwarded_message, mock_context)
            
            # Should reply with error message
            assert mock_forwarded_message.message.reply_text.call_count >= 1
            # Find the error message call
            error_found = False
            for call in mock_forwarded_message.message.reply_text.call_args_list:
                if "Извините, произошла ошибка" in call[0][0]:
                    error_found = True
                    break
            assert error_found

    # Test Dropbox upload
    @patch('bot.subprocess.Popen')
    @patch('bot.refresh_access_token')
    def test_upload_to_dropbox(self, mock_refresh_token, mock_popen, converter):
        """Test Dropbox upload functionality."""
        mock_refresh_token.return_value = "test_token"
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"Success", b"")
        mock_popen.return_value = mock_process
        
        converter.upload_to_dropbox("/test/file.epub")
        
        mock_refresh_token.assert_called_once()
        mock_popen.assert_called_once()

    # Test different forwarded message types
    @pytest.mark.asyncio
    async def test_handle_forwarded_from_channel(self, converter, mock_update, mock_context):
        """Test handling message forwarded from channel."""
        mock_update.message.forward_origin = MagicMock()
        mock_update.message.forward_origin.type = "channel"
        mock_update.message.forward_origin.sender_chat = MagicMock()
        mock_update.message.forward_origin.sender_chat.title = "Test Channel"
        mock_update.message.text = "Test message"
        
        with patch.object(converter, 'create_epub', return_value='/tmp/test.epub'):
            with patch('builtins.open', MagicMock()):
                with patch('os.path.exists', return_value=True):
                    await converter.handle_message(mock_update, mock_context)
                    
                    mock_update.message.reply_document.assert_called_once()


# Integration test for main function
@patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'test_token'})
@patch('bot.Application')
def test_main_function(mock_application):
    """Test main function initialization."""
    from bot import main
    
    mock_app_instance = MagicMock()
    mock_application.builder.return_value.token.return_value.build.return_value = mock_app_instance
    
    main()
    
    # Should create application and add handlers
    mock_app_instance.add_handler.assert_called()
    mock_app_instance.run_polling.assert_called_once()


@patch.dict(os.environ, {}, clear=True)
def test_main_function_no_token():
    """Test main function without token."""
    from bot import main
    
    # Should return early without token
    result = main()
    assert result is None