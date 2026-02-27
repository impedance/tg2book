"""
One-time script to authenticate the Pyrogram userbot and create the session file.

Run this ONCE locally (or in an interactive Docker container) before deploying:
    python login_userbot.py

It will prompt for your phone number and the verification code from Telegram,
then save the session file to data/userbot.session. Mount the data/ directory
into the Docker container so the session persists between restarts.
"""

import asyncio
import os
from pathlib import Path

from pyrogram import Client

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
SESSION_NAME = str(DATA_DIR / "userbot")


async def main() -> None:
    api_id_str = os.environ.get("API_ID") or input("Enter API_ID: ").strip()
    api_hash = os.environ.get("API_HASH") or input("Enter API_HASH: ").strip()

    api_id = int(api_id_str)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    async with Client(SESSION_NAME, api_id=api_id, api_hash=api_hash) as app:
        me = await app.get_me()
        print(f"\n✅ Авторизация прошла успешно!")
        print(f"   Аккаунт: {me.first_name} (@{me.username})")
        print(f"   Сессия сохранена в: {SESSION_NAME}.session")
        print("\nТеперь запустите бот через Docker Compose — он подхватит сессию автоматически.")


if __name__ == "__main__":
    asyncio.run(main())
