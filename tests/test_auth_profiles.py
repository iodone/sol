"""Tests for auth profile CRUD operations."""

from __future__ import annotations

import json
import os

import pytest

from sol.auth.profile import (
    AuthType,
    EnvSecret,
    LiteralSecret,
    Profile,
    Profiles,
)
from sol.errors import AuthError


class TestProfile:
    """Test Profile model behavior."""

    def test_literal_secret_resolve(self):
        profile = Profile(
            name="test",
            auth_type=AuthType.bearer,
            secret_source=LiteralSecret(value="my-token"),
        )
        assert profile.resolve_secret() == "my-token"

    def test_env_secret_resolve(self, monkeypatch):
        monkeypatch.setenv("TEST_SECRET", "env-value")
        profile = Profile(
            name="test",
            auth_type=AuthType.api_key,
            secret_source=EnvSecret(key="TEST_SECRET"),
        )
        assert profile.resolve_secret() == "env-value"

    def test_env_secret_missing_raises(self, monkeypatch):
        monkeypatch.delenv("MISSING_VAR", raising=False)
        profile = Profile(
            name="test",
            auth_type=AuthType.bearer,
            secret_source=EnvSecret(key="MISSING_VAR"),
        )
        with pytest.raises(AuthError, match="not set"):
            profile.resolve_secret()


class TestAuthType:
    """Test AuthType enum."""

    def test_values(self):
        assert AuthType.bearer.value == "bearer"
        assert AuthType.api_key.value == "api_key"
        assert AuthType.basic.value == "basic"
        assert AuthType.oauth2.value == "oauth2"


class TestProfilesCRUD:
    """Test Profiles load/save/get/set/remove/list."""

    def test_set_and_get_profile(self, tmp_path):
        store = Profiles(path=tmp_path / "creds.json")
        profile = Profile(
            name="myapi",
            auth_type=AuthType.bearer,
            secret_source=LiteralSecret(value="tok123"),
            description="My API token",
        )
        store.set_profile(profile)
        result = store.get_profile("myapi")
        assert result is not None
        assert result.name == "myapi"
        assert result.auth_type == AuthType.bearer

    def test_get_nonexistent(self, tmp_path):
        store = Profiles(path=tmp_path / "creds.json")
        assert store.get_profile("nope") is None

    def test_remove_profile(self, tmp_path):
        store = Profiles(path=tmp_path / "creds.json")
        store.set_profile(
            Profile(
                name="rm",
                auth_type=AuthType.basic,
                secret_source=LiteralSecret(value="x"),
            )
        )
        assert store.remove_profile("rm") is True
        assert store.get_profile("rm") is None
        assert store.remove_profile("rm") is False

    def test_list_profiles_sorted(self, tmp_path):
        store = Profiles(path=tmp_path / "creds.json")
        for name in ["charlie", "alice", "bob"]:
            store.set_profile(
                Profile(
                    name=name,
                    auth_type=AuthType.bearer,
                    secret_source=LiteralSecret(value="x"),
                )
            )
        names = [p.name for p in store.list_profiles()]
        assert names == ["alice", "bob", "charlie"]

    def test_save_and_load_roundtrip(self, tmp_path):
        path = tmp_path / "creds.json"
        store = Profiles(path=path)
        store.set_profile(
            Profile(
                name="roundtrip",
                auth_type=AuthType.api_key,
                secret_source=EnvSecret(key="RT_KEY"),
                description="roundtrip test",
            )
        )
        store.save()

        store2 = Profiles(path=path)
        store2.load()
        p = store2.get_profile("roundtrip")
        assert p is not None
        assert p.auth_type == AuthType.api_key
        assert isinstance(p.secret_source, EnvSecret)
        assert p.secret_source.key == "RT_KEY"

    def test_load_nonexistent_file(self, tmp_path):
        store = Profiles(path=tmp_path / "nonexistent.json")
        store.load()  # should not raise
        assert store.list_profiles() == []

    def test_load_invalid_json_raises(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json", encoding="utf-8")
        store = Profiles(path=path)
        with pytest.raises(AuthError, match="Failed to load"):
            store.load()
