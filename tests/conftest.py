"""Shared fixtures and MockAdapter for the Sol test suite."""

from __future__ import annotations

from typing import Any

import pytest

from sol.adapter import Adapter, AdapterMeta, ExecutionResult
from sol.schema import Operation, OperationDetail, Parameter


class MockAdapter(Adapter):
    """A fully-implemented mock adapter for testing.

    Handles URLs starting with ``mock://`` and provides canned operations
    for testing the discovery, inspect, and invoke pipeline.
    """

    _priority = 200
    meta = AdapterMeta(protocol_name="mock", priority=200)

    def __init__(
        self,
        *,
        protocol: str = "mock",
        handles_url: str | None = None,
        operations: list[Operation] | None = None,
    ) -> None:
        self._protocol = protocol
        self._handles_url = handles_url  # if set, only this URL matches
        self._operations = operations or [
            Operation(
                operation_id="greet",
                display_name="Greet",
                description="Say hello",
                parameters=[
                    Parameter(
                        name="name",
                        param_type="string",
                        required=True,
                        description="Name to greet",
                    ),
                ],
            ),
            Operation(
                operation_id="echo",
                display_name="Echo",
                description="Echo back input",
                parameters=[
                    Parameter(name="message", param_type="string", required=True),
                ],
            ),
        ]

    async def protocol_name(self) -> str:
        return self._protocol

    async def priority(self) -> int:
        return self._priority

    async def can_handle(self, url: str) -> bool:
        if self._handles_url is not None:
            return url == self._handles_url
        return url.startswith("mock://")

    async def list_operations(self, url: str) -> list[Operation]:
        return list(self._operations)

    async def describe_operation(self, url: str, op_id: str) -> OperationDetail:
        for op in self._operations:
            if op.operation_id == op_id:
                return OperationDetail(
                    operation_id=op.operation_id,
                    display_name=op.display_name,
                    description=op.description,
                    parameters=op.parameters,
                    return_type="object",
                    input_schema={"type": "object"},
                )
        from sol.errors import OperationNotFoundError

        raise OperationNotFoundError(f"Operation '{op_id}' not found")

    async def execute(
        self,
        url: str,
        op_id: str,
        args: dict[str, Any],
        *,
        auth_headers: dict[str, str] | None = None,
    ) -> ExecutionResult:
        return ExecutionResult(
            data={"op": op_id, "args": args, "url": url},
            status_code=200,
            headers={"content-type": "application/json"},
        )


@pytest.fixture
def mock_adapter() -> MockAdapter:
    """Return a fresh MockAdapter instance."""
    return MockAdapter()


@pytest.fixture
def mock_adapter_factory():
    """Factory fixture for creating MockAdapter with custom params."""

    def _factory(**kwargs: Any) -> MockAdapter:
        return MockAdapter(**kwargs)

    return _factory
