"""Query plan caching for improved performance."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CachedQuery:
    """Cached query plan entry.

    Attributes:
        sql: SQL query text
        compiled_sql: Compiled SQL (if different from original)
        params: Query parameters (if any)
        created_at: Cache entry creation timestamp
        last_accessed: Last access timestamp
        access_count: Number of times this query was accessed
        metadata: Additional metadata
    """

    sql: str
    compiled_sql: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    created_at: float = 0.0
    last_accessed: float = 0.0
    access_count: int = 0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.created_at == 0.0:
            self.created_at = time.time()
        if self.last_accessed == 0.0:
            self.last_accessed = self.created_at


class QueryCache:
    """Thread-safe query plan cache.

    Caches compiled SQL queries to avoid repeated parsing and compilation.
    Uses LRU eviction policy when cache is full.

    Args:
        max_size: Maximum number of cached queries (default: 1000)
        ttl_seconds: Time-to-live for cache entries in seconds (default: 3600)
        enabled: Enable/disable caching (default: True)

    Example:
        >>> cache = QueryCache(max_size=500)
        >>>
        >>> # Cache a query
        >>> cache.set("SELECT * FROM users", compiled_sql="SELECT * FROM users")
        >>>
        >>> # Retrieve from cache
        >>> cached = cache.get("SELECT * FROM users")
        >>> if cached:
        ...     print(f"Cache hit! SQL: {cached.compiled_sql}")
        >>>
        >>> # Get statistics
        >>> stats = cache.get_statistics()
        >>> print(f"Hit rate: {stats['hit_rate']:.2%}")
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 3600.0, enabled: bool = True):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled

        self._cache: Dict[str, CachedQuery] = {}
        self._lock = Lock()

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def _compute_key(self, sql: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Compute cache key for query.

        Args:
            sql: SQL query text
            params: Query parameters

        Returns:
            Cache key (hash)
        """
        # Create hash from SQL + params
        key_data = sql
        if params:
            # Sort params for consistent hashing
            sorted_params = sorted(params.items())
            key_data += str(sorted_params)

        return hashlib.sha256(key_data.encode()).hexdigest()

    def get(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Optional[CachedQuery]:
        """Get cached query.

        Args:
            sql: SQL query text
            params: Query parameters

        Returns:
            CachedQuery if found and not expired, None otherwise
        """
        if not self.enabled:
            return None

        key = self._compute_key(sql, params)

        with self._lock:
            cached = self._cache.get(key)

            if cached is None:
                self._misses += 1
                return None

            # Check TTL
            age = time.time() - cached.created_at
            if age > self.ttl_seconds:
                # Expired
                del self._cache[key]
                self._misses += 1
                return None

            # Update access stats
            cached.last_accessed = time.time()
            cached.access_count += 1
            self._hits += 1

            return cached

    def set(
        self, sql: str, compiled_sql: Optional[str] = None, params: Optional[Dict[str, Any]] = None, **metadata: Any
    ) -> None:
        """Cache a query.

        Args:
            sql: SQL query text
            compiled_sql: Compiled SQL (if different from original)
            params: Query parameters
            **metadata: Additional metadata to store
        """
        if not self.enabled:
            return

        key = self._compute_key(sql, params)

        with self._lock:
            # Check if we need to evict
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()

            # Create cache entry
            cached = CachedQuery(sql=sql, compiled_sql=compiled_sql or sql, params=params, metadata=metadata)

            self._cache[key] = cached

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return

        # Find LRU entry
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_accessed)

        del self._cache[lru_key]
        self._evictions += 1

    def invalidate(self, sql: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> None:
        """Invalidate cached query.

        Args:
            sql: SQL query text (if None, invalidate all)
            params: Query parameters
        """
        with self._lock:
            if sql is None:
                # Invalidate all
                self._cache.clear()
            else:
                # Invalidate specific query
                key = self._compute_key(sql, params)
                self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear entire cache."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def get_statistics(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics:
            - size: Current cache size
            - max_size: Maximum cache size
            - hits: Number of cache hits
            - misses: Number of cache misses
            - hit_rate: Cache hit rate (0.0-1.0)
            - evictions: Number of evictions
            - enabled: Whether cache is enabled
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "evictions": self._evictions,
                "enabled": self.enabled,
            }

    def get_top_queries(self, limit: int = 10) -> list[CachedQuery]:
        """Get most frequently accessed queries.

        Args:
            limit: Maximum number of queries to return

        Returns:
            List of CachedQuery objects sorted by access count
        """
        with self._lock:
            sorted_queries = sorted(self._cache.values(), key=lambda q: q.access_count, reverse=True)
            return sorted_queries[:limit]

    def cleanup_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        if not self.enabled:
            return 0

        with self._lock:
            now = time.time()
            expired_keys = [key for key, cached in self._cache.items() if (now - cached.created_at) > self.ttl_seconds]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)


# Global query cache instance (optional)
_global_cache: Optional[QueryCache] = None


def get_global_cache() -> Optional[QueryCache]:
    """Get global query cache instance.

    Returns:
        Global QueryCache or None if not initialized
    """
    return _global_cache


def set_global_cache(cache: Optional[QueryCache]) -> None:
    """Set global query cache instance.

    Args:
        cache: QueryCache instance or None to disable
    """
    global _global_cache
    _global_cache = cache


def enable_global_cache(max_size: int = 1000, ttl_seconds: float = 3600.0) -> QueryCache:
    """Enable global query caching.

    Args:
        max_size: Maximum cache size
        ttl_seconds: Time-to-live for cache entries

    Returns:
        Global QueryCache instance

    Example:
        >>> cache = enable_global_cache(max_size=500)
        >>> # Queries are now cached globally
        >>> stats = cache.get_statistics()
        >>> print(f"Hit rate: {stats['hit_rate']:.2%}")
    """
    cache = QueryCache(max_size=max_size, ttl_seconds=ttl_seconds)
    set_global_cache(cache)
    return cache


def disable_global_cache() -> None:
    """Disable global query caching."""
    set_global_cache(None)


# Public API
__all__ = [
    "CachedQuery",
    "QueryCache",
    "get_global_cache",
    "set_global_cache",
    "enable_global_cache",
    "disable_global_cache",
]
