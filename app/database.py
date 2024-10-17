import sqlite3
from datetime import datetime, timezone
import os


def get_db_connection():
    # 确保 data 目录存在
    os.makedirs("data", exist_ok=True)

    conn = sqlite3.connect("data/llm_cache.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cache (
            hashed_key TEXT PRIMARY KEY,
            key TEXT,
            value TEXT,
            is_stream BOOLEAN,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # migration
    cursor.execute("PRAGMA table_info(cache)")
    columns = [column[1] for column in cursor.fetchall()]

    if "is_stream" not in columns:
        cursor.execute("ALTER TABLE cache ADD COLUMN is_stream BOOLEAN DEFAULT 0")

    if "timestamp" not in columns:
        cursor.execute(
            "ALTER TABLE cache ADD COLUMN timestamp DATETIME DEFAULT CURRENT_TIMESTAMP"
        )

        utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "UPDATE cache SET timestamp = ? WHERE timestamp IS NULL", (utc_now,)
        )

    conn.commit()
    conn.close()
