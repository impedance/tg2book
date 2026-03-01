import asyncio
import os

from dotenv import load_dotenv
from pyrogram import Client

load_dotenv()

API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("USERBOT_SESSION_STRING")

app = Client(
    "test_userbot_history",
    session_string=SESSION_STRING,
    api_id=API_ID,
    api_hash=API_HASH,
    no_updates=True,
)


async def main():
    await app.start()

    channels_to_test = ["publicinoss", "llm_under_hood"]
    for ch in channels_to_test:
        print(f"\n--- Checking {ch} ---")
        try:
            chat = await app.get_chat(ch)
            print(f"Chat ID: {chat.id}, Title: {chat.title}, Type: {chat.type}")

            # Fetch last 3 messages
            async for message in app.get_chat_history(chat.id, limit=3):
                text = message.text or message.caption or "<No Text>"
                print(f"Message {message.id}: {text}")
        except Exception as e:
            print(f"Error fetching {ch}: {e}")

    await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
