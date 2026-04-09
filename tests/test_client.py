"""Tests for AsyncHTTPClient retry logic and behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from sol.client import AsyncHTTPClient, HTTPResponse


class TestHTTPResponse:
    """Test HTTPResponse model."""

    def test_is_success_200(self):
        resp = HTTPResponse(status_code=200, headers={}, body=b"ok")
        assert resp.is_success is True

    def test_is_success_204(self):
        resp = HTTPResponse(status_code=204, headers={}, body=b"")
        assert resp.is_success is True

    def test_is_not_success_404(self):
        resp = HTTPResponse(status_code=404, headers={}, body=b"not found")
        assert resp.is_success is False

    def test_is_not_success_500(self):
        resp = HTTPResponse(status_code=500, headers={}, body=b"error")
        assert resp.is_success is False

    def test_text_property(self):
        resp = HTTPResponse(status_code=200, headers={}, body=b"hello world")
        assert resp.text == "hello world"

    def test_json_body(self):
        resp = HTTPResponse(
            status_code=200, headers={}, body=b'{"k":"v"}', json_body={"k": "v"}
        )
        assert resp.json_body == {"k": "v"}


@pytest.mark.asyncio
class TestAsyncHTTPClientRetry:
    """Test retry logic."""

    async def test_successful_request_no_retry(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"result": "ok"}
        mock_response.content = b'{"result": "ok"}'

        client = AsyncHTTPClient(max_retries=3)
        mock_httpx = AsyncMock(return_value=mock_response)
        client._client = MagicMock()
        client._client.request = mock_httpx

        resp = await client.request("GET", "http://example.com/api")
        assert resp.status_code == 200
        assert resp.json_body == {"result": "ok"}
        assert mock_httpx.call_count == 1

    async def test_retry_on_connect_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b"ok"

        client = AsyncHTTPClient(max_retries=3)
        mock_httpx = AsyncMock(
            side_effect=[
                httpx.ConnectError("conn fail"),
                httpx.ConnectError("conn fail"),
                mock_response,
            ]
        )
        client._client = MagicMock()
        client._client.request = mock_httpx

        resp = await client.request("GET", "http://example.com/api")
        assert resp.status_code == 200
        assert mock_httpx.call_count == 3

    async def test_exhausted_retries_raises(self):
        client = AsyncHTTPClient(max_retries=2)
        mock_httpx = AsyncMock(
            side_effect=[httpx.ConnectError("fail"), httpx.ConnectError("fail")]
        )
        client._client = MagicMock()
        client._client.request = mock_httpx

        with pytest.raises(httpx.ConnectError):
            await client.request("GET", "http://example.com")

    async def test_retry_on_read_timeout(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b"ok"

        client = AsyncHTTPClient(max_retries=2)
        mock_httpx = AsyncMock(
            side_effect=[httpx.ReadTimeout("timeout"), mock_response]
        )
        client._client = MagicMock()
        client._client.request = mock_httpx

        resp = await client.request("GET", "http://example.com")
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestAsyncHTTPClientContextManager:
    """Test context manager protocol."""

    async def test_context_manager(self):
        async with AsyncHTTPClient() as client:
            assert client._client is not None
        assert client._client is None


@pytest.mark.asyncio
class TestAsyncHTTPClientHeaders:
    """Test header configuration."""

    async def test_default_user_agent(self):
        client = AsyncHTTPClient()
        assert "sol/" in client._base_headers["User-Agent"]

    async def test_custom_base_headers(self):
        client = AsyncHTTPClient(base_headers={"X-Custom": "val"})
        assert client._base_headers["X-Custom"] == "val"
        assert "User-Agent" in client._base_headers

    async def test_auth_headers_merged(self):
        client = AsyncHTTPClient(auth_headers={"Authorization": "Bearer tok"})
        assert client._base_headers["Authorization"] == "Bearer tok"
