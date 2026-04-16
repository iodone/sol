---
name: sol-skill-creator
description: Create wrapper skills that call protocol-specific APIs through Sol adapters. Use when defining a new protocol skill and you need templates, validation rules, and best practices based on Sol's adapter architecture.
---

# Sol Skill Creator

Use this skill to design and standardize protocol wrapper skills built on top of `sol`.

## Prerequisites

- `sol` skill is available as the base execution contract.
- Target wrapper skill scope is clear (protocol name, endpoint patterns, auth model, core operations).

## Output Contract

A wrapper skill created with this skill should include:

- `SKILL.md` (skill documentation)
- `README.md` (for package distribution)
- `pyproject.toml` (if creating an adapter package)
- `tests/` (unit tests for adapter)

## Core Workflow

1. **Define protocol scope:**
   - Protocol name (e.g., "datum", "openapi")
   - URL scheme (e.g., `datum://`, `https://`)
   - Authentication model (bearer, custom, OAuth)
   - Core operations (3-5 most important operations)

2. **Verify protocol behavior:**
   - Test endpoint manually (curl, httpie, etc.)
   - Confirm schema format (OpenAPI spec, custom JSON, etc.)
   - Document auth requirements

3. **Design adapter interface:**
   ```python
   class MyAdapter(Adapter):
       @property
       def protocol_name(self) -> str:
           return "myprotocol"
       
       async def can_handle(self, url: str) -> bool:
           # URL scheme detection
       
       async def discover(self, url: str) -> list[OperationDetail]:
           # List operations
       
       async def execute(...) -> ExecutionResult:
           # Execute operation
   ```

4. **Implement operation catalog:**
   - Define operation IDs (e.g., `catalog.list`, `table.create`)
   - Map to HTTP methods and paths
   - Define parameters and types

5. **Write skill documentation:**
   - Clear "When To Use" section
   - Auth setup instructions
   - Core operation examples
   - Troubleshooting guide

6. **Add tests:**
   - Protocol detection tests
   - Operation discovery tests
   - Execution tests (with mocked responses)
   - Auth integration tests

7. **Package and distribute:**
   - Add entry point in `pyproject.toml`
   - Publish to PyPI or install locally
   - Verify `sol <url>` detects the adapter

## Hard Rules

- **Protocol name uniqueness**: One protocol = one adapter name
- **URL scheme consistency**: `scheme://` must always map to same protocol
- **Auth type explicitness**: Document required auth type clearly
- **Operation naming**: Use dot notation (`resource.action`)
- **Error handling**: Always return `ExecutionResult` with proper error codes
- **Testing**: Minimum 80% coverage for adapter code

## Skill Template Structure

```
my-protocol-skill/
├── SKILL.md                    # Agent-facing documentation
├── README.md                   # Human-facing documentation
├── pyproject.toml              # Package metadata
├── src/
│   └── sol_myprotocol/
│       ├── __init__.py
│       ├── adapter.py          # Main adapter implementation
│       ├── operations.py       # Operation catalog
│       └── _base.py            # Shared utilities
└── tests/
    ├── test_adapter.py
    ├── test_operations.py
    └── fixtures/
        └── mock_responses.json
```

## SKILL.md Template

```markdown
---
name: <protocol-name>
description: <One-line description>
metadata:
  short-description: <Short version>
---

# <Protocol Name> Skill

Use this skill when working with <protocol description>.

## When To Use

- Specific use case 1
- Specific use case 2

## Prerequisites

- sol is installed
- <protocol> adapter is installed: `pip install sol-<protocol>`

## Quick Start

\`\`\`bash
# Setup auth (if needed)
sol auth set <credential-name> --type <type> --secret "<secret>"
sol auth bind <url> <credential-name>

# Discover operations
sol <scheme>://<host> -h

# Execute operation
sol <scheme>://<host> <operation> key=value
\`\`\`

## Core Operations

### <operation-1>
Description...
\`\`\`bash
sol <url> <operation> param1=value1
\`\`\`

### <operation-2>
Description...
\`\`\`bash
sol <url> <operation> param1=value1
\`\`\`

## Authentication

<Auth setup details>

## Examples

<Real-world examples>

## Troubleshooting

<Common issues and solutions>
```

## pyproject.toml Template

```toml
[project]
name = "sol-<protocol>"
version = "0.1.0"
description = "<Protocol> adapter for Sol"
requires-python = ">= 3.12"
dependencies = [
    "sol @ git+https://github.com/iodone/sol.git",
]

[project.entry-points.'sol.adapters']
<protocol> = "sol_<protocol>.adapter:<Protocol>Adapter"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

## Adapter Implementation Template

```python
\"\"\"<Protocol> adapter for Sol.\"\"\"

from __future__ import annotations

from typing import Any

from sol.adapter import Adapter, OperationDetail, ExecutionResult
from sol.client import AsyncHTTPClient


class <Protocol>Adapter(Adapter):
    \"\"\"Adapter for <protocol> protocol.\"\"\"

    @property
    def protocol_name(self) -> str:
        return "<protocol>"

    @property
    def priority(self) -> int:
        return 100  # Default priority

    async def can_handle(self, url: str) -> bool:
        \"\"\"Check if URL is a <protocol> URL.\"\"\"
        return url.startswith("<scheme>://")

    async def discover(self, url: str) -> list[OperationDetail]:
        \"\"\"List available operations.\"\"\"
        return [
            OperationDetail(
                operation_id="resource.action",
                display_name="Action Name",
                description="Action description",
                parameters={
                    "param1": {
                        "type": "string",
                        "required": True,
                        "description": "Parameter description"
                    }
                },
                returns="object",
                examples=["resource.action param1=value"],
            ),
        ]

    async def execute(
        self,
        url: str,
        op_id: str,
        args: dict[str, Any],
        *,
        auth_headers: dict[str, str] | None = None,
    ) -> ExecutionResult:
        \"\"\"Execute an operation.\"\"\"
        # Implementation here
        async with AsyncHTTPClient(auth_headers=auth_headers) as client:
            response = await client.get(url)
            return ExecutionResult(
                data=response.json(),
                status_code=response.status_code,
            )
```

## Testing Template

```python
\"\"\"Tests for <Protocol> adapter.\"\"\"

import pytest
from sol_<protocol>.adapter import <Protocol>Adapter


class TestProtocolDetection:
    async def test_can_handle_valid_url(self):
        adapter = <Protocol>Adapter()
        assert await adapter.can_handle("<scheme>://example.com")

    async def test_cannot_handle_invalid_url(self):
        adapter = <Protocol>Adapter()
        assert not await adapter.can_handle("https://example.com")


class TestDiscovery:
    async def test_list_operations(self):
        adapter = <Protocol>Adapter()
        ops = await adapter.discover("<scheme>://example.com")
        assert len(ops) > 0
        assert ops[0].operation_id == "resource.action"


class TestExecution:
    async def test_execute_operation(self, httpx_mock):
        httpx_mock.add_response(json={"result": "success"})
        adapter = <Protocol>Adapter()
        result = await adapter.execute(
            "<scheme>://example.com",
            "resource.action",
            {"param1": "value1"}
        )
        assert result.status_code == 200
        assert result.data == {"result": "success"}
```

## Validation Checklist

Before publishing a skill:

- [ ] Protocol name is unique and descriptive
- [ ] URL scheme is consistent and documented
- [ ] Auth requirements are clearly stated
- [ ] At least 3 core operations are implemented
- [ ] SKILL.md includes all required sections
- [ ] Tests achieve 80%+ coverage
- [ ] Entry point is correctly registered
- [ ] `sol <url> -h` works after installation
- [ ] Auth integration is tested end-to-end
- [ ] Error messages are helpful and actionable

## Philosophy Alignment

Sol skills should follow these principles:

| Principle | Implementation |
|-----------|----------------|
| **简洁有效** | Minimal code, maximal clarity |
| **美** | Clean abstractions, no hacks |
| **低熵** | Self-documenting configuration |
| **可扩展** | Easy to add new operations |
| **Effect 模式** | Pure functions + explicit IO |

## Examples

### Datum Protocol Skill

See `sol-datum` package for a complete example:
- Protocol: Datum OpenAPI
- Scheme: `datum://`
- Auth: Custom workspace token
- Operations: catalog, database, table metadata

### OpenAPI Skill (Built-in)

Sol includes a built-in OpenAPI adapter:
- Protocol: OpenAPI
- Scheme: `https://`
- Auth: Bearer, API key, basic
- Operations: Dynamic from OpenAPI spec

## See Also

- Sol adapter interface: `src/sol/adapter.py`
- Base skill template: `src/skills/sol/SKILL.md`
- Datum adapter example: `datum-api-hub` project
- Sol authentication: `src/sol/auth/`
