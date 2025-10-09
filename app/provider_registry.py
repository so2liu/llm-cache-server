import hashlib
from typing import Optional

from .database import get_db_connection
from .utils import ProviderType


def hash_api_key(api_key: str) -> str:
    """Generate a hash of the API key for caching."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def get_cached_provider(api_key: str) -> Optional[ProviderType]:
    """Get cached provider/base URL for an API key from SQLite."""
    key_hash = hash_api_key(api_key)
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT base_url FROM token_provider_cache WHERE token_hash = ?", (key_hash,)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return row[0]
    return None


def cache_provider(api_key: str, provider: ProviderType) -> None:
    """Cache the provider/base URL for an API key in SQLite."""
    key_hash = hash_api_key(api_key)
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO token_provider_cache (token_hash, base_url, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        """,
        (key_hash, provider),
    )

    conn.commit()
    conn.close()
