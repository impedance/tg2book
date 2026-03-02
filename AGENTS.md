# AGENTS.md

## 1) What this repo is
tg2book is a Telegram bot that turns Telegram text/posts into an EPUB and syncs it to Dropbox for e-readers. It runs a dual Pyrogram client (Bot API + Userbot MTProto) in one event loop.

System-of-record map: `docs/index.md`.

## 2) Fast commands (run these first)
- Smoke: `make smoke`
- Agent smoke: `make agent-smoke`
- Preflight: `make preflight`

Notes:
- Default is containerized (`USE_DOCKER=1`). Host-mode: add `USE_DOCKER=0`.
- CI/debug output goes to `artifacts/` (pytest JUnit XML).

## 3) Non-negotiable invariants (enforced by checks)
- Offline-by-default: tests must not use real network. Opt-in only via `INTEGRATION=1`.
- Zero-dependency EPUB core: do not add heavy libs like `ebooklib`, `lxml`, `Pillow`.
- Async I/O isolation: blocking work (files/Dropbox) must be behind `asyncio.to_thread()`.
- SQLite: keep `aiosqlite` and WAL mode to avoid `database is locked`.
- Secrets: never commit `.env` or session strings (`USERBOT_SESSION_STRING`).
- Framework: use Pyrogram (no parallel Telegram frameworks).

## 4) Repo map (code)
- Entrypoints: `bot.py`, `start.sh`, `login_userbot.py`, `login_qr.py`
- Core domain logic (pure-ish): `epub_functions.py`, `utils/text_utils.py`, `src/qr_utils.py`
- Boundaries / config: `config.py` (`Settings`)
- Adapters (I/O): `dropbox_module.py` (HTTP), `userbot_db.py` (SQLite), `services/epub_service.py` (orchestration)
- Docs: `docs/` (see `docs/index.md`)
- Tests: `tests/` (offline), `tests/manual/` (credentialed/manual)

## 5) Typing
- Typecheck: `make typecheck` (or `make preflight`).
- Fix typecheck failures at the boundary first, then update call sites (avoid papering over with `Any`).

Typing surfaces (keep stable):
- Config boundary: `config.py` → `Settings`
- Dropbox boundary: `dropbox_module.py` → request/headers/payload helpers
- Service boundary: `services/epub_service.py` → `process_text_to_epub()`, `process_file_to_dropbox()`

## 6) How to finish a task
1) Make the change.
2) Run `make smoke` until green.
3) Run `make preflight` until green.
4) If you changed harness wiring, update `docs/harness_plan.md`.

## 7) Self-debug playbook
- Fix order: `make smoke` → failures in order structural → format/lint → typecheck → tests.
- If CI fails but local passes: inspect `artifacts/` from the workflow run.

## 8) Common pitfalls
- Accidentally making real network calls in tests (must be mocked; use `INTEGRATION=1` only for explicit opt-in).
- Doing blocking file/Dropbox work on the event loop (must be `asyncio.to_thread()`).
- Adding EPUB parsing/rendering dependencies instead of ZIP-level checks.
