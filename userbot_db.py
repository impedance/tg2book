"""
Async SQLite storage for the list of channels monitored by the userbot.

The database file lives at data/userbot_db.sqlite so that it can be
mounted as a persistent Docker volume (./data:/app/data).
"""

import os
from pathlib import Path

import aiosqlite

DB_PATH = Path(os.environ.get("DATA_DIR", "data")) / "userbot_db.sqlite"


async def init_db() -> None:
    """Create the channels table if it does not exist yet."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS channels (
                username TEXT PRIMARY KEY
            )
            """
        )
        await db.commit()


async def add_channel(username: str) -> bool:
    """Add a channel to the watchlist. Returns True if added, False if already present."""
    username = username.lstrip("@").lower()
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT INTO channels (username) VALUES (?)", (username,))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def remove_channel(username: str) -> bool:
    """Remove a channel from the watchlist. Returns True if removed, False if not found."""
    username = username.lstrip("@").lower()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM channels WHERE username = ?", (username,))
        await db.commit()
        return cursor.rowcount > 0


async def get_channels() -> list[str]:
    """Return all currently monitored channel usernames (without @)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT username FROM channels ORDER BY username") as cursor:
            rows = await cursor.fetchall()
    return [row[0] for row in rows]
