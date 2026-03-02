# Harness Plan (Discovery Report)

This file documents what the harness is wiring and why. Keep it short and update it when the harness changes.

## Stack detection
- Detected stacks: Python

## Current tooling (before harness)
- Format: `make format` (Ruff: `ruff check --fix .` + `ruff format .`)
- Lint: `make lint` (Ruff: `ruff check .`)
- Typecheck: `make typecheck` (Mypy on the key modules)
- Tests:
  - `make smoke` (fast loop: ruff + focused pytest subset)
  - `make agent-smoke` (smoke + black-box pytest: `tests/test_integration.py`)
  - `make test` (full pytest suite)
- CI:
  - `.github/workflows/ci.yml` (pip-based ruff/mypy/pytest)
  - `.github/workflows/agent-harness.yml` (runs `make smoke`/`make preflight`, uploads `artifacts/`)

## Code map (where things live)
- Core domain logic:
  - `epub_functions.py` (zero-dep EPUB zip generation)
  - `utils/text_utils.py` (text shaping/title extraction)
  - `src/qr_utils.py` (QR/session helpers)
- Boundaries/DTO/config:
  - `config.py` (`Settings` / env parsing)
- Adapters (network/DB/filesystem):
  - `dropbox_module.py` (Dropbox API v2 HTTP calls)
  - `userbot_db.py` (SQLite via `aiosqlite`)
  - `services/epub_service.py` (coordinates filesystem + Dropbox + EPUB generation)
- Entrypoints:
  - `bot.py` (bot + userbot event loop)
  - `start.sh` (local run helper)
  - `login_userbot.py`, `login_qr.py` (session bootstrap helpers)

## Test taxonomy (offline-by-default)
- Smoke tests:
  - `tests/test_optimization.py`
  - `tests/test_epub_golden.py`
  - `tests/test_epub_service_guardrails.py`
- Golden tests:
  - `tests/test_epub_golden.py` (fixtures in `tests/fixtures/`)
- Black-box tests:
  - `tests/test_integration.py` (patches Dropbox HTTP call, asserts uploaded EPUB is valid)
- Integration tests (opt-in, credentialed/manual): `tests/manual/` (gated by `INTEGRATION=1` when applicable)

## Harness decisions
- Make targets (smoke/agent-smoke/preflight) run:
  - Default local dev: inside dev container (set via `USE_DOCKER=1`, the default)
  - CI/host mode: `USE_DOCKER=0` runs tools via the local Python environment
- Offline-by-default enforcement method:
  - `tests/conftest.py` blocks `socket.socket` / `socket.create_connection` unless `INTEGRATION=1`
- Typing surfaces (3+):
  - Config boundary: `config.py` → `Settings`
  - Dropbox boundary: `dropbox_module.py` → `refresh_access_token()`, upload helpers (HTTP request/headers)
  - Service boundary: `services/epub_service.py` → `process_text_to_epub()`, `process_file_to_dropbox()`
- Structural checks added:
  - `AGENTS_MD_MISSING`, `DOCS_INDEX_MISSING`, `DOCS_TESTING_MISSING`, `HARNESS_PLAN_MISSING`
  - `AGENTS_MD_NO_SMOKE`, `AGENTS_MD_NO_INDEX_LINK`, `DOCS_INDEX_NO_SMOKE`, `DOCS_INDEX_NO_PREFLIGHT`
  - `HARNESS_PLAN_PLACEHOLDERS`, `WORKFLOW_MISSING`, `PYTEST_CONFTEST_MISSING`, `OFFLINE_ENFORCEMENT_MISSING`

## Open questions / assumptions
- Questions asked (if any): none
- Assumptions:
  - The pytest suite is expected to remain fully offline by default; any credentialed checks stay in `tests/manual/`.
  - CI runs harness loops in host mode (`USE_DOCKER=0`) to avoid requiring Docker-in-Docker.
