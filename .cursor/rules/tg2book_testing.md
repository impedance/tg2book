---
description: Testing practices and requirements for the Telegram to EPUB bot
globs: ["test_*.py"]
alwaysApply: true
---

# Testing Rules for TG2Book

## Testing Framework

This project uses pytest as the primary testing framework with these key components:

- **pytest-asyncio**: For testing asynchronous functions
- **unittest.mock**: For creating mock objects and patching functions

## Test File Structure

Test files should follow these naming conventions:
- Test files should be named `test_*.py`
- Test classes should be named `Test*`
- Test functions should be named `test_*`

## Mock Fixtures

When testing the Telegram bot, use these standard fixtures:

```python
@pytest.fixture
def converter():
    """Create a TelegramToEpub instance for testing."""
    return TelegramToEpub()

@pytest.fixture
def mock_update():
    """Create a mock Update object."""
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = MagicMock()
    update.message.reply_document = MagicMock()
    return update

@pytest.fixture
def mock_context():
    """Create a mock Context object."""
    return MagicMock()
```

## Testing Message Types

For testing different message scenarios, create specialized fixtures:

```python
@pytest.fixture
def mock_forward_from_user(mock_update):
    """Create a mock Update with forwarded message from user."""
    mock_update.message.forward_origin = MagicMock()
    mock_update.message.forward_origin.type = "user"
    # Configure other properties
    return mock_update

@pytest.fixture
def mock_forward_from_chat(mock_update):
    """Create a mock Update with forwarded message from chat."""
    mock_update.message.forward_origin = MagicMock()
    mock_update.message.forward_origin.type = "chat"
    # Configure other properties
    return mock_update
```

## Testing Async Functions

When testing async functions, use the pytest.mark.asyncio decorator:

```python
@pytest.mark.asyncio
async def test_async_function():
    # Test code here
    pass
```

## Mocking External Dependencies

When testing functions that use external libraries:

```python
# Mocking specific functions
with patch('ebooklib.epub.write_epub') as mock_write_epub:
    # Test code that calls write_epub
    mock_write_epub.assert_called_once()

# Mocking file operations
with patch('builtins.open', MagicMock(return_value=MagicMock())):
    # Test code that opens files
```

## Testing Error Handling

For testing error scenarios:

```python
@pytest.mark.asyncio
async def test_error_handling(converter, mock_update):
    with patch.object(converter, 'some_method', side_effect=Exception("Test error")):
        with patch('logging.Logger.error'):  # Optional: don't log during tests
            # Call the function that should handle errors
            # Assert the error was handled properly
```

## Test Coverage

Aim for 90%+ test coverage of the codebase with special attention to:
1. Command handlers
2. Message processing logic
3. EPUB creation
4. Error handling 