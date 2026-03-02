# PRD: Agent Harness (Agent-First Quality System)

**Purpose:** a prescriptive, copy-pastable PRD that an AI coding agent can execute end-to-end in a single repo. It sets up an “agent-first” harness (docs entrypoints, Make targets, linters/formatters, type checking, tests, and CI) so agents reliably ship correct changes and can self-verify.

**Design constraint:** **no discretionary choices**. Where stacks differ, the agent MUST follow the deterministic “Stack Detection + Tooling Matrix” in this document.

---

## A) Task for the agent (how to execute this PRD)

### A.0 Discovery + clarification policy (MANDATORY)

To make this PRD “drop-in” for both new and existing repos, the agent MUST start with a deterministic discovery pass and is explicitly allowed to ask limited clarifying questions.

**Discovery pass (MUST, before editing code):**
- Detect stack(s) using section **C**.
- Identify the current “source of truth” commands (if any) for:
  - format, lint, typecheck, tests
  - local run/dev (if relevant)
  - CI workflows (if present)
- Identify where code lives (for the Code Map):
  - core domain logic
  - boundaries/DTOs/config
  - adapters (network/DB/filesystem/queues)
  - entrypoints (handlers/CLI/web/bot)
- Identify existing test taxonomy (unit/smoke/golden/black-box/integration), including any current external calls.
- Identify the top 3–5 repo-specific invariants that should become mechanical checks (or confirm only the required baseline invariants will be added).

**Clarification gate (allowed, but constrained):**
- If discovery reveals ambiguity that cannot be resolved from the repo with high confidence, the agent MUST ask the user.
- Maximum: **5 questions** total.
- Each question MUST be:
  - specific and actionable (not open-ended brainstorming),
  - necessary to avoid guessing a high-impact behavior (tool choice, test entrypoint, critical user journey, adapter boundaries),
  - accompanied by a one-line “why this matters” and “what I will do after you answer”.

**Assumptions policy (MANDATORY):**
- If the user does not respond, proceed with the safest, least-invasive default:
  - wire existing tooling into `make smoke/preflight` rather than migrating toolchains,
  - keep default paths offline-by-default,
  - document any assumptions in `docs/harness_plan.md`.

### A.1 Deliverables (what you must create/change)

1. Create or update `AGENTS.md` using the template in this PRD (short, stable entrypoint).
2. Create `docs/index.md` as the documentation hub (“map”, progressive disclosure): links + commands + checklists.
3. Create `docs/harness_plan.md` (short discovery report + decisions; template in section **J**).
4. Provide a single stable command interface via a **`Makefile`**:
   - `smoke` (fast)
   - `agent-smoke` (smoke + 1–3 offline black-box checks)
   - `preflight` (format + lint + typecheck + full tests)
5. Wire **linting + formatting** into `make smoke` and `make preflight` (per section **E**).
6. Wire **type checking** into `make preflight` and ensure it is materially useful (per section **E.4/E.5**).
7. Wire **tests** into the Make targets:
   - subset/fast tests in `make smoke`,
   - full suite in `make preflight`.
8. Add **at least 1** custom structural check with a remediation message (implemented as a fast script or structural test).
9. Enforce **offline-by-default** mechanically (per section **F**).
10. Add **agent legibility artifacts** (see section **H**): at minimum, produce a deterministic test report artifact (JUNIT or equivalent) in CI and upload it.
11. Add an **evaluation harness** seed (see section **H.4**): at minimum, ensure `agent-smoke` runs at least one offline black-box or golden test that exercises a real user journey.
12. Configure CI (GitHub Actions) to run:
    - `make smoke` on every PR
    - `make preflight` on every PR (or at minimum on `main` if preflight is too slow; but you MUST implement the workflow file regardless).

Notes:
- Items 1–6 are the **foundation set**: entrypoints + map + lint + typing. Implement these first so agents can self-verify early.

### A.2 Minimal execution plan (recommended order)

1. Run the discovery pass (section **A.0**) and write `docs/harness_plan.md` (template in section **J**). (Stack detection happens here.)
2. Add the docs entrypoints: `AGENTS.md` and `docs/index.md` (templates in section **J**).
3. Add/Update `Makefile` targets using section **D** (no other interface is allowed).
4. Add/Update tool configuration (section **E**) and wire **lint + typecheck** early so agents can self-verify quickly.
5. Add structural checks with remediation output (section **F**) including the required docs coherence checks and offline-by-default enforcement.
6. Add/Update tests and `agent-smoke` evaluation seed (section **H.4**).
7. Add CI workflows (section **G**) calling `make smoke` and `make preflight`, uploading `artifacts/` (section **H.2**).
8. Run `make preflight` until green; only then declare completion.

### A.3 Definition of Done (acceptance criteria)

- `smoke`, `agent-smoke`, `preflight` exist and pass locally and in CI.
- `AGENTS.md` contains: commands, invariants, repo map, link to `docs/index.md`.
- `docs/index.md` contains: links to key docs, commands, and “if you change X → run Y” checklists.
- `docs/harness_plan.md` exists and documents discovery findings and key decisions (tools, test taxonomy, invariants).
- CI runs at least `smoke` on every PR and fails on violations.
- Lint/typecheck/structural failures provide a **clear next step** (remediation) rather than “guess the fix”.
- CI uploads at least one machine-readable failure artifact (test report and/or structured logs) so agents can self-correct from CI output.

---

## 0) Terms

- **Harness:** tools + rules + feedback loops that quickly and automatically tell an agent when it is wrong and how to correct course.
- **Invariant:** a rule that must always hold (architecture boundaries, dependency direction, async boundaries, secret handling).
- **Remediation instruction:** actionable “how to fix” text emitted by a check.
- **Smoke:** the fastest verification loop (seconds/minutes) the agent must run repeatedly.
- **Preflight:** the full verification run required before handoff/merge.

---

## 1) Evidence (what this PRD is based on)

### 1.1 OpenAI: Harness engineering (agent-first)

This PRD follows OpenAI’s “enforce constraints mechanically” approach:

- Custom linters + structural tests for architecture constraints:  
  Quote: “enforced mechanically via custom linters … and structural tests.”  
  Source: https://openai.com/index/harness-engineering/

- Remediation instructions in lint error messages:  
  Quote: “write the error messages to inject remediation instructions into agent context.”  
  Source: https://openai.com/index/harness-engineering/

- Progressive disclosure (“map, not a manual”):  
  Quote: “give Codex a map … rather than a 1,000-page manual.”  
  Source: https://openai.com/index/harness-engineering/

### 1.2 Mitchell Hashimoto: AI adoption journey

This PRD also follows the “engineer the harness” loop:

- Harness principle:  
  Quote: “give the agent fast, high quality tools to automatically tell it when it is wrong.”  
  Source: https://mitchellh.com/writing/my-ai-adoption-journey

---

## B) Non-negotiable requirements (agent-first defaults)

These MUST be true after implementation:

1. **Offline-by-default (business logic):** `smoke` and `preflight` MUST not perform real external service calls (no production APIs, no real secrets). Dependency installation in CI is allowed in setup steps. This MUST be **mechanically enforced** by at least one check (see section **F**).
2. **Non-interactive:** all checks MUST run unattended in CI.
3. **Stable interface:** agents and CI MUST only need `make smoke` / `make agent-smoke` / `make preflight`.
4. **Fail fast + remediation:** at least one check MUST produce remediation instructions; custom checks MUST always do so.
5. **Deterministic:** checks must not depend on local machine state (except the repo itself).
6. **Agent self-verification:** the repo MUST include a clear, short, deterministic description of:
   - the code map (where core logic lives, where boundaries/adapters live),
   - the typing surfaces (what must be typed and where),
   - the lint/typecheck/test commands an agent must run to validate itself.
   This MUST live in `AGENTS.md` and `docs/index.md` using the templates in section **J**.
7. **Docs layering (no drift):**
   - `docs/index.md` is the **system of record** (“the map”): it may be longer and should contain the full Code Map / Typing Surfaces / Test Map / CI artifacts guidance.
   - `AGENTS.md` is a **short stable entrypoint**: it MUST contain only a concise subset + links to `docs/index.md` (do not duplicate long guidance).
   - Structural checks MUST enforce required headings/links so these docs cannot silently drift.

---

## C) Stack detection (deterministic, no discretion)

The agent MUST determine which stack(s) apply by scanning the repo root:

1. **TypeScript/Node** if any of:
   - `package.json` exists
   - `pnpm-lock.yaml` or `package-lock.json` or `yarn.lock` exists
2. **Python** if any of:
   - `pyproject.toml` exists
   - `requirements.txt` or `requirements-dev.txt` exists
3. **Go** if:
   - `go.mod` exists

If multiple stacks match, implement harness for **all** detected stacks and make `make preflight` run them all.

---

## D) Makefile interface (MANDATORY)

Your repo MUST have a `Makefile` with these targets. The agent MUST wire them to the detected stack(s).

