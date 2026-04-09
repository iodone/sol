"""OutputEnvelope — deterministic JSON output shape."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorInfo(BaseModel):
    """Structured error information within an envelope."""

    code: str
    message: str
    details: str | None = None


class Metadata(BaseModel):
    """Response metadata attached to every envelope."""

    version: str = "v1"
    cached: bool = False
    duration_ms: float | None = None
    adapter: str | None = None
    cache_source: str | None = None
    cache_age_ms: float | None = None
    cache_stale: bool | None = None


class OutputEnvelope(BaseModel):
    """Deterministic JSON output shape mirroring uxc's envelope.

    Every Sol command produces exactly this shape, making output
    predictable for both humans and machines.
    """

    ok: bool
    kind: str | None = None
    protocol: str | None = None
    endpoint: str | None = None
    operation: str | None = None
    data: Any | None = None
    error_info: ErrorInfo | None = Field(
        default=None, alias="error", serialization_alias="error"
    )
    meta: Metadata = Field(default_factory=Metadata)

    model_config = {"populate_by_name": True, "serialize_by_alias": True}

    @classmethod
    def success(
        cls,
        kind: str | None = None,
        protocol: str | None = None,
        endpoint: str | None = None,
        operation: str | None = None,
        data: Any = None,
        *,
        meta: Metadata | None = None,
    ) -> OutputEnvelope:
        """Create a successful envelope."""
        return cls(
            ok=True,
            kind=kind,
            protocol=protocol,
            endpoint=endpoint,
            operation=operation,
            data=data,
            meta=meta or Metadata(),
        )

    @classmethod
    def error(
        cls,
        code: str,
        message: str,
        *,
        kind: str | None = None,
        protocol: str | None = None,
        endpoint: str | None = None,
        operation: str | None = None,
        details: str | None = None,
        meta: Metadata | None = None,
    ) -> OutputEnvelope:
        """Create an error envelope."""
        return cls(
            ok=False,
            kind=kind,
            protocol=protocol,
            endpoint=endpoint,
            operation=operation,
            data=None,
            error_info=ErrorInfo(code=code, message=message, details=details),
            meta=meta or Metadata(),
        )
