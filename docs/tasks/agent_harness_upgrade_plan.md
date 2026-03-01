# Agent Harness Upgrade Plan

Goal: maximize day-1 effectiveness of coding agents in this repo with minimal changes, aligned with the "harness engineering" approach and with Mitchell Hashimoto's practical AI adoption workflow.

Scope for this plan: items (1), (2), (3), (5), (6), (7) from the earlier recommendations. Item (4) (git hygiene for runtime artifacts) is intentionally not in scope here, but should be addressed soon because it creates noisy diffs and risk.

## 0. Baseline Check (Before Changes)

1. Confirm current developer workflow commands and their runtime environment.
2. Confirm that tests are discoverable and fast enough to be used as a tight feedback loop.
3. Confirm docs are consistent and do not contradict each other.

Acceptance criteria:
- `make format`, `make lint`, `make typecheck`, `make test` are documented and work in the intended environment (Docker vs local venv).
- One canonical doc exists for agent rules and repo invariants.

Notes from current repo state:
- `AGENTS.md` is mostly correct about invariants (zero-deps, `asyncio.to_thread`, WAL), but the "Repo Map" line for tests is inaccurate: there are test modules in the repo root (`test_*.py`) and also a `tests/` folder.
- `CLAUDE.md` contradicts the architecture (it claims `python-telegram-bot` usage for `bot.py`) and should be corrected or replaced with pointers to `AGENTS.md` and `docs/architecture.md`.

## 1. Fix/Align Documentation Sources of Truth (CLAUDE.md and AGENTS.md)

### 1.1 Update `CLAUDE.md` to match reality

Edits:
- Replace any mention of `python-telegram-bot` with the actual stack: Pyrogram bot + Pyrogram userbot on one event loop.
- Update the "Main Files" list to match the current file layout (`services/epub_service.py`, `userbot_db.py`, `utils/text_utils.py`, `docs/architecture.md`, etc.).
- Add a short "Agent invariants" section and link to `AGENTS.md` and `docs/architecture.md` as canonical.
- Remove/avoid duplicating long instructions that already exist elsewhere; prefer linking.

Acceptance criteria:
- No contradictions between `CLAUDE.md`, `AGENTS.md`, and `docs/architecture.md` on frameworks, architecture, and invariants.

### 1.2 Patch `AGENTS.md` if needed

Edits (expected small):
- Fix the tests mapping line to reflect both locations: root `test_*.py` and `tests/`.
- Replace TODO entries for docs/commands once implemented in steps (2), (3), (6).
- Add "Fast paths for agents" section that lists `make preflight` and `make smoke` (introduced below).

Acceptance criteria:
- `AGENTS.md` reads like an executable operating manual for agents with no stale repo claims.

## 2. Add `make smoke` (fast, local harness check)

Design principle:
- Smoke must be fast and deterministic so agents run it by default after small edits.

Implementation:
1. Add `smoke` target to `Makefile`.
2. The smoke target should run a minimal set of checks, in order:
3. `ruff check` on the repo (or on changed files if you want to keep it fast without GitHub CI).
4. Run a minimal pytest selection that hits the core invariants:
5. Always include `tests/test_optimization.py` (it asserts the event loop is not blocked and WAL is enabled).
6. Optionally include one EPUB "golden input" test (added in step 5) once it exists.

Acceptance criteria:
- `make smoke` completes quickly (target: under ~15-30 seconds in the typical local Docker environment).
- `make smoke` fails on obvious agent regressions: formatting/lint violations, blocking I/O in async paths, or EPUB structure regressions.

## 3. Add `make preflight` (single command before pushing / merging)

Design principle:
- Reduce agent/human coordination cost by having exactly one "do the right thing" command.

Implementation:
1. Add `preflight` target to `Makefile`.
2. `preflight` should run:
3. `make format`
4. `make lint`
5. `make typecheck`
6. `make test`

Acceptance criteria:
- There is a single recommended command that returns green for a releasable change.
- `AGENTS.md` references `make preflight` as the default verification step.

## 5. Add a Tiny "Golden Inputs" Harness for EPUB (micro-evals without CI)