### D.1 Why a Makefile is required

- Keeps this PRD stack-agnostic: agents/CI call `make smoke` rather than remembering tool-specific commands.
- Prevents doc/CI drift: when tooling changes, update Make targets, not every doc.
- Reduces “wrong command” agent failures.

### D.2 Make target contract (MUST)

Targets MUST:
- be deterministic and non-interactive;
- fail fast with clear error output;
- avoid hidden network calls (unless explicitly behind `INTEGRATION=1`, which MUST NOT be used in CI by default).

Required targets:
- `smoke`
- `agent-smoke`
- `preflight`

---

## E) Tooling matrix (MANDATORY defaults)

The agent MUST implement the following, per detected stack. If the repo already has equivalent tools, wire them; otherwise add the recommended tooling.

### E.1 Defaults (no discretion)

The agent MUST use these tools unless the repo already has an equivalent wired into `make preflight`:

- **Python:** `ruff` (format + lint), `mypy` (typecheck), `pytest` (tests).
- **TypeScript/Node:** `prettier` (format), `eslint` (lint), `tsc --noEmit` (typecheck), `vitest` (tests; if the repo already uses jest, keep jest).
- **Go:** `gofmt` (format), `golangci-lint` (preferred; else `go vet`), `go test ./...` (tests).

If `package.json` exists, the agent MUST ensure these scripts exist (names are fixed; implementations may vary):
- `format`, `lint`, `typecheck`, `test`
- `test:smoke` (optional; if absent, `smoke` may run `npm test`)
- `test:blackbox` (recommended; if absent, the agent MUST create offline black-box checks via `tests/blackbox` or equivalent)

---

## E.4 Type checking must be useful (MANDATORY, Pareto rule)

Enabling a type checker is not sufficient. The agent MUST make type checking materially useful by implementing **at least 3 typed boundary surfaces** (or all of them if the repo has fewer than 3).

Definition: a “boundary surface” is one of:
- Public API entrypoints (exported functions/classes called by other modules/packages).
- External adapters (HTTP clients, DB adapters, filesystem adapters, message queue adapters).
- Configuration loading/parsing and its in-memory representation.
- Inter-module DTOs (request/response objects, event payloads).

Requirements:
- Each boundary surface MUST have an explicit type/interface (avoid `any`/`interface{}` as the default).
- The type/interface MUST be used by at least one call site so violations are caught by typecheck.
- Add at least 1 small test (unit or structural) that imports/uses the typed surface (prevents dead, unused typing).

Baseline configuration (MANDATORY, minimal, low-noise):
- Python: add `mypy.ini` or `[tool.mypy]` in `pyproject.toml` with `warn_return_any = True`, `no_implicit_optional = True`, `ignore_missing_imports = True`. If enabling `check_untyped_defs`, do so only if the repo stays green; otherwise document why it is disabled in `docs/index.md`.
- TypeScript: ensure `tsconfig.json` exists and `npm run typecheck` uses `tsc --noEmit`. Default to `"strict": true` for new repos; for existing repos, set `"strict": false` only if required to keep CI green and document the reason in `docs/index.md`.
- Go: ensure `go vet ./...` runs in `make preflight`. If adding `golangci-lint`, enable `govet` and `staticcheck` by default.

### E.5 Agent-facing typing map (MANDATORY)

Typechecking is only useful if agents know what “good typing” looks like in this repo.

Requirements:
- `docs/index.md` MUST include a **Typing Surfaces** section listing the 3+ boundary surfaces (from **E.4**) and the canonical files/modules that define them.
- `AGENTS.md` MUST include a short **Typing** section with:
  - what command runs typecheck,
  - what to do when typecheck fails (where to add/adjust types),
  - and a reminder to avoid `Any`/untyped boundary shapes by default.

---

## F) Structural checks with remediation (MANDATORY)

You MUST implement at least one fast structural check that:
- enforces a real invariant for your repo; and
- prints a remediation message on failure.

Implementation rules:
- It MUST run in `make smoke`.
- It MUST fail the process with non-zero exit code.
- Its output MUST follow the remediation message spec in section **I**.

Required invariant (MUST implement in every repo):
- **Docs entrypoints check:** verify `docs/index.md` and `AGENTS.md` exist and contain the required headings/commands from this PRD.
- **Harness plan exists:** verify `docs/harness_plan.md` exists (discovery report + decisions).

