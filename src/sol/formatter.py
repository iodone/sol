"""Rich output formatting for human-readable modes."""

from __future__ import annotations

import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sol.envelope import OutputEnvelope


def _is_tty() -> bool:
    """Check if stdout is a TTY."""
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def get_console(*, stderr: bool = False) -> Console:
    """Get a Rich Console, forcing no color when not a TTY."""
    stream = sys.stderr if stderr else sys.stdout
    force_terminal = None if _is_tty() else False
    return Console(file=stream, force_terminal=force_terminal)


def render_discovery_table(envelope: OutputEnvelope) -> None:
    """Render operation list as a Rich table (discovery mode with -h)."""
    console = get_console()
    ops = envelope.data or []

    table = Table(
        title=f"Operations — {envelope.endpoint or 'unknown'}",
        title_style="bold cyan",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("ID", style="green", no_wrap=True)
    table.add_column("Description", style="dim")

    for op in ops:
        op_id = op.get("operation_id", "") if isinstance(op, dict) else str(op)
        desc = op.get("description", "") if isinstance(op, dict) else ""
        table.add_row(op_id, desc or "—")

    if envelope.protocol:
        console.print(f"[dim]Protocol:[/dim] [bold]{envelope.protocol}[/bold]")
    console.print(table)
    if envelope.meta and envelope.meta.cached:
        console.print("[dim]  (cached)[/dim]")


def render_inspect_panel(envelope: OutputEnvelope) -> None:
    """Render operation details as a formatted panel with parameters table."""
    console = get_console()
    detail = envelope.data or {}

    op_id = detail.get("operation_id", envelope.operation or "unknown")
    display_name = detail.get("display_name") or op_id
    description = detail.get("description", "")
    return_type = detail.get("return_type", "")
    params = detail.get("parameters", [])

    # Build content lines
    lines: list[str] = []
    if description:
        lines.append(f"[dim]{description}[/dim]")
    if return_type:
        lines.append(f"[bold]Returns:[/bold] {return_type}")
    if envelope.protocol:
        lines.append(f"[bold]Protocol:[/bold] {envelope.protocol}")

    # Parameters table
    if params:
        param_table = Table(
            show_header=True,
            header_style="bold yellow",
            box=None,
            pad_edge=False,
        )
        param_table.add_column("Name", style="green")
        param_table.add_column("Type", style="cyan")
        param_table.add_column("Required", style="red")
        param_table.add_column("Description", style="dim")

        for p in params:
            name = p.get("name", "")
            ptype = p.get("param_type", "string")
            req = "yes" if p.get("required") else "no"
            pdesc = p.get("description", "") or "—"
            param_table.add_row(name, ptype, req, pdesc)

    panel_content = "\n".join(lines)
    panel = Panel(
        panel_content,
        title=f"[bold]{display_name}[/bold]",
        subtitle=f"[dim]{op_id}[/dim]" if display_name != op_id else None,
        border_style="blue",
    )
    console.print(panel)

    if params:
        console.print()
        console.print("[bold]Parameters:[/bold]")
        console.print(param_table)

    if envelope.meta and envelope.meta.cached:
        console.print("[dim]  (cached)[/dim]")


def render_error_panel(envelope: OutputEnvelope) -> None:
    """Render error envelope as a styled Rich panel."""
    console = get_console(stderr=True)
    err = envelope.error_info

    code = err.code if err else "UNKNOWN"
    message = err.message if err else "Unknown error"
    details = err.details if err else None

    lines = [f"[bold white]{message}[/bold white]"]
    if details:
        lines.append(f"\n[dim]{details}[/dim]")
    if envelope.endpoint:
        lines.append(f"\n[bold]Endpoint:[/bold] {envelope.endpoint}")
    if envelope.protocol:
        lines.append(f"[bold]Protocol:[/bold] {envelope.protocol}")

    panel = Panel(
        "\n".join(lines),
        title=f"[bold red]{code}[/bold red]",
        border_style="red",
    )
    console.print(panel)


def emit_rich(envelope: OutputEnvelope) -> None:
    """Route an envelope to the appropriate Rich renderer."""
    if not envelope.ok:
        render_error_panel(envelope)
        return

    kind = envelope.kind
    if kind == "discovery":
        render_discovery_table(envelope)
    elif kind == "inspect":
        render_inspect_panel(envelope)
    else:
        # Fallback: pretty-print data
        console = get_console()
        if envelope.data is not None:
            console.print(envelope.data)
