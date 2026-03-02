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

test -f AGENTS.md || fail "AGENTS_MD_MISSING" "AGENTS.md is missing." "Agents lack a stable entrypoint and will run wrong commands." "Create AGENTS.md and document the fast loops + invariants." "AGENTS.md"
test -f docs/index.md || fail "DOCS_INDEX_MISSING" "docs/index.md is missing." "Agents cannot find the repo map." "Create docs/index.md as the documentation hub and code map." "docs/index.md"
test -f docs/testing.md || fail "DOCS_TESTING_MISSING" "docs/testing.md is missing." "Agents won't know the offline test rules and fast loops." "Create docs/testing.md describing smoke/agent-smoke/preflight and offline constraints." "docs/testing.md"
test -f docs/harness_plan.md || fail "HARNESS_PLAN_MISSING" "docs/harness_plan.md is missing." "Agents will guess repo tooling and boundaries, causing drift." "Create docs/harness_plan.md documenting current wiring + decisions." "docs/harness_plan.md"

grep -q "make smoke" AGENTS.md || fail "AGENTS_MD_NO_SMOKE" "AGENTS.md does not mention make smoke." "Agents won't know the fast loop." "Add a fast-commands section mentioning make smoke/agent-smoke/preflight." "AGENTS.md"
grep -q "docs/index.md" AGENTS.md || fail "AGENTS_MD_NO_INDEX_LINK" "AGENTS.md does not reference docs/index.md." "Agents lack a pointer to the system-of-record map." "Add a link/reference to docs/index.md in AGENTS.md." "AGENTS.md"
grep -Fq "## 1) What this repo is" AGENTS.md || fail "AGENTS_MD_NO_SHAPE" "AGENTS.md is missing the repo-shape section." "Agents won't understand runtime constraints and will make unsafe changes." "Add '## 1) What this repo is' and describe the runtime shape and constraints." "AGENTS.md"
grep -Fq "## 4) Repo map (code)" AGENTS.md || fail "AGENTS_MD_NO_REPO_MAP" "AGENTS.md is missing the Repo map (code) section." "Agents cannot navigate deterministically." "Add '## 4) Repo map (code)' and list key paths." "AGENTS.md"
grep -Fq "## 5) Typing" AGENTS.md || fail "AGENTS_MD_NO_TYPING" "AGENTS.md is missing the Typing section." "Typecheck failures will be fixed by guesswork." "Add '## 5) Typing' with boundary-first guidance." "AGENTS.md"

grep -q "make smoke" docs/index.md || fail "DOCS_INDEX_NO_SMOKE" "docs/index.md does not mention make smoke." "Agents won't know the fast loop." "Add a fast-commands section mentioning make smoke/agent-smoke/preflight." "docs/index.md"
grep -q "make preflight" docs/index.md || fail "DOCS_INDEX_NO_PREFLIGHT" "docs/index.md does not mention make preflight." "Agents may skip full verification." "Add a fast-commands section mentioning make preflight." "docs/index.md"
grep -Fq "## Code Map (read this first)" docs/index.md || fail "DOCS_INDEX_NO_CODE_MAP" "docs/index.md is missing the Code Map section." "Agents cannot navigate the codebase deterministically." "Add '## Code Map (read this first)' with core/boundary/adapter/entrypoint paths." "docs/index.md"
grep -Fq "## Typing Surfaces" docs/index.md || fail "DOCS_INDEX_NO_TYPING_SURFACES" "docs/index.md is missing the Typing Surfaces section." "Typecheck failures will be fixed by guesswork." "Add '## Typing Surfaces (must stay typed)' listing at least 3 surfaces." "docs/index.md"
grep -Fq "## Test Map (how to self-verify)" docs/index.md || fail "DOCS_INDEX_NO_TEST_MAP" "docs/index.md is missing the Test Map section." "Agents won't know which checks to run per change." "Add '## Test Map (how to self-verify)' mapping make targets to tests." "docs/index.md"

grep -q "<paths>" docs/harness_plan.md && fail "HARNESS_PLAN_PLACEHOLDERS" "docs/harness_plan.md still contains <paths> placeholders." "The harness plan must reflect real repo boundaries." "Fill in the Code map and Test taxonomy sections with real paths." "docs/harness_plan.md"
grep -q "<command" docs/harness_plan.md && fail "HARNESS_PLAN_PLACEHOLDERS" "docs/harness_plan.md still contains <command...> placeholders." "The harness plan must reflect real repo tooling." "Fill in the Current tooling section with real commands." "docs/harness_plan.md"

test -f .github/workflows/agent-harness.yml || fail "WORKFLOW_MISSING" ".github/workflows/agent-harness.yml is missing." "CI won't run the agent harness loops or upload artifacts." "Add .github/workflows/agent-harness.yml that runs make smoke/preflight and uploads artifacts/." ".github/workflows/agent-harness.yml"

test -f tests/conftest.py || fail "PYTEST_CONFTEST_MISSING" "tests/conftest.py is missing." "Test harness cannot enforce offline-by-default behavior." "Add tests/conftest.py with offline-by-default network guards." "tests/conftest.py"
grep -q "OFFLINE_BY_DEFAULT" tests/conftest.py || fail "OFFLINE_ENFORCEMENT_MISSING" "Offline-by-default enforcement marker is missing from tests/conftest.py." "Agents may accidentally introduce real network calls into tests." "Add a session-level guard in tests/conftest.py that blocks sockets unless INTEGRATION=1." "tests/conftest.py"

exit 0
