"""Operation, Parameter, and OperationDetail models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Parameter(BaseModel):
    """Describes a single parameter for an operation."""

    name: str
    param_type: str = "string"
    required: bool = False
    description: str | None = None


class Operation(BaseModel):
    """Summary of a callable operation exposed by a protocol adapter."""

    operation_id: str
    display_name: str | None = None
    description: str | None = None
    parameters: list[Parameter] = []


class OperationDetail(Operation):
    """Extended operation info including return type and input schema."""

    return_type: str | None = None
    input_schema: dict[str, Any] | None = None
