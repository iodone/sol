"""Core pipeline — discover, inspect, invoke.

This module contains the protocol-agnostic pipeline logic that both
``sol`` (the multi-protocol CLI) and standalone adapter CLIs share.
No Typer dependency here — pure async functions operating on Adapter instances.
"""

from __future__ import annotations

import time
from typing import Any

from sol.adapter import Adapter
from sol.cache import SchemaCache
from sol.envelope import Metadata, OutputEnvelope
from sol.errors import SolError


async def discover(
    adapter: Adapter,
    url: str,
    *,
    cache: SchemaCache | None = None,
    ttl: int = 3600,
    cli_name: str = "sol",
) -> OutputEnvelope:
    """List all operations available at *url* via *adapter*."""
    protocol = await adapter.protocol_name()
    cache_key = f"discovery:{url}"

    if cache is not None:
        entry = await cache.get(cache_key, stale_ok=True)
        if entry is not None:
            meta = Metadata(
                cached=True,
                cache_source=entry.cache_source,
                cache_age_ms=int(entry.cache_age_ms),
                cache_stale=entry.stale,
            )
            return OutputEnvelope.success(
                kind="discovery",
                protocol=protocol,
                endpoint=url,
                data=entry.schema_data,
                meta=meta,
            )

    try:
        ops = await adapter.list_operations(url)
        op_dicts = [op.model_dump() for op in ops]
        data = {
            "operations": op_dicts,
            "count": len(op_dicts),
            "examples": (
                [f"{cli_name} {url} {ops[0].operation_id} key=value"] if ops else []
            ),
        }
        if cache is not None:
            await cache.put(cache_key, data, protocol, ttl)
        return OutputEnvelope.success(
            kind="discovery",
            protocol=protocol,
            endpoint=url,
            data=data,
        )
    except SolError as exc:
        return OutputEnvelope.error(
            code="DISCOVERY_FAILED",
            message=exc.message,
            endpoint=url,
            protocol=protocol,
            details=exc.details,
        )


async def inspect(
    adapter: Adapter,
    url: str,
    operation: str,
    *,
    cache: SchemaCache | None = None,
    ttl: int = 3600,
    cli_name: str = "sol",
) -> OutputEnvelope:
    """Describe a single operation."""
    protocol = await adapter.protocol_name()
    cache_key = f"inspect:{url}:{operation}"

    if cache is not None:
        entry = await cache.get(cache_key, stale_ok=True)
        if entry is not None:
            meta = Metadata(
                cached=True,
                cache_source=entry.cache_source,
                cache_age_ms=int(entry.cache_age_ms),
                cache_stale=entry.stale,
            )
            return OutputEnvelope.success(
                kind="inspect",
                protocol=protocol,
                endpoint=url,
                operation=operation,
                data=entry.schema_data,
                meta=meta,
            )

    try:
        detail = await adapter.describe_operation(url, operation)
        if not detail.invocation_examples:
            if detail.parameters:
                example_args = (
                    " ".join(f"{p.name}=value" for p in detail.parameters if p.required)
                    or "key=value"
                )
            else:
                example_args = "key=value"
            detail.invocation_examples = [
                f"{cli_name} {url} {operation} {example_args}"
            ]
        data = detail.model_dump()
        if cache is not None:
            await cache.put(cache_key, data, protocol, ttl)
        return OutputEnvelope.success(
            kind="inspect",
            protocol=protocol,
            endpoint=url,
            operation=operation,
            data=data,
        )
    except SolError as exc:
        return OutputEnvelope.error(
            code="INSPECT_FAILED",
            message=exc.message,
            endpoint=url,
            operation=operation,
            protocol=protocol,
            details=exc.details,
        )


async def invoke(
    adapter: Adapter,
    url: str,
    operation: str,
    args: dict[str, Any],
    *,
    auth_headers: dict[str, str] | None = None,
) -> OutputEnvelope:
    """Execute an operation."""
    protocol = await adapter.protocol_name()
    t0 = time.monotonic()

    try:
        result = await adapter.execute(url, operation, args, auth_headers=auth_headers)
        duration = (time.monotonic() - t0) * 1000
        return OutputEnvelope.success(
            kind="invocation",
            protocol=protocol,
            endpoint=url,
            operation=operation,
            data=result.data,
            meta=Metadata(duration_ms=duration),
        )
    except SolError as exc:
        return OutputEnvelope.error(
            code="EXECUTION_FAILED",
            message=exc.message,
            endpoint=url,
            operation=operation,
            protocol=protocol,
            details=exc.details,
        )


async def run_pipeline(
    adapter: Adapter,
    url: str,
    operation: str | None,
    args: dict[str, Any],
    *,
    api_help: bool = False,
    cache: SchemaCache | None = None,
    ttl: int = 3600,
    auth_headers: dict[str, str] | None = None,
    cli_name: str = "sol",
) -> OutputEnvelope:
    """Route to discover / inspect / invoke based on operation and flags.

    Decision logic (mirrors uxc):
      - operation is None          → discover
      - operation + api_help       → inspect
      - operation (± args)         → invoke
    """
    if operation is None:
        return await discover(adapter, url, cache=cache, ttl=ttl, cli_name=cli_name)
    if api_help and not args:
        return await inspect(
            adapter, url, operation, cache=cache, ttl=ttl, cli_name=cli_name
        )
    return await invoke(adapter, url, operation, args, auth_headers=auth_headers)
