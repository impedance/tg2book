# Tech Context

## Technologies Used

*   Python 3.x
*   python-telegram-bot 20.7
*   ebooklib 0.17.1
*   tempfile (for temporary directory management)
*   shutil (for file operations)

## Development Setup

1.  Install Python 3.x.
2.  Install the required libraries: `pip install -r requirements.txt`
3.  Create a Telegram bot and obtain its API token.
4.  Set the API token as an environment variable: `export TELEGRAM_BOT_TOKEN="your_token_here"`
5.  Run the bot: `python bot.py`

## Technical Constraints

*   Telegram API rate limits.
*   EPUB format limitations.
*   Handling different types of forwarded messages.
*   Proper cleanup of temporary files.

## Dependencies

*   python-telegram-bot==20.7
*   ebooklib==0.17.1
*   requests==2.31.0
*   beautifulsoup4==4.12.2
*   lxml==4.9.3
*   Pillow==10.1.0

## Testing Dependencies

*   pytest
*   pytest-asyncio
*   pytest-cov

## Tool Usage Patterns

*   VS Code for development.
*   Git for version control.
*   Telegram for testing the bot.
*   pytest for running tests.
