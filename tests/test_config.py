"""Tests for SolSettings configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from sol.config import SolSettings


class TestSolSettingsDefaults:
    """Test default configuration values."""

    def test_default_config_dir(self, monkeypatch):
        monkeypatch.delenv("SOL_CONFIG_DIR", raising=False)
        monkeypatch.delenv("SOL_CACHE_DIR", raising=False)
        monkeypatch.delenv("SOL_CACHE_ENABLED", raising=False)
        monkeypatch.delenv("SOL_CACHE_TTL", raising=False)
        monkeypatch.delenv("SOL_LOG_LEVEL", raising=False)
        settings = SolSettings()
        assert settings.config_dir == Path.home() / ".config" / "sol"

    def test_default_cache_enabled(self, monkeypatch):
        monkeypatch.delenv("SOL_CACHE_ENABLED", raising=False)
        settings = SolSettings()
        assert settings.cache_enabled is True

    def test_default_cache_ttl(self, monkeypatch):
        monkeypatch.delenv("SOL_CACHE_TTL", raising=False)
        settings = SolSettings()
        assert settings.cache_ttl == 3600

    def test_default_log_level(self, monkeypatch):
        monkeypatch.delenv("SOL_LOG_LEVEL", raising=False)
        settings = SolSettings()
        assert settings.log_level == "WARNING"


class TestSolSettingsEnvOverrides:
    """Test that SOL_ env vars override defaults."""

    def test_cache_enabled_false(self, monkeypatch):
        monkeypatch.setenv("SOL_CACHE_ENABLED", "false")
        settings = SolSettings()
        assert settings.cache_enabled is False

    def test_cache_ttl_override(self, monkeypatch):
        monkeypatch.setenv("SOL_CACHE_TTL", "7200")
        settings = SolSettings()
        assert settings.cache_ttl == 7200

    def test_log_level_override(self, monkeypatch):
        monkeypatch.setenv("SOL_LOG_LEVEL", "DEBUG")
        settings = SolSettings()
        assert settings.log_level == "DEBUG"


class TestCacheDbPath:
    """Test cache_db_path property."""

    def test_default_cache_db_path(self, monkeypatch):
        monkeypatch.delenv("SOL_CACHE_DIR", raising=False)
        monkeypatch.delenv("SOL_CONFIG_DIR", raising=False)
        settings = SolSettings()
        expected = Path.home() / ".config" / "sol" / "cache.db"
        assert settings.cache_db_path == expected

    def test_custom_cache_dir(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SOL_CACHE_DIR", str(tmp_path))
        settings = SolSettings()
        assert settings.cache_db_path == tmp_path / "cache.db"
