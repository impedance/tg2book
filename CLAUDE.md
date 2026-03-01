# Telegram to EPUB Converter Bot

## Project Overview
A Telegram bot that converts Telegram posts into EPUB format for e-readers. The bot processes Telegram post links and returns downloadable EPUB files with embedded media.

## Key Features
- Converts Telegram posts to EPUB format
- Supports forwarded messages with preserved structure
- Embeds media (images, videos) directly within the EPUB
- Maintains clean, readable formatting for text content
- Properly handles hyperlinks and embedded media
- Automatic Dropbox upload for file storage

## Architecture

### Main Files
- `bot.py` - Main bot implementation using python-telegram-bot
- `dropbox_module.py` - Dropbox integration for file uploads
- `dropbox-loader.py` - Dropbox file upload utility
- `start.sh` - Bot startup script with logging
- `exchange_code.py` - OAuth helper for Dropbox refresh token

### Environment Variables (.env)
```
TELEGRAM_BOT_TOKEN - Bot token from @BotFather
DROPBOX_APP_KEY - Dropbox app key
DROPBOX_APP_SECRET - Dropbox app secret  
DROPBOX_REFRESH_TOKEN - Dropbox refresh token for API access
```

## Technology Stack
- **pyrogram** - Telegram bot and userbot framework (MTProto)
- **epub_functions.py** - Custom zero-dependency EPUB 3 generator
- **requests** - HTTP requests for Dropbox API
- **Dropbox API** - File storage integration

## Running the Project

### Quick Start
```bash
./start.sh
```

### Manual Start
```bash
python3 bot.py
```

### Setup Requirements
1. Get Telegram bot token from @BotFather
2. Create Dropbox app at https://www.dropbox.com/developers/apps
3. Get Dropbox refresh token using `exchange_code.py`
4. Configure all tokens in `.env` file

## Common Issues & Solutions

### Invalid Telegram Token
- Get new token from @BotFather
- Update TELEGRAM_BOT_TOKEN in .env

### Dropbox Auth Failure
- Refresh token expired
- Use exchange_code.py to get new refresh token:
  ```bash
  # 1. Open auth URL in browser
  # 2. Get authorization code
  # 3. Run script
  python3 exchange_code.py YOUR_AUTH_CODE
  ```

### File Upload Issues  
- Check Dropbox permissions
- Verify file paths in dropbox_module.py
- Default upload path: `/Apps/Dropbox PocketBook/from-bot/`

## Development Notes
- Bot logs to both console and `bot.log` file
- Uses temporary files for EPUB generation
- Automatically cleans up temp files after upload
- Supports offline token refresh for Dropbox API