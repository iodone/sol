"""Typer CLI — discover, inspect, and invoke commands."""

from __future__ import annotations

import asyncio
import fnmatch
import json
import sys
from typing import Any, Optional

import typer

from sol.auth.cli import auth_app
from sol.cache_cli import cache_app
from sol.envelope import OutputEnvelope
from sol.errors import SolError
from sol.formatter import emit_rich, get_console

import click
from typer.core import TyperGroup


class SolGroup(TyperGroup):
    """Custom Click group that routes subcommands before consuming positional args.

    This solves the Typer limitation where invoke_without_command=True with
    positional arguments would consume subcommand names as args.
    """

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        # When the first non-option arg is a known subcommand, extract it and
        # all remaining args into protected_args so the callback doesn't consume them.
        cmds = self.list_commands(ctx)
        for i, arg in enumerate(args):
            if arg.startswith("-"):
                continue
            if arg in cmds:
                # Split: options before the command go to the callback,
                # the command and everything after go to protected_args.
                subcmd_args = args[i:]
                # Temporarily disable no_args_is_help so parsing empty before-args works
                saved = self.no_args_is_help
                self.no_args_is_help = False
                ctx.allow_interspersed_args = False
                result = super().parse_args(ctx, args[:i])
                self.no_args_is_help = saved
                ctx._protected_args = subcmd_args + ctx.protected_args
                return result
            break
        ctx.allow_interspersed_args = True
        return super().parse_args(ctx, args)


app = typer.Typer(
    name="sol",
    help="Universal API CLI — discover, inspect, and invoke any protocol.\n\n"
    "Usage:\n\n"
    "  sol <URL> -h                 Discover operations\n\n"
    "  sol <URL> <operation> -h     Inspect an operation\n\n"
    "  sol <URL> <operation> k=v    Invoke with arguments",
    add_completion=False,
    invoke_without_command=True,
    no_args_is_help=True,
    cls=SolGroup,
    context_settings={"help_option_names": ["--help"]},
)


app.add_typer(auth_app, name="auth")
app.add_typer(cache_app, name="cache")


def parse_key_value(raw: str) -> tuple[str, Any]:
    """Parse a single key=value or key:=json argument.

    Returns (key, value) where key may be dotted (e.g. 'user.name').
    - key=value  → value stays as string
    - key:=json  → value parsed as JSON (int, bool, list, dict, etc.)
    """
    # Check for := (JSON typed) before = (string)
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


def set_nested(d: dict[str, Any], dotted_key: str, value: Any) -> None:
    """Set a value in a nested dict using dotted key notation.

    Example: set_nested({}, 'user.name', 'foo') → {'user': {'name': 'foo'}}
    """
    parts = dotted_key.split(".")
    current = d
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def build_args_dict(kv_args: list[str]) -> dict[str, Any]:
    """Parse a list of key=value strings into a (potentially nested) dict."""
    result: dict[str, Any] = {}
    for raw in kv_args:
        key, value = parse_key_value(raw)
        set_nested(result, key, value)
    return result


def read_data_input(data: str | None) -> dict[str, Any] | None:
    """Read JSON body from --data string or stdin (when --data is '-')."""
    if data is None:
        return None
    if data == "-":
        raw = sys.stdin.read()
    else:
        raw = data
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON in --data: {exc}") from exc
    if not isinstance(parsed, dict):
        raise typer.BadParameter("--data JSON must be an object (dict)")
    return parsed


