"""Tests for AuthBindings host-pattern matching."""

from __future__ import annotations

import json

import pytest

from sol.auth.binding import AuthBinding, AuthBindings
from sol.auth.profile import AuthType, LiteralSecret, Profile, Profiles
from sol.errors import AuthError


@pytest.fixture
def profiles_store(tmp_path):
    """Create a Profiles store with test profiles."""
    store = Profiles(path=tmp_path / "creds.json")
    store.set_profile(
        Profile(
            name="github",
            auth_type=AuthType.bearer,
            secret_source=LiteralSecret(value="ghp_token"),
        )
    )
    store.set_profile(
        Profile(
            name="default",
            auth_type=AuthType.api_key,
            secret_source=LiteralSecret(value="default-key"),
        )
    )
    return store


class TestAuthBinding:
    """Test AuthBinding model."""

    def test_default_priority(self):
        b = AuthBinding(host="*.example.com", credential="test")
        assert b.priority == 0

    def test_custom_priority(self):
        b = AuthBinding(host="api.github.com", credential="gh", priority=10)
        assert b.priority == 10


class TestAuthBindingsMatch:
    """Test URL matching logic."""

    def test_exact_host_match(self, profiles_store):
        bindings = AuthBindings(path=None)
        bindings._bindings = [
            AuthBinding(host="api.github.com", credential="github"),
        ]
        profile = bindings.match(
            "https://api.github.com/repos", profiles=profiles_store
        )
        assert profile is not None
        assert profile.name == "github"

    def test_wildcard_match(self, profiles_store):
        bindings = AuthBindings(path=None)
        bindings._bindings = [
            AuthBinding(host="*.github.com", credential="github"),
        ]
        profile = bindings.match(
            "https://api.github.com/repos", profiles=profiles_store
        )
        assert profile is not None
        assert profile.name == "github"

    def test_no_match_returns_none(self, profiles_store):
        bindings = AuthBindings(path=None)
        bindings._bindings = [
            AuthBinding(host="*.github.com", credential="github"),
        ]
        profile = bindings.match(
            "https://api.example.com/data", profiles=profiles_store
        )
        assert profile is None

    def test_priority_ordering(self, profiles_store):
        bindings = AuthBindings(path=None)
        bindings._bindings = [
            AuthBinding(host="*.github.com", credential="default", priority=0),
            AuthBinding(host="*.github.com", credential="github", priority=10),
        ]
        profile = bindings.match(
            "https://api.github.com/repos", profiles=profiles_store
        )
        assert profile is not None
        assert profile.name == "github"

    def test_empty_url_returns_none(self, profiles_store):
        bindings = AuthBindings(path=None)
        bindings._bindings = [
            AuthBinding(host="*", credential="default"),
        ]
        profile = bindings.match("", profiles=profiles_store)
        assert profile is None

    def test_missing_profile_returns_none(self, profiles_store):
        bindings = AuthBindings(path=None)
        bindings._bindings = [
            AuthBinding(host="*.example.com", credential="nonexistent"),
        ]
        profile = bindings.match("https://api.example.com", profiles=profiles_store)
        assert profile is None


class TestAuthBindingsCRUD:
    """Test binding add/remove/list operations."""

    def test_add_and_list(self):
        bindings = AuthBindings(path=None)
        bindings._bindings = []
        b = AuthBinding(host="*.test.com", credential="test_cred")
        bindings.add_binding(b)
        listed = bindings.list_bindings()
        assert len(listed) == 1
        assert listed[0].host == "*.test.com"

    def test_remove_binding(self):
        bindings = AuthBindings(path=None)
        bindings._bindings = [
            AuthBinding(host="a.com", credential="cred_a"),
            AuthBinding(host="b.com", credential="cred_b"),
        ]
        assert bindings.remove_binding("a.com", "cred_a") is True
        assert len(bindings.list_bindings()) == 1

    def test_remove_nonexistent(self):
        bindings = AuthBindings(path=None)
        bindings._bindings = []
        assert bindings.remove_binding("nope.com", "nope") is False


class TestAuthBindingsResolveAlias:
    """Test alias resolution."""

    def test_resolve_alias_with_scheme_http(self):
        """resolve_alias should strip http:// scheme from binding.host."""
        bindings = AuthBindings(path=None)
        bindings._bindings = [
            AuthBinding(
                host="http://api-gateway.dptest.pt.xiaomi.com",
                credential="test-cred",
                alias="staging",
            ),
        ]
        resolved = bindings.resolve_alias("staging")
        assert resolved == "api-gateway.dptest.pt.xiaomi.com"

    def test_resolve_alias_with_scheme_https(self):
        """resolve_alias should strip https:// scheme from binding.host."""
        bindings = AuthBindings(path=None)
        bindings._bindings = [
            AuthBinding(
                host="https://api-gateway.dp.pt.xiaomi.com",
                credential="prod-cred",
                alias="prod",
            ),
        ]
        resolved = bindings.resolve_alias("prod")
        assert resolved == "api-gateway.dp.pt.xiaomi.com"

    def test_resolve_alias_without_scheme(self):
        """resolve_alias should return hostname as-is if no scheme present."""
        bindings = AuthBindings(path=None)
        bindings._bindings = [
            AuthBinding(
                host="api.example.com",
                credential="example-cred",
                alias="example",
            ),
        ]
        resolved = bindings.resolve_alias("example")
        assert resolved == "api.example.com"

    def test_resolve_alias_with_port(self):
        """resolve_alias should preserve port in hostname."""
        bindings = AuthBindings(path=None)
        bindings._bindings = [
            AuthBinding(
                host="http://localhost:8080",
                credential="local-cred",
                alias="local",
            ),
        ]
        resolved = bindings.resolve_alias("local")
        assert resolved == "localhost:8080"

    def test_resolve_alias_case_insensitive(self):
        """resolve_alias should be case-insensitive."""
        bindings = AuthBindings(path=None)
        bindings._bindings = [
            AuthBinding(
                host="https://api.github.com",
                credential="gh",
                alias="GitHub",
            ),
        ]
        assert bindings.resolve_alias("github") == "api.github.com"
        assert bindings.resolve_alias("GITHUB") == "api.github.com"
        assert bindings.resolve_alias("GitHub") == "api.github.com"

    def test_resolve_alias_not_found(self):
        """resolve_alias should return None if alias not found."""
        bindings = AuthBindings(path=None)
        bindings._bindings = [
            AuthBinding(
                host="https://api.example.com",
                credential="test",
                alias="example",
            ),
        ]
        assert bindings.resolve_alias("nonexistent") is None

    def test_resolve_alias_no_alias_field(self):
        """resolve_alias should return None if binding has no alias."""
        bindings = AuthBindings(path=None)
        bindings._bindings = [
            AuthBinding(host="https://api.example.com", credential="test"),
        ]
        assert bindings.resolve_alias("example") is None


class TestAuthBindingsPersistence:
    """Test save/load."""

    def test_save_and_load_roundtrip(self, tmp_path):
        path = tmp_path / "bindings.json"
        b = AuthBindings(path=path)
        b._bindings = [
            AuthBinding(host="*.api.com", credential="my_cred", priority=5),
        ]
        b.save()

        b2 = AuthBindings(path=path)
        b2.load()
        items = b2.list_bindings()
        assert len(items) == 1
        assert items[0].host == "*.api.com"
        assert items[0].priority == 5

    def test_load_nonexistent_file(self, tmp_path):
        b = AuthBindings(path=tmp_path / "missing.json")
        b.load()  # should not raise
        assert b.list_bindings() == []
