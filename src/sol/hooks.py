"""pluggy hookspecs for lifecycle extensibility."""

from __future__ import annotations

from typing import Any

import pluggy

hookspec = pluggy.HookspecMarker("sol")
hookimpl = pluggy.HookimplMarker("sol")


class SolHookSpecs:
    """Hook specifications for Sol lifecycle events.

    Plugins implement these hooks to extend Sol's behavior at key points
    in the discover → inspect → invoke pipeline.
    """

    @hookspec
    def on_before_discover(self, url: str) -> None:
        """Called before adapter discovery begins for a URL."""

    @hookspec
    def on_after_discover(self, url: str, adapter: Any) -> None:
        """Called after an adapter is selected for a URL."""

    @hookspec
    def on_before_execute(
        self, url: str, operation_id: str, args: dict[str, Any]
    ) -> None:
        """Called before an operation is executed."""

    @hookspec
    def on_after_execute(self, url: str, operation_id: str, result: Any) -> None:
        """Called after an operation finishes executing."""

    @hookspec(firstresult=True)
    def on_before_auth(self, url: str, profile: Any) -> dict[str, str] | None:
        """Called before auth headers are injected into a request.

        Plugins can return a dict of headers to override the default auth
        injection, or None to let the default behavior proceed.

        Args:
            url: The target URL being called.
            profile: The resolved auth Profile (or None if no profile matched).
        """

    @hookspec
    def on_error(self, error: Exception) -> None:
        """Called when an error occurs during any lifecycle phase."""
