# Telegram to EPUB Converter

A Telegram bot that converts Telegram posts into EPUB format for e-readers.

## Features

- Converts Telegram posts to EPUB format
- Supports forwarded messages with preserved structure
- Embeds media (images, videos) directly within the EPUB
- Maintains clean, readable formatting for text content
- Properly handles hyperlinks and embedded media

## Prerequisites

- Python 3.x
- Telegram Bot API token (obtain from @BotFather)
- Required Python packages (see requirements.txt)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/tg2book.git
cd tg2book
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
```

## Usage

1. Start the bot:
```bash
python bot.py
```

2. In Telegram:
   - Send a link to a Telegram post to the bot
   - The bot will process the post and return an EPUB file

## Development

The project uses the following technologies:
- python-telegram-bot for Telegram bot implementation
- ebooklib for EPUB generation
- beautifulsoup4 for HTML parsing
- requests for content downloading

## License

MIT License 