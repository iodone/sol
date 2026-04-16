---
name: sol
description: Discover and invoke any protocol through Sol's universal API CLI. Use when you need to list operations, inspect schemas, and execute OpenAPI, Datum, or custom protocol calls via pluggable adapters.
metadata:
  short-description: Universal protocol CLI with pluggable adapters
---

# Sol Skill

Use this skill when a task requires calling remote APIs and you want a unified CLI experience across different protocols through Sol's adapter architecture.

## When To Use

- You need to call APIs from different protocols (OpenAPI, Datum, custom) with one consistent workflow.
- The target protocol has a Sol adapter installed (built-in or third-party).
- You need structured, machine-readable output (`ok`, `kind`, `data`, `error`).

Do not use this skill for pure local file operations with no remote interface.

## Prerequisites

- `sol` is installed and available in `PATH`.
- Required adapter is installed (e.g., `sol-datum` for Datum API).

### Install sol

**From source (recommended for development):**
```bash
cd ~/work/github/sol
uv pip install -e .
```

**From Git:**
```bash
pip install git+https://github.com/iodone/sol.git
```

## Core Workflow

1. **Discover operations:**
   ```bash
   sol <url> -h
   ```
   Example: `sol datum://staging.10122 -h`

2. **Inspect operation schema:**
   ```bash
   sol <url> <operation> -h
   ```
   Example: `sol datum://staging.10122 catalog.list -h`

3. **Execute with arguments:**
   ```bash
   sol <url> <operation> [key=value ...]
   ```
   Example: `sol datum://staging.10122 catalog.list service=iceberg`

4. **Parse result as JSON envelope:**
   - Success: `.ok == true`, consume `.data`
   - Failure: `.ok == false`, inspect `.error.code` and `.error.message`

## Authentication

Sol uses a unified auth system with bindings and credentials.

### List credentials:
```bash
sol auth list
```

### Set credential:
```bash
# Bearer token
sol auth set my-token --type bearer --secret "my-secret-token"

# Custom headers (for non-standard auth)
sol auth set datum-ws --type custom --header "Authorization=workspace-token/1.0 abc123"
```

### Bind credential to host:
```bash
sol auth bind <url> <credential-name> [--alias <short-name>]
```

Example:
```bash
sol auth bind http://api-gateway.dptest.pt.xiaomi.com datum-ws --alias staging.10122
```

### List bindings:
```bash
sol auth bindings
```

## URL Aliases

Use short aliases instead of full URLs:

```bash
# After binding with --alias staging.10122
sol datum://staging.10122 catalog.list
# Equivalent to:
sol datum://api-gateway.dptest.pt.xiaomi.com catalog.list
```

## Input Modes

- **Key-value (preferred):**
  ```bash
  sol <url> <operation> field1=value1 field2=value2
  ```

- **JSON payload:**
  ```bash
  sol <url> <operation> '{"field1":"value1","field2":"value2"}'
  ```

## Output Contract

Sol returns structured JSON envelopes:

**Success:**
```json
{
  "ok": true,
  "kind": "invocation",
  "protocol": "datum",
  "endpoint": "datum://staging.10122",
  "operation": "catalog.list",
  "data": [...],
  "meta": {
    "version": "v1",
    "cached": false,
    "duration_ms": 123.45
  }
}
```

**Failure:**
```json
{
  "ok": false,
  "error": {
    "code": "AUTH_FAILED",
    "message": "No credential matched for URL"
  },
  "meta": {...}
}
```

## Protocol Detection

Sol automatically detects protocol from URL scheme:

| Scheme | Protocol | Example |
|--------|----------|---------|
| `https://` | OpenAPI | `sol https://api.github.com` |
| `datum://` | Datum | `sol datum://staging.10122` |
| Custom | Custom adapter | Define in adapter |

## Cache Management

Control operation caching:

```bash
# Cache stats
sol cache stats

# Clear cache
sol cache clear

# Disable cache for one call
sol <url> <operation> --no-cache
```

## Adapter Development

Create custom adapters by implementing the `Adapter` interface:

```python
from sol.adapter import Adapter, OperationDetail, ExecutionResult

class MyAdapter(Adapter):
    @property
    def protocol_name(self) -> str:
        return "myprotocol"
    
    async def can_handle(self, url: str) -> bool:
        return url.startswith("myprotocol://")
    
    async def discover(self, url: str) -> list[OperationDetail]:
        # Return available operations
        ...
    
    async def execute(
        self,
        url: str,
        op_id: str,
        args: dict,
        *,
        auth_headers: dict | None = None
    ) -> ExecutionResult:
        # Execute operation
        ...
```

Register via entry point in `pyproject.toml`:
```toml
[project.entry-points.'sol.adapters']
myprotocol = "my_adapter:MyAdapter"
```

## Philosophy

Sol follows these design principles:

- **简洁有效** (Simple and Effective): One CLI for all protocols
- **美** (Beautiful): Clean abstractions, no protocol-specific hacks
- **低熵** (Low Entropy): Configuration is self-documenting
- **可扩展** (Extensible): New protocols via pluggable adapters

## Troubleshooting

### Authentication issues

```bash
# Check if credential exists
sol auth list

# Check binding match
sol auth bindings

# Test with explicit credential
sol <url> <operation> --credential <name>
```

### Protocol detection fails

```bash
# Check installed adapters
python -c "from sol.framework import Framework; print(Framework().registry.list_adapters())"

# Manually specify protocol (future feature)
# sol <url> <operation> --protocol openapi
```

### URL normalization issues

Sol normalizes custom schemes based on bindings:
- `datum://` → `http://` or `https://` (inferred from binding)
- Custom scheme → Binding's scheme

Check binding configuration if URLs don't resolve correctly.

## See Also

- Sol GitHub repository: https://github.com/iodone/sol
- Datum adapter example: `sol-datum` package
- Auth system documentation: Run `sol auth --help`
