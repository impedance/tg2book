# Documentation Hub

This is the “system of record” for both humans and coding agents. Keep this page short and link out to deeper docs.

## Start Here
- Architecture: `docs/architecture.md`
- Testing & offline rules: `docs/testing.md`
- Runbook (ops/debug): `docs/RUNBOOK.md`
- Deployment notes: `docs/DEPLOY.md`
- Harness engineering notes (project-specific): `docs/harness-engine-recommend.md`
- Task logs: `docs/tasks/`

## Fast commands
Use these commands for tight “change → verify → iterate” cycles.

- `make smoke` — fastest regression loop (ruff + focused tests).
- `make agent-smoke` — smoke + black-box integration tests (still offline).
- `make preflight` — format + lint + mypy + full test suite before handoff.

Notes:
- Default is containerized (`USE_DOCKER=1`). Host-mode (no Docker): add `USE_DOCKER=0`.
- Tests are offline-by-default: real network is blocked unless you opt-in with `INTEGRATION=1`.
- CI and local runs write debugging output to `artifacts/`.

## Code Map (read this first)
- **Core domain logic:** `epub_functions.py`, `utils/text_utils.py`, `src/qr_utils.py`
- **Boundaries / DTOs / config:** `config.py` (`Settings`)
- **Adapters (I/O):** `dropbox_module.py` (HTTP), `userbot_db.py` (SQLite), `services/epub_service.py` (orchestration)
- **Entrypoints:** `bot.py`, `start.sh`, `login_userbot.py`, `login_qr.py`

Rules of thumb:
- Domain logic must not call real network/DB directly; go through adapters.
- Blocking work must stay behind `asyncio.to_thread()` (enforced by guardrail tests).

## Typing Surfaces (must stay typed)
- Config loading: `config.py` → `Settings`
- Dropbox client boundary: `dropbox_module.py` → upload/auth helpers and request payload/headers
- Service boundary: `services/epub_service.py` → `process_text_to_epub()`, `process_file_to_dropbox()`

## Test Map (how to self-verify)
- **Smoke tests:** `make smoke`
  - Runs `tools/structural_check.sh`, `ruff check .`, then:
    - `tests/test_optimization.py`
    - `tests/test_epub_golden.py` (fixtures in `tests/fixtures/`)
    - `tests/test_epub_service_guardrails.py`
- **Black-box tests (offline):** `make agent-smoke`
  - Adds `tests/test_integration.py` (patches Dropbox HTTP call, asserts uploaded EPUB is a valid ZIP/EPUB)
- **Full suite:** `make test` (all automated pytest tests)
- **Credentialed/manual:** `tests/manual/` (intentionally not in automated collection)

## CI Artifacts (debugging failures)
- GitHub Actions uploads `artifacts/` for both `smoke` and `preflight`.

### If you change EPUB generation (`epub_functions.py`, `utils/text_utils.py`)
- Run `make smoke` (includes golden EPUB checks).
- Run `make agent-smoke` to verify the ZIP uploaded to Dropbox is a valid EPUB.

### If you change Dropbox HTTP code (`dropbox_module.py`)
- Run `make agent-smoke` to verify request payloads and headers.

### If you change async boundaries (`services/epub_service.py`)
- Ensure all blocking work stays behind `asyncio.to_thread()`.
- Run `make smoke` (includes guardrails asserting offloading).

### If you change config/env parsing (`config.py`)
- Run `make preflight` (covers typing + full suite).

### If you change DB behavior (`userbot_db.py`)
- Run `make smoke` (WAL/concurrency guardrails) and `make preflight`.
