"""OAuth2 flows — authorization_code (with PKCE) and device_code."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import secrets
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field

from sol.errors import AuthError


class OAuthTokenResponse(BaseModel):
    """Parsed token response from an OAuth2 token endpoint."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None

    @property
    def expires_at(self) -> float | None:
        if self.expires_in is not None:
            return time.time() + self.expires_in
        return None


class OAuthSession(BaseModel):
    """Persistent OAuth2 session state for a profile."""

    access_token: str
    token_type: str = "Bearer"
    refresh_token: str | None = None
    expires_at: float | None = None
    token_endpoint: str = ""
    client_id: str = ""
    client_secret: str = ""

    def is_expired(self, skew_seconds: int = 60) -> bool:
        if self.expires_at is None:
            return False
        return time.time() + skew_seconds >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OAuthSession:
        return cls.model_validate(data)


def _generate_pkce() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _parse_token_response(data: dict[str, Any]) -> OAuthTokenResponse:
    """Parse a JSON token response into OAuthTokenResponse."""
    if "error" in data:
        desc = data.get("error_description", data["error"])
        raise AuthError(f"OAuth2 token error: {desc}")
    if "access_token" not in data:
        raise AuthError("OAuth2 token response missing access_token")
    return OAuthTokenResponse(
        access_token=data["access_token"],
        token_type=data.get("token_type", "Bearer"),
        expires_in=data.get("expires_in"),
        refresh_token=data.get("refresh_token"),
        scope=data.get("scope"),
    )


# ---------------------------------------------------------------------------
# Authorization Code Flow with PKCE
# ---------------------------------------------------------------------------