def emit(envelope: OutputEnvelope, *, fmt: str = "json") -> None:
    """Print an OutputEnvelope to stdout.

    Formats:
      - json: machine-readable JSON (default when -h is not used)
      - table: Rich tables/panels for human-readable output (default when -h is used)
      - text: plain text fallback
    """
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


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    url: Optional[str] = typer.Argument(None, help="Target URL to discover/invoke"),
    operation: Optional[str] = typer.Argument(
        None, help="Operation to inspect or invoke"
    ),
    args: Optional[list[str]] = typer.Argument(
        None, help="key=value arguments for the operation"
    ),
    data: Optional[str] = typer.Option(
        None, "--data", "-d", help="JSON body string, or '-' to read from stdin"
    ),
    format: str = typer.Option(
        "json", "--format", "-f", help="Output format: json, table, or text"
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass schema cache"),
    credential: Optional[str] = typer.Option(
        None, "--credential", "-c", help="Auth profile name to use"
    ),
    verbose: int = typer.Option(
        0, "--verbose", "-v", count=True, help="Increase logging verbosity"
    ),
    api_help: bool = typer.Option(
        False, "-h", hidden=True, help="Discover or inspect the target endpoint"
    ),
) -> None:
    """Discover, inspect, and invoke API operations.

    \b
    Examples:
      sol https://api.example.com -h              Discover operations
      sol https://api.example.com listUsers -h     Inspect operation
      sol https://api.example.com getUser id=42    Invoke with args
    """
    if ctx.invoked_subcommand is not None:
        return
    if url is None:
        raise typer.Exit()

    # Configure logging based on verbosity
    from loguru import logger

    logger.remove()  # Remove default handler
    if verbose >= 2:
        logger.add(sys.stderr, level="DEBUG", format="{name} {level}: {message}")
    elif verbose >= 1:
        logger.add(sys.stderr, level="INFO", format="{name} {level}: {message}")
    else:
        logger.add(sys.stderr, level="WARNING", format="{name} {level}: {message}")

    # When -h is used and format is still default "json", switch to "table"
    if api_help and format == "json":
        format = "table"

    # Build argument dict from key=value positionals and --data
    kv_dict = build_args_dict(args or [])
    data_dict = read_data_input(data)
    if data_dict:
        # --data values are merged under kv args (kv args take precedence)
        merged = {**data_dict, **kv_dict}
    else:
        merged = kv_dict

    # Run the async pipeline
    use_spinner = format == "table"
    envelope = asyncio.run(
        _run(
            url,
            operation,
            merged,
            no_cache=no_cache,
            credential=credential,
            use_spinner=use_spinner,
            api_help=api_help,
        )
    )
    emit(envelope, fmt=format)

    if not envelope.ok:
        raise typer.Exit(code=1)


async def _run(
    url: str,
    operation: str | None,
    args: dict[str, Any],
    *,
    no_cache: bool = False,
    credential: str | None = None,
    use_spinner: bool = False,
    api_help: bool = False,
) -> OutputEnvelope:
    """Execute the discover → inspect → invoke pipeline."""
    from sol import SolFramework
    from sol.cache import SchemaCache
    from sol.config import SolSettings
    from sol.envelope import Metadata

    framework = SolFramework()
    settings = SolSettings()

    # Initialize cache unless --no-cache
    cache: SchemaCache | None = None
    if not no_cache:
        db_path = settings.cache_db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        cache = SchemaCache(db_path=str(db_path))
        await cache.initialize()

    try:
        return await _run_pipeline(
            framework,
            cache,
            url,
            operation,
            args,
            settings=settings,
            credential=credential,
            use_spinner=use_spinner,
            api_help=api_help,
        )
    finally:
        if cache is not None:
            await cache.close()