Also required (MUST implement in every repo):
- **Offline-by-default enforcement:** implement at least one mechanical check that makes it hard/impossible for unit tests to hit the network by accident (while still allowing opt-in integration tests behind `INTEGRATION=1`).

Acceptable enforcement patterns (choose at least one; stack-dependent, but deterministic):
- **Python (preferred, zero-deps):** add a `pytest` fixture in `tests/conftest.py` that blocks outbound network by default (e.g., monkeypatch `socket.create_connection` / `socket.socket.connect`), and bypasses only when `INTEGRATION=1`.
- **Node (preferred):** a `vitest`/`jest` setup file that fails tests on unexpected `http(s)` requests unless `INTEGRATION=1` (implementation depends on runtime; keep it minimal and deterministic).
- **Repo-wide (structural):** a fast check that fails if test code imports production external adapters directly (e.g., tests importing a real Dropbox/AWS/Stripe client), with a remediation message pointing to the mock/fake interface.

Additional invariants (OUT OF SCOPE unless explicitly requested by the user):
- Python: forbid `requests` usage under test paths; enforce “no external service calls” in tests.
- TypeScript: enforce “no server-only imports in browser bundles”.
- Go: enforce package boundary rules; forbid `//go:linkname` unless explicitly approved.

---

## G) CI (GitHub Actions) (MANDATORY)

You MUST add `.github/workflows/agent-harness.yml` (or equivalent) that runs:
- `make smoke` on pull requests
- `make preflight` on pull requests (or on `main` if too slow; but still create the job and document the switch in the workflow file)

CI MUST:
- be non-interactive;
- not require real secrets for the default path;
- show remediation output in logs.

---

## H) Agent Legibility + Evaluation Harnesses (MANDATORY)

This section extends the harness beyond “pass/fail” to make failures legible to agents, and to provide a minimal evaluation harness (goldens/black-boxes) that represent real user journeys.

### H.1 Agent legibility (what must be visible to an agent)

At minimum, when `make smoke` / `make preflight` fails in CI, the agent MUST be able to retrieve:
- the exact failing command(s),
- a machine-readable test report (or equivalent structured output),
- and enough context to locate the failure (file, test name, traceback).

### H.2 Required CI artifacts (MUST)

The harness MUST produce and upload artifacts in CI (even on failure):
- a `artifacts/` directory (fixed path),
- plus at least one test report file inside it.

Deterministic defaults (pick per stack; do not invent new tools if the repo already has equivalents):
- **Python/pytest:** write JUnit XML (e.g., `artifacts/pytest.xml`).
- **Node (vitest/jest):** write a JUnit report (e.g., `artifacts/junit.xml`) or a deterministic JSON report.
- **Go:** write `go test -json` output to `artifacts/go-test.json`.

Implementation rule:
- Artifact generation MUST be enabled by default in CI (no secrets, no external calls).

### H.3 Optional deep legibility (RECOMMENDED, when applicable)

If the repo has a UI or renders documents, add at least one “snapshot” style artifact generator that runs offline:
- UI: a screenshot/DOM snapshot of a critical screen in a headless run.
- Docs/EPUB/PDF: extract or diff a golden output to show what changed (text diff or checksum).

### H.4 Evaluation harness seed (MUST)

The harness MUST contain at least one “evaluation” check that is closer to a user journey than a unit test and runs offline:
- **Golden tests** (preferred when outputs are stable): fixed input → exact output match (or normalized match).
- **Black-box tests:** call the public entrypoint (CLI/module/API boundary) with deterministic inputs and assert outputs/side-effects.

Rules:
- It MUST be runnable via `make agent-smoke` (either through `tests/blackbox`, `tests/golden`, or equivalent).
- It MUST not call external services by default (use fakes/mocks/fixtures; allow opt-in via `INTEGRATION=1` only).
- If a golden output changes intentionally, document the update command in `docs/index.md`.

### H.5 Agent-to-agent review loop scaffold (RECOMMENDED)

OpenAI’s harness work emphasizes agent-to-agent review loops. Implementing a real LLM review bot may require external services and secrets, so the default harness MUST remain offline-by-default.

However, the repo SHOULD include a deterministic scaffold so teams can enable it later without reworking the harness:
- Add a short `docs/agent_review.md` describing the expected loop: “author agent runs preflight, then reviewer agent checks invariants and tests, then author agent iterates”.
- Add a CI job placeholder that is **disabled by default** and clearly marked as opt-in (e.g., requires `CODE_REVIEW=1` and required secrets). The job MUST not run on forks or without secrets.

---

## I) Remediation message spec (MANDATORY)

Any custom lint/structural check MUST print failures using these **exact field labels**, one per line:

Rule: <RULE_ID>
Problem: <what broke>
Why: <one-line impact>
Fix: <concrete steps>
Docs: <path in repo>
Command: make smoke (then make preflight)

---

## J) Templates (copy/paste)

The agent MUST implement these templates in the target repo (adapting only project-specific names/paths).

### J.1 `docs/index.md` (documentation hub)

```md
# Documentation Hub

This repo is agent-first. Treat this file as the map (progressive disclosure), not a manual.

## Start here
- Architecture: `docs/architecture.md` (or equivalent)
- Testing rules: `docs/testing.md` (or equivalent)
- Runbook: `docs/RUNBOOK.md` (or equivalent)
- Deployment: `docs/DEPLOY.md` (or equivalent)

## Fast commands
- `make smoke` — fastest regression loop
- `make agent-smoke` — smoke + offline black-box checks
- `make preflight` — format + lint + typecheck + full tests

## Code Map (read this first)

List the codebase in a way an agent can navigate deterministically:
- **Core domain logic:** `<paths>` — pure business logic (should be easiest to unit test)
- **Boundaries / DTOs:** `<paths>` — typed request/response/event shapes
- **Adapters (I/O):** `<paths>` — network, DB, filesystem, queues; MUST be mockable
- **Entrypoints:** `<paths>` — CLI/web/bot handlers; should be thin glue

Rules of thumb (keep short, project-specific):
- Domain logic MUST NOT call real network/DB directly; go through adapters.
- Tests should mock adapters; integration tests are behind `INTEGRATION=1`.

## Typing Surfaces (must stay typed)

List at least 3 boundary surfaces and where they live. Example:
- Config loading: `<path>` — `<type name>`
- External API client: `<path>` — `<interface/type>`
- Inter-module DTOs: `<path>` — `<types>`

## Test Map (how to self-verify)

Describe the repository’s test taxonomy and the Make targets that run them:
- **Smoke tests:** `<paths>` — run via `make smoke`
- **Golden tests:** `<paths>` — run via `make agent-smoke` (offline, deterministic)
- **Black-box tests:** `<paths>` — run via `make agent-smoke` (offline by default)
- **Full test suite:** run via `make preflight`

## CI Artifacts (debugging failures)

CI uploads `artifacts/` on every run. Typical files:
- `artifacts/pytest*.xml` (pytest JUnit)
- `artifacts/go-test*.json` (Go JSON output)

## Self-debug playbook (stack-agnostic)

When something fails, do not guess. Follow this deterministic loop:

1) Run the fastest loop:
   - `make smoke`
2) If smoke is green, run full verification:
   - `make preflight`
3) Fix failures in this order:
   - **structural checks** (repo invariants, docs entrypoints, offline enforcement)
   - **format/lint** (style and static rules)
   - **typecheck** (boundary shapes / DTOs / config)
   - **tests** (unit → golden/black-box → full suite)
4) If CI fails but local passes:
   - inspect the uploaded `artifacts/` and reproduce with `make preflight`
5) If an agent repeats the same mistake twice:
   - encode it: update `AGENTS.md` (for simple command/path confusion) or add a mechanical check with remediation.

## Change checklists

### If you change core logic
- Run `make smoke`
- Run `make agent-smoke`

### If you change boundaries (API/DTO/config)
- Run `make preflight`

### If you change adapters (network/DB/filesystem)
- Run `make preflight`
- Ensure offline tests mock the adapter (no real calls)
```

### J.2 `AGENTS.md` (agent entrypoint)

```md
# AGENTS.md

## 1) What this repo is
One paragraph describing the product, runtime shape, and critical constraints.

## 2) Fast commands (run these first)
- Smoke: `make smoke`
- Agent smoke: `make agent-smoke`
- Preflight: `make preflight`

## 3) Non-negotiable invariants (enforced by checks)
- Offline-by-default: no real network calls in `smoke`/`preflight`.
- No secrets in git: do not commit `.env`, tokens, keys.
- Keep architecture boundaries (see `docs/index.md` for the map).

## 4) Repo map (code)
- `docs/index.md` — documentation hub (map)
- Core logic: `<paths>`
- Boundaries/DTOs: `<paths>`
- Adapters (I/O): `<paths>`
- Entrypoints: `<paths>`

## 5) Typing
- Typecheck: `make preflight` (or `make typecheck` if exposed)
- Keep boundary surfaces typed (see `docs/index.md` → Typing Surfaces).
- If typecheck fails at a boundary: fix the type/interface at the boundary first, then update call sites (avoid papering over with `Any`).

## 6) How to finish a task
- Make changes.
- Run `make smoke` until green.
- Run `make preflight` until green.
- Summarize changes and include the commands you ran.

## 7) Self-debug playbook (stack-agnostic)
- Never “try random fixes”. Always run checks and follow the failure output.
- Fix order: structural → format/lint → typecheck → tests.
- If a check output is unclear: improve it (add remediation text or a structural check) so the next agent can self-correct.
- If you need integration behavior: gate it behind `INTEGRATION=1` and keep default paths offline.

## 8) Common pitfalls (only add after real recurring mistakes)
- Example: “Don’t call the network from unit tests; mock it.”
```

### J.3 `Makefile` (required targets)

This is a template. The agent MUST wire it to the detected stack(s) (section C/E).

```make
.ARTIFACTS_DIR ?= artifacts

.PHONY: smoke agent-smoke preflight format lint typecheck test structural test-smoke test-blackbox

smoke: structural lint
	@$(MAKE) test-smoke

agent-smoke: smoke
	@$(MAKE) test-blackbox

preflight: format lint typecheck test

##
## Structural check(s) with remediation output (MUST)
##
structural:
	@bash tools/structural_check.sh

##
## Generic targets (wire per stack)
##
format:
	@set -euo pipefail; \
	if [ -f pyproject.toml ] || [ -f requirements.txt ] || [ -f requirements-dev.txt ]; then \
		python -m ruff format .; \
	fi; \
	if [ -f package.json ]; then \
		npm run -s format; \
	fi; \
	if [ -f go.mod ]; then \
		gofmt -w .; \
	fi

lint:
	@set -euo pipefail; \
	if [ -f pyproject.toml ] || [ -f requirements.txt ] || [ -f requirements-dev.txt ]; then \
		python -m ruff check .; \
	fi; \
	if [ -f package.json ]; then \
		npm run -s lint; \
	fi; \
	if [ -f go.mod ]; then \
		if command -v golangci-lint >/dev/null 2>&1; then \
			golangci-lint run; \
		else \
			go vet ./...; \
		fi; \
	fi

typecheck:
	@set -euo pipefail; \
	if [ -f pyproject.toml ] || [ -f requirements.txt ] || [ -f requirements-dev.txt ]; then \
		python -m mypy .; \
	fi; \
	if [ -f package.json ]; then \
		npm run -s typecheck; \
	fi; \
	if [ -f go.mod ]; then \
		go vet ./...; \
	fi

test:
	@set -euo pipefail; \
	mkdir -p "$(ARTIFACTS_DIR)"; \
	if [ -f pyproject.toml ] || [ -f requirements.txt ] || [ -f requirements-dev.txt ]; then \
		python -m pytest --junitxml="$(ARTIFACTS_DIR)/pytest.xml"; \
	fi; \
	if [ -f package.json ]; then \
		npm test; \
	fi; \
	if [ -f go.mod ]; then \
		go test -json ./... | tee "$(ARTIFACTS_DIR)/go-test.json"; \
	fi

test-smoke:
	@set -euo pipefail; \
	mkdir -p "$(ARTIFACTS_DIR)"; \
	if [ -d tests/smoke ] && ( [ -f pyproject.toml ] || [ -f requirements.txt ] || [ -f requirements-dev.txt ] ); then \
		python -m pytest tests/smoke --junitxml="$(ARTIFACTS_DIR)/pytest-smoke.xml"; \
	elif [ -f pyproject.toml ] || [ -f requirements.txt ] || [ -f requirements-dev.txt ]; then \
		python -m pytest --junitxml="$(ARTIFACTS_DIR)/pytest.xml"; \
	fi; \
	if [ -f package.json ]; then \
		npm run -s test:smoke --if-present || npm test; \
	fi; \
	if [ -f go.mod ]; then \
		go test -json ./... | tee "$(ARTIFACTS_DIR)/go-test-smoke.json"; \
	fi

test-blackbox:
	@set -euo pipefail; \
	mkdir -p "$(ARTIFACTS_DIR)"; \
	if [ -d tests/blackbox ] && ( [ -f pyproject.toml ] || [ -f requirements.txt ] || [ -f requirements-dev.txt ] ); then \
		python -m pytest tests/blackbox --junitxml="$(ARTIFACTS_DIR)/pytest-blackbox.xml"; \
	elif [ -f pyproject.toml ] || [ -f requirements.txt ] || [ -f requirements-dev.txt ]; then \
		echo "No Python black-box tests found (expected tests/blackbox)."; exit 2; \
	elif [ -f package.json ]; then \
		npm run -s test:blackbox --if-present || (echo "No black-box tests found (expected tests/blackbox or npm script test:blackbox)"; exit 2); \
	elif [ -f go.mod ]; then \
		echo \"No black-box tests found (expected tests/blackbox or equivalent)\"; exit 2; \
	fi
```

### J.4 GitHub Actions workflow (required)

Create `.github/workflows/agent-harness.yml`:

```yml
name: agent-harness

on:
  pull_request:
  push:
    branches: [main]

jobs:
  harness:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        target: [smoke, preflight]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        if: hashFiles('package.json') != ''
        with:
          node-version: 20
      - uses: actions/setup-python@v5
        if: hashFiles('pyproject.toml', 'requirements.txt', 'requirements-dev.txt', 'requirements-test.txt') != ''
        with:
          python-version: "3.11"
      - uses: actions/setup-go@v5
        if: hashFiles('go.mod') != ''
        with:
          go-version-file: go.mod
      - name: Install dependencies (best-effort, deterministic)
        shell: bash
        run: |
          set -euo pipefail

          # Node
          if [ -f package.json ]; then
            if [ -f pnpm-lock.yaml ]; then
              corepack enable
              pnpm install --frozen-lockfile
            elif [ -f yarn.lock ]; then
              corepack enable
              yarn install --frozen-lockfile
            elif [ -f package-lock.json ]; then
              npm ci
            else
              npm install
            fi
          fi

          # Python
          if [ -f requirements.txt ]; then
            python -m pip install --upgrade pip
            python -m pip install -r requirements.txt
          fi
          if [ -f requirements-dev.txt ]; then
            python -m pip install -r requirements-dev.txt
          fi
          if [ -f requirements-test.txt ]; then
            python -m pip install -r requirements-test.txt
          fi

          # Go
          if [ -f go.mod ]; then
            go mod download
          fi
      - name: Run harness
        run: make ${{ matrix.target }}

      - name: Upload harness artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: harness-${{ matrix.target }}
          path: artifacts/
```

Notes:
- If the repo needs language setup (Node/Python/Go), the agent MUST add the appropriate setup steps (e.g., `actions/setup-node`, `actions/setup-python`, `actions/setup-go`) deterministically based on stack detection (section C).

### J.5 `tools/structural_check.sh` (required)

Create `tools/structural_check.sh` (must be executable). This implements the required “Docs entrypoints check”.

```bash
#!/usr/bin/env bash
set -euo pipefail

fail() {
  local rule="$1"
  local problem="$2"
  local why="$3"
  local fix="$4"
  local docs="$5"
  cat <<EOF
Rule: ${rule}
Problem: ${problem}
Why: ${why}
Fix: ${fix}
Docs: ${docs}
Command: make smoke (then make preflight)
EOF
  exit 2
}

test -f docs/index.md || fail "DOCS_INDEX_MISSING" "docs/index.md is missing." "Agents cannot find the repo map." "Create docs/index.md using the template in docs/PRD_agent_harness.md." "docs/PRD_agent_harness.md"
test -f AGENTS.md || fail "AGENTS_MD_MISSING" "AGENTS.md is missing." "Agents lack a stable entrypoint and will run wrong commands." "Create AGENTS.md using the template in docs/PRD_agent_harness.md." "docs/PRD_agent_harness.md"
test -f docs/harness_plan.md || fail "HARNESS_PLAN_MISSING" "docs/harness_plan.md is missing." "Agents will guess repo tooling and boundaries, causing drift." "Create docs/harness_plan.md using the template in docs/PRD_agent_harness.md." "docs/PRD_agent_harness.md"

grep -q "make smoke" docs/index.md || fail "DOCS_INDEX_NO_COMMANDS" "docs/index.md does not mention make smoke." "Agents won't know the fast loop." "Add the Fast commands section to docs/index.md." "docs/PRD_agent_harness.md"
grep -q "make preflight" AGENTS.md || fail "AGENTS_MD_NO_PREFLIGHT" "AGENTS.md does not mention make preflight." "Agents may skip full verification." "Add the Fast commands section to AGENTS.md." "docs/PRD_agent_harness.md"

# Docs layering (system of record vs entrypoint) is only stable if headings exist.
grep -q "^## Code Map (read this first)" docs/index.md || fail "DOCS_INDEX_NO_CODE_MAP" "docs/index.md is missing the Code Map section." "Agents cannot navigate the codebase deterministically." "Add the Code Map section to docs/index.md (see docs/PRD_agent_harness.md)." "docs/PRD_agent_harness.md"
grep -q "^## Typing Surfaces" docs/index.md || fail "DOCS_INDEX_NO_TYPING_SURFACES" "docs/index.md is missing the Typing Surfaces section." "Typecheck failures will be fixed by guesswork." "Add the Typing Surfaces section to docs/index.md and list boundary surfaces." "docs/PRD_agent_harness.md"
grep -q "^## Test Map (how to self-verify)" docs/index.md || fail "DOCS_INDEX_NO_TEST_MAP" "docs/index.md is missing the Test Map section." "Agents won't know which tests to run for which change." "Add the Test Map section to docs/index.md (smoke/golden/black-box/full)." "docs/PRD_agent_harness.md"

grep -q "^## 4) Repo map (code)" AGENTS.md || fail "AGENTS_MD_NO_REPO_MAP" "AGENTS.md is missing the Repo map (code) section." "Agents will search randomly and touch wrong layers." "Add the Repo map (code) section to AGENTS.md with core/boundaries/adapters/entrypoints." "docs/PRD_agent_harness.md"
grep -q "^## 5) Typing" AGENTS.md || fail "AGENTS_MD_NO_TYPING" "AGENTS.md is missing the Typing section." "Agents won't know how to fix typecheck failures correctly." "Add the Typing section to AGENTS.md and link to docs/index.md Typing Surfaces." "docs/PRD_agent_harness.md"

grep -q "docs/index.md" AGENTS.md || fail "AGENTS_MD_NO_INDEX_LINK" "AGENTS.md does not reference docs/index.md." "Agents lack a pointer to the system-of-record map." "Add a link/reference to docs/index.md in AGENTS.md." "docs/PRD_agent_harness.md"

exit 0
```

