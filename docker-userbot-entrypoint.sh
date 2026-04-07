#!/bin/sh

set -eu

session_base="${USERBOT_SESSION:-/app/runtime/tg2book_userbot}"

case "$session_base" in
  *.session) session_db="$session_base" ;;
  *) session_db="${session_base}.session" ;;
esac

session_dir="$(dirname "$session_db")"
mkdir -p "$session_dir"

if [ ! -f "$session_db" ]; then
  echo "USERBOT session not found at $session_db"
  echo "Run: make userbot-login"
  exec sleep infinity
fi

exec python userbot_listener.py
