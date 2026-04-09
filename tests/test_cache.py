"""Async tests for SchemaCache operations."""

from __future__ import annotations

import time

import pytest
import pytest_asyncio

from sol.cache import CacheEntry, CacheStats, SchemaCache


@pytest_asyncio.fixture
async def cache(tmp_path):
    """Create a SchemaCache with a temporary database."""
    db_path = str(tmp_path / "test_cache.db")
    c = SchemaCache(db_path=db_path)
    await c.initialize()
    yield c
    await c.close()


@pytest.mark.asyncio
class TestSchemaCachePutGet:
    """Test basic put/get operations."""

    async def test_put_and_get(self, cache: SchemaCache):
        await cache.put("key1", {"ops": [1, 2]}, "openapi", ttl=3600)
        entry = await cache.get("key1")
        assert entry is not None
        assert entry.key == "key1"
        assert entry.schema_data == {"ops": [1, 2]}
        assert entry.protocol == "openapi"
        assert entry.stale is False

    async def test_get_missing_key(self, cache: SchemaCache):
        entry = await cache.get("nonexistent")
        assert entry is None

    async def test_put_overwrites(self, cache: SchemaCache):
        await cache.put("k", {"v": 1}, "proto", ttl=3600)
        await cache.put("k", {"v": 2}, "proto", ttl=3600)
        entry = await cache.get("k")
        assert entry is not None
        assert entry.schema_data == {"v": 2}


@pytest.mark.asyncio
class TestSchemaCacheTTL:
    """Test TTL and expiry behavior."""

    async def test_expired_entry_returns_none(self, cache: SchemaCache):
        """Entries past TTL return None by default."""
        await cache.put("exp", {"data": True}, "test", ttl=0)
        # TTL=0 means expires_at = now, so it's immediately expired
        import asyncio

        await asyncio.sleep(0.05)
        entry = await cache.get("exp")
        assert entry is None

    async def test_expired_entry_stale_ok(self, cache: SchemaCache):
        """With stale_ok=True, expired entries are returned with stale=True."""
        await cache.put("stale", {"data": True}, "test", ttl=0)
        import asyncio

        await asyncio.sleep(0.05)
        entry = await cache.get("stale", stale_ok=True)
        assert entry is not None
        assert entry.stale is True
        assert entry.cache_source == "cache-stale"

    async def test_active_entry_not_stale(self, cache: SchemaCache):
        await cache.put("fresh", {"data": True}, "test", ttl=3600)
        entry = await cache.get("fresh")
        assert entry is not None
        assert entry.stale is False
        assert entry.cache_source == "cache-hit"


@pytest.mark.asyncio
class TestSchemaCacheStats:
    """Test stats operation."""

    async def test_empty_stats(self, cache: SchemaCache):
        stats = await cache.stats()
        assert isinstance(stats, CacheStats)
        assert stats.total_entries == 0
        assert stats.active_entries == 0
        assert stats.expired_entries == 0

    async def test_stats_with_entries(self, cache: SchemaCache):
        await cache.put("a", {}, "p", ttl=3600)
        await cache.put("b", {}, "p", ttl=3600)
        stats = await cache.stats()
        assert stats.total_entries == 2
        assert stats.active_entries == 2
        assert stats.expired_entries == 0

    async def test_stats_with_expired(self, cache: SchemaCache):
        await cache.put("active", {}, "p", ttl=3600)
        await cache.put("expired", {}, "p", ttl=0)
        import asyncio

        await asyncio.sleep(0.05)
        stats = await cache.stats()
        assert stats.total_entries == 2
        assert stats.active_entries == 1
        assert stats.expired_entries == 1


@pytest.mark.asyncio
class TestSchemaCacheClear:
    """Test clear operation."""

    async def test_clear_removes_all(self, cache: SchemaCache):
        await cache.put("a", {}, "p", ttl=3600)
        await cache.put("b", {}, "p", ttl=3600)
        await cache.clear()
        stats = await cache.stats()
        assert stats.total_entries == 0

    async def test_clear_empty_cache(self, cache: SchemaCache):
        await cache.clear()  # should not raise
        stats = await cache.stats()
        assert stats.total_entries == 0


@pytest.mark.asyncio
class TestSchemaCacheDelete:
    """Test delete operation."""

    async def test_delete_existing(self, cache: SchemaCache):
        await cache.put("del_me", {}, "p", ttl=3600)
        await cache.delete("del_me")
        entry = await cache.get("del_me")
        assert entry is None

    async def test_delete_nonexistent(self, cache: SchemaCache):
        await cache.delete("nope")  # should not raise


@pytest.mark.asyncio
class TestSchemaCacheList:
    """Test list operation."""

    async def test_list_entries(self, cache: SchemaCache):
        await cache.put("x", {"x": 1}, "px", ttl=3600)
        await cache.put("y", {"y": 2}, "py", ttl=3600)
        entries = await cache.list()
        assert len(entries) == 2
        keys = {e.key for e in entries}
        assert keys == {"x", "y"}


@pytest.mark.asyncio
class TestCacheEntryProperties:
    """Test CacheEntry model properties."""

    async def test_cache_age_ms(self, cache: SchemaCache):
        await cache.put("age", {}, "p", ttl=3600)
        entry = await cache.get("age")
        assert entry is not None
        assert entry.cache_age_ms >= 0
        assert entry.cache_age_ms < 5000  # should be very fresh


class TestSchemaCacheNotInitialized:
    """Test error when cache not initialized."""

    def test_ensure_db_raises(self):
        cache = SchemaCache(db_path="unused.db")
        with pytest.raises(RuntimeError, match="not initialized"):
            cache._ensure_db()