class _CallbackState(BaseModel):
    """Mutable state shared between the callback server and the main flow."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    code: str | None = None
    error: str | None = None
    event: asyncio.Event = Field(default_factory=asyncio.Event)


class _CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for the local OAuth callback server."""

    callback_state: _CallbackState  # set on the class before serving

    def do_GET(self) -> None:  # noqa: N802
        qs = parse_qs(urlparse(self.path).query)
        if "error" in qs:
            self.callback_state.error = qs["error"][0]
        elif "code" in qs:
            self.callback_state.code = qs["code"][0]
        else:
            self.callback_state.error = "no code in callback"

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h2>Authorization complete.</h2>"
            b"<p>You can close this window.</p></body></html>"
        )
        # Signal the event from the event loop's thread
        self.callback_state.event.set()

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default stderr logging."""
        pass


async def authorization_code_flow(
    *,
    authorization_endpoint: str,
    token_endpoint: str,
    client_id: str,
    client_secret: str = "",
    scopes: list[str] | None = None,
    redirect_port: int = 8484,
) -> OAuthTokenResponse:
    """Run the OAuth2 authorization_code flow with PKCE.

    1. Starts a local HTTP server on redirect_port to receive the callback.
    2. Opens the browser (prints URL for the user) to the authorization endpoint.
    3. Waits for the callback with the authorization code.
    4. Exchanges the code for tokens at the token endpoint.
    """
    redirect_uri = f"http://localhost:{redirect_port}/callback"
    verifier, challenge = _generate_pkce()
    state = secrets.token_urlsafe(32)

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if scopes:
        params["scope"] = " ".join(scopes)

    auth_url = f"{authorization_endpoint}?{urlencode(params)}"

    # Set up the callback server
    cb_state = _CallbackState()
    _CallbackHandler.callback_state = cb_state

    server = HTTPServer(("127.0.0.1", redirect_port), _CallbackHandler)
    server_thread = Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    # Print the URL for the user
    print(f"\nOpen this URL to authorize:\n\n  {auth_url}\n", file=sys.stderr)
    print(
        f"Waiting for callback on http://localhost:{redirect_port}/callback ...",
        file=sys.stderr,
    )

    # Wait for the callback (with timeout)
    try:
        await asyncio.wait_for(
            asyncio.to_thread(server_thread.join, timeout=300),
            timeout=300,
        )
    except asyncio.TimeoutError:
        server.server_close()
        raise AuthError("Authorization code flow timed out waiting for callback")
    finally:
        server.server_close()

    if cb_state.error:
        raise AuthError(f"Authorization failed: {cb_state.error}")
    if not cb_state.code:
        raise AuthError("No authorization code received")

    # Exchange code for tokens
    token_data = {
        "grant_type": "authorization_code",
        "code": cb_state.code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    if client_secret:
        token_data["client_secret"] = client_secret

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            token_endpoint,
            data=token_data,
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            raise AuthError(
                f"Token exchange failed (HTTP {resp.status_code})",
                details=resp.text,
            )
        return _parse_token_response(resp.json())


# ---------------------------------------------------------------------------
# Device Code Flow
# ---------------------------------------------------------------------------


async def device_code_flow(
    *,
    device_authorization_endpoint: str,
    token_endpoint: str,
    client_id: str,
    client_secret: str = "",
    scopes: list[str] | None = None,
) -> OAuthTokenResponse:
    """Run the OAuth2 device_code flow (RFC 8628).

    1. Requests a device code from the device authorization endpoint.
    2. Displays the verification URL and user code.
    3. Polls the token endpoint until authorization is granted or times out.
    """
    request_data: dict[str, str] = {"client_id": client_id}
    if scopes:
        request_data["scope"] = " ".join(scopes)

    async with httpx.AsyncClient() as client:
        # Step 1: Request device code
        resp = await client.post(
            device_authorization_endpoint,
            data=request_data,
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            raise AuthError(
                f"Device authorization failed (HTTP {resp.status_code})",
                details=resp.text,
            )
        device_data = resp.json()

    device_code = device_data.get("device_code")
    user_code = device_data.get("user_code")
    verification_uri = device_data.get("verification_uri") or device_data.get(
        "verification_url"
    )
    interval = device_data.get("interval", 5)
    expires_in = device_data.get("expires_in", 600)

    if not device_code or not verification_uri:
        raise AuthError(
            "Invalid device authorization response",
            details=json.dumps(device_data),
        )

    print(
        f"\nTo authorize, visit:\n\n  {verification_uri}\n\n"
        f"And enter code: {user_code}\n",
        file=sys.stderr,
    )

    # Step 2: Poll for token
    deadline = time.time() + expires_in
    poll_data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "device_code": device_code,
        "client_id": client_id,
    }
    if client_secret:
        poll_data["client_secret"] = client_secret

    async with httpx.AsyncClient() as client:
        while time.time() < deadline:
            await asyncio.sleep(interval)
            resp = await client.post(
                token_endpoint,
                data=poll_data,
                headers={"Accept": "application/json"},
            )
            body = resp.json()
            error = body.get("error")

            if error == "authorization_pending":
                continue
            elif error == "slow_down":
                interval += 5  # RFC 8628 §3.5
                continue
            elif error:
                desc = body.get("error_description", error)
                raise AuthError(f"Device code flow error: {desc}")
            else:
                return _parse_token_response(body)

    raise AuthError("Device code flow timed out waiting for authorization")


# ---------------------------------------------------------------------------
# Token Refresh
# ---------------------------------------------------------------------------


async def refresh_token_flow(
    *,
    token_endpoint: str,
    client_id: str,
    client_secret: str = "",
    refresh_token: str,
) -> OAuthTokenResponse:
    """Refresh an OAuth2 access token using a refresh_token grant."""
    data: dict[str, str] = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    if client_secret:
        data["client_secret"] = client_secret

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            token_endpoint,
            data=data,
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            raise AuthError(
                f"Token refresh failed (HTTP {resp.status_code})",
                details=resp.text,
            )
        return _parse_token_response(resp.json())


# ---------------------------------------------------------------------------
# Session Persistence
# ---------------------------------------------------------------------------

from pathlib import Path as _Path

_DEFAULT_SESSIONS_DIR = _Path.home() / ".config" / "sol" / "oauth_sessions"


def _sessions_dir() -> _Path:
    return _DEFAULT_SESSIONS_DIR


def save_oauth_session(profile_name: str, session: OAuthSession) -> None:
    """Persist an OAuth session to disk."""
    d = _sessions_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{profile_name}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_oauth_session(profile_name: str) -> OAuthSession | None:
    """Load a persisted OAuth session, or None if not found."""
    path = _sessions_dir() / f"{profile_name}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return OAuthSession.from_dict(data)
    except (json.JSONDecodeError, KeyError, OSError):
        return None
