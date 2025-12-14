"""Smart in-memory cache with TTL support."""

from datetime import datetime, timedelta
from typing import Any, Optional
import hashlib
import json


class SmartCache:
    """
    In-memory cache with TTL (Time-To-Live) support.
    
    For production, this can be swapped with Redis by implementing
    the same interface (get, set, delete, clear).
    """
    
    def __init__(self, default_ttl_hours: int = 24):
        self._cache: dict[str, dict] = {}
        self._default_ttl = timedelta(hours=default_ttl_hours)
    
    def _make_key(self, *args) -> str:
        """Create a deterministic cache key from arguments."""
        key_string = ":".join(str(arg).lower().strip() for arg in args)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if exists and not expired.
        
        Returns None if key doesn't exist or has expired.
        """
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        
        # Check if expired
        if datetime.now() > entry["expires_at"]:
            del self._cache[key]
            return None
        
        return entry["value"]
    
    def set(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> None:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to store (must be JSON serializable for consistency)
            ttl: Optional custom TTL, defaults to cache default
        """
        ttl = ttl or self._default_ttl
        self._cache[key] = {
            "value": value,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + ttl
        }
    
    def delete(self, key: str) -> bool:
        """Delete a key from cache. Returns True if key existed."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> int:
        """Clear all cache entries. Returns count of cleared entries."""
        count = len(self._cache)
        self._cache.clear()
        return count
    
    def stats(self) -> dict:
        """Get cache statistics."""
        now = datetime.now()
        valid_entries = sum(
            1 for entry in self._cache.values() 
            if now < entry["expires_at"]
        )
        expired_entries = len(self._cache) - valid_entries
        
        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "default_ttl_hours": self._default_ttl.total_seconds() / 3600
        }
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now > entry["expires_at"]
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        return len(expired_keys)


# Global cache instance
cache = SmartCache(default_ttl_hours=24)


