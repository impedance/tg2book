#!/bin/bash

# Load environment variables from .env file
set -o allexport
source .env
set +o allexport

# Log the start time
echo "$(date) - Starting the bot..."

# Load environment variables from .env file
set -o allexport
source .env
set +o allexport

# Run the bot and log the output
python3 bot.py 2>&1 | tee bot.log

# Log the exit time
echo "$(date) - Bot exited."
