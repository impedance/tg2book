---
description: Development practices and planned enhancements for the Telegram to EPUB bot
globs: ["*.py", "*.md"]
alwaysApply: true
---

# Development Rules for TG2Book

## Development Workflow

1. **Feature Development**: Focus on implementing core features and functionality
2. **Code Quality**: Maintain clean, readable, and well-documented code
3. **Memory Bank Updates**: Update documentation in memory-bank after significant changes

## Code Style

### Imports

```python
# Standard library imports
import os
import logging
import tempfile
import shutil
from datetime import datetime

# Third-party imports
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from ebooklib import epub

# Project imports (if applicable)
# from utils import helpers
```

### Class and Function Documentation

```python
class ClassName:
    """Class description."""
    
    def method_name(self, param1, param2):
        """
        Method description.
        
        Args:
            param1: Description of param1
            param2: Description of param2
            
        Returns:
            Description of return value
        """
        # Method implementation
```

### Error Handling

```python
try:
    # Operation that might fail
except SpecificException as e:
    logger.error(f"Specific error: {e}")
    await update.message.reply_text("User-friendly error message")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    await update.message.reply_text("Generic error message")
```

## Planned Enhancements

### Short-term
- Fix issue with EPUB file sending
- Improve error handling with more specific messages
- Add support for more message types

### Medium-term
- Add support for images and media
- Implement book metadata customization
- Add table of contents generation

### Long-term
- Support for multi-message conversations
- UI for customizing EPUB generation
- Convert messages from channels

## Refactoring Priorities

1. Improve error handling in `handle_message` method
2. Split large methods into smaller, more focused functions
3. Extract EPUB generation into a separate class
4. Improve logging with more detailed information

## Dependencies

- python-telegram-bot: For Telegram integration
- ebooklib: For EPUB file generation

Remember to maintain the requirements.txt file when adding new dependencies. 