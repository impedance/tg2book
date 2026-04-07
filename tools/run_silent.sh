#!/usr/bin/env bash
set -euo pipefail

DESC="${1:-}"
if [ -z "${DESC}" ]; then
  echo "Usage: $0 <description> <command> [args...]" >&2
  exit 2
fi
shift

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <description> <command> [args...]" >&2
  exit 2
fi

TMP_FILE="$(mktemp "${TMPDIR:-/tmp}/run_silent.XXXXXX")"
if "$@" >"$TMP_FILE" 2>&1; then
  printf "  ✓ %s\n" "$DESC"
  rm -f "$TMP_FILE"
  exit 0
fi

RC=$?
printf "  ✗ %s\n" "$DESC" >&2
cat "$TMP_FILE" >&2 || true
rm -f "$TMP_FILE"
exit "$RC"
