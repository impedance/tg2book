"""
One-time script to authenticate the Pyrogram userbot and create the session file.
"""

import asyncio
import logging
import os
from pathlib import Path

from pyrogram import Client

from config import settings

# Disable verbose logging to make console clean
# logging.basicConfig(level=logging.DEBUG)
# logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
SESSION_NAME = str(DATA_DIR / "userbot")


async def main() -> None:
    api_id = settings.API_ID
    api_hash = settings.API_HASH

    if not api_id or not api_hash:
        print("❌ Ошибка: API_ID или API_HASH не найдены в .env")
        api_id = int(input("Введите API_ID вручную: ").strip())
        api_hash = input("Введите API_HASH вручную: ").strip()

    print(f"Используем API_ID: {api_id}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Имитируем официальные данные приложения для стабильности
    app = Client(
        SESSION_NAME,
        api_id=api_id,
        api_hash=api_hash,
        device_model="Android 11",
        system_version="30.0.0",
        app_version="8.0.0"
    )

    async with app:
        me = await app.get_me()
        session_string = await app.export_session_string()
        
        print(f"\n✅ Авторизация прошла успешно!")
        print(f"   Аккаунт: {me.first_name} (@{me.username})")
        print(f"   Сессия сохранена в: {SESSION_NAME}.session")
        print(f"\n🔗 ВАША СТРОКА СЕССИИ (STRING SESSION):")
        print("-" * 50)
        print(session_string)
        print("-" * 50)
        print("\nСкопируйте эту длинную строку и вставьте её в .env на сервере в USERBOT_SESSION_STRING.")
        print("После этого файлы .session больше не понадобятся.")


if __name__ == "__main__":
    asyncio.run(main())
