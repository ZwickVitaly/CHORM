"""Tests for query plan caching."""

import time

import pytest

from chorm.query_cache import (
    CachedQuery,
    QueryCache,
    enable_global_cache,
    disable_global_cache,
    get_global_cache,
)


class TestCachedQuery:
    """Test CachedQuery dataclass."""

    def test_cached_query_creation(self):
        """Test creating CachedQuery."""
        query = CachedQuery(sql="SELECT * FROM users", compiled_sql="SELECT * FROM users WHERE 1=1")

        assert query.sql == "SELECT * FROM users"
        assert query.compiled_sql == "SELECT * FROM users WHERE 1=1"
        assert query.access_count == 0
        assert query.created_at > 0
        assert query.last_accessed > 0

    def test_cached_query_with_params(self):
        """Test CachedQuery with parameters."""
        query = CachedQuery(sql="SELECT * FROM users WHERE id = :id", params={"id": 123})

        assert query.params == {"id": 123}

    def test_cached_query_metadata(self):
        """Test CachedQuery with metadata."""
        query = CachedQuery(sql="SELECT 1", metadata={"tag": "test", "priority": "high"})

        assert query.metadata["tag"] == "test"
        assert query.metadata["priority"] == "high"


class TestQueryCache:
    """Test QueryCache class."""

    def test_cache_initialization(self):
        """Test cache initialization with default values."""
        cache = QueryCache()

        assert cache.enabled is True
        assert cache.max_size == 1000
        assert cache.ttl_seconds == 3600.0

    def test_cache_custom_config(self):
        """Test cache with custom configuration."""
        cache = QueryCache(max_size=100, ttl_seconds=60.0, enabled=False)

        assert cache.max_size == 100
        assert cache.ttl_seconds == 60.0
        assert cache.enabled is False

    def test_set_and_get(self):
        """Test setting and getting cached query."""
        cache = QueryCache()

        cache.set("SELECT * FROM users", compiled_sql="SELECT * FROM users")

        cached = cache.get("SELECT * FROM users")

        assert cached is not None
        assert cached.sql == "SELECT * FROM users"
        assert cached.compiled_sql == "SELECT * FROM users"
        assert cached.access_count == 1

    def test_cache_miss(self):
        """Test cache miss."""
        cache = QueryCache()

        cached = cache.get("SELECT * FROM nonexistent")

        assert cached is None

    def test_cache_with_params(self):
        """Test caching queries with parameters."""
        cache = QueryCache()

        # Cache query with params
        cache.set("SELECT * FROM users WHERE id = :id", params={"id": 123})

        # Same query, same params - should hit
        cached = cache.get("SELECT * FROM users WHERE id = :id", params={"id": 123})
        assert cached is not None

        # Same query, different params - should miss
        cached = cache.get("SELECT * FROM users WHERE id = :id", params={"id": 456})
        assert cached is None

    def test_cache_disabled(self):
        """Test that disabled cache doesn't store queries."""
        cache = QueryCache(enabled=False)

        cache.set("SELECT 1")
        cached = cache.get("SELECT 1")

        assert cached is None

    def test_access_count_increment(self):
        """Test that access count increments on each get."""
        cache = QueryCache()

        cache.set("SELECT 1")

        cache.get("SELECT 1")
        cache.get("SELECT 1")
        cached = cache.get("SELECT 1")

        assert cached.access_count == 3

    def test_last_accessed_update(self):
        """Test that last_accessed is updated on get."""
        cache = QueryCache()

        cache.set("SELECT 1")

        cached1 = cache.get("SELECT 1")
        last_accessed_1 = cached1.last_accessed

        time.sleep(0.01)

        cached2 = cache.get("SELECT 1")
        last_accessed_2 = cached2.last_accessed

        # Same object, but last_accessed should be updated
        assert last_accessed_2 >= last_accessed_1

    def test_ttl_expiration(self):
        """Test that expired entries are not returned."""
        cache = QueryCache(ttl_seconds=0.05)  # 50ms TTL

        cache.set("SELECT 1")

        # Should hit immediately
        cached = cache.get("SELECT 1")
        assert cached is not None

        # Wait for expiration
        time.sleep(0.06)

        # Should miss after expiration
        cached = cache.get("SELECT 1")
        assert cached is None

    def test_max_size_eviction(self):
        """Test LRU eviction when max_size is reached."""
        cache = QueryCache(max_size=3)

        # Fill cache
        cache.set("SELECT 1")
        cache.set("SELECT 2")
        cache.set("SELECT 3")

        # Access SELECT 1 to make it recently used
        cache.get("SELECT 1")

        # Add new query - should evict SELECT 2 (LRU)
        cache.set("SELECT 4")

        assert cache.get("SELECT 1") is not None  # Recently used
        assert cache.get("SELECT 2") is None  # Evicted (LRU)
        assert cache.get("SELECT 3") is not None  # Still in cache
        assert cache.get("SELECT 4") is not None  # Just added

    def test_invalidate_specific(self):
        """Test invalidating specific query."""
        cache = QueryCache()

        cache.set("SELECT 1")
        cache.set("SELECT 2")

        cache.invalidate("SELECT 1")

        assert cache.get("SELECT 1") is None
        assert cache.get("SELECT 2") is not None

    def test_invalidate_all(self):
        """Test invalidating all queries."""
        cache = QueryCache()

        cache.set("SELECT 1")
        cache.set("SELECT 2")

        cache.invalidate()  # No SQL = invalidate all

        assert cache.get("SELECT 1") is None
        assert cache.get("SELECT 2") is None

    def test_clear(self):
        """Test clearing cache."""
        cache = QueryCache()

        cache.set("SELECT 1")
        cache.set("SELECT 2")
        cache.get("SELECT 1")

        cache.clear()

        stats = cache.get_statistics()
        assert stats["size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    def test_get_statistics(self):
        """Test getting cache statistics."""
        cache = QueryCache(max_size=100)

        cache.set("SELECT 1")
        cache.set("SELECT 2")

        cache.get("SELECT 1")  # Hit
        cache.get("SELECT 2")  # Hit
        cache.get("SELECT 3")  # Miss

        stats = cache.get_statistics()

        assert stats["size"] == 2
        assert stats["max_size"] == 100
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 2 / 3
        assert stats["enabled"] is True

    def test_get_top_queries(self):
        """Test getting most frequently accessed queries."""
        cache = QueryCache()

        cache.set("SELECT 1")
        cache.set("SELECT 2")
        cache.set("SELECT 3")

        # Access with different frequencies
        cache.get("SELECT 1")
        cache.get("SELECT 1")
        cache.get("SELECT 1")

        cache.get("SELECT 2")
        cache.get("SELECT 2")

        cache.get("SELECT 3")

        top = cache.get_top_queries(limit=2)

        assert len(top) == 2
        assert top[0].sql == "SELECT 1"  # Most accessed
        assert top[0].access_count == 3
        assert top[1].sql == "SELECT 2"  # Second most
        assert top[1].access_count == 2

    def test_cleanup_expired(self):
        """Test cleaning up expired entries."""
        cache = QueryCache(ttl_seconds=0.05)  # 50ms TTL

        cache.set("SELECT 1")
        cache.set("SELECT 2")
        cache.set("SELECT 3")

        # Wait for expiration
        time.sleep(0.06)

        # Add new query (not expired)
        cache.set("SELECT 4")

        # Cleanup expired
        removed = cache.cleanup_expired()

        assert removed == 3  # 3 expired entries removed

        stats = cache.get_statistics()
        assert stats["size"] == 1  # Only SELECT 4 remains

    def test_metadata_storage(self):
        """Test storing metadata with cached queries."""
        cache = QueryCache()

        cache.set("SELECT * FROM users", tag="user_query", priority="high")

        cached = cache.get("SELECT * FROM users")

        assert cached.metadata["tag"] == "user_query"
        assert cached.metadata["priority"] == "high"


class TestGlobalCache:
    """Test global query cache."""

    def teardown_method(self):
        """Clean up after each test."""
        disable_global_cache()

    def test_enable_global_cache(self):
        """Test enabling global cache."""
        cache = enable_global_cache(max_size=500)

        assert cache is not None
        assert cache.max_size == 500
        assert get_global_cache() is cache

    def test_disable_global_cache(self):
        """Test disabling global cache."""
        enable_global_cache()
        assert get_global_cache() is not None

        disable_global_cache()
        assert get_global_cache() is None

    def test_get_global_cache_default(self):
        """Test getting global cache when not initialized."""
        assert get_global_cache() is None
