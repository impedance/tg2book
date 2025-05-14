#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Load environment variables from .env file
export $(grep -v '^#' .env | xargs)

# Run the bot
python bot.py
