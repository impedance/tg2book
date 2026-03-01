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
- Dropbox App credentials (for file storage)
- Telegram API credentials (`API_ID` / `API_HASH`) from [my.telegram.org](https://my.telegram.org) (for userbot)
- Required Python packages (see `requirements.txt`)

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

3. Set up environment variables in `.env` file:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
DROPBOX_APP_KEY=your_dropbox_app_key
DROPBOX_APP_SECRET=your_dropbox_app_secret
DROPBOX_REFRESH_TOKEN=your_dropbox_refresh_token
API_ID=your_api_id
API_HASH=your_api_hash
```

### Авторизация юзербота (QR-код)

Бот использует юзербот для чтения каналов. Для получения строки сессии:

1. Установите временную зависимость (только один раз, локально):
```bash
pip install "qrcode[pil]"
```

2. Запустите скрипт авторизации:
```bash
python3 login_qr.py
```

3. Отсканируйте QR-код в Telegram: **Настройки → Устройства → Войти** (или нажмите на ссылку `tg://login?token=...` в консоли, или откройте файл `login_qr.png`).

4. Скопируйте выведенную строку сессии в `.env`:
```bash
USERBOT_SESSION_STRING=<вставьте строку>
```

> ⚠️ **Никогда не коммитьте `USERBOT_SESSION_STRING` в git!**  
> `qrcode[pil]` **не** входит в основной `requirements.txt` — он нужен только для одноразовой генерации сессии.

### Getting Dropbox Credentials

1. Go to https://www.dropbox.com/developers/apps
2. Create a new app or use existing one
3. Copy App Key and App Secret to `.env` file
4. To get refresh token:
   - Open: `https://www.dropbox.com/oauth2/authorize?client_id=YOUR_APP_KEY&response_type=code&token_access_type=offline`
   - Authorize the app and copy the authorization code from redirect URL
   - Run: `python3 exchange_code.py YOUR_AUTHORIZATION_CODE`
   - The script will automatically update `.env` with the refresh token

## Usage
For local development with Docker:
- `make build`: Build and start the development container with the repository bind-mounted into `/app`
- `make run`: Restart the development container after code changes without rebuilding the image
- `make smoke`: Fast local regression pass for agents and small edits
- `make preflight`: Full verification before handoff or merge
- `make test`: Run tests inside container
- `make logs`: View logs
- `make prod-up`: Build and start the lean production container without dev dependencies

1. Start the bot:
```bash
./start.sh
```
or
```bash
python3 bot.py
```

2. In Telegram:
   - Send a link to a Telegram post to the bot
   - The bot will process the post and return an EPUB file

## Development

The project uses the following technologies:
- Pyrogram for Telegram bot and userbot implementation
- Custom zero-dependency EPUB generator (`epub_functions.py`)
- requests for Dropbox content uploading

Tests live under `tests/`, while credentialed/manual diagnostics are kept in `tests/manual/`.

Docker is split into two modes:
- `docker-compose.dev.yml` for development: dev tools installed, source code bind-mounted, no rebuild needed for ordinary code edits.
- `docker-compose.prod.yml` for production: runtime dependencies only, no bundled test suite or dev tooling.

## License

MIT License 
