# Testing Guide

## Goals
- Keep tests offline, deterministic, and fast enough for agent iteration.
- Prefer narrow unit tests around pure helpers and EPUB archive invariants.
- Use integration-style tests only when they still avoid real Telegram and Dropbox traffic.

## Default Commands
- `make smoke` — quick regression loop (`ruff` + focused architecture/EPUB tests) in the dev container.
- `make test` — full automated pytest suite in the dev container.
- `make preflight` — formatting, lint, typing, and full tests before handoff.

## Project Testing Rules
- Never perform real network I/O in tests; mock Telegram, Pyrogram, and Dropbox surfaces.
- Preserve the async boundary: blocking file or Dropbox work should be verified through `asyncio.to_thread()`.
- Prefer `tmp_path` for filesystem and SQLite tests.
- Keep EPUB checks at the ZIP level instead of adding heavy parsing dependencies.

## Common Patterns
- **Pyrogram / Telegram mocks**: Stub modules before importing `bot.py`, then patch only the specific methods used by the test.
- **Async flows**: Use `pytest.mark.asyncio`, `AsyncMock`, and queue-based assertions instead of long sleeps.
- **SQLite / WAL**: Point `userbot_db.DB_PATH` at a `tmp_path` database, call `init_db()`, then assert `PRAGMA journal_mode` or concurrent access behavior.
- **EPUB golden tests**: Use plain text fixtures from `tests/fixtures/`, generate an `.epub`, then inspect it with `zipfile.ZipFile`.

## Manual Diagnostics
- `tests/manual/` contains credentialed scripts for userbot troubleshooting.
- These scripts are intentionally outside the automated pytest collection path.

## Pitfalls
- Do not call Dropbox APIs directly from tests.
- Do not rely on real Telegram sessions or channel history in automated checks.
- Avoid long `asyncio.sleep()` delays; use tiny waits or mocked coroutines instead.
