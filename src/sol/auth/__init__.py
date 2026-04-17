"""Auth subsystem — profiles, bindings, and OAuth2 flows."""

from __future__ import annotations

import base64

import httpx
from loguru import logger

from sol.auth.profile import (
    AuthType,
    EnvSecret,
    LiteralSecret,
    Profile,
    Profiles,
    SecretSource,
)
from sol.auth.binding import AuthBinding, AuthBindings
from sol.auth.oauth import (
    OAuthSession,
    OAuthTokenResponse,
    authorization_code_flow,
    device_code_flow,
    load_oauth_session,
    refresh_token_flow,
    save_oauth_session,
)
from sol.errors import AuthError

__all__ = [
    "AuthBinding",
    "AuthBindings",
    "AuthType",
    "EnvSecret",
    "LiteralSecret",
    "OAuthSession",
    "OAuthTokenResponse",
    "Profile",
    "Profiles",
    "SecretSource",
    "authorization_code_flow",
    "device_code_flow",
    "inject_auth",
    "load_oauth_session",
    "make_auth_headers",
    "refresh_token_flow",
    "resolve_auth_headers",
    "save_oauth_session",
]


def inject_auth(request: httpx.Request, profile: Profile) -> httpx.Request:
    """Apply authentication from a profile to an httpx Request.

    Modifies the request in-place and returns it for convenience.

    - bearer: Authorization: Bearer <secret>
    - api_key: X-API-Key header (default) with the secret value
    - basic: Authorization: Basic <base64(secret)> where secret is "user:password"
    - oauth2: Authorization: Bearer <secret> (same as bearer, token from resolve_secret)
    - custom: Apply custom_headers directly (no processing)
    """
    if profile.auth_type == AuthType.custom:
        # Custom auth: use custom_headers directly
        if profile.custom_headers:
            for key, value in profile.custom_headers.items():
                request.headers[key] = value
        return request
    
    # Standard auth types: resolve secret and apply
    secret = profile.resolve_secret()

    if profile.auth_type == AuthType.bearer:
        request.headers["Authorization"] = f"Bearer {secret}"

    elif profile.auth_type == AuthType.api_key:
        request.headers["X-API-Key"] = secret

    elif profile.auth_type == AuthType.basic:
        # secret should be "username:password"
        encoded = base64.b64encode(secret.encode("utf-8")).decode("ascii")
        request.headers["Authorization"] = f"Basic {encoded}"

    elif profile.auth_type == AuthType.oauth2:
        request.headers["Authorization"] = f"Bearer {secret}"

    else:
        raise AuthError(f"Unsupported auth type: {profile.auth_type}")

    return request


def make_auth_headers(profile: Profile) -> dict[str, str]:
    """Produce a dict of auth headers from a profile (non-OAuth2 types).

    For OAuth2 profiles, use resolve_auth_headers() which handles
    session loading and token refresh.
    """
    if profile.auth_type == AuthType.custom:
        # Custom auth: return custom_headers directly
        return profile.custom_headers or {}
    
    # Standard auth types: resolve secret and build headers
    secret = profile.resolve_secret()

    if profile.auth_type == AuthType.bearer:
        return {"Authorization": f"Bearer {secret}"}

    elif profile.auth_type == AuthType.api_key:
        return {"X-API-Key": secret}

    elif profile.auth_type == AuthType.basic:
        encoded = base64.b64encode(secret.encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}

    elif profile.auth_type == AuthType.oauth2:
        return {"Authorization": f"Bearer {secret}"}

    else:
        raise AuthError(f"Unsupported auth type: {profile.auth_type}")


async def resolve_auth_headers(
    url: str,
    *,
    credential: str | None = None,
    profiles: Profiles | None = None,
    bindings: AuthBindings | None = None,
) -> tuple[dict[str, str] | None, Profile | None, AuthBinding | None]:
    """Resolve auth headers for a URL, with binding metadata.

    Resolution order:
    1. If ``credential`` is given, load that named profile.
    2. Otherwise, auto-resolve via AuthBindings.match(url).
    3. If the profile is OAuth2, load the session from disk,
       check expiry, and auto-refresh if needed.

    Returns:
        A tuple of (headers_dict, profile, binding). All may be None if no auth
        was resolved. binding contains metadata (meta field) for adapter use.
    """
    # Load profiles if not provided
    if profiles is None:
        profiles = Profiles()
        profiles.load()

    # Step 1: Resolve profile and binding
    profile: Profile | None = None
    matched_binding: AuthBinding | None = None

    if credential is not None:
        profile = profiles.get_profile(credential)
        if profile is None:
            raise AuthError(
                f"Credential profile '{credential}' not found",
                details="Use 'sol auth list' to see available profiles.",
            )
        logger.debug("Using explicit credential profile: %s", credential)
        # No binding when using explicit credential
        matched_binding = None
    else:
        # Auto-resolve via bindings
        if bindings is None:
            bindings = AuthBindings()
            bindings.load()
        result = bindings.match_with_binding(url, profiles=profiles)
        if result is not None:
            profile, matched_binding = result
            logger.debug(
                "Auto-resolved credential profile '%s' for %s", profile.name, url
            )
        else:
            logger.debug("No credential profile matched for %s", url)

    if profile is None:
        return None, None, None

    # Step 2: Handle OAuth2 session refresh
    if profile.auth_type == AuthType.oauth2:
        session = load_oauth_session(profile.name)
        if session is not None:
            if session.is_expired():
                if (
                    session.refresh_token
                    and session.token_endpoint
                    and session.client_id
                ):
                    logger.debug(
                        "OAuth2 token expired for '%s', refreshing...", profile.name
                    )
                    token_resp = await refresh_token_flow(
                        token_endpoint=session.token_endpoint,
                        client_id=session.client_id,
                        client_secret=session.client_secret,
                        refresh_token=session.refresh_token,
                    )
                    # Update and persist session
                    session.access_token = token_resp.access_token
                    session.token_type = token_resp.token_type
                    if token_resp.refresh_token:
                        session.refresh_token = token_resp.refresh_token
                    if token_resp.expires_at is not None:
                        session.expires_at = token_resp.expires_at
                    save_oauth_session(profile.name, session)
                    logger.debug("OAuth2 token refreshed for '%s'", profile.name)
                else:
                    logger.warning(
                        "OAuth2 token expired for '%s' but no refresh_token/endpoint available",
                        profile.name,
                    )

            # Use the (possibly refreshed) session token
            return {" Authorization": f"Bearer {session.access_token}"}, profile, matched_binding
        # No session on disk — fall through to resolve_secret
        logger.debug(
            "No OAuth2 session on disk for '%s', using profile secret", profile.name
        )

    # Step 3: Produce headers from profile
    headers = make_auth_headers(profile)
    return headers, profile, matched_binding
