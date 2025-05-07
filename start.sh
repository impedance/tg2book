#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Load environment variables from .env file
source .env

# Run the bot
python bot.py
