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

    def test_custom_auth_has_custom_headers(self):
        """Custom auth type should use custom_headers."""
        profile = Profile(
            name="datum",
            auth_type=AuthType.custom,
            custom_headers={
                "Authorization": "workspace-token/1.0 abc123",
                "X-Custom-Header": "custom-value",
            },
        )
        assert profile.custom_headers == {
            "Authorization": "workspace-token/1.0 abc123",
            "X-Custom-Header": "custom-value",
        }

    def test_custom_auth_resolve_secret_raises(self):
        """Custom auth type should not call resolve_secret()."""
        profile = Profile(
            name="datum",
            auth_type=AuthType.custom,
            custom_headers={"Authorization": "workspace-token/1.0 abc123"},
        )
        with pytest.raises(AuthError, match="Cannot resolve secret for custom auth type"):
            profile.resolve_secret()

    def test_custom_auth_without_secret_source(self):
        """Custom auth type does not require secret_source."""
        profile = Profile(
            name="datum",
            auth_type=AuthType.custom,
            custom_headers={"Authorization": "workspace-token/1.0 abc123"},
        )
        assert profile.secret_source is None
        assert profile.custom_headers is not None


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


class TestMakeAuthHeaders:
    """Test make_auth_headers() for different auth types."""

    def test_bearer_auth_headers(self):
        from sol.auth import make_auth_headers

        profile = Profile(
            name="test",
            auth_type=AuthType.bearer,
            secret_source=LiteralSecret(value="my-bearer-token"),
        )
        headers = make_auth_headers(profile)
        assert headers == {"Authorization": "Bearer my-bearer-token"}

    def test_api_key_auth_headers(self):
        from sol.auth import make_auth_headers

        profile = Profile(
            name="test",
            auth_type=AuthType.api_key,
            secret_source=LiteralSecret(value="my-api-key"),
        )
        headers = make_auth_headers(profile)
        assert headers == {"X-API-Key": "my-api-key"}

    def test_basic_auth_headers(self):
        from sol.auth import make_auth_headers
        import base64

        profile = Profile(
            name="test",
            auth_type=AuthType.basic,
            secret_source=LiteralSecret(value="user:pass"),
        )
        headers = make_auth_headers(profile)
        expected = base64.b64encode(b"user:pass").decode("ascii")
        assert headers == {"Authorization": f"Basic {expected}"}

    def test_custom_auth_headers(self):
        from sol.auth import make_auth_headers

        profile = Profile(
            name="datum",
            auth_type=AuthType.custom,
            custom_headers={
                "Authorization": "workspace-token/1.0 abc123",
                "X-Workspace-ID": "10122",
            },
        )
        headers = make_auth_headers(profile)
        assert headers == {
            "Authorization": "workspace-token/1.0 abc123",
            "X-Workspace-ID": "10122",
        }

    def test_custom_auth_empty_headers(self):
        from sol.auth import make_auth_headers

        profile = Profile(
            name="datum",
            auth_type=AuthType.custom,
            custom_headers={},
        )
        headers = make_auth_headers(profile)
        assert headers == {}


class TestInjectAuth:
    """Test inject_auth() for different auth types."""

    def test_bearer_inject(self):
        import httpx
        from sol.auth import inject_auth

        profile = Profile(
            name="test",
            auth_type=AuthType.bearer,
            secret_source=LiteralSecret(value="my-token"),
        )
        req = httpx.Request("GET", "https://api.example.com")
        inject_auth(req, profile)
        assert req.headers["Authorization"] == "Bearer my-token"

    def test_api_key_inject(self):
        import httpx
        from sol.auth import inject_auth

        profile = Profile(
            name="test",
            auth_type=AuthType.api_key,
            secret_source=LiteralSecret(value="my-key"),
        )
        req = httpx.Request("GET", "https://api.example.com")
        inject_auth(req, profile)
        assert req.headers["X-API-Key"] == "my-key"

    def test_custom_inject(self):
        import httpx
        from sol.auth import inject_auth

        profile = Profile(
            name="datum",
            auth_type=AuthType.custom,
            custom_headers={
                "Authorization": "workspace-token/1.0 abc123",
                "X-Custom": "value",
            },
        )
        req = httpx.Request("GET", "https://api.example.com")
        inject_auth(req, profile)
        assert req.headers["Authorization"] == "workspace-token/1.0 abc123"
        assert req.headers["X-Custom"] == "value"

    def test_custom_inject_multiple_headers(self):
        import httpx
        from sol.auth import inject_auth

        profile = Profile(
            name="test",
            auth_type=AuthType.custom,
            custom_headers={
                "Authorization": "custom-auth-value",
                "X-API-Version": "v2",
                "X-Client-ID": "client123",
            },
        )
        req = httpx.Request("GET", "https://api.example.com")
        inject_auth(req, profile)
        assert req.headers["Authorization"] == "custom-auth-value"
        assert req.headers["X-API-Version"] == "v2"
        assert req.headers["X-Client-ID"] == "client123"
