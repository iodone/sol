"""Credential profiles (bearer, api-key, basic, oauth2)."""

from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from sol.errors import AuthError


class AuthType(str, Enum):
    """Supported authentication types."""

    bearer = "bearer"
    api_key = "api_key"
    basic = "basic"
    oauth2 = "oauth2"
    custom = "custom"  # Custom headers (no automatic processing)


class LiteralSecret(BaseModel):
    """A secret value stored directly (encrypted at rest is the user's responsibility)."""

    kind: Literal["literal"] = "literal"
    value: str


class EnvSecret(BaseModel):
    """A secret resolved from an environment variable at runtime."""

    kind: Literal["env"] = "env"
    key: str


SecretSource = Annotated[
    Union[LiteralSecret, EnvSecret],
    Field(discriminator="kind"),
]


class Profile(BaseModel):
    """A single credential profile.
    
    For custom auth type, provide custom_headers instead of secret_source.
    For other types (bearer, api_key, basic, oauth2), provide secret_source.
    """

    name: str
    auth_type: AuthType
    secret_source: SecretSource | None = None  # Required for non-custom types
    custom_headers: dict[str, str] | None = None  # Required for custom type
    description: str = ""

    def resolve_secret(self) -> str:
        """Resolve the secret value from its source.

        Returns the plaintext secret string.
        Raises AuthError if an env var reference is unset or auth_type is custom.
        """
        if self.auth_type == AuthType.custom:
            raise AuthError(
                "Cannot resolve secret for custom auth type",
                details="Custom auth uses custom_headers directly, not secret_source.",
            )
        
        if self.secret_source is None:
            raise AuthError(
                f"Profile '{self.name}' has no secret_source",
                details=f"Auth type '{self.auth_type}' requires secret_source.",
            )
        
        src = self.secret_source
        if isinstance(src, LiteralSecret):
            return src.value
        if isinstance(src, EnvSecret):
            val = os.environ.get(src.key)
            if val is None:
                raise AuthError(
                    f"Environment variable '{src.key}' is not set",
                    details=f"Profile '{self.name}' references env var '{src.key}' which is not defined",
                )
            return val
        raise AuthError(f"Unknown secret source kind on profile '{self.name}'")


# Default credentials file path
_DEFAULT_CREDENTIALS_PATH = Path.home() / ".config" / "sol" / "credentials.json"


class Profiles:
    """Manages loading, saving, and querying credential profiles.

    Persists to ~/.config/sol/credentials.json by default.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _DEFAULT_CREDENTIALS_PATH
        self._profiles: dict[str, Profile] = {}

    def load(self) -> None:
        """Load profiles from the credentials file."""
        if not self.path.exists():
            self._profiles = {}
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise AuthError(
                "Failed to load credentials file",
                details=str(exc),
            ) from exc
        version = raw.get("version", 1)
        if version != 1:
            raise AuthError(f"Unsupported credentials file version: {version}")
        profiles_data = raw.get("profiles", {})
        self._profiles = {}
        for name, data in profiles_data.items():
            data["name"] = name
            self._profiles[name] = Profile.model_validate(data)

    def save(self) -> None:
        """Persist profiles to the credentials file atomically."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        profiles_data: dict[str, dict] = {}
        for name, profile in self._profiles.items():
            d = profile.model_dump()
            d.pop("name", None)
            profiles_data[name] = d
        doc = {"version": 1, "profiles": profiles_data}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
        # Restrict permissions (owner-only read/write)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass  # Windows or restricted filesystem

    def get_profile(self, name: str) -> Profile | None:
        """Get a profile by name, or None if not found."""
        return self._profiles.get(name)

    def set_profile(self, profile: Profile) -> None:
        """Add or update a profile."""
        self._profiles[profile.name] = profile

    def remove_profile(self, name: str) -> bool:
        """Remove a profile by name. Returns True if it existed."""
        return self._profiles.pop(name, None) is not None

    def list_profiles(self) -> list[Profile]:
        """Return all profiles, sorted by name."""
        return sorted(self._profiles.values(), key=lambda p: p.name)
