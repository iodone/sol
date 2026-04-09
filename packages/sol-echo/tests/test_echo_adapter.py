"""Tests for the EchoAdapter."""

from __future__ import annotations

import pytest

from sol_echo.adapter import EchoAdapter


@pytest.fixture
def adapter() -> EchoAdapter:
    return EchoAdapter()


class TestCanHandle:
    @pytest.mark.asyncio
    async def test_handles_echo_protocol(self, adapter: EchoAdapter) -> None:
        assert await adapter.can_handle("echo://test") is True

    @pytest.mark.asyncio
    async def test_handles_url_with_echo(self, adapter: EchoAdapter) -> None:
        assert await adapter.can_handle("http://example.com/echo") is True

    @pytest.mark.asyncio
    async def test_rejects_unrelated_url(self, adapter: EchoAdapter) -> None:
        assert await adapter.can_handle("https://api.github.com/repos") is False


class TestListOperations:
    @pytest.mark.asyncio
    async def test_returns_operations(self, adapter: EchoAdapter) -> None:
        ops = await adapter.list_operations("echo://test")
        assert len(ops) == 3
        op_ids = [op.operation_id for op in ops]
        assert "greet" in op_ids
        assert "echo" in op_ids
        assert "ping" in op_ids

    @pytest.mark.asyncio
    async def test_operations_have_descriptions(self, adapter: EchoAdapter) -> None:
        ops = await adapter.list_operations("echo://test")
        for op in ops:
            assert op.description is not None


class TestExecute:
    @pytest.mark.asyncio
    async def test_greet_with_name(self, adapter: EchoAdapter) -> None:
        result = await adapter.execute("echo://test", "greet", {"name": "World"})
        assert result.data["greeting"] == "Hello, World!"
        assert result.data["args"] == {"name": "World"}
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_greet_default_name(self, adapter: EchoAdapter) -> None:
        result = await adapter.execute("echo://test", "greet", {})
        assert result.data["greeting"] == "Hello, World!"

    @pytest.mark.asyncio
    async def test_ping(self, adapter: EchoAdapter) -> None:
        result = await adapter.execute("echo://test", "ping", {})
        assert result.data["response"] == "pong"

    @pytest.mark.asyncio
    async def test_echo_arbitrary_args(self, adapter: EchoAdapter) -> None:
        result = await adapter.execute("echo://test", "echo", {"message": "hi", "extra": "data"})
        assert result.data["echoed_operation"] == "echo"
        assert result.data["echoed_args"]["message"] == "hi"


class TestProtocolMeta:
    @pytest.mark.asyncio
    async def test_protocol_name(self, adapter: EchoAdapter) -> None:
        assert await adapter.protocol_name() == "echo"

    @pytest.mark.asyncio
    async def test_priority(self, adapter: EchoAdapter) -> None:
        assert await adapter.priority() == 50

    @pytest.mark.asyncio
    async def test_describe_known_operation(self, adapter: EchoAdapter) -> None:
        detail = await adapter.describe_operation("echo://test", "greet")
        assert detail.operation_id == "greet"
        assert detail.input_schema is not None

    @pytest.mark.asyncio
    async def test_describe_unknown_operation(self, adapter: EchoAdapter) -> None:
        detail = await adapter.describe_operation("echo://test", "nonexistent")
        assert detail.operation_id == "nonexistent"
