import asyncio
from pyrogram import Client
from pyrogram.raw import functions
from config import settings

async def main():
    app = Client(
        name="test_qr",
        api_id=settings.API_ID,
        api_hash=settings.API_HASH,
        in_memory=True,
    )
    print("Connecting...")
    await app.connect()
    
    # Try exporting
    result = await app.invoke(
        functions.auth.ExportLoginToken(
            api_id=settings.API_ID,
            api_hash=settings.API_HASH,
            except_ids=[],
        )
    )
    print("ExportLoginToken success", type(result))
    await app.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
