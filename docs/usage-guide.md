# Sol Usage Guide

## Core Interaction Pattern

Sol follows a simple, consistent flow across all protocols:

1. **Discover** — What can this endpoint do?
2. **Inspect** — What does this operation need?
3. **Invoke** — Execute with structured parameters

This pattern stays the same whether you're calling OpenAPI, GraphQL, gRPC, or MCP endpoints.

---

## Example: Multi-Region Echo Service

Let's walk through a realistic scenario: managing multiple regional deployments of an echo service.

### Step 1: Configure Credentials

Each region has its own authentication token:

```bash
sol auth set us-key --secret "us-production-token-xxx"
sol auth set eu-key --secret "eu-production-token-xxx"
sol auth set dev-key --secret "dev-testing-token-xxx"
```

### Step 2: Bind Hosts with Aliases

Map each credential to its host and give it a short alias:

```bash
sol auth bind us-key --host echo-us.example.com --alias us
sol auth bind eu-key --host echo-eu.example.com --alias eu
sol auth bind dev-key --host echo-dev.example.com --alias dev
```

**Alias naming guidelines:**
- ✅ Recommended: `prod`, `us-west`, `api-v2`, `region.eu`
- ❌ Avoid: `region/us` (slashes are URL path separators and won't work as expected)

### Step 3: Discover Operations

Check what each region supports:

```bash
# Discover operations in US region
sol echo://us -h

# Output:
# Available operations:
#   send       Send a message and get echo response
#   broadcast  Broadcast to all connected clients
#   ping       Health check
```

### Step 4: Inspect Operation Details

See what parameters an operation needs:

```bash
sol echo://us send -h

# Output:
# Operation: send
# Description: Send a message and get echo response
# Parameters:
#   message (string, required) — The message to echo
#   timestamp (boolean, optional) — Include timestamp in response
```

### Step 5: Invoke

Call operations using aliases — credentials are automatically applied:

```bash
# Send to US region
sol echo://us send message="Hello from US" timestamp=true

# Send to EU region
sol echo://eu send message="Hello from EU"

# Test in dev environment
sol echo://dev send message="Testing new feature"
```

**No need to:**
- Specify `--credential` each time
- Remember full hostnames
- Switch between auth profiles manually

Sol automatically:
1. Resolves alias (`us` → `echo-us.example.com`)
2. Matches host to binding
3. Loads the correct credential
4. Injects it into the request

---

## URL Patterns and Protocol Detection

Sol supports multiple ways to specify targets, depending on the protocol and use case.

### Pattern 1: Direct Endpoint URL

```bash
sol https://api.example.com/openapi.json -h
sol https://api.example.com/openapi.json getUser id=123
```

**When to use**: For any real API endpoint — OpenAPI schemas, GraphQL endpoints, gRPC services, etc.

**How it works**: Sol fetches the URL, tries each registered adapter's `can_handle()` method in priority order, and the first match wins.

### Pattern 2: Protocol-Specific Scheme with Alias

```bash
sol echo://prod -h
sol echo://prod send message="Hello"
```

**When to use**: 
- **Production workflows**: Use aliases for frequently-accessed hosts
- **Testing/demo**: `echo://` is a built-in test adapter for validating the plugin pipeline
- **Custom protocols**: Adapters can register custom URL schemes (e.g., `mcp://`, `graphql://`) for unambiguous routing

**How it works**: 
1. Sol extracts the hostname part (`prod`)
2. Checks if it's an alias in bindings
3. Resolves to real host (`echo.example.com`)
4. Matches binding to get credential
5. Routes to the appropriate adapter

### Pattern 3: Full URL with Scheme

```bash
sol echo://echo.example.com:7007 -h
sol echo://echo.example.com send message="Hello"
```

**When to use**: When you need to specify the full address (port, path) or the host isn't aliased.

**How it works**: Direct host matching against bindings, no alias resolution.

---

## When to Use Each Pattern

| Pattern | Example | Use Case |
|---------|---------|----------|
| **Alias** | `sol echo://prod send` | Daily operations, frequent calls, multi-environment |
| **Full URL** | `sol echo://api.example.com send` | One-off calls, explicit routing |
| **HTTPS URL** | `sol https://api.example.com/spec getUser` | OpenAPI/REST endpoints with schema discovery |

---

## Multi-Environment Workflow

A typical production setup:

```bash
# One-time setup
sol auth set prod-key --secret "$PROD_TOKEN"
sol auth set staging-key --secret "$STAGING_TOKEN"
sol auth set dev-key --secret "$DEV_TOKEN"

sol auth bind prod-key --host api.example.com --alias prod
sol auth bind staging-key --host api-staging.example.com --alias staging
sol auth bind dev-key --host api-dev.example.com --alias dev

# Daily usage (no auth flags needed)
sol echo://dev send message="Test feature"
sol echo://staging send message="Staging validation"
sol echo://prod send message="Production deployment"
```

---

## Echo Adapter: Two Entry Points

The echo adapter is available in **two ways**:

### 1. Standalone CLI: `echo`

```bash
echo -h                    # Discover operations
echo greet -h              # Inspect greet operation
echo greet name=Meta42     # Invoke greet
```

**When to use**: Direct testing, quick validation, or when you don't need sol's full pipeline (protocol detection, caching, auth).

**How it's registered**: Entry point in `packages/sol-echo/pyproject.toml`:
```toml
[project.scripts]
echo = "sol_echo.__main__:app"
```

### 2. Via Sol: `sol echo://`

```bash
sol echo://test -h
sol echo://test greet name=Meta42
```

**When to use**: When you want the full sol pipeline — caching, auth resolution, hook lifecycle, or when testing multi-protocol detection logic.

**How it's registered**: Entry point in `packages/sol-echo/pyproject.toml`:
```toml
[project.entry-points.'sol.adapters']
echo = "sol_echo.adapter:EchoAdapter"
```

---

## Protocol Detection Priority

Adapters are tried in **descending priority order**:

1. **Built-in adapters** (registered via `SolFramework._register_builtin_adapters()`)
   - `OpenAPIAdapter` (priority: 200)
2. **Entry-point adapters** (registered via `importlib.metadata.entry_points(group="sol.adapters")`)
   - `EchoAdapter` (priority: 50)

Higher priority = tried first. If multiple adapters claim they can handle a URL, the highest-priority one wins.

---

## URL Scheme Best Practices

| Scheme | Recommended Use |
|--------|----------------|
| `https://` | Production APIs, real endpoints |
| `http://` | Local dev servers, insecure endpoints |
| `echo://` | Testing, pipeline validation, multi-region demos |
| Custom (`mcp://`, `graphql://`) | Protocol-specific adapters that want unambiguous routing |

---

## FAQ

### Q: Why use `echo://prod` instead of just `prod`?

The `echo://` prefix makes it clear this is a **network operation** with a specific protocol. It avoids ambiguity with operation names and maintains consistent URL semantics across all adapters.

### Q: Can I skip protocol detection and force a specific adapter?

Not directly via CLI (yet), but you can:
- Use protocol-specific schemes (`echo://`, `mcp://`) to guide detection
- In Python code, instantiate the adapter directly and call methods

### Q: Do I need to configure bindings for every endpoint?

No — bindings are **optional**. You only need them when:
- The endpoint requires authentication
- You want to use a short alias for convenience
- You're managing multiple environments

For public, unauthenticated APIs, just use the full URL directly.

### Q: Can I use wildcard patterns in bindings?

Yes! Bindings support glob patterns:

```bash
sol auth bind shared-key --host "*.example.com"  # Matches all subdomains
sol auth bind api-key --host "api-*.example.com" # Matches api-dev, api-prod, etc.
```

---

## Summary

```bash
# Real endpoints (OpenAPI, GraphQL, etc.)
sol https://api.example.com/spec -h

# Aliased hosts (with auto-auth)
sol echo://prod send message="Hello"

# Full protocol URLs
sol echo://echo.example.com:7007 send message="Hello"

# Standalone echo CLI
echo greet name=Alice
```

Sol's power is in its **unified interface** — the same `sol <target> <operation> key=value` pattern works for any protocol, with adapters handling protocol-specific details transparently.
