# System Patterns

## System Architecture

The system consists of the following components:

*   **Telegram Bot:** Listens for forwarded messages from users.
*   **Message Processor:** Extracts content and metadata from forwarded Telegram messages.
*   **Content Formatter:**  
  - Formats raw Telegram message data into EPUB-compatible content.
  - Handles text formatting, links, and basic structure.
  - Generates appropriate HTML content for the EPUB file.
*   **EPUB Generator:** Generates the EPUB file from the formatted content.
*   **File Storage:** Temporarily stores the generated EPUB file.

## Key Technical Decisions

*   Using Python for its ease of use and extensive libraries.
*   Using `python-telegram-bot` for Telegram bot development.
*   Using `ebooklib` for EPUB generation.
*   Using temporary directories for file storage during processing.

## Design Patterns in Use

*   **Facade:** The TelegramToEpub class acts as a facade, hiding the complexity of the EPUB generation from the user.
*   **Command Pattern:** Each bot command handler is implemented as a separate method.

## Component Relationships

The TelegramToEpub class integrates all components: message processing, content formatting, EPUB generation, and file handling.

## Critical Implementation Paths

1.  User forwards a Telegram message to the bot.
2.  The bot extracts the sender information from the forwarded message.
3.  The bot formats the message content into HTML.
4.  The EPUB generator creates an EPUB file with the content.
5.  The file is temporarily stored and then sent back to the user.
6.  Temporary files are cleaned up.

## Testing Approach

The testing strategy for this project uses pytest with mocking:

```
test_bot.py
├── TestTelegramToEpub class
│   ├── Fixtures for mock objects
│   │   ├── converter (TelegramToEpub instance)
│   │   ├── mock_update (Telegram Update)
│   │   ├── mock_context (Telegram Context)
│   │   ├── mock_forward_from_user (Update with forwarded user message)
│   │   └── mock_forward_from_chat (Update with forwarded chat message)
│   │
│   ├── Command Tests
│   │   ├── test_start_command
│   │   └── test_help_command
│   │
│   └── Message Handling Tests
│       ├── test_create_epub
│       ├── test_handle_non_forwarded_message
│       ├── test_handle_forwarded_message_from_user
│       ├── test_handle_forwarded_message_from_chat
│       └── test_handle_message_exception
```

- **Mock Implementation**: External dependencies (ebooklib, telegram) are mocked to avoid requiring them during testing
- **Async Testing**: Using pytest.mark.asyncio for testing async functions
- **Test Coverage**: Tests cover all main functionality paths
- **Error Handling**: Tests explicitly verify error handling behavior
