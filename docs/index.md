# Documentation Hub

This is the “system of record” for both humans and coding agents. Keep this page short and link out to deeper docs.

## Start Here
- Architecture: `docs/architecture.md`
- Testing & offline rules: `docs/testing.md`
- Runbook (ops/debug): `docs/RUNBOOK.md`
- Deployment notes: `docs/DEPLOY.md`
- Harness engineering notes (project-specific): `docs/harness-engine-recommend.md`
- Task logs: `docs/tasks/`

## Agent Harness (fast, offline loops)
Use these commands for tight “change → verify → iterate” cycles:

- `make smoke` — fastest regression loop (ruff + focused tests).
- `make agent-smoke` — smoke + black-box integration tests (still offline).
- `make preflight` — format + lint + mypy + full test suite before handoff.

## Change Checklists

### If you change EPUB generation (`epub_functions.py`, `utils/text_utils.py`)
- Run `make smoke` (includes golden EPUB checks).
- Run `make agent-smoke` to verify the ZIP uploaded to Dropbox is a valid EPUB.

### If you change Dropbox HTTP code (`dropbox_module.py`)
- Run `make agent-smoke` to verify request payloads and headers.

### If you change async boundaries (`services/epub_service.py`)
- Ensure all blocking work stays behind `asyncio.to_thread()`.
- Run `make smoke` (includes guardrails asserting offloading).

