import os
import asyncio
import logging
from telethon import TelegramClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("login_userbot")

async def main():
    api_id_raw = os.getenv("API_ID", "").strip()
    api_hash = os.getenv("API_HASH", "").strip()
    session_name = os.getenv("USERBOT_SESSION", "tg2book_userbot").strip()

    if not api_id_raw or not api_hash:
        logger.error("Не заданы API_ID или API_HASH в .env")
        return

    api_id = int(api_id_raw)
    
    logger.info("Запуск интерактивной авторизации для сессии: %s", session_name)
    client = TelegramClient(session_name, api_id, api_hash)
    
    # .start() will prompt for phone number and code interactively
    await client.start()
    
    logger.info("Авторизация успешно завершена! Файл сессии обновлен.")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
