"""Tests for the Adapter ABC contract."""

from __future__ import annotations

import pytest

from sol.adapter import Adapter, AdapterMeta, ExecutionResult
from sol.schema import Operation, OperationDetail, Parameter

from conftest import MockAdapter


class TestAdapterABC:
    """Verify that the ABC contract is enforced."""

    def test_cannot_instantiate_bare_abc(self):
        """Adapter ABC cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Adapter()  # type: ignore[abstract]

    def test_incomplete_subclass_raises(self):
        """A subclass missing abstract methods cannot be instantiated."""

        class Partial(Adapter):
            async def protocol_name(self) -> str:
                return "partial"

        with pytest.raises(TypeError):
            Partial()  # type: ignore[abstract]

    def test_mock_adapter_is_adapter(self, mock_adapter: MockAdapter):
        """MockAdapter is a valid Adapter subclass."""
        assert isinstance(mock_adapter, Adapter)


class TestAdapterMeta:
    """Verify AdapterMeta model."""

    def test_default_priority(self):
        meta = AdapterMeta(protocol_name="test")
        assert meta.priority == 100

    def test_custom_priority(self):
        meta = AdapterMeta(protocol_name="grpc", priority=50)
        assert meta.protocol_name == "grpc"
        assert meta.priority == 50


class TestExecutionResult:
    """Verify ExecutionResult model."""

    def test_defaults(self):
        result = ExecutionResult()
        assert result.data is None
        assert result.status_code is None
        assert result.headers is None

    def test_with_data(self):
        result = ExecutionResult(data={"key": "value"}, status_code=200)
        assert result.data == {"key": "value"}
        assert result.status_code == 200


@pytest.mark.asyncio
class TestMockAdapterBehavior:
    """Verify MockAdapter implements the full ABC contract."""

    async def test_protocol_name(self, mock_adapter: MockAdapter):
        assert await mock_adapter.protocol_name() == "mock"

    async def test_priority(self, mock_adapter: MockAdapter):
        assert await mock_adapter.priority() == 200

    async def test_can_handle_mock_url(self, mock_adapter: MockAdapter):
        assert await mock_adapter.can_handle("mock://test") is True

    async def test_cannot_handle_http_url(self, mock_adapter: MockAdapter):
        assert await mock_adapter.can_handle("http://example.com") is False

    async def test_list_operations(self, mock_adapter: MockAdapter):
        ops = await mock_adapter.list_operations("mock://test")
        assert len(ops) == 2
        assert all(isinstance(op, Operation) for op in ops)
        assert ops[0].operation_id == "greet"

    async def test_describe_operation(self, mock_adapter: MockAdapter):
        detail = await mock_adapter.describe_operation("mock://test", "greet")
        assert isinstance(detail, OperationDetail)
        assert detail.operation_id == "greet"
        assert detail.return_type == "object"

    async def test_describe_unknown_operation(self, mock_adapter: MockAdapter):
        from sol.errors import OperationNotFoundError

        with pytest.raises(OperationNotFoundError):
            await mock_adapter.describe_operation("mock://test", "nonexistent")

    async def test_execute(self, mock_adapter: MockAdapter):
        result = await mock_adapter.execute("mock://test", "greet", {"name": "World"})
        assert isinstance(result, ExecutionResult)
        assert result.data["op"] == "greet"
        assert result.data["args"] == {"name": "World"}
        assert result.status_code == 200
