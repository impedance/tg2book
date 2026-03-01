# AGENTS.md

## Overview
tg2book is a Telegram bot that converts Telegram posts into EPUB format and automatically synchronizes them to a connected Dropbox account for e-readers. It uses a dual Pyrogram client (Bot API + Userbot MTProto) in a single event loop.

## Quickstart
1. **Setup**: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
2. **Config**: Setup `.env` with `TELEGRAM_BOT_TOKEN`, Dropbox secrets, `API_ID` / `API_HASH`. Generate userbot session locally via `pip install "qrcode[pil]" && python3 login_qr.py`.
3. **Run**: `docker compose up -d --build` (or `make build` / `make run`). Local run: `./start.sh` or `python3 bot.py`.
4. **Verify**: Send a post link or direct text to the bot in Telegram. Ensure an EPUB is returned and synced to Dropbox.

## Agent Workflow
1. **Clarify**: Confirm goal and constraints before touching the code. Check docs.
2. **Plan**: Propose a plan. Group components logically and identify missing tests.
3. **Implement**: Edit code, maintaining the zero-dependency philosophy (no `ebooklib`, `Pillow`, `lxml`).
4. **Verify**: Run `make format`, `make lint`, `make typecheck`, and `make test`.
5. **Summarize**: Present PR-ready output with evidence of passing tests and exact files changed.

## Commands
Run these inside the project root:
- **Lint**: `make lint` (ruff check)
- **Format**: `make format` (ruff check --fix && ruff format)
- **Typecheck**: `make typecheck` (mypy)
- **Test**: `make test` (pytest inside container)
- **Run**: `make run` (restarts docker container) / `make build` (rebuilds container)
- **Smoke test**: *TODO: Create `make smoke` or dedicated smoke test script.*

## Repo Map
- `bot.py`: Main entrypoint; initializes Pyrogram Bot and Userbot in a single event loop.
- `services/`: Business logic. `epub_service.py` coordinates EPUB generation and Dropbox uploads.
- `epub_functions.py`: Zero-dependency EPUB 3 generator (uses `zipfile` and `xml.sax.saxutils`).
- `dropbox_module.py`: Lightweight HTTP client for Dropbox API v2.
- `userbot_db.py`: Local `aiosqlite` database for tracking Userbot channels.
- `docs/`: Deeper documentation.
- `tests/`: Pytest suite (`test_bot.py`, `test_integration.py`, etc.).
- `Makefile` & `docker-compose.yml`: Local build/test orchestration.

## Rules & Invariants
- **Zero-Dependency Philosophy**: Do NOT introduce heavy libraries like `ebooklib`, `lxml`, or `Pillow` for core logic.
- **Async I/O Isolation**: All blocking/synchronous functions (file I/O, Dropbox requests) MUST be offloaded using `asyncio.to_thread()`.
- **Database Rules**: Use `aiosqlite` with `PRAGMA journal_mode=WAL;` to prevent lock exceptions.
- **Userbot Session**: NEVER commit `USERBOT_SESSION_STRING` or `.env` files to version control.
- **Framework Limits**: Use Pyrogram strictly for both clients (userbot and bot). Do NOT add `python-telegram-bot` or other overlapping frameworks.
- **Testing**: Tests must use `pytest` async fixtures. Ensure test isolation by mocking Telegram and Dropbox calls.

## Docs Graph
- [Architecture](docs/architecture.md): Deep-dive into technical decisions, dual-client setup, and async orchestration.
- [Tasks](docs/tasks/): Directory containing historical/active task logs.
- *TODO: Create `docs/index.md` as the main documentation hub.*
- *TODO: Create `docs/deployment.md` for production setup guidelines.*
- *TODO: Create `docs/testing.md` for detailed test mock patterns.*

## Troubleshooting
- **Symptom**: `Peer id invalid` on Userbot.
  - **Check**: Pyrogram session lacks local peer info.
  - **Command**: Trigger or wait for `_dialogs_sync_worker` to refresh dialogs.
- **Symptom**: `database is locked` error.
  - **Check**: Ensure `PRAGMA journal_mode=WAL;` is set and `userbot_db.py` uses asynchronous executing.
- **Symptom**: Missing module errors during tests.
  - **Check**: Test-only packages might be missing.
  - **Command**: `pip install -r requirements-test.txt` or rebuild container.
- **Symptom**: Userbot cannot login/start.
  - **Check**: Session string is expired or missing.
  - **Command**: Run `python3 login_qr.py` locally and update `.env`.