Goal:
- Give agents a reliable, local, non-network regression harness for EPUB generation without adding heavy dependencies.

Implementation:
1. Create a small fixtures folder, for example `tests/fixtures/`.
2. Add 3-5 representative message inputs as plain `.txt` files.
3. Add a new pytest module, for example `tests/test_epub_golden.py`.
4. For each fixture:
5. Call the EPUB generator code path (prefer calling `epub_functions.create_epub` directly for speed).
6. Treat the resulting `.epub` as a `zipfile.ZipFile` and validate a minimal set of invariants:
7. Required files exist (`mimetype`, `META-INF/container.xml`, package OPF, at least one XHTML content file).
8. The `mimetype` entry is stored without compression (EPUB requirement).
9. The XHTML contains an expected sanitized title and preserves basic formatting rules.

Acceptance criteria:
- The tests run offline and do not perform real Telegram or Dropbox network calls.
- A typical agent change to EPUB logic is caught by these tests before manual verification.

## 6. Add `docs/testing.md` (how to write tests that agents won't break)

Goal:
- Prevent "agent wrote a flaky test" and encode project-specific mocking patterns.

Implementation:
1. Create `docs/testing.md`.
2. Document the required testing invariants:
3. No real network I/O in tests.
4. Prefer unit tests around pure functions and EPUB zip invariants.
5. How to mock Telegram/Pyrogram surfaces used by `bot.py`.
6. How to test async code paths (`pytest-asyncio`, event loop scope, `asyncio.Queue` patterns).
7. How to test DB behaviors with `tmp_path` and `aiosqlite` WAL checks.
8. Add a short "common pitfalls" section:
9. Avoid calling Dropbox in tests.
10. Avoid sleeping long in tests; use small sleeps or mocked `asyncio.sleep`.

Acceptance criteria:
- A new contributor or agent can add a test without guessing how to mock Telegram/Dropbox.

## 7. Tighten Static Analysis and "Architecture Guardrails"

Goal:
- Make it hard for agents to accidentally violate core architecture (blocking I/O, drift from invariants), without adding heavy new tooling.

### 7.1 Mypy coverage improvements

Implementation:
1. Expand the `make typecheck` target to include all relevant modules, at minimum:
2. `bot.py`, `services/epub_service.py`, `dropbox_module.py`, `epub_functions.py`, `userbot_db.py`, `utils/`, `src/`.
3. Keep `ignore_missing_imports = true` for Pyrogram if needed, but prefer typed wrappers for your own modules.

Acceptance criteria:
- New code in core paths is typechecked by default, not only a subset of files.

### 7.2 Ruff rule alignment

Implementation:
1. Keep current ruff config, but add targeted guardrails where it helps agents:
2. Consider enabling a minimal set of rules that prevent common async mistakes if not already covered.
3. Avoid broad new rule sets that cause churn; prefer incremental tightening.
4. Add a short section in `AGENTS.md` explaining the repo's linting philosophy: "low noise, high signal".

Acceptance criteria:
- Lint stays actionable; agents can fix issues quickly without fighting a huge ruleset.

### 7.3 Lightweight architecture checks

Implementation:
1. Add a small test or check that enforces "blocking Dropbox calls must be behind `asyncio.to_thread`" for the main code path.
2. Start with the simplest approach (a unit test around `process_text_to_epub` and `process_file_to_dropbox` behavior).

Acceptance criteria:
- A future edit that calls `dropbox_module.upload_to_dropbox` directly from an async function fails fast.

## Suggested Execution Order (Minimal Risk)

1. Docs alignment (step 1) so agents have one coherent operating manual.
2. Add `make preflight` (step 3) so verification is standardized.
3. Add `make smoke` (step 2) so iteration is fast.
4. Add EPUB golden tests (step 5) to stabilize output.
5. Add `docs/testing.md` (step 6) to prevent future test drift.
6. Tighten typecheck/lint guardrails (step 7) last to avoid blocking earlier wins.

## Verification Checklist (After Implementation)

Run locally from repo root:
- `make preflight`
- `make smoke`

Expected outcome:
- Both targets succeed without requiring real Telegram or Dropbox credentials for the test suite.

