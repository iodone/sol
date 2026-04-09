"""Adapter ABC — the contract all protocol plugins implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from sol.schema import Operation, OperationDetail


class ExecutionResult(BaseModel):
    """Result returned by Adapter.execute()."""

    data: Any = None
    status_code: int | None = None
    headers: dict[str, str] | None = None


class AdapterMeta(BaseModel):
    """Metadata about an adapter, used for discovery ordering."""

    protocol_name: str
    priority: int = 100


class Adapter(ABC):
    """Abstract base class that every protocol adapter must implement.

    Adapters are discovered via entry points and sorted by priority
    (higher = tried first) during protocol detection.
    """

    @abstractmethod
    async def protocol_name(self) -> str:
        """Return the protocol this adapter handles (e.g. 'openapi', 'graphql')."""

    @abstractmethod
    async def priority(self) -> int:
        """Return priority for detection cascade (higher = tried first)."""

    @abstractmethod
    async def can_handle(self, url: str) -> bool:
        """Return True if this adapter can handle the given URL."""

    @abstractmethod
    async def list_operations(self, url: str) -> list[Operation]:
        """List all operations available at the given URL."""

    @abstractmethod
    async def describe_operation(self, url: str, op_id: str) -> OperationDetail:
        """Return detailed info about a specific operation."""

    @abstractmethod
    async def execute(
        self,
        url: str,
        op_id: str,
        args: dict[str, Any],
        *,
        auth_headers: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """Execute an operation and return the result.

        Args:
            url: The target URL.
            op_id: The operation identifier.
            args: The invocation arguments.
            auth_headers: Optional auth headers to inject into HTTP requests.
        """
