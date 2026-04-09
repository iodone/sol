"""Cache management CLI subcommands."""

from __future__ import annotations

import asyncio

import typer

from sol.cache import SchemaCache
from sol.config import SolSettings

cache_app = typer.Typer(
    name="cache",
    help="Manage the schema cache.",
    no_args_is_help=True,
)


def _get_cache() -> SchemaCache:
    """Create a SchemaCache instance using SolSettings."""
    settings = SolSettings()
    db_path = settings.cache_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return SchemaCache(db_path=str(db_path))


@cache_app.command("stats")
def cache_stats() -> None:
    """Show cache statistics (total, active, expired entries)."""

    async def _stats() -> None:
        cache = _get_cache()
        await cache.initialize()
        try:
            st = await cache.stats()
            typer.echo(f"Total entries:   {st.total_entries}")
            typer.echo(f"Active entries:  {st.active_entries}")
            typer.echo(f"Expired entries: {st.expired_entries}")
        finally:
            await cache.close()

    asyncio.run(_stats())


@cache_app.command("clear")
def cache_clear() -> None:
    """Remove all entries from the cache."""

    async def _clear() -> None:
        cache = _get_cache()
        await cache.initialize()
        try:
            st = await cache.stats()
            await cache.clear()
            typer.echo(f"Cleared {st.total_entries} cache entries.")
        finally:
            await cache.close()

    asyncio.run(_clear())
