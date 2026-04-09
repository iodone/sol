"""Tests for AdapterRegistry discovery and protocol detection."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from sol.adapter import Adapter
from sol.discovery import AdapterRegistry
from sol.errors import ProtocolDetectionError

from conftest import MockAdapter


class TestAdapterRegistryInit:
    """Test registry initialization and adapter scanning."""

    def test_empty_registry_when_no_entry_points(self):
        """With no entry points installed, registry has no adapters."""
        with patch("sol.discovery.importlib.metadata.entry_points", return_value=[]):
            registry = AdapterRegistry()
            assert registry.adapters == []

    def test_manual_adapter_addition(self):
        """Adapters can be added manually after construction."""
        with patch("sol.discovery.importlib.metadata.entry_points", return_value=[]):
            registry = AdapterRegistry()
            adapter = MockAdapter()
            registry.adapters.append(adapter)
            assert len(registry.adapters) == 1
            assert registry.adapters[0] is adapter


class TestSortedAdapters:
    """Test priority-based sorting."""

    def test_sorted_by_priority_descending(self):
        with patch("sol.discovery.importlib.metadata.entry_points", return_value=[]):
            registry = AdapterRegistry()
            high = MockAdapter(protocol="high")
            high._priority = 300
            low = MockAdapter(protocol="low")
            low._priority = 50
            registry.adapters = [low, high]
            sorted_pairs = registry._sorted_adapters()
            assert sorted_pairs[0][0] is high
            assert sorted_pairs[1][0] is low


@pytest.mark.asyncio
class TestProtocolDetection:
    """Test the detection cascade."""

    async def test_detect_matching_adapter(self):
        with patch("sol.discovery.importlib.metadata.entry_points", return_value=[]):
            registry = AdapterRegistry()
            adapter = MockAdapter()
            registry.adapters = [adapter]
            result = await registry.detect_protocol("mock://test")
            assert result is adapter

    async def test_detect_no_match_raises(self):
        with patch("sol.discovery.importlib.metadata.entry_points", return_value=[]):
            registry = AdapterRegistry()
            adapter = MockAdapter()
            registry.adapters = [adapter]
            with pytest.raises(ProtocolDetectionError):
                await registry.detect_protocol("http://unknown.com")

    async def test_detect_priority_ordering(self):
        """Higher-priority adapter wins when both can handle."""
        with patch("sol.discovery.importlib.metadata.entry_points", return_value=[]):
            registry = AdapterRegistry()
            low = MockAdapter(protocol="low")
            low._priority = 10
            high = MockAdapter(protocol="high")
            high._priority = 500
            registry.adapters = [low, high]
            result = await registry.detect_protocol("mock://test")
            assert await result.protocol_name() == "high"

    async def test_get_adapter_delegates_to_detect(self):
        with patch("sol.discovery.importlib.metadata.entry_points", return_value=[]):
            registry = AdapterRegistry()
            adapter = MockAdapter()
            registry.adapters = [adapter]
            result = await registry.get_adapter("mock://test")
            assert result is adapter
