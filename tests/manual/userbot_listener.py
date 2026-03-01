import asyncio
import os
import sys

from dotenv import load_dotenv
from pyrogram import Client

load_dotenv()

API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("USERBOT_SESSION_STRING")

if not API_ID or not API_HASH or not SESSION_STRING:
    print("Missing credentials")
    sys.exit(1)

app = Client(
    "test_userbot",
    session_string=SESSION_STRING,
    api_id=API_ID,
    api_hash=API_HASH,
    no_updates=False,
)


@app.on_message()
async def my_handler(client, message):  # noqa: ARG001
    chat_type = message.chat.type if message.chat else "Private"
    print(f"PONG! Received message in {chat_type}: {message.text or message.caption}")


async def main():
    print("Starting client...")
    await app.start()
    me = await app.get_me()
    print(f"Logged in as {me.first_name}")
    print("Waiting for messages for 60 seconds...")

    # Wait to see if we get any messages
    await asyncio.sleep(60)

    await app.stop()
    print("Done")


if __name__ == "__main__":
    asyncio.run(main())
