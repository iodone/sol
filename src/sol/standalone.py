"""Standalone CLI generator for individual adapters.

Allows any adapter to become its own independent CLI with full
discover → inspect → invoke pipeline, without going through sol's
protocol detection layer.

Usage in an adapter package::

    # sol_echo/__main__.py
    from sol.standalone import standalone_cli
    from sol_echo.adapter import EchoAdapter

    app = standalone_cli(EchoAdapter(), name="echo")

    if __name__ == "__main__":
        app()
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, Optional

import click
import typer

from sol.adapter import Adapter
from sol.envelope import OutputEnvelope
from sol.formatter import emit_rich
from sol.pipeline import run_pipeline


def _parse_key_value(raw: str) -> tuple[str, Any]:
    """Parse key=value or key:=json."""
    if ":=" in raw:
        key, _, json_str = raw.partition(":=")
        if not key:
            raise typer.BadParameter(f"Empty key in argument: {raw!r}")
        try:
            value = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(
                f"Invalid JSON after ':=' in {raw!r}: {exc}"
            ) from exc
        return key, value
    if "=" not in raw:
        raise typer.BadParameter(f"Argument must be key=value, got: {raw!r}")
    key, _, value = raw.partition("=")
    if not key:
        raise typer.BadParameter(f"Empty key in argument: {raw!r}")
    return key, value


def _set_nested(d: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    current = d
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _build_args(kv_args: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for raw in kv_args:
        key, value = _parse_key_value(raw)
        _set_nested(result, key, value)
    return result


def _emit(envelope: OutputEnvelope, *, fmt: str = "json") -> None:
    if fmt == "table":
        emit_rich(envelope)
    elif fmt == "text":
        if envelope.ok:
            if envelope.data is not None:
                if isinstance(envelope.data, (dict, list)):
                    typer.echo(json.dumps(envelope.data, indent=2))
                else:
                    typer.echo(str(envelope.data))
        else:
            err = envelope.error_info
            msg = err.message if err else "Unknown error"
            typer.echo(f"Error [{err.code if err else 'UNKNOWN'}]: {msg}", err=True)
    else:
        typer.echo(envelope.model_dump_json(indent=2, exclude_none=True))


class _StandaloneCommand(click.Command):
    """Click command that intercepts -h before normal parsing.

    This lets ``echo -h`` trigger discovery and ``echo greet -h``
    trigger inspect, rather than Click consuming -h as a help flag.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Typer may pass extra kwargs like rich_markup_mode that
        # base click.Command doesn't recognize — absorb them.
        kwargs.pop("rich_markup_mode", None)
        kwargs.pop("rich_help_panel", None)
        super().__init__(*args, **kwargs)

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        # Extract -h from args before Click sees it
        if "-h" in args:
            args = [a for a in args if a != "-h"]
            ctx.ensure_object(dict)
            ctx.obj["api_help"] = True
        else:
            ctx.ensure_object(dict)
            ctx.obj["api_help"] = False
        return super().parse_args(ctx, args)


def standalone_cli(
    adapter: Adapter,
    *,
    name: str | None = None,
    default_url: str | None = None,
) -> typer.Typer:
    """Generate a standalone Typer CLI for a single adapter.

    The generated CLI has the same discover → inspect → invoke pipeline
    as ``sol``, but skips protocol detection (adapter is known).

    Args:
        adapter: An instantiated Adapter.
        name: CLI name (used in help text and examples).
        default_url: Default URL when the adapter doesn't need one.
    """
    cli_name = name or "adapter"
    _default_url = default_url or f"{cli_name}://default"

    app = typer.Typer(
        name=cli_name,
        help=(
            f"{cli_name} — standalone API CLI.\n\n"
            f"Usage:\n\n"
            f"  {cli_name} -h                     Discover operations\n\n"
            f"  {cli_name} <operation> -h          Inspect an operation\n\n"
            f"  {cli_name} <operation> key=value   Invoke with arguments"
        ),
        add_completion=False,
        invoke_without_command=True,
        no_args_is_help=False,
        context_settings={"help_option_names": ["--help"]},
    )

    @app.command(cls=_StandaloneCommand)
    def main(
        ctx: typer.Context,
        operation: Optional[str] = typer.Argument(
            None, help="Operation to inspect or invoke"
        ),
        args: Optional[list[str]] = typer.Argument(None, help="key=value arguments"),
        url: str = typer.Option(
            _default_url,
            "--url",
            "-u",
            help="Target URL",
        ),
        format: str = typer.Option(
            "json", "--format", "-f", help="Output format: json, table, text"
        ),
        no_cache: bool = typer.Option(False, "--no-cache", help="Bypass schema cache"),
    ) -> None:
        api_help = ctx.obj.get("api_help", False)

        # No operation and no -h → show help
        if operation is None and not api_help:
            typer.echo(ctx.get_help())
            raise typer.Exit()

        if api_help and format == "json":
            format = "table"

        kv_dict = _build_args(args or [])

        async def _run() -> OutputEnvelope:
            from sol.cache import SchemaCache
            from sol.config import SolSettings

            settings = SolSettings()
            cache: SchemaCache | None = None
            if not no_cache:
                db_path = settings.cache_db_path
                db_path.parent.mkdir(parents=True, exist_ok=True)
                cache = SchemaCache(db_path=str(db_path))
                await cache.initialize()

            try:
                return await run_pipeline(
                    adapter,
                    url,
                    operation,
                    kv_dict,
                    api_help=api_help,
                    cache=cache,
                    ttl=settings.cache_ttl,
                    cli_name=cli_name,
                )
            finally:
                if cache is not None:
                    await cache.close()

        envelope = asyncio.run(_run())
        _emit(envelope, fmt=format)

        if not envelope.ok:
            raise typer.Exit(code=1)

    return app
