"""SQLite-backed storage for monitored Telegram channels."""

from __future__ import annotations

import re
import sqlite3
from typing import List


DEFAULT_DB_PATH = "channels.db"


def _normalize_channel_identifier(identifier: str) -> str:
    """Normalize channel identifier for stable storage and de-duplication."""
    if identifier is None:
        raise ValueError("Channel identifier is required")

    normalized = identifier.strip()
    if not normalized:
        raise ValueError("Channel identifier is required")

    normalized = re.sub(r"^https?://t\.me/", "", normalized, flags=re.IGNORECASE)
    normalized = normalized.lstrip("@")

    if not normalized:
        raise ValueError("Channel identifier is required")

    if re.fullmatch(r"-?\d+", normalized):
        return normalized

    return normalized.lower()


def normalize_channel_identifier(identifier: str) -> str:
    """Public normalization helper for command handlers and ingestion filters."""
    return _normalize_channel_identifier(identifier)


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Create the monitored channels table if needed."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS monitored_channels (
                identifier TEXT PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_message_id INTEGER DEFAULT 0
            )
            """
        )
        # Migration for existing databases
        try:
            conn.execute("ALTER TABLE monitored_channels ADD COLUMN last_message_id INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        conn.commit()


def add_channel(identifier: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Add a normalized channel identifier. Returns False for duplicates."""
    init_db(db_path)
    normalized = _normalize_channel_identifier(identifier)

    with sqlite3.connect(db_path) as conn:
        try:
            conn.execute(
                "INSERT INTO monitored_channels (identifier) VALUES (?)",
                (normalized,),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def remove_channel(identifier: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Remove a channel identifier. Returns False when nothing was removed."""
    init_db(db_path)
    normalized = _normalize_channel_identifier(identifier)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM monitored_channels WHERE identifier = ?",
            (normalized,),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_channels(db_path: str = DEFAULT_DB_PATH) -> List[str]:
    """Return monitored channel identifiers in stable order."""
    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT identifier FROM monitored_channels ORDER BY identifier COLLATE NOCASE ASC"
        ).fetchall()
        return [row[0] for row in rows]


def get_channels_with_details(db_path: str = DEFAULT_DB_PATH) -> List[dict]:
    """Return monitored channels with all details (identifier, last_message_id)."""
    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT identifier, last_message_id FROM monitored_channels ORDER BY identifier COLLATE NOCASE ASC"
        ).fetchall()
        return [dict(row) for row in rows]


def update_last_message_id(identifier: str, last_id: int, db_path: str = DEFAULT_DB_PATH) -> None:
    """Update the last processed message ID for a channel."""
    init_db(db_path)
    normalized = _normalize_channel_identifier(identifier)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE monitored_channels SET last_message_id = ? WHERE identifier = ?",
            (last_id, normalized),
        )
        conn.commit()
