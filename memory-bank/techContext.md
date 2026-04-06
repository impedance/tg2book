# Tech Context

## Technologies Used

- Python 3.11 in Docker image
- `python-telegram-bot==20.7`
- `Telethon==1.36.0`
- `ebooklib==0.17.1`
- `dropbox==11.36.2`
- `requests==2.31.0`
- `beautifulsoup4==4.12.2`
- `lxml==4.9.3`
- `Pillow==10.1.0`
- SQLite via stdlib `sqlite3`
- Docker / Docker Compose

## Runtime Entry Points

- `bot.py` — polling bot for user chat interactions.
- `userbot_listener.py` — Telethon listener for channel ingestion.
- `start.sh` — локальный запуск bot с `.venv` и `.env`.
- `start_userbot.sh` — локальный запуск userbot с `.venv` и `.env`.

## Runtime State

- `runtime/channels.db` — SQLite registry of monitored channels in Docker runtime.
- `runtime/tg2book_userbot.session` — Telethon session file in Docker runtime.
- `bot.log`, `userbot.log` — локальные лог-файлы при shell-старте.

## Required Environment Variables

For main bot:

- `TELEGRAM_BOT_TOKEN`
- `DROPBOX_APP_KEY`
- `DROPBOX_APP_SECRET`
- `DROPBOX_REFRESH_TOKEN`

For admin/userbot flow:

- `ADMIN_ID`
- `API_ID`
- `API_HASH`

Optional:

- `USERBOT_SESSION`
- `CHANNEL_REGISTRY_DB`

## Technical Constraints

- Telegram Bot API and Telethon session handling require valid credentials and network access.
- Dropbox upload depends on refresh-token flow and external API availability.
- Userbot currently ignores channel posts without text.
- Docker runtime persists `channels.db` and `*.session` through bind mount `./runtime:/app/runtime`.

## Testing Setup

- `pytest`
- `pytest-asyncio`
- `pytest-cov`

Key test files:

- `test_bot.py`
- `tests/test_channel_registry.py`
- `tests/test_userbot_listener.py`
- `tests/test_dropbox_pipeline_baseline.py`
