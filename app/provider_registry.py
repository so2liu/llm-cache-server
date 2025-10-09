import hashlib
from typing import Optional

from .utils import ProviderType

# In-memory cache: {api_key_hash: provider_name}
_token_provider_cache: dict[str, ProviderType] = {}


def hash_api_key(api_key: str) -> str:
    """Generate a hash of the API key for caching."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def get_cached_provider(api_key: str) -> Optional[ProviderType]:
    """Get cached provider for an API key."""
    key_hash = hash_api_key(api_key)
    return _token_provider_cache.get(key_hash)


def cache_provider(api_key: str, provider: ProviderType) -> None:
    """Cache the provider for an API key."""
    key_hash = hash_api_key(api_key)
    _token_provider_cache[key_hash] = provider
