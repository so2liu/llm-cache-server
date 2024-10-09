import sqlite3


def get_db_connection():
    conn = sqlite3.connect("data/llm_cache.db")
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
            is_stream BOOLEAN
        )
    """
    )

    # Check if is_stream column exists
    cursor.execute("PRAGMA table_info(cache)")
    columns = [column[1] for column in cursor.fetchall()]

    if "is_stream" not in columns:
        # Add is_stream column and set default value
        cursor.execute("ALTER TABLE cache ADD COLUMN is_stream BOOLEAN DEFAULT 0")

    conn.commit()
    conn.close()
