"""EchoAdapter — minimal adapter that validates the Sol plugin pipeline end-to-end."""

from __future__ import annotations

from typing import Any

from sol.adapter import Adapter, ExecutionResult
from sol.schema import Operation, OperationDetail, Parameter

# Hardcoded operations this adapter exposes
_ECHO_OPERATIONS = [
    Operation(
        operation_id="greet",
        display_name="Greet",
        description="Echo back a greeting with the provided name",
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
        description="Echo back all provided arguments",
        parameters=[
            Parameter(
                name="message",
                param_type="string",
                required=False,
                description="Message to echo",
            ),
        ],
    ),
    Operation(
        operation_id="ping",
        display_name="Ping",
        description="Return a simple pong response",
        parameters=[],
    ),
]

_ECHO_DETAILS: dict[str, OperationDetail] = {
    "greet": OperationDetail(
        operation_id="greet",
        display_name="Greet",
        description="Echo back a greeting with the provided name",
        parameters=[
            Parameter(
                name="name",
                param_type="string",
                required=True,
                description="Name to greet",
            ),
        ],
        return_type="object",
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    ),
    "echo": OperationDetail(
        operation_id="echo",
        display_name="Echo",
        description="Echo back all provided arguments",
        parameters=[
            Parameter(
                name="message",
                param_type="string",
                required=False,
                description="Message to echo",
            ),
        ],
        return_type="object",
        input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
    ),
    "ping": OperationDetail(
        operation_id="ping",
        display_name="Ping",
        description="Return a simple pong response",
        parameters=[],
        return_type="object",
        input_schema={"type": "object", "properties": {}},
    ),
}


class EchoAdapter(Adapter):
    """Minimal adapter that handles echo:// URLs and echoes back arguments.

    Used to validate the entire Sol plugin pipeline end-to-end:
    entry-point discovery → protocol detection → operation listing → execution.
    """

    _priority = 50

    async def protocol_name(self) -> str:
        return "echo"

    async def priority(self) -> int:
        return 50

    async def can_handle(self, url: str) -> bool:
        return url.startswith("echo://") or "echo" in url.lower()

    async def list_operations(self, url: str) -> list[Operation]:
        return list(_ECHO_OPERATIONS)

    async def describe_operation(self, url: str, op_id: str) -> OperationDetail:
        if op_id in _ECHO_DETAILS:
            return _ECHO_DETAILS[op_id]
        return OperationDetail(
            operation_id=op_id,
            display_name=op_id.title(),
            description=f"Unknown echo operation: {op_id}",
            parameters=[],
        )

    async def execute(
        self,
        url: str,
        op_id: str,
        args: dict[str, Any],
        *,
        auth_headers: dict[str, str] | None = None,
    ) -> ExecutionResult:
        if op_id == "greet":
            name = args.get("name", "World")
            data = {"greeting": f"Hello, {name}!", "args": args}
        elif op_id == "ping":
            data = {"response": "pong"}
        else:
            data = {"echoed_operation": op_id, "echoed_args": args, "url": url}
        return ExecutionResult(data=data, status_code=200)
