# Sol Usage Guide

## URL Patterns and Protocol Detection

Sol supports multiple ways to specify targets, depending on the protocol and use case.

### Pattern 1: Direct Endpoint URL

```bash
sol https://api.example.com/openapi.json -h
sol https://api.example.com/openapi.json getUser id=123
```

**When to use**: For any real API endpoint — OpenAPI schemas, GraphQL endpoints, gRPC services, etc.

**How it works**: Sol fetches the URL, tries each registered adapter's `can_handle()` method in priority order, and the first match wins.

### Pattern 2: Protocol-Specific Scheme (e.g., `echo://`)

```bash
echo -h                    # Standalone echo CLI
echo greet name=Meta42     # Direct invocation

sol echo://test -h         # Via sol with explicit protocol hint
sol echo://test greet name=Meta42
```

**When to use**: 
- **Testing/demo**: `echo://` is a built-in test adapter for validating the plugin pipeline
- **Custom protocols**: Adapters can register custom URL schemes (e.g., `mcp://`, `graphql://`) for unambiguous routing

**How it works**: The `echo://` scheme is recognized by `EchoAdapter.can_handle()`, which matches URLs starting with `echo://` or containing `"echo"` in the hostname.

### Pattern 3: Ambiguous URL (relies on detection)

```bash
sol api.example.com/spec -h
```

**When to use**: When the URL doesn't explicitly indicate the protocol, and you want Sol to auto-detect.

**How it works**: Sol tries adapters in priority order. For example, if the URL returns JSON with an `openapi` key, `OpenAPIAdapter` claims it.

---

## When to Use Each Pattern

| Pattern | Use Case | Example |
|---|---|---|
| `sol <url>` | Production APIs, real endpoints | `sol petstore.swagger.io/v2/swagger.json -h` |
| `echo <args>` | Standalone echo CLI (testing) | `echo greet name=Alice` |
| `sol echo://...` | Echo via sol (protocol hint) | `sol echo://test greet name=Bob` |

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
|---|---|
| `https://` | Production APIs, real endpoints |
| `http://` | Local dev servers, insecure endpoints |
| `echo://` | Testing, pipeline validation |
| Custom (`mcp://`, `graphql://`) | Protocol-specific adapters that want unambiguous routing |

---

## FAQ

### Q: Why does `sol echo://test` work but `sol echo` doesn't?

`echo` (without `://`) is ambiguous — it could be a hostname. Sol tries protocol detection, but `EchoAdapter.can_handle("echo")` may fail if the URL doesn't match its patterns. Use `echo://` for explicit protocol signaling.

### Q: Can I skip protocol detection and force a specific adapter?

Not directly via CLI (yet), but you can:
- Use protocol-specific schemes (`echo://`, `mcp://`) to guide detection
- In Python code, instantiate the adapter directly and call methods

### Q: When should I use the standalone `echo` vs `sol echo://`?

- **Standalone `echo`**: Fast, direct, no detection overhead. Good for testing adapter logic in isolation.
- **`sol echo://`**: Full pipeline (detection, caching, auth, hooks). Good for integration testing or when you want the same UX as production adapters.

---

## Summary

```bash
# Real endpoints (OpenAPI, GraphQL, etc.)
sol https://api.example.com/spec -h

# Standalone echo CLI
echo greet name=Alice

# Echo via sol (with protocol hint)
sol echo://test greet name=Bob

# Ambiguous URL (relies on auto-detection)
sol api.example.com/spec -h
```

Sol's power is in **unified interface** — the same `sol <url> <op> key=value` pattern works for any protocol, with adapters handling protocol-specific details transparently.
