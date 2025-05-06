---
description: Key patterns and conventions for the Telegram to EPUB bot project
globs: ["*.py"]
alwaysApply: true
---

# TG2Book Patterns and Conventions

## Project Structure

This project is a Telegram bot that converts forwarded messages to EPUB format. The main components are:

- `bot.py`: Main bot implementation with the TelegramToEpub class
- `test_bot.py`: Unit tests using pytest and mocking

## Class Structure

The primary class is `TelegramToEpub` which contains:

- Bot command handlers (start, help)
- Message handling logic
- EPUB creation functionality

## Code Patterns

### Message Handling

When working with messages, always check for the `forward_origin` property to determine if a message is forwarded:

```python
if not message.forward_origin:
    # Handle non-forwarded message
    return

# Handle forwarded message
if message.forward_origin.type == "user":
    # Handle user forwarded message
elif message.forward_origin.type == "chat":
    # Handle chat forwarded message
elif message.forward_origin.type == "hidden_user":
    # Handle hidden user forwarded message
```

### EPUB Creation

The EPUB creation follows this pattern:

```python
book = epub.EpubBook()
book.set_title(title)
book.set_language('ru')

# Add content
c1 = epub.EpubHtml(title='Content', file_name='content.xhtml', lang='ru')
c1.content = f'<html><body>{content}</body></html>'
book.add_item(c1)

# Add navigation
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())

# Create spine
book.spine = ['nav', c1]

# Save the EPUB file
epub_path = os.path.join(self.temp_dir, f'{clean_title}.epub')
epub.write_epub(epub_path, book)
```

### Error Handling

Error handling should follow this pattern:

```python
try:
    # Operation that might fail
except Exception as e:
    logger.error(f"Error message: {e}")
    await message.reply_text("User-friendly error message")
```

## Testing Patterns

Tests should use pytest fixtures for mocking:

```python
@pytest.fixture
def mock_object():
    """Create a mock object."""
    obj = MagicMock()
    # Configure the mock
    return obj

@pytest.mark.asyncio
async def test_something(converter, mock_object):
    """Test a specific functionality."""
    # Arrange
    # Act
    # Assert
```

For testing async functions, use the `@pytest.mark.asyncio` decorator.

When mocking external libraries, prefer to mock at the method level rather than the module level:

```python
with patch('ebooklib.epub.write_epub') as mock_write_epub:
    # Test code that calls write_epub
```

## Common Patterns

1. Use temporary directories for file operations during testing
2. Clean up resources in `__del__` methods
3. Follow the command pattern for Telegram bot handlers
4. Use clear error messages for users 