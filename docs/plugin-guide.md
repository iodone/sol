# Plugin Guide: Building a Sol Adapter

This guide walks through building a complete Sol satellite adapter package from scratch. By the end, you'll have a working adapter that Sol discovers automatically on install.

We'll build **sol-openapi** as the running example — a package that handles OpenAPI/Swagger URLs.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Familiarity with async Python and Pydantic

## Step 1: Create the Package

Create the package directory structure:

```bash
mkdir -p sol-openapi/src/sol_openapi
cd sol-openapi
```

Your layout will be:

```
sol-openapi/
├── pyproject.toml
├── src/
│   └── sol_openapi/
│       ├── __init__.py
│       └── adapter.py
└── tests/
    ├── __init__.py
    └── test_adapter.py
```

Create the directory and files:

```bash
mkdir -p src/sol_openapi tests
touch src/sol_openapi/__init__.py
touch src/sol_openapi/adapter.py
touch tests/__init__.py
touch tests/test_adapter.py
```

## Step 2: Configure pyproject.toml

This is the most critical file — it tells Sol about your adapter via the entry points mechanism.

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "sol-openapi"
version = "0.1.0"
description = "OpenAPI/Swagger adapter for Sol"
readme = "README.md"
requires-python = ">= 3.12"
license = "MIT"
dependencies = [
    "sol>=0.1.0",
    "httpx>=0.27",
]

[project.entry-points.'sol.adapters']
openapi = "sol_openapi:OpenAPIAdapter"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[tool.hatch.build.targets.wheel]
sources = ["src"]
only-include = ["src/sol_openapi"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

### The Entry Point (Key Section)

```toml
[project.entry-points.'sol.adapters']
openapi = "sol_openapi:OpenAPIAdapter"
```

This tells Python's packaging system:

- **Group:** `sol.adapters` — Sol scans this group at runtime
- **Name:** `openapi` — A unique identifier for your adapter
- **Value:** `sol_openapi:OpenAPIAdapter` — The module path and class name to load

When a user runs `pip install sol-openapi`, this entry point is registered in the environment's metadata. Sol's `AdapterRegistry` finds it via `importlib.metadata.entry_points(group="sol.adapters")`.

## Step 3: Implement the Adapter

### The `__init__.py` Module

Export your adapter class from the package root so the entry point can find it:

```python
# src/sol_openapi/__init__.py
"""Sol adapter for OpenAPI / Swagger APIs."""

from sol_openapi.adapter import OpenAPIAdapter

__all__ = ["OpenAPIAdapter"]
```

### The Adapter Implementation

Create `src/sol_openapi/adapter.py`. Your adapter must subclass `sol.adapter.Adapter` and implement all six abstract methods:

```python
# src/sol_openapi/adapter.py
"""OpenAPI adapter — discovers and invokes OpenAPI-described APIs."""

from __future__ import annotations

from typing import Any

from loguru import logger

from sol.adapter import Adapter, ExecutionResult
from sol.client import AsyncHTTPClient
from sol.schema import Operation, OperationDetail, Parameter


class OpenAPIAdapter(Adapter):
    """Adapter for OpenAPI 3.x and Swagger 2.x APIs.

    Detection: Fetches the URL and checks for an OpenAPI or Swagger
    schema marker in the JSON response.
    """

    # ──────────────────────────────────────────────
    # Identity & Priority
    # ──────────────────────────────────────────────

    async def protocol_name(self) -> str:
        return "openapi"

    async def priority(self) -> int:
        return 200  # Higher priority — try before generic adapters

    # ──────────────────────────────────────────────
    # Detection
    # ──────────────────────────────────────────────

    async def can_handle(self, url: str) -> bool:
        """Probe the URL for an OpenAPI/Swagger schema.

        Returns True if the response contains 'openapi' or 'swagger'
        as a top-level key.
        """
        try:
            async with AsyncHTTPClient(timeout=10.0) as client:
                resp = await client.get(self._schema_url(url))
                if not resp.is_success or resp.json_body is None:
                    return False
                return "openapi" in resp.json_body or "swagger" in resp.json_body
        except Exception:
            logger.debug("OpenAPI detection failed for {}", url, exc_info=True)
            return False

    # ──────────────────────────────────────────────
    # Discovery
    # ──────────────────────────────────────────────

    async def list_operations(self, url: str) -> list[Operation]:
        """Parse the OpenAPI schema and return all operations."""
        schema = await self._fetch_schema(url)
        operations: list[Operation] = []

        paths = schema.get("paths", {})
        for path, methods in paths.items():
            for method, details in methods.items():
                if method.startswith("x-") or method == "parameters":
                    continue
                op_id = details.get("operationId", f"{method}:{path}")
                operations.append(
                    Operation(
                        operation_id=op_id,
                        display_name=details.get("summary"),
                        description=details.get("description"),
                    )
                )

        return operations

    # ──────────────────────────────────────────────
    # Inspection
    # ──────────────────────────────────────────────

    async def describe_operation(self, url: str, op_id: str) -> OperationDetail:
        """Return detailed info about a specific operation."""
        schema = await self._fetch_schema(url)
        method, path, details = self._find_operation(schema, op_id)

        params: list[Parameter] = []
        for p in details.get("parameters", []):
            params.append(
                Parameter(
                    name=p["name"],
                    param_type=p.get("schema", {}).get("type", "string"),
                    required=p.get("required", False),
                    description=p.get("description"),
                )
            )

        return OperationDetail(
            operation_id=op_id,
            display_name=details.get("summary"),
            description=details.get("description"),
            parameters=params,
            return_type=self._extract_return_type(details),
        )

    # ──────────────────────────────────────────────
    # Execution
    # ──────────────────────────────────────────────

    async def execute(
        self,
        url: str,
        op_id: str,
        args: dict[str, Any],
        *,
        auth_headers: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """Invoke an OpenAPI operation."""
        schema = await self._fetch_schema(url)
        method, path, details = self._find_operation(schema, op_id)

        # Resolve path parameters
        resolved_path = path
        for p in details.get("parameters", []):
            if p.get("in") == "path" and p["name"] in args:
                resolved_path = resolved_path.replace(
                    f"{{{p['name']}}}", str(args.pop(p["name"]))
                )

        # Build the request URL
        base_url = self._base_url(schema, url)
        request_url = f"{base_url}{resolved_path}"

        async with AsyncHTTPClient(auth_headers=auth_headers) as client:
            if method in ("get", "delete", "head"):
                resp = await client.get(request_url, params=args or None)
            else:
                resp = await client.post(request_url, json=args or None)

        return ExecutionResult(
            data=resp.json_body if resp.json_body is not None else resp.text,
            status_code=resp.status_code,
            headers=resp.headers,
        )

    # ──────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────

    def _schema_url(self, url: str) -> str:
        """Ensure the URL has a scheme."""
        if not url.startswith(("http://", "https://")):
            return f"https://{url}"
        return url

    async def _fetch_schema(self, url: str) -> dict[str, Any]:
        """Fetch and return the OpenAPI schema as a dict."""
        async with AsyncHTTPClient() as client:
            resp = await client.get(self._schema_url(url))
        if resp.json_body is None:
            from sol.errors import SchemaRetrievalError
            raise SchemaRetrievalError(f"No JSON response from {url}")
        return resp.json_body

    def _find_operation(
        self, schema: dict[str, Any], op_id: str
    ) -> tuple[str, str, dict[str, Any]]:
        """Find an operation by ID in the schema. Returns (method, path, details)."""
        for path, methods in schema.get("paths", {}).items():
            for method, details in methods.items():
                if method.startswith("x-") or method == "parameters":
                    continue
                found_id = details.get("operationId", f"{method}:{path}")
                if found_id == op_id:
                    return method, path, details
        from sol.errors import OperationNotFoundError
        raise OperationNotFoundError(f"Operation '{op_id}' not found in schema")

    def _base_url(self, schema: dict[str, Any], fallback: str) -> str:
        """Extract the base URL from the schema or fall back to the input URL."""
        servers = schema.get("servers", [])
        if servers:
            return servers[0].get("url", self._schema_url(fallback))
        return self._schema_url(fallback)

    def _extract_return_type(self, details: dict[str, Any]) -> str | None:
        """Extract the response content type from the operation details."""
        responses = details.get("responses", {})
        for status, resp in responses.items():
            if status.startswith("2"):
                content = resp.get("content", {})
                if content:
                    return next(iter(content.keys()), None)
        return None
```

### Adapter Method Reference

| Method | When Sol Calls It | What to Return |
|---|---|---|
| `protocol_name()` | Metadata/logging | A string identifier like `"openapi"` |
| `priority()` | Detection ordering | An integer; higher = tried first (default 100) |
| `can_handle(url)` | Protocol detection cascade | `True` if this adapter can serve the URL |
| `list_operations(url)` | `sol <url> -h` | A list of `Operation` models |
| `describe_operation(url, op_id)` | `sol <url> <op> -h` | An `OperationDetail` model |
| `execute(url, op_id, args)` | `sol <url> <op> key=value` | An `ExecutionResult` model |

## Step 4: Write Tests

Create `tests/test_adapter.py`:

```python
# tests/test_adapter.py
"""Tests for the OpenAPI adapter."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from sol_openapi import OpenAPIAdapter
from sol.schema import Operation


SAMPLE_SCHEMA = {
    "openapi": "3.0.0",
    "info": {"title": "Pet Store", "version": "1.0.0"},
    "servers": [{"url": "https://petstore.example.com/v1"}],
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "description": "Returns all pets in the store",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                        "description": "Max number of pets to return",
                    }
                ],
                "responses": {
                    "200": {
                        "content": {"application/json": {}}
                    }
                },
            }
        },
        "/pets/{petId}": {
            "get": {
                "operationId": "getPet",
                "summary": "Get a pet by ID",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {
                        "content": {"application/json": {}}
                    }
                },
            }
        },
    },
}


@pytest.fixture
def adapter() -> OpenAPIAdapter:
    return OpenAPIAdapter()


class TestProtocolIdentity:
    async def test_protocol_name(self, adapter: OpenAPIAdapter) -> None:
        assert await adapter.protocol_name() == "openapi"

    async def test_priority(self, adapter: OpenAPIAdapter) -> None:
        assert await adapter.priority() == 200


class TestDetection:
    async def test_can_handle_openapi(self, adapter: OpenAPIAdapter) -> None:
        """Should detect a valid OpenAPI schema."""
        mock_response = AsyncMock()
        mock_response.is_success = True
        mock_response.json_body = SAMPLE_SCHEMA

        with patch.object(adapter, "_schema_url", return_value="https://example.com"):
            with patch("sol_openapi.adapter.AsyncHTTPClient") as MockClient:
                instance = MockClient.return_value.__aenter__.return_value
                instance.get = AsyncMock(return_value=mock_response)
                assert await adapter.can_handle("example.com") is True

    async def test_can_handle_non_openapi(self, adapter: OpenAPIAdapter) -> None:
        """Should reject non-OpenAPI responses."""
        mock_response = AsyncMock()
        mock_response.is_success = True
        mock_response.json_body = {"not": "openapi"}

        with patch.object(adapter, "_schema_url", return_value="https://example.com"):
            with patch("sol_openapi.adapter.AsyncHTTPClient") as MockClient:
                instance = MockClient.return_value.__aenter__.return_value
                instance.get = AsyncMock(return_value=mock_response)
                assert await adapter.can_handle("example.com") is False


class TestDiscovery:
    async def test_list_operations(self, adapter: OpenAPIAdapter) -> None:
        """Should parse all operations from the schema."""
        with patch.object(adapter, "_fetch_schema", return_value=SAMPLE_SCHEMA):
            ops = await adapter.list_operations("example.com")

        assert len(ops) == 2
        op_ids = {op.operation_id for op in ops}
        assert op_ids == {"listPets", "getPet"}

    async def test_describe_operation(self, adapter: OpenAPIAdapter) -> None:
        """Should return operation details with parameters."""
        with patch.object(adapter, "_fetch_schema", return_value=SAMPLE_SCHEMA):
            detail = await adapter.describe_operation("example.com", "listPets")

        assert detail.operation_id == "listPets"
        assert detail.display_name == "List all pets"
        assert len(detail.parameters) == 1
        assert detail.parameters[0].name == "limit"
        assert detail.parameters[0].param_type == "integer"


class TestExecution:
    async def test_execute_get(self, adapter: OpenAPIAdapter) -> None:
        """Should execute a GET operation with path parameters."""
        mock_response = AsyncMock()
        mock_response.json_body = {"id": "123", "name": "Fido"}
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = ""

        with patch.object(adapter, "_fetch_schema", return_value=SAMPLE_SCHEMA):
            with patch("sol_openapi.adapter.AsyncHTTPClient") as MockClient:
                instance = MockClient.return_value.__aenter__.return_value
                instance.get = AsyncMock(return_value=mock_response)
                result = await adapter.execute(
                    "example.com", "getPet", {"petId": "123"}
                )

        assert result.data == {"id": "123", "name": "Fido"}
        assert result.status_code == 200
```

Run tests with:

```bash
uv run pytest -v
```

## Step 5: Add Hook Implementations (Optional)

Your adapter package can also implement lifecycle hooks. Add a hook class alongside your adapter:

```python
# src/sol_openapi/hooks.py
"""Optional lifecycle hooks for the OpenAPI adapter."""

from __future__ import annotations

from typing import Any

from loguru import logger
from sol.hooks import hookimpl


class OpenAPIHooks:
    """Lifecycle hooks for OpenAPI-specific behavior."""

    @hookimpl
    def on_after_discover(self, url: str, adapter: Any) -> None:
        """Log when OpenAPI is selected."""
        if hasattr(adapter, "protocol_name"):
            logger.info("OpenAPI adapter selected for {}", url)

    @hookimpl
    def on_error(self, error: Exception) -> None:
        """Add OpenAPI-specific context to errors."""
        logger.debug("OpenAPI plugin saw error: {}", error)
```

To have these hooks auto-loaded, register the hook class via the same entry point group or register it from your adapter's `__init__`:

```python
# src/sol_openapi/__init__.py
"""Sol adapter for OpenAPI / Swagger APIs."""

from sol_openapi.adapter import OpenAPIAdapter
from sol_openapi.hooks import OpenAPIHooks

__all__ = ["OpenAPIAdapter", "OpenAPIHooks"]
```

## Step 6: Local Development Workflow

### Install in Development Mode

From your package directory:

```bash
# Using uv (recommended)
uv pip install -e ".[dev]"

# Or with pip
pip install -e ".[dev]"
```

The `-e` (editable) flag means changes to your code take effect immediately — no reinstall needed.

### Verify Entry Point Registration

After installing, verify Sol can find your adapter:

```bash
# Check the entry point is registered
python -c "
import importlib.metadata
eps = importlib.metadata.entry_points(group='sol.adapters')
for ep in eps:
    print(f'{ep.name} = {ep.value}')
"
```

Expected output:

```
openapi = sol_openapi:OpenAPIAdapter
```

### Test with Sol

```bash
# Discover operations on a known OpenAPI endpoint
sol petstore3.swagger.io/api/v3 -h

# Inspect a specific operation
sol petstore3.swagger.io/api/v3 listPets -h

# Invoke an operation
sol petstore3.swagger.io/api/v3 getPet petId=1
```

## Step 7: Publishing

### Prepare for Release

1. Update `version` in `pyproject.toml`.
2. Add a `README.md` describing your adapter.
3. Add a `LICENSE` file.

### Build and Publish

```bash
# Build the distribution
uv build

# Upload to PyPI
uv publish

# Or with twine
pip install twine
twine upload dist/*
```

### Users Install Your Package

```bash
pip install sol-openapi
# or
uv add sol-openapi
```

That's it — after install, `sol` automatically discovers and uses your adapter. No configuration files to edit, no registration calls to make.

## Complete pyproject.toml Reference

Here's a fully annotated `pyproject.toml` for a satellite adapter:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "sol-openapi"
version = "0.1.0"
description = "OpenAPI/Swagger adapter for Sol"
readme = "README.md"
requires-python = ">= 3.12"
license = "MIT"
authors = [
    { name = "Your Name", email = "you@example.com" },
]
keywords = ["sol", "openapi", "swagger", "api", "cli"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries",
]
dependencies = [
    "sol>=0.1.0",           # Core framework
    "httpx>=0.27",          # HTTP client (shared with sol core)
]

# ┌─────────────────────────────────────────────────────┐
# │  THIS IS THE KEY SECTION — adapter entry point       │
# │                                                       │
# │  Group:  sol.adapters                                 │
# │  Name:   openapi  (unique per adapter)                │
# │  Value:  module_path:ClassName                        │
# └─────────────────────────────────────────────────────┘
[project.entry-points.'sol.adapters']
openapi = "sol_openapi:OpenAPIAdapter"

[project.urls]
Homepage = "https://github.com/yourname/sol-openapi"
Repository = "https://github.com/yourname/sol-openapi"
Issues = "https://github.com/yourname/sol-openapi/issues"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.4",
]

