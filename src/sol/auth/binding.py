"""AuthBindings — host-pattern to credential mapping."""

from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel

from sol.auth.profile import Profile, Profiles
from sol.errors import AuthError


class AuthBinding(BaseModel):
    """Maps a host glob pattern to a credential profile."""

    host: str  # glob pattern, e.g. "*.example.com" or "api.github.com"
    credential: str  # profile name
    alias: str | None = None  # optional short name, e.g. "prod" for "api.example.com"
    priority: int = 0  # higher = preferred
    meta: dict[str, str] | None = None  # optional metadata (e.g., region, workspace)


# Default bindings file path
_DEFAULT_BINDINGS_PATH = Path.home() / ".config" / "sol" / "auth_bindings.json"


class AuthBindings:
    """Manages host-to-credential bindings with glob matching.

    Persists to ~/.config/sol/auth_bindings.json by default.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _DEFAULT_BINDINGS_PATH
        self._bindings: list[AuthBinding] = []

    def load(self) -> None:
        """Load bindings from the bindings file."""
        if not self.path.exists():
            self._bindings = []
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise AuthError(
                "Failed to load auth bindings file",
                details=str(exc),
            ) from exc
        version = raw.get("version", 1)
        if version != 1:
            raise AuthError(f"Unsupported auth bindings file version: {version}")
        self._bindings = [
            AuthBinding.model_validate(b) for b in raw.get("bindings", [])
        ]

    def save(self) -> None:
        """Persist bindings to the bindings file atomically."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        doc = {
            "version": 1,
            "bindings": [b.model_dump() for b in self._bindings],
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def add_binding(self, binding: AuthBinding) -> None:
        """Add a binding."""
        self._bindings.append(binding)

    def remove_binding(self, host: str, credential: str) -> bool:
        """Remove bindings matching host+credential. Returns True if any removed."""
        before = len(self._bindings)
        self._bindings = [
            b
            for b in self._bindings
            if not (b.host == host and b.credential == credential)
        ]
        return len(self._bindings) < before

    def list_bindings(self) -> list[AuthBinding]:
        """Return all bindings."""
        return list(self._bindings)

    def resolve_alias(self, alias: str) -> str | None:
        """Resolve an alias to its real host.

        Args:
            alias: The alias string (e.g., "prod")

        Returns:
            The real hostname (without scheme) if alias is found, None otherwise.
            
        Example:
            >>> # binding: http://api-gateway.dptest.pt.xiaomi.com → staging
            >>> bindings.resolve_alias("staging")
            "api-gateway.dptest.pt.xiaomi.com"  # hostname only, no http://
        """
        for binding in self._bindings:
            if binding.alias and binding.alias.lower() == alias.lower():
                # Extract hostname from binding.host (which may include scheme)
                if "://" in binding.host:
                    parsed = urlparse(binding.host)
                    return parsed.netloc or parsed.hostname or binding.host
                return binding.host
        return None

    def match(self, url: str, profiles: Profiles | None = None) -> Profile | None:
        """Find the best matching profile for a URL.

        Matches binding host patterns against the URL's hostname,
        picks the highest-priority match, then resolves the profile.

        Supports:
        - Alias resolution: staging → real host
        - Scheme-aware matching: https://host matches only https://
        - Scheme-agnostic matching: host matches any scheme

        Matching priority (highest first):
        1. Exact scheme + host match (e.g., "https://api.example.com")
        2. Wildcard host match (e.g., "*.example.com")
        3. Scheme-agnostic host match (e.g., "api.example.com")

        Args:
            url: The target URL to match against.
            profiles: A Profiles instance to look up credentials.
                      If None, loads from default path.

        Returns:
            The matched Profile, or None if no binding matches or
            the referenced profile doesn't exist.
        """
        result = self.match_with_binding(url, profiles)
        return result[0] if result else None

    def match_with_binding(
        self, url: str, profiles: Profiles | None = None
    ) -> tuple[Profile, AuthBinding] | None:
        """Find the best matching profile and binding for a URL.

        Same as match() but returns both profile and binding.

        Returns:
            (Profile, AuthBinding) tuple, or None if no match.
        """
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        scheme = parsed.scheme.lower() if parsed.scheme else ""

        if not hostname:
            return None

        # Try alias resolution first
        real_host = self.resolve_alias(hostname)
        if real_host:
            hostname = real_host.lower()

        # Find all matching bindings
        matches = []
        for binding in self._bindings:
            binding_host = binding.host.lower()

            # Check if binding includes scheme (contains ://)
            if "://" in binding_host:
                # Scheme-aware binding: must match both scheme and host
                binding_parsed = urlparse(binding_host)
                if binding_parsed.scheme == scheme and fnmatch.fnmatch(
                    hostname, binding_parsed.hostname or ""
                ):
                    matches.append((binding, 2))  # Priority boost for exact match
            else:
                # Scheme-agnostic binding: match only host
                if fnmatch.fnmatch(hostname, binding_host):
                    matches.append((binding, 1))  # Lower priority

        if not matches:
            return None

        # Sort by: 1) match type (scheme-aware > agnostic), 2) binding priority
        matches.sort(key=lambda m: (m[1], m[0].priority), reverse=True)
        best_binding = matches[0][0]

        # Resolve to a profile
        if profiles is None:
            profiles = Profiles()
            profiles.load()

        profile = profiles.get_profile(best_binding.credential)
        if profile is None:
            return None

        return (profile, best_binding)