async def _run_pipeline(
    framework: Any,
    cache: Any,
    url: str,
    operation: str | None,
    args: dict[str, Any],
    *,
    settings: Any = None,
    credential: str | None = None,
    use_spinner: bool = False,
    api_help: bool = False,
) -> OutputEnvelope:
    """Inner pipeline with protocol detection, auth, then core pipeline."""
    from contextlib import contextmanager
    from urllib.parse import urlparse

    from rich.status import Status

    from sol.auth import resolve_auth_headers
    from sol.auth.binding import AuthBindings
    from sol.formatter import _is_tty, get_console
    from sol.pipeline import run_pipeline
    from loguru import logger

    @contextmanager
    def spinner(message: str):
        """Show a Rich Status spinner when use_spinner=True and stdout is a TTY."""
        if use_spinner and _is_tty():
            console = get_console(stderr=True)
            with Status(message, console=console, spinner="dots"):
                yield
        else:
            yield

    # --- Alias resolution (before protocol detection) ---
    original_url = url
    parsed = urlparse(url)
    if parsed.hostname:
        bindings = AuthBindings()
        bindings.load()
        real_host = bindings.resolve_alias(parsed.hostname)
        if real_host:
            # Keep original scheme (datum://, echo://), only replace hostname
            # datum://staging.10122/path → datum://api-gateway.dptest.pt.xiaomi.com/path
            port_part = f":{parsed.port}" if parsed.port else ""
            path_part = parsed.path or ""
            query_part = f"?{parsed.query}" if parsed.query else ""
            url = f"{parsed.scheme}://{real_host}{port_part}{path_part}{query_part}"
            logger.debug("Alias '{}' resolved to '{}'", parsed.hostname, real_host)

    try:
        with spinner("Detecting protocol…"):
            adapter = await framework.registry.detect_protocol(url)
    except SolError as exc:
        return OutputEnvelope.error(
            code="NO_ADAPTER",
            message=exc.message,
            endpoint=original_url,
            details=exc.details,
        )

    # --- Find matched binding for scheme inference ---
    matched_binding_host: str | None = None
    try:
        from sol.auth.binding import AuthBindings

        bindings = AuthBindings()
        bindings.load()

        # Find matched binding to infer scheme
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if hostname:
            real_host = bindings.resolve_alias(hostname)
            if real_host:
                hostname = real_host.lower()

            # Find matching binding (ignore scheme for now, just match hostname)
            for binding in bindings._bindings:
                binding_host = binding.host.lower()
                if "://" in binding_host:
                    # Scheme-aware binding: extract hostname
                    binding_parsed = urlparse(binding_host)
                    if fnmatch.fnmatch(hostname, binding_parsed.hostname or ""):
                        matched_binding_host = binding_host
                        break
                elif fnmatch.fnmatch(hostname, binding_host):
                    # Scheme-agnostic binding: use default https
                    matched_binding_host = f"https://{binding_host}"
                    break
    except Exception:
        # Binding resolution is best-effort for scheme inference
        pass

    # --- Scheme normalization for HTTP-based custom protocols ---
    # Use scheme from matched binding (if available), otherwise default to https
    execution_url = url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https", "ws", "wss"):
        # Infer scheme from binding or default to https
        target_scheme = "https"
        if matched_binding_host and "://" in matched_binding_host:
            binding_parsed = urlparse(matched_binding_host)
            target_scheme = binding_parsed.scheme or "https"

        port_part = f":{parsed.port}" if parsed.port else ""
        path_part = parsed.path or ""
        query_part = f"?{parsed.query}" if parsed.query else ""
        execution_url = (
            f"{target_scheme}://{parsed.netloc}{port_part}{path_part}{query_part}"
        )
        logger.debug(
            "Normalized custom scheme '{}' to {}:// (inferred from binding)",
            parsed.scheme,
            target_scheme,
        )

    # --- Auth resolution (after scheme normalization) ---
    auth_headers: dict[str, str] | None = None
    try:
        auth_headers, profile = await resolve_auth_headers(
            execution_url, credential=credential
        )

        # Fire on_before_auth hook — plugins can override headers
        hook_headers = framework.hook.on_before_auth(url=execution_url, profile=profile)
        if hook_headers is not None:
            auth_headers = hook_headers
    except SolError as exc:
        return OutputEnvelope.error(
            code="AUTH_FAILED",
            message=exc.message,
            endpoint=original_url,
            details=exc.details,
        )

    ttl = settings.cache_ttl if settings else 3600

    return await run_pipeline(
        adapter,
        execution_url,  # Use normalized URL for execution
        operation,
        args,
        api_help=api_help,
        cache=cache,
        ttl=ttl,
        auth_headers=auth_headers,
        cli_name="sol",
        display_url=original_url,  # Use original URL for display
    )
