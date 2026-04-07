import pytest
import os
import tempfile
import shutil
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

# Import project modules
import bot
import channel_registry

class TestIntegrationFlow:
    @pytest.fixture
    def temp_runtime(self):
        """Create a temporary runtime directory for tests."""
        tmp_dir = tempfile.mkdtemp()
        db_path = os.path.join(tmp_dir, "test_channels.db")
        old_db = os.environ.get("CHANNEL_REGISTRY_DB")
        os.environ["CHANNEL_REGISTRY_DB"] = db_path
        
        yield tmp_dir, db_path
        
        if old_db:
            os.environ["CHANNEL_REGISTRY_DB"] = old_db
        else:
            del os.environ["CHANNEL_REGISTRY_DB"]
        shutil.rmtree(tmp_dir)

    @pytest.fixture
    def converter(self, temp_runtime):
        """Create a TelegramToEpub instance for integration testing."""
        return bot.TelegramToEpub()

    @pytest.fixture
    def mock_update(self):
        """Standard mock for Telegram Update."""
        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock(return_value=AsyncMock(delete=AsyncMock()))
        update.message.reply_document = AsyncMock()
        update.message.delete = AsyncMock()
        update.message.chat.id = 12345
        update.message.from_user.id = 12345
        update.message.date = datetime.now()
        update.message.text = None
        update.message.caption = None
        update.message.document = None
        update.message.forward_origin = None
        update.message.entities = []
        update.message.caption_entities = []
        update.message.link = ""
        return update

    @pytest.fixture
    def mock_context(self):
        """Standard mock for Telegram Context."""
        context = MagicMock()
        context.bot.get_file = AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_scenario_1_bot_text_to_dropbox(self, converter, mock_update, mock_context):
        """
        Scenario 1: Full Flow - Bot Text Input
        Verify: Text -> EPUB -> Dropbox -> Summary
        """
        mock_update.message.text = "Test Title\n\nThis is the body of the message."
        
        # We want to verify that create_epub and upload_to_dropbox are called with expected data
        with patch('bot.create_epub', wraps=bot.create_epub) as mock_create_epub, \
             patch('bot.dropbox_module.upload_to_dropbox', return_value=True) as mock_upload:
            
            await converter.handle_message(mock_update, mock_context)
            
            # 1. Check if EPUB was created with correct metadata
            mock_create_epub.assert_called_once()
            args, _ = mock_create_epub.call_args
            assert args[0] == "Test Title"
            assert "This is the body of the message." in args[2]
            
            # 2. Check if Dropbox upload was initiated with sanitized filename
            mock_upload.assert_called_once()
            epub_path, dropbox_filename = mock_upload.call_args[0]
            assert dropbox_filename == "Test_Title.epub"
            assert epub_path.endswith(".epub")
            
            # 3. Check if summary was sent
            assert mock_update.message.reply_text.await_count >= 2
            summary_call = mock_update.message.reply_text.call_args_list[-1]
            assert "Test Title" in summary_call[0][0]
            assert "HTML" == summary_call[1].get("parse_mode")
            
            # 4. Check if source message was deleted (default behavior for bot messages)
            mock_update.message.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_scenario_2_bot_forwarded_to_dropbox(self, converter, mock_update, mock_context):
        """
        Scenario 2: Full Flow - Forwarded Message
        Verify: Metadata extraction and summary link
        """
        mock_update.message.text = "Forwarded content body."
        # Mock forward origin from a user
        mock_update.message.forward_origin = MagicMock()
        mock_update.message.forward_origin.type = "user"
        mock_update.message.forward_origin.sender_user.full_name = "Jane Doe"
        mock_update.message.forward_origin.sender_user.username = "janedoe"
        
        with patch('bot.create_epub', wraps=bot.create_epub) as mock_create_epub,              patch('bot.dropbox_module.upload_to_dropbox', return_value=True) as mock_upload:
            
            await converter.handle_message(mock_update, mock_context)
            
            # 1. Author should be extracted from sender name
            mock_create_epub.assert_called_once()
            args, _ = mock_create_epub.call_args
            assert args[1] == "Jane Doe"
            
            # 2. Check if summary contains author name
            summary_call = mock_update.message.reply_text.call_args_list[-1]
            assert "Jane Doe" in summary_call[0][0]

    @pytest.mark.asyncio
    async def test_scenario_3_epub_pass_through(self, converter, mock_update, mock_context):
        """
        Scenario 3: Pass-through - EPUB File Upload
        Verify: No conversion, direct upload to Dropbox
        """
        # Mocking an EPUB document
        document = MagicMock()
        document.file_name = "Original_Book.epub"
        document.mime_type = "application/epub+zip"
        document.file_id = "file_id_123"
        mock_update.message.document = document
        
        # Mock file download
        file_mock = AsyncMock()
        file_mock.download_to_drive = AsyncMock()
        mock_context.bot.get_file = AsyncMock(return_value=file_mock)
        
        with patch('bot.create_epub') as mock_create_epub,              patch('bot.dropbox_module.upload_to_dropbox', return_value=True) as mock_upload,              patch('builtins.open', MagicMock()):
            
            await converter.handle_message(mock_update, mock_context)
            
            # 1. create_epub should NOT be called
            mock_create_epub.assert_not_called()
            
            # 2. get_file and download_to_drive from Telegram should be called
            mock_context.bot.get_file.assert_awaited_with("file_id_123")
            file_mock.download_to_drive.assert_awaited()
            
            # 3. upload_to_dropbox should be called with the original filename (sanitized)
            mock_upload.assert_called_once()
            _, dropbox_filename = mock_upload.call_args[0]
            assert "Original_Book" in dropbox_filename

    @pytest.mark.asyncio
    async def test_scenario_4_channel_registry_integration(self, converter, mock_update):
        """
        Scenario 4: Integration - Channel Registry
        Verify: /add_channel correctly updates DB and /list_channels reflects it
        """
        # Set Admin ID for this test
        os.environ["ADMIN_ID"] = "12345"
        
        context = MagicMock()
        context.args = ["@NewTestChannel"]
        
        await converter.add_channel(mock_update, context)
        
        # 1. Verify successful response
        mock_update.message.reply_text.assert_awaited()
        assert "Канал добавлен" in mock_update.message.reply_text.call_args[0][0]
        
        # 2. Verify listing works
        mock_update.message.reply_text.reset_mock()
        context.args = []
        await converter.list_channels(mock_update, context)
        
        summary_call = mock_update.message.reply_text.call_args[0][0]
        assert "newtestchannel" in summary_call

    @pytest.mark.asyncio
    async def test_scenario_5_userbot_ingestion_flow(self, converter, mock_update):
        """
        Scenario 5: Cross-Service - Userbot Post Ingestion
        Verify: Channel post triggers the full pipeline
        """
        # Register a channel first
        os.environ["ADMIN_ID"] = "12345"
        channel_registry.add_channel("@target_channel", os.environ["CHANNEL_REGISTRY_DB"])
        
        summary_target = MagicMock()
        summary_target.reply_text = AsyncMock(return_value=AsyncMock(delete=AsyncMock()))
        
        with patch('bot.create_epub', wraps=bot.create_epub) as mock_create_epub,              patch('bot.dropbox_module.upload_to_dropbox', return_value=True) as mock_upload:
            
            success = await converter.process_channel_post(
                text_content="New post from channel",
                source_name="Target Channel",
                source_identifier="@target_channel",
                summary_target=summary_target,
                post_link="https://t.me/target_channel/1"
            )
            
            # 1. Pipeline should succeed
            assert success is True
            
            # 2. create_epub and upload_to_dropbox should be called
            mock_create_epub.assert_called_once()
            mock_upload.assert_called_once()
            
            # 3. Summary should be sent to the target
            summary_target.reply_text.assert_awaited()
            summary_call = summary_target.reply_text.call_args_list[-1]
            assert "Target Channel" in summary_call[0][0]