### J.6 `docs/agent_review.md` (optional scaffold, recommended)

If you implement the agent-to-agent review scaffold (section **H.5**), add `docs/agent_review.md`:

```md
# Agent Review Loop (Opt-in)

This repo is agent-first. When enabled, changes should go through an agent-to-agent review loop:

1) Author agent: implement change + run `make smoke` repeatedly until green.
2) Author agent: run `make preflight` until green.
3) Reviewer agent: check that invariants are preserved, tests meaningfully cover the change, and remediation guidance remains accurate.
4) Author agent: iterate until reviewer feedback is resolved.

Default: this is a process guide only (no external calls). If a CI review job is added, it MUST be opt-in and must not run without explicit enablement + secrets.
```

### J.7 `docs/harness_plan.md` (required)

Create `docs/harness_plan.md` as a short, stable discovery report so agents do not guess:

```md
# Harness Plan (Discovery Report)

This file documents what the harness is wiring and why. Keep it short and update it when the harness changes.

## Stack detection
- Detected stacks (from PRD section C): `<Python/Node/Go/...>`

## Current tooling (before harness)
- Format: `<command or "none">`
- Lint: `<command or "none">`
- Typecheck: `<command or "none">`
- Tests: `<command(s) or "none">`
- CI: `<workflow paths or "none">`

## Code map (where things live)
- Core domain logic: `<paths>`
- Boundaries/DTO/config: `<paths>`
- Adapters (network/DB/filesystem/queues): `<paths>`
- Entrypoints: `<paths>`

## Test taxonomy (offline-by-default)
- Smoke tests: `<paths>`
- Golden tests: `<paths>`
- Black-box tests: `<paths>`
- Integration tests (opt-in): `<paths>` (gated by `INTEGRATION=1`)

## Harness decisions
- Make targets (`smoke/agent-smoke/preflight`) run: `<brief mapping>`
- Offline-by-default enforcement method: `<what blocks network by default>`
- Typing surfaces (3+): `<list surfaces and canonical type/module>`
- Structural checks added: `<RULE_ID list>`

## Open questions / assumptions
- Questions asked (if any): `<list>`
- Assumptions (if user didn’t answer): `<list>`
```

---

## K) Final acceptance checklist (agent must report this)

In the final summary, the agent MUST include:
- The list of files created/changed.
- The exact commands run locally.
- Evidence that CI runs `make smoke` and `make preflight` (workflow file present).
- A one-line pointer to `docs/harness_plan.md` (discovery report + key decisions).

Acceptance is defined by section **A.3 Definition of Done**. This section only specifies the required reporting format for handoff.
