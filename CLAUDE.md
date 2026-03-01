# tg2book

## Overview
- Telegram bot that converts Telegram posts into EPUB and syncs them to Dropbox.
- Runtime architecture: one `asyncio` event loop with two Pyrogram clients — Bot API bot + MTProto userbot.

## Main Files
- `bot.py` — main entrypoint, queue orchestration, admin commands, Pyrogram handlers.
- `services/epub_service.py` — async coordinator for EPUB generation and Dropbox upload.
- `epub_functions.py` — zero-dependency EPUB 3 generator using `zipfile` and SVG cover rendering.
- `dropbox_module.py` — direct Dropbox HTTP client.
- `userbot_db.py` — `aiosqlite` storage for monitored channels with WAL enabled.
- `utils/text_utils.py` — title extraction, filename sanitization, text formatting helpers.
- `docs/architecture.md` — canonical architecture reference.
- `docs/testing.md` — testing patterns and guardrails.

## Agent Invariants
- Use Pyrogram only; do not reintroduce `python-telegram-bot` or parallel Telegram frameworks.
- Offload blocking file/network work with `asyncio.to_thread()`.
- Keep core EPUB logic zero-dependency; do not add `ebooklib`, `lxml`, or `Pillow`.
- Preserve SQLite WAL behavior in `userbot_db.py`.

## Verification
- Fast loop: `make smoke`
- Full verification: `make preflight`

## Canonical Docs
- Repo operating manual: `AGENTS.md`
- Architecture details: `docs/architecture.md`
- Testing guidance: `docs/testing.md`
