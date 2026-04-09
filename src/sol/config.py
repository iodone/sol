"""SolSettings — pydantic-settings based configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class SolSettings(BaseSettings):
    """Sol configuration with env variable and config file support.

    Environment variables use the SOL_ prefix (e.g. SOL_CACHE_ENABLED=false).
    Also reads from a config file at {config_dir}/config.toml if it exists.
    """

    model_config = SettingsConfigDict(
        env_prefix="SOL_",
        env_file=".env",
        extra="ignore",
    )

    config_dir: Path = Path.home() / ".config" / "sol"
    cache_dir: Path | None = None
    cache_enabled: bool = True
    cache_ttl: int = 3600
    log_level: str = "WARNING"

    @property
    def cache_db_path(self) -> Path:
        """Return the resolved cache DB path.

        Uses cache_dir if set (via SOL_CACHE_DIR env var), otherwise
        defaults to {config_dir}/cache.db.
        """
        if self.cache_dir is not None:
            return self.cache_dir / "cache.db"
        return self.config_dir / "cache.db"
