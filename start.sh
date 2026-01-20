#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "$(date) - Creating virtual environment in $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

# Activate the virtual environment so dependencies are already available
source "$VENV_DIR/bin/activate"

if [ -f .env ]; then
  set -o allexport
  source .env
  set +o allexport
fi

echo "$(date) - Starting the bot..."

# Run the bot and log the output
python3 bot.py 2>&1 | tee bot.log

echo "$(date) - Bot exited."
