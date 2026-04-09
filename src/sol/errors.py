"""SolError hierarchy."""

from __future__ import annotations


class SolError(Exception):
    """Base exception for all Sol errors."""

    def __init__(self, message: str, *, details: str | None = None) -> None:
        self.message = message
        self.details = details
        super().__init__(message)


class ProtocolDetectionError(SolError):
    """No adapter could detect the protocol for a given URL."""


class SchemaRetrievalError(SolError):
    """Failed to retrieve or parse a remote schema."""


class OperationNotFoundError(SolError):
    """The requested operation does not exist."""


class InvalidArgumentsError(SolError):
    """Supplied arguments do not match the operation's parameter schema."""


class ExecutionError(SolError):
    """An error occurred during operation execution."""


class AuthError(SolError):
    """Authentication or authorization failure."""
