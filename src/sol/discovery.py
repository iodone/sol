"""Entry-point scanning and protocol detection cascade."""

from __future__ import annotations

import importlib.metadata
from typing import Any

import pluggy
from loguru import logger

from sol.adapter import Adapter
from sol.errors import ProtocolDetectionError
from sol.hooks import SolHookSpecs


class AdapterRegistry:
    """Discovers adapters via entry points and runs protocol detection.

    Scans ``importlib.metadata.entry_points(group='sol.adapters')`` to find
    installed adapter plugins, instantiates them, and provides a priority-sorted
    detection cascade.
    """

    def __init__(self, plugin_manager: pluggy.PluginManager | None = None) -> None:
        self._pm = plugin_manager
        self.adapters: list[Adapter] = []
        self.discover_adapters()

    def discover_adapters(self) -> list[Adapter]:
        """Scan entry points and instantiate all installed adapters.

        Returns the list of discovered adapter instances sorted by priority
        (highest first).
        """
        self.adapters = []
        eps = importlib.metadata.entry_points(group="sol.adapters")
        for ep in eps:
            try:
                adapter_cls = ep.load()
                adapter = adapter_cls()
                if isinstance(adapter, Adapter):
                    self.adapters.append(adapter)
                    logger.info(
                        "Discovered adapter: %s (entry point: %s)",
                        type(adapter).__name__,
                        ep.name,
                    )
                else:
                    logger.warning(
                        "Entry point %s did not produce an Adapter instance, got %s",
                        ep.name,
                        type(adapter).__name__,
                    )
            except Exception:
                logger.exception("Failed to load adapter from entry point: %s", ep.name)
        return self.adapters

    def _sorted_adapters(self) -> list[tuple[Adapter, int]]:
        """Return adapters paired with their priority, sorted descending."""
        priorities: list[tuple[Adapter, int]] = []
        for adapter in self.adapters:
            # priority() is async on the ABC, but for sorting we need sync access.
            # Adapters should also expose priority via AdapterMeta or a class attr.
            # Fall back to a sensible default.
            prio = getattr(adapter, "_priority", None) or getattr(adapter, "meta", None)
            if prio is not None and hasattr(prio, "priority"):
                prio = prio.priority
            elif isinstance(prio, int):
                pass
            else:
                prio = 100
            priorities.append((adapter, prio))
        priorities.sort(key=lambda pair: pair[1], reverse=True)
        return priorities

    async def detect_protocol(self, url: str) -> Adapter:
        """Run the detection cascade: try adapters by descending priority.

        The first adapter whose ``can_handle(url)`` returns True wins.

        Raises:
            ProtocolDetectionError: If no adapter can handle the URL.
        """
        if self._pm:
            self._pm.hook.on_before_discover(url=url)

        attempted: list[str] = []
        for adapter, _prio in self._sorted_adapters():
            name = type(adapter).__name__
            attempted.append(name)
            try:
                if await adapter.can_handle(url):
                    if self._pm:
                        self._pm.hook.on_after_discover(url=url, adapter=adapter)
                    return adapter
            except Exception:
                logger.exception(
                    "Adapter %s raised during can_handle for %s", name, url
                )

        msg = (
            f"No adapter could handle URL: {url}\n"
            f"Attempted adapters: {', '.join(attempted) if attempted else '(none installed)'}"
        )
        error = ProtocolDetectionError(msg)
        if self._pm:
            self._pm.hook.on_error(error=error)
        raise error

    async def get_adapter(self, url: str) -> Adapter:
        """Return the matched adapter instance for a URL.

        Convenience wrapper around :meth:`detect_protocol`.
        """
        return await self.detect_protocol(url)
