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
    endpoint: str | None = None,
    cache: SchemaCache | None = None,
    ttl: int = 3600,
    cli_name: str = "sol",
) -> OutputEnvelope:
    """List all operations available at *url* via *adapter*.

    Args:
        endpoint: Optional URL to display in output (defaults to url)
    """
    protocol = await adapter.protocol_name()
    cache_key = f"discovery:{url}"
    display_endpoint = endpoint or url

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
                endpoint=display_endpoint,
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
                [f"{cli_name} {display_endpoint} {ops[0].operation_id} key=value"]
                if ops
                else []
            ),
        }
        if cache is not None:
            await cache.put(cache_key, data, protocol, ttl)
        return OutputEnvelope.success(
            kind="discovery",
            protocol=protocol,
            endpoint=display_endpoint,
            data=data,
        )
    except SolError as exc:
        return OutputEnvelope.error(
            code="DISCOVERY_FAILED",
            message=exc.message,
            endpoint=display_endpoint,
            protocol=protocol,
            details=exc.details,
        )


async def inspect(
    adapter: Adapter,
    url: str,
    operation: str,
    *,
    endpoint: str | None = None,
    cache: SchemaCache | None = None,
    ttl: int = 3600,
    cli_name: str = "sol",
) -> OutputEnvelope:
    """Describe a single operation.

    Args:
        endpoint: Optional URL to display in output (defaults to url)
    """
    protocol = await adapter.protocol_name()
    cache_key = f"inspect:{url}:{operation}"
    display_endpoint = endpoint or url

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
                endpoint=display_endpoint,
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
                f"{cli_name} {display_endpoint} {operation} {example_args}"
            ]
        data = detail.model_dump()
        if cache is not None:
            await cache.put(cache_key, data, protocol, ttl)
        return OutputEnvelope.success(
            kind="inspect",
            protocol=protocol,
            endpoint=display_endpoint,
            operation=operation,
            data=data,
        )
    except SolError as exc:
        return OutputEnvelope.error(
            code="INSPECT_FAILED",
            message=exc.message,
            endpoint=display_endpoint,
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
    endpoint: str | None = None,
    auth_headers: dict[str, str] | None = None,
) -> OutputEnvelope:
    """Execute an operation.

    Args:
        endpoint: Optional URL to display in output (defaults to url)
    """
    protocol = await adapter.protocol_name()
    display_endpoint = endpoint or url
    t0 = time.monotonic()

    try:
        result = await adapter.execute(url, operation, args, auth_headers=auth_headers)
        duration = (time.monotonic() - t0) * 1000
        return OutputEnvelope.success(
            kind="invocation",
            protocol=protocol,
            endpoint=display_endpoint,
            operation=operation,
            data=result.data,
            meta=Metadata(duration_ms=duration),
        )
    except SolError as exc:
        return OutputEnvelope.error(
            code="EXECUTION_FAILED",
            message=exc.message,
            endpoint=display_endpoint,
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
    display_url: str | None = None,
) -> OutputEnvelope:
    """Route to discover / inspect / invoke based on operation and flags.

    Decision logic (mirrors uxc):
      - operation is None          → discover
      - operation + api_help       → inspect
      - operation (± args)         → invoke

    Args:
        display_url: Optional URL to display in output (e.g., original datum:// URL)
                     If None, uses `url` for display.
    """
    # Use display_url for user-facing output, url for execution
    endpoint = display_url or url

    if operation is None:
        return await discover(
            adapter, url, endpoint=endpoint, cache=cache, ttl=ttl, cli_name=cli_name
        )
    if api_help and not args:
        return await inspect(
            adapter,
            url,
            operation,
            endpoint=endpoint,
            cache=cache,
            ttl=ttl,
            cli_name=cli_name,
        )
    return await invoke(
        adapter, url, operation, args, endpoint=endpoint, auth_headers=auth_headers
    )
