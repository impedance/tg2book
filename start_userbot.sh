#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "$(date) - Creating virtual environment in $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

if [ -f .env ]; then
  set -o allexport
  source .env
  set +o allexport
fi

echo "$(date) - Starting userbot listener..."
python3 userbot_listener.py 2>&1 | tee userbot.log
echo "$(date) - Userbot listener exited."
