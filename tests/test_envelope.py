"""Tests for OutputEnvelope serialization."""

from __future__ import annotations

import json

from sol.envelope import ErrorInfo, Metadata, OutputEnvelope


class TestOutputEnvelopeSuccess:
    """Test the success constructor and serialization."""

    def test_success_defaults(self):
        env = OutputEnvelope.success()
        assert env.ok is True
        assert env.data is None
        assert env.error_info is None
        assert env.meta.cached is False

    def test_success_with_data(self):
        env = OutputEnvelope.success(
            kind="discovery",
            protocol="openapi",
            endpoint="http://example.com",
            data=[{"op": "list"}],
        )
        assert env.ok is True
        assert env.kind == "discovery"
        assert env.protocol == "openapi"
        assert env.data == [{"op": "list"}]

    def test_success_serialization(self):
        env = OutputEnvelope.success(kind="test", data={"key": "value"})
        raw = env.model_dump_json(exclude_none=True)
        parsed = json.loads(raw)
        assert parsed["ok"] is True
        assert parsed["data"] == {"key": "value"}
        assert "error" not in parsed

    def test_success_with_cache_metadata(self):
        meta = Metadata(cached=True, cache_source="cache-hit", cache_age_ms=150.0)
        env = OutputEnvelope.success(kind="discovery", data=[], meta=meta)
        assert env.meta.cached is True
        assert env.meta.cache_source == "cache-hit"


class TestOutputEnvelopeError:
    """Test the error constructor and serialization."""

    def test_error_basic(self):
        env = OutputEnvelope.error(code="NOT_FOUND", message="Not found")
        assert env.ok is False
        assert env.data is None
        assert env.error_info is not None
        assert env.error_info.code == "NOT_FOUND"
        assert env.error_info.message == "Not found"

    def test_error_with_details(self):
        env = OutputEnvelope.error(
            code="AUTH_FAILED",
            message="Unauthorized",
            details="Token expired",
            endpoint="http://api.example.com",
        )
        assert env.error_info.details == "Token expired"
        assert env.endpoint == "http://api.example.com"

    def test_error_serialization_alias(self):
        """error_info serializes as 'error' in JSON."""
        env = OutputEnvelope.error(code="ERR", message="msg")
        raw = json.loads(env.model_dump_json(exclude_none=True))
        assert "error" in raw
        assert "error_info" not in raw
        assert raw["error"]["code"] == "ERR"


class TestMetadata:
    """Test Metadata model."""

    def test_defaults(self):
        meta = Metadata()
        assert meta.cached is False
        assert meta.duration_ms is None
        assert meta.adapter is None

    def test_custom_values(self):
        meta = Metadata(cached=True, duration_ms=42.5, adapter="openapi")
        assert meta.cached is True
        assert meta.duration_ms == 42.5


class TestErrorInfo:
    """Test ErrorInfo model."""

    def test_basic(self):
        info = ErrorInfo(code="TEST", message="Test error")
        assert info.code == "TEST"
        assert info.details is None

    def test_with_details(self):
        info = ErrorInfo(code="X", message="Y", details="Z")
        assert info.details == "Z"
