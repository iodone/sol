"""Tests for the error hierarchy."""

from __future__ import annotations

import pytest

from sol.errors import (
    AuthError,
    ExecutionError,
    InvalidArgumentsError,
    OperationNotFoundError,
    ProtocolDetectionError,
    SchemaRetrievalError,
    SolError,
)


class TestSolErrorHierarchy:
    """Verify error hierarchy and attributes."""

    def test_sol_error_is_exception(self):
        assert issubclass(SolError, Exception)

    def test_sol_error_message(self):
        err = SolError("test message")
        assert err.message == "test message"
        assert str(err) == "test message"
        assert err.details is None

    def test_sol_error_details(self):
        err = SolError("msg", details="extra info")
        assert err.details == "extra info"

    @pytest.mark.parametrize(
        "error_cls",
        [
            ProtocolDetectionError,
            SchemaRetrievalError,
            OperationNotFoundError,
            InvalidArgumentsError,
            ExecutionError,
            AuthError,
        ],
    )
    def test_subclass_inherits_sol_error(self, error_cls):
        assert issubclass(error_cls, SolError)
        err = error_cls("test")
        assert isinstance(err, SolError)
        assert isinstance(err, Exception)
        assert err.message == "test"

    def test_can_catch_as_sol_error(self):
        with pytest.raises(SolError):
            raise ProtocolDetectionError("no adapter")

    def test_specific_catch(self):
        with pytest.raises(AuthError):
            raise AuthError("unauthorized", details="token expired")
