"""Tests for the OpenAPI adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from sol.adapters.openapi import OpenAPIAdapter
from sol.schema import Operation

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


SAMPLE_SCHEMA = {
    "openapi": "3.0.0",
    "info": {"title": "Pet Store", "version": "1.0.0"},
    "servers": [{"url": "https://petstore.example.com/v1"}],
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "description": "Returns all pets in the store",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                        "description": "Max number of pets to return",
                    }
                ],
                "responses": {"200": {"content": {"application/json": {}}}},
            }
        },
        "/pets/{petId}": {
            "get": {
                "operationId": "getPet",
                "summary": "Get a pet by ID",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {"200": {"content": {"application/json": {}}}},
            }
        },
    },
}


@pytest.fixture
def adapter() -> OpenAPIAdapter:
    return OpenAPIAdapter()


class TestProtocolIdentity:
    async def test_protocol_name(self, adapter: OpenAPIAdapter) -> None:
        assert await adapter.protocol_name() == "openapi"

    async def test_priority(self, adapter: OpenAPIAdapter) -> None:
        assert await adapter.priority() == 200


class TestDetection:
    async def test_can_handle_openapi(self, adapter: OpenAPIAdapter) -> None:
        """Should detect a valid OpenAPI schema."""
        mock_response = AsyncMock()
        mock_response.is_success = True
        mock_response.json_body = SAMPLE_SCHEMA

        with patch.object(adapter, "_schema_url", return_value="https://example.com"):
            with patch("sol.adapters.openapi.adapter.AsyncHTTPClient") as MockClient:
                instance = MockClient.return_value.__aenter__.return_value
                instance.get = AsyncMock(return_value=mock_response)
                assert await adapter.can_handle("example.com") is True

    async def test_can_handle_non_openapi(self, adapter: OpenAPIAdapter) -> None:
        """Should reject non-OpenAPI responses."""
        mock_response = AsyncMock()
        mock_response.is_success = True
        mock_response.json_body = {"not": "openapi"}

        with patch.object(adapter, "_schema_url", return_value="https://example.com"):
            with patch("sol.adapters.openapi.adapter.AsyncHTTPClient") as MockClient:
                instance = MockClient.return_value.__aenter__.return_value
                instance.get = AsyncMock(return_value=mock_response)
                assert await adapter.can_handle("example.com") is False


class TestDiscovery:
    async def test_list_operations(self, adapter: OpenAPIAdapter) -> None:
        """Should parse all operations from the schema."""
        with patch.object(adapter, "_fetch_schema", return_value=SAMPLE_SCHEMA):
            ops = await adapter.list_operations("example.com")

        assert len(ops) == 2
        op_ids = {op.operation_id for op in ops}
        assert op_ids == {"listPets", "getPet"}

    async def test_describe_operation(self, adapter: OpenAPIAdapter) -> None:
        """Should return operation details with parameters."""
        with patch.object(adapter, "_fetch_schema", return_value=SAMPLE_SCHEMA):
            detail = await adapter.describe_operation("example.com", "listPets")

        assert detail.operation_id == "listPets"
        assert detail.display_name == "List all pets"
        assert len(detail.parameters) == 1
        assert detail.parameters[0].name == "limit"
        assert detail.parameters[0].param_type == "integer"


class TestExecution:
    async def test_execute_get(self, adapter: OpenAPIAdapter) -> None:
        """Should execute a GET operation with path parameters."""
        mock_response = AsyncMock()
        mock_response.json_body = {"id": "123", "name": "Fido"}
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = ""

        with patch.object(adapter, "_fetch_schema", return_value=SAMPLE_SCHEMA):
            with patch("sol.adapters.openapi.adapter.AsyncHTTPClient") as MockClient:
                instance = MockClient.return_value.__aenter__.return_value
                instance.get = AsyncMock(return_value=mock_response)
                result = await adapter.execute(
                    "example.com", "getPet", {"petId": "123"}
                )

        assert result.data == {"id": "123", "name": "Fido"}
        assert result.status_code == 200
