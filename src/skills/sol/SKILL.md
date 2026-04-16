---
name: sol
description: Discover and invoke APIs through Sol's universal CLI with pluggable adapters. Use when you need to list operations, inspect schemas, and execute OpenAPI (or custom protocol) calls via one CLI contract.
metadata:
  short-description: Universal API CLI with adapter architecture
---

# Sol Skill

Use this skill when a task requires calling remote APIs and the endpoint exposes operations through Sol's adapter system.

## When To Use

- You need to call APIs from another skill and want one consistent CLI workflow.
- The interface is OpenAPI 3.x/Swagger 2.x, or has a custom Sol adapter installed.
- You need deterministic, machine-readable output (`ok`, `kind`, `data`, `error`).

Do not use this skill for pure local file operations with no remote interface.

## Docs & Support

- Sol repository: `https://github.com/iodone/sol`
- If behavior looks wrong, open an issue:
  - `https://github.com/iodone/sol/issues/new`
  - include command, URL, and the JSON envelope (`ok`, `error`, `meta`) for faster triage.

## Prerequisites

- `sol` is installed and available in `PATH`.

### Install sol

Choose one of the following methods:

**From source (development):**
```bash
cd ~/work/github/sol
uv sync
```

**From PyPI (when published):**
```bash
pip install sol
```

**From Git:**
```bash
pip install git+https://github.com/iodone/sol.git
```

## Core Workflow

1. Discover operations:
   - `sol <url> -h`
2. Inspect a specific operation:
   - `sol <url> <operation> -h`
3. Execute with structured input:
   - `sol <url> <operation> key=value`
   - `sol <url> <operation> '<payload-json>'`
4. Parse result as JSON envelope:
   - Success: `.ok == true`, consume `.data`
   - Failure: `.ok == false`, inspect `.error.code` and `.error.message`
5. For auth-protected endpoints:
   - bearer token: see below
   - API key: see below
   - custom headers: see below

## Auth Configuration

### Simple Bearer Token

```bash
# 1. Set credential
sol auth set my-token --type bearer --secret "your-secret-token"

# 2. Bind to URL
sol auth bind https://api.example.com my-token

# 3. Use automatically
sol https://api.example.com getUser id=123
# Auth headers injected automatically
```

### API Key (Header or Query)

```bash
# Header-based
sol auth set my-key --type api_key \
  --secret "your-key" \
  --location header \
  --param-name "X-API-Key"

# Query-based
sol auth set my-key --type api_key \
  --secret "your-key" \
  --location query \
  --param-name "api_key"

sol auth bind https://api.example.com my-key
```

### Custom Headers (Non-Standard Auth)

When APIs use non-standard authentication:

```bash
sol auth set my-custom --type custom \
  --header "X-Custom-Token=abc123" \
  --header "X-Workspace-ID=456"

sol auth bind https://api.example.com my-custom
```

Use custom auth when:
- API doesn't use standard `Bearer` prefix
- Multiple headers are required
- Auth format is proprietary

### Aliases for Short URLs

```bash
# Create binding with alias
sol auth bind https://api-prod.example.com my-token --alias prod

# Use short form
sol myapi://prod getUser id=123

# Equivalent to
sol https://api-prod.example.com getUser id=123
```

### Credential Management

```bash
# List all credentials
sol auth list

# List all bindings
sol auth bindings

# Remove credential
sol auth remove my-token

# Remove binding
sol auth unbind https://api.example.com
```

## Input Modes

- **Preferred (simple payload)**: key/value
  - `sol <url> <operation> field=value`
- **Bare JSON positional**:
  - `sol <url> <operation> '{"field":"value"}'`

Do not pass raw JSON through `--args`; use positional JSON.

## Output Contract For Reuse

Other skills should treat this skill as the API execution layer and consume only the stable envelope:

- Success fields: `ok`, `kind`, `protocol`, `endpoint`, `operation`, `data`, `meta`
- Failure fields: `ok`, `error.code`, `error.message`, `meta`

Default output is JSON. Do not use `--text` in agent automation paths.

## Reuse Rule For Other Skills

- If a skill needs remote API execution, reuse this skill instead of embedding protocol-specific calling logic.
- Upstream skill inputs should be limited to:
  - target URL
  - operation id/name
  - JSON payload
  - required fields to extract from `.data`

## Protocol Detection

Sol automatically detects protocols based on:

1. **URL scheme** (e.g., `https://`, custom schemes)
2. **Content probing** (e.g., fetching OpenAPI spec)
3. **Adapter priority** (higher priority = tried first)

**Built-in adapter:**
- **OpenAPI**: Detects OpenAPI 3.x and Swagger 2.x specs

**External adapters** (install separately):
- Custom protocol adapters via Python entry points

## Cache Management

Sol caches operation results for performance:

```bash
# View cache stats
sol cache stats

# Clear cache
sol cache clear

# Disable cache for one call
sol <url> <operation> --no-cache
```

## Troubleshooting

### Auth Issues

**Problem:** "No credential matched for URL"

**Solution:**
```bash
# Check if credential exists
sol auth list

# Check if binding exists
sol auth bindings

# Create binding if missing
sol auth bind <url> <credential-name>
```

### Protocol Detection Fails

**Problem:** "No adapter can handle this URL"

**Solution:**
- For OpenAPI: Ensure the URL returns a valid OpenAPI/Swagger spec
- For other protocols: Install the corresponding adapter package
- Check adapter installation: `python -c "from sol.framework import Framework; print(Framework().registry.list_adapters())"`

### URL Normalization Issues

Sol normalizes custom schemes based on bindings:
- `myapi://alias` → resolved to binding's full URL
- Scheme is inferred from binding (http/https)

If URLs don't resolve:
```bash
# Check binding configuration
sol auth bindings | grep <alias>
```

## Reference Files (Load On Demand)

- Common usage patterns and examples:
  - `references/usage-patterns.md`
- Protocol adapter development guide:
  - See `sol-skill-creator` skill

## See Also

- Sol GitHub repository: https://github.com/iodone/sol
- Architecture docs: `docs/architecture.md` in repo
- Plugin guide: `docs/plugin-guide.md` in repo
- OpenAPI adapter source: `src/sol/adapters/openapi/adapter.py`
