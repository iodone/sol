# Sol Adapter Templates

## Minimal Adapter Template

```python
from sol.adapter import Adapter, ExecutionResult
from sol.schema import Operation, OperationDetail, Parameter

class MinimalAdapter(Adapter):
    async def protocol_name(self) -> str:
        return "minimal"
    
    async def priority(self) -> int:
        return 100
    
    async def can_handle(self, url: str) -> bool:
        return url.startswith("minimal://")
    
    async def list_operations(self, url: str) -> list[Operation]:
        return [
            Operation(
                operation_id="hello",
                display_name="Say Hello"
            )
        ]
    
    async def describe_operation(self, url: str, op_id: str) -> OperationDetail:
        return OperationDetail(
            operation_id="hello",
            display_name="Say Hello",
            description="Simple hello operation",
            parameters={
                "name": Parameter(
                    name="name",
                    param_type="string",
                    required=True,
                    description="Name to greet"
                )
            }
        )
    
    async def execute(self, url, op_id, args, *, auth_headers=None):
        if op_id == "hello":
            return ExecutionResult(
                data={"message": f"Hello, {args.get('name', 'world')}!"},
                status_code=200
            )
        return ExecutionResult(
            data={"error": f"Unknown operation: {op_id}"},
            status_code=400
        )
```

## REST API Adapter Template

```python
from sol.adapter import Adapter, ExecutionResult
from sol.client import AsyncHTTPClient
from sol.schema import Operation, OperationDetail

OPERATIONS = {
    "resource.list": ("GET", "/api/resources"),
    "resource.get": ("GET", "/api/resources/{id}"),
    "resource.create": ("POST", "/api/resources"),
}

class RESTAdapter(Adapter):
    async def protocol_name(self) -> str:
        return "rest"
    
    async def priority(self) -> int:
        return 100
    
    async def can_handle(self, url: str) -> bool:
        return "api.example.com" in url
    
    async def list_operations(self, url: str) -> list[Operation]:
        return [
            Operation(operation_id=op_id, display_name=op_id)
            for op_id in OPERATIONS.keys()
        ]
    
    async def describe_operation(self, url: str, op_id: str) -> OperationDetail:
        method, path = OPERATIONS[op_id]
        return OperationDetail(
            operation_id=op_id,
            display_name=op_id,
            description=f"{method} {path}",
            parameters={}
        )
    
    async def execute(self, url, op_id, args, *, auth_headers=None):
        method, path_template = OPERATIONS[op_id]
        
        # Substitute path params
        path = path_template
        for key, value in args.items():
            path = path.replace(f"{{{key}}}", str(value))
        
        full_url = url.rstrip("/") + path
        
        async with AsyncHTTPClient(auth_headers=auth_headers) as client:
            if method == "GET":
                resp = await client.get(full_url)
            elif method == "POST":
                resp = await client.post(full_url, json=args)
            
            return ExecutionResult(
                data=resp.json_body,
                status_code=resp.status_code
            )
```

## Test Template

```python
import pytest
from sol_myprotocol.adapter import MyProtocolAdapter

@pytest.fixture
def adapter():
    return MyProtocolAdapter()

class TestProtocolDetection:
    async def test_can_handle_valid_url(self, adapter):
        assert await adapter.can_handle("myprotocol://host")
    
    async def test_cannot_handle_invalid_url(self, adapter):
        assert not await adapter.can_handle("https://host")

class TestOperationDiscovery:
    async def test_list_operations(self, adapter):
        ops = await adapter.list_operations("myprotocol://host")
        assert len(ops) > 0
    
    async def test_describe_operation(self, adapter):
        detail = await adapter.describe_operation("myprotocol://host", "op1")
        assert detail.operation_id == "op1"

class TestExecution:
    async def test_execute_success(self, adapter, httpx_mock):
        httpx_mock.add_response(json={"result": "ok"})
        result = await adapter.execute("myprotocol://host", "op1", {})
        assert result.status_code == 200
```

## pyproject.toml Template

```toml
[project]
name = "sol-myprotocol"
version = "0.1.0"
description = "MyProtocol adapter for Sol"
requires-python = ">= 3.12"
dependencies = ["sol>=0.2.0"]

[project.entry-points.'sol.adapters']
myprotocol = "sol_myprotocol.adapter:MyProtocolAdapter"

[dependency-groups]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "pytest-httpx>=0.30"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```