[tool.hatch.build.targets.wheel]
sources = ["src"]
only-include = ["src/sol_openapi"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py312"
src = ["src"]
```

## Adapter Checklist

Before publishing, verify:

- [ ] `pyproject.toml` has `[project.entry-points.'sol.adapters']` section
- [ ] Entry point value points to a class that subclasses `sol.adapter.Adapter`
- [ ] All six abstract methods are implemented (`protocol_name`, `priority`, `can_handle`, `list_operations`, `describe_operation`, `execute`)
- [ ] `can_handle()` is non-destructive and fast (it runs for every URL during detection)
- [ ] `execute()` accepts and uses `auth_headers` parameter
- [ ] Tests cover detection, discovery, inspection, and execution
- [ ] Package installs cleanly with `pip install -e .`
- [ ] Entry point is visible via `importlib.metadata.entry_points(group="sol.adapters")`
- [ ] `sol <url> -h` works with your adapter installed

## Troubleshooting

### Adapter Not Found

```
No adapter could handle URL: ...
Attempted adapters: (none installed)
```

- Check the entry point is registered: `python -c "import importlib.metadata; print(list(importlib.metadata.entry_points(group='sol.adapters')))"`
- Verify the package is installed: `pip list | grep sol-`
- Make sure the class path in the entry point is correct (module:Class format)

### Detection Fails

- Run with `-v` or `-vv` to see debug logs: `sol <url> -h -vv`
- Check that `can_handle()` doesn't throw exceptions (they're caught and logged)
- Verify the URL returns the expected response format

### Import Errors

- Make sure `sol` core is installed as a dependency
- Check that your `__init__.py` exports the adapter class
- Verify the `[tool.hatch.build.targets.wheel]` includes your source directory
