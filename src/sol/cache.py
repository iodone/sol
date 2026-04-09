"""SQLite schema cache with TTL (aiosqlite)."""

from __future__ import annotations

import json
import time

import aiosqlite
from pydantic import BaseModel, ConfigDict


class CacheEntry(BaseModel):
    """A cached schema entry with metadata."""

    model_config = ConfigDict(protected_namespaces=())

    key: str
    schema: dict
    protocol: str
    fetched_at: float
    expires_at: float
    stale: bool = False

    @property
    def cache_age_ms(self) -> float:
        """Age of this entry in milliseconds."""
        return (time.time() - self.fetched_at) * 1000

    @property
    def cache_source(self) -> str:
        """Return 'cache-hit' or 'cache-stale' depending on state."""
        return "cache-stale" if self.stale else "cache-hit"


class CacheStats(BaseModel):
    """Aggregate stats about the schema cache."""

    total_entries: int
    active_entries: int
    expired_entries: int


class SchemaCache:
    """SQLite-backed schema cache with TTL support.

    Stores fetched schemas as JSON blobs with fetched_at, expires_at,
    and protocol columns. Supports cache-hit/miss/stale semantics.
    """

    def __init__(self, db_path: str = "schemas.db") -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open the database and create the schema table if needed."""
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS schema_cache (
                key TEXT PRIMARY KEY,
                schema_json TEXT NOT NULL,
                protocol TEXT NOT NULL,
                fetched_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
            """)
        await self._db.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    def _ensure_db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("SchemaCache not initialized — call initialize() first")
        return self._db

    async def get(self, key: str, *, stale_ok: bool = False) -> CacheEntry | None:
        """Retrieve a cached schema by key.

        Returns None for missing entries. Returns None for expired entries
        unless stale_ok=True, in which case expired entries are returned
        with stale=True.
        """
        db = self._ensure_db()
        async with db.execute(
            "SELECT key, schema_json, protocol, fetched_at, expires_at FROM schema_cache WHERE key = ?",
            (key,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        now = time.time()
        expired = now > row[4]

        if expired and not stale_ok:
            return None

        return CacheEntry(
            key=row[0],
            schema=json.loads(row[1]),
            protocol=row[2],
            fetched_at=row[3],
            expires_at=row[4],
            stale=expired,
        )

    async def put(self, key: str, schema: dict, protocol: str, ttl: int) -> None:
        """Store or update a schema in the cache with a TTL in seconds."""
        db = self._ensure_db()
        now = time.time()
        await db.execute(
            """
            INSERT OR REPLACE INTO schema_cache (key, schema_json, protocol, fetched_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (key, json.dumps(schema), protocol, now, now + ttl),
        )
        await db.commit()

    async def delete(self, key: str) -> None:
        """Remove a specific entry from the cache."""
        db = self._ensure_db()
        await db.execute("DELETE FROM schema_cache WHERE key = ?", (key,))
        await db.commit()

    async def list(self) -> list[CacheEntry]:
        """Return all cache entries (including expired ones, marked stale)."""
        db = self._ensure_db()
        now = time.time()
        entries: list[CacheEntry] = []
        async with db.execute(
            "SELECT key, schema_json, protocol, fetched_at, expires_at FROM schema_cache"
        ) as cursor:
            async for row in cursor:
                entries.append(
                    CacheEntry(
                        key=row[0],
                        schema=json.loads(row[1]),
                        protocol=row[2],
                        fetched_at=row[3],
                        expires_at=row[4],
                        stale=now > row[4],
                    )
                )
        return entries

    async def clear(self) -> None:
        """Remove all entries from the cache."""
        db = self._ensure_db()
        await db.execute("DELETE FROM schema_cache")
        await db.commit()

    async def stats(self) -> CacheStats:
        """Return aggregate statistics about the cache."""
        db = self._ensure_db()
        now = time.time()
        async with db.execute("SELECT COUNT(*) FROM schema_cache") as cursor:
            total = (await cursor.fetchone())[0]  # type: ignore[index]
        async with db.execute(
            "SELECT COUNT(*) FROM schema_cache WHERE expires_at > ?", (now,)
        ) as cursor:
            active = (await cursor.fetchone())[0]  # type: ignore[index]
        return CacheStats(
            total_entries=total,
            active_entries=active,
            expired_entries=total - active,
        )
