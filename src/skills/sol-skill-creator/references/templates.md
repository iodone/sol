# Sol Adapter Templates

## Quick Start Template

Minimal adapter for rapid prototyping:

```python
from sol.adapter import Adapter, OperationDetail, ExecutionResult

class QuickAdapter(Adapter):
    @property
    def protocol_name(self) -> str:
        return "quick"

    async def can_handle(self, url: str) -> bool:
        return url.startswith("quick://")

    async def discover(self, url: str) -> list[OperationDetail]:
        return [
            OperationDetail(
                operation_id="hello",
                display_name="Say Hello",
                description="Simple hello operation",
                parameters={"name": {"type": "string", "required": True}},
                returns="object",
                examples=["hello name=world"],
            )
        ]

    async def execute(self, url, op_id, args, *, auth_headers=None):
        if op_id == "hello":
            return ExecutionResult(
                data={"message": f"Hello, {args.get('name', 'world')}!"},
                status_code=200,
            )
        return ExecutionResult(
            data={"error": f"Unknown operation: {op_id}"},
            status_code=400,
        )
```

## REST API Adapter Template

For REST APIs with predictable patterns:

```python
from sol.adapter import Adapter, OperationDetail, ExecutionResult
from sol.client import AsyncHTTPClient

# Define operation catalog
OPERATIONS = {
    "resource.list": ("GET", "/api/resources"),
    "resource.get": ("GET", "/api/resources/{id}"),
    "resource.create": ("POST", "/api/resources"),
    "resource.update": ("PUT", "/api/resources/{id}"),
    "resource.delete": ("DELETE", "/api/resources/{id}"),
}

OPERATION_DETAILS = [
    OperationDetail(
        operation_id="resource.list",
        display_name="List Resources",
        description="Get all resources",
        parameters={
            "limit": {"type": "integer", "required": False},
            "offset": {"type": "integer", "required": False},
        },
        returns="array",
        examples=["resource.list limit=10"],
    ),
    # ... more operations
]

class RESTAdapter(Adapter):
    @property
    def protocol_name(self) -> str:
        return "myapi"

    async def can_handle(self, url: str) -> bool:
        return url.startswith("myapi://") or "myapi.example.com" in url

    async def discover(self, url: str) -> list[OperationDetail]:
        return OPERATION_DETAILS

    async def execute(self, url, op_id, args, *, auth_headers=None):
        if op_id not in OPERATIONS:
            return ExecutionResult(
                data={"error": f"Unknown operation: {op_id}"},
                status_code=400,
            )

        method, path_template = OPERATIONS[op_id]
        
        # Substitute path params
        path = path_template
        for key, value in args.items():
            path = path.replace(f"{{{key}}}", str(value))

        full_url = url.rstrip("/") + path

        async with AsyncHTTPClient(auth_headers=auth_headers) as client:
            if method == "GET":
                response = await client.get(full_url, params=args)
            elif method == "POST":
                response = await client.post(full_url, json=args)
            elif method == "PUT":
                response = await client.put(full_url, json=args)
            elif method == "DELETE":
                response = await client.delete(full_url)

            return ExecutionResult(
                data=response.json(),
                status_code=response.status_code,
            )
```

## Dynamic Discovery Template

For APIs with runtime schema discovery:

```python
class DynamicAdapter(Adapter):
    @property
    def protocol_name(self) -> str:
        return "dynamic"

    async def can_handle(self, url: str) -> bool:
        return url.startswith("dynamic://")

    async def discover(self, url: str) -> list[OperationDetail]:
        # Fetch schema from API
        async with AsyncHTTPClient() as client:
            response = await client.get(f"{url}/schema")
            schema = response.json()

        # Convert to OperationDetail
        operations = []
        for op in schema["operations"]:
            operations.append(
                OperationDetail(
                    operation_id=op["id"],
                    display_name=op["name"],
                    description=op["description"],
                    parameters=op["parameters"],
                    returns=op["returns"],
                    examples=op.get("examples", []),
                )
            )
        return operations

    async def execute(self, url, op_id, args, *, auth_headers=None):
        # Fetch operation spec
        async with AsyncHTTPClient(auth_headers=auth_headers) as client:
            response = await client.post(
                f"{url}/execute",
                json={"operation": op_id, "args": args}
            )
            return ExecutionResult(
                data=response.json(),
                status_code=response.status_code,
            )
```

## Custom Auth Template

For non-standard authentication:

```python
class CustomAuthAdapter(Adapter):
    # ... basic adapter methods ...

    async def execute(self, url, op_id, args, *, auth_headers=None):
        # Custom auth handling
        headers = {}
        if auth_headers:
            # Sol provides auth_headers from custom auth type
            headers.update(auth_headers)
            
            # Additional custom processing if needed
            if "X-Custom-Signature" not in headers:
                # Generate signature
                signature = self._sign_request(url, op_id, args)
                headers["X-Custom-Signature"] = signature

        async with AsyncHTTPClient(auth_headers=headers) as client:
            response = await client.post(url, json={"op": op_id, "args": args})
            return ExecutionResult(
                data=response.json(),
                status_code=response.status_code,
            )

    def _sign_request(self, url, op_id, args):
        # Implement custom signing logic
        import hashlib
        payload = f"{url}{op_id}{str(args)}"
        return hashlib.sha256(payload.encode()).hexdigest()
```

## Multi-Module Template

For large adapters with multiple domains:

```
sol_myprotocol/
├── __init__.py
├── adapter.py          # Main adapter
├── metadata.py         # Metadata operations
├── data.py             # Data operations  
├── admin.py            # Admin operations
└── _base.py            # Shared utilities
```

**adapter.py:**
```python
from sol_myprotocol import metadata, data, admin

class MyProtocolAdapter(Adapter):
    # ... base methods ...

    async def discover(self, url: str) -> list[OperationDetail]:
        return [
            *metadata.OPERATIONS,
            *data.OPERATIONS,
            *admin.OPERATIONS,
        ]

    async def execute(self, url, op_id, args, *, auth_headers=None):
        # Route to appropriate module
        if op_id.startswith("metadata."):
            return await metadata.execute(url, op_id, args, auth_headers)
        elif op_id.startswith("data."):
            return await data.execute(url, op_id, args, auth_headers)
        elif op_id.startswith("admin."):
            return await admin.execute(url, op_id, args, auth_headers)
        else:
            return ExecutionResult(
                data={"error": f"Unknown operation: {op_id}"},
                status_code=400,
            )
```

**metadata.py:**
```python
from sol.adapter import OperationDetail, ExecutionResult
from sol_myprotocol._base import execute_api

OPERATIONS = [
    OperationDetail(
        operation_id="metadata.list",
        display_name="List Metadata",
        description="Get metadata catalog",
        parameters={},
        returns="array",
        examples=["metadata.list"],
    ),
]

async def execute(url, op_id, args, auth_headers):
    if op_id == "metadata.list":
        return await execute_api(url, "GET", "/metadata", args, auth_headers)
    return ExecutionResult(data={"error": "Unknown op"}, status_code=400)
```

## Test Template

```python
import pytest
from sol_myprotocol.adapter import MyProtocolAdapter

@pytest.fixture
def adapter():
    return MyProtocolAdapter()

class TestProtocolDetection:
    async def test_can_handle_valid(self, adapter):
        assert await adapter.can_handle("myproto://host")

    async def test_cannot_handle_invalid(self, adapter):
        assert not await adapter.can_handle("https://host")

class TestDiscovery:
    async def test_discover_returns_operations(self, adapter):
        ops = await adapter.discover("myproto://host")
        assert len(ops) > 0
        assert all(hasattr(op, "operation_id") for op in ops)

class TestExecution:
    async def test_execute_success(self, adapter, httpx_mock):
        httpx_mock.add_response(
            json={"result": "success"},
            status_code=200
        )
        result = await adapter.execute(
            "myproto://host",
            "resource.list",
            {}
        )
        assert result.status_code == 200
        assert result.data == {"result": "success"}

    async def test_execute_with_auth(self, adapter, httpx_mock):
        httpx_mock.add_response(json={"result": "ok"})
        result = await adapter.execute(
            "myproto://host",
            "resource.list",
            {},
            auth_headers={"Authorization": "Bearer token123"}
        )
        # Verify auth header was sent
        request = httpx_mock.get_request()
        assert request.headers["Authorization"] == "Bearer token123"
```

## Package Template

**pyproject.toml:**
```toml
[project]
name = "sol-myprotocol"
version = "0.1.0"
description = "MyProtocol adapter for Sol"
authors = [{name = "Your Name", email = "you@example.com"}]
requires-python = ">= 3.12"
license = "MIT"
dependencies = [
    "sol @ git+https://github.com/iodone/sol.git",
]

[project.entry-points.'sol.adapters']
myprotocol = "sol_myprotocol.adapter:MyProtocolAdapter"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-httpx>=0.30",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
sources = ["src"]
```

**README.md:**
```markdown
# Sol MyProtocol Adapter

MyProtocol adapter for Sol universal API CLI.

## Installation

\`\`\`bash
pip install sol-myprotocol
\`\`\`

## Usage

\`\`\`bash
# Discover operations
sol myproto://example.com -h

# Execute operation
sol myproto://example.com resource.list limit=10
\`\`\`

## Authentication

\`\`\`bash
sol auth set my-cred --type bearer --secret "token123"
sol auth bind myproto://example.com my-cred
\`\`\`

## Development

\`\`\`bash
# Install in editable mode
pip install -e .

# Run tests
pytest
\`\`\`
```
