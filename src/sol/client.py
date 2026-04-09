"""AsyncHTTPClient — httpx wrapper with connection pooling."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel

from sol import __version__


class HTTPResponse(BaseModel):
    """Typed response object returned by AsyncHTTPClient methods."""

    status_code: int
    headers: dict[str, str]
    body: bytes
    json_body: Any | None = None

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class AsyncHTTPClient:
    """Shared async HTTP transport wrapping httpx.AsyncClient.

    Features:
    - Connection pooling via httpx
    - Configurable timeout
    - Default User-Agent header (sol/<version>)
    - Retry logic with configurable attempts
    - Context manager for resource cleanup
    """

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        base_headers: dict[str, str] | None = None,
        auth_headers: dict[str, str] | None = None,
        max_retries: int = 3,
    ) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        default_headers = {"User-Agent": f"sol/{__version__}"}
        if base_headers:
            default_headers.update(base_headers)
        if auth_headers:
            default_headers.update(auth_headers)
        self._base_headers = default_headers
        self._client: httpx.AsyncClient | None = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                headers=self._base_headers,
            )
        return self._client

    async def __aenter__(self) -> AsyncHTTPClient:
        self._ensure_client()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying httpx client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        json: Any | None = None,
        content: bytes | None = None,
    ) -> HTTPResponse:
        """Send an HTTP request with retry logic."""
        client = self._ensure_client()
        last_exc: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                resp = await client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                    content=content,
                )
                json_body = None
                ct = resp.headers.get("content-type", "")
                if "json" in ct:
                    try:
                        json_body = resp.json()
                    except Exception:
                        pass
                return HTTPResponse(
                    status_code=resp.status_code,
                    headers=dict(resp.headers),
                    body=resp.content,
                    json_body=json_body,
                )
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                last_exc = exc
                if attempt == self._max_retries - 1:
                    break
                continue

        raise last_exc or RuntimeError("Request failed after retries")

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> HTTPResponse:
        """Send a GET request."""
        return await self.request("GET", url, headers=headers, params=params)

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        json: Any | None = None,
        content: bytes | None = None,
    ) -> HTTPResponse:
        """Send a POST request."""
        return await self.request(
            "POST", url, headers=headers, params=params, json=json, content=content
        )
