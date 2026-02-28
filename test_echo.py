import asyncio
import os
import sys

from pyrogram import Client, filters
from dotenv import load_dotenv

load_dotenv()

API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("USERBOT_SESSION_STRING")

app = Client(
    "test_userbot_echo",
    session_string=SESSION_STRING,
    api_id=API_ID,
    api_hash=API_HASH,
    no_updates=False
)

received = []

@app.on_message(filters.me)
async def my_handler(client, message):
    chat_type = message.chat.type if message.chat else "Private"
    text = message.text or message.caption or ""
    print(f"PONG! Received message in {chat_type}: {text}")
    received.append(text)

async def main():
    print("Starting client...")
    await app.start()
    
    print("Sending message to Saved Messages...")
    await app.send_message("me", "Hello from test script!")
    
    print("Waiting 5 seconds to see if we catch it...")
    await asyncio.sleep(5)
    
    if received:
        print("SUCCESS! Caught the message.")
    else:
        print("FAIL! Did not catch the message via on_message.")
        
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
