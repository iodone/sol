# Sol

Universal API CLI — discover, inspect, and invoke any protocol through a single interface.

Sol provides a unified command-line interface for working with APIs across protocols (OpenAPI, GraphQL, gRPC, JSON-RPC, MCP). Protocol support is fully pluggable, and sol ships with built-in OpenAPI support.

## Key Features

- **Protocol-agnostic**: One CLI pattern for any API (OpenAPI, GraphQL, MCP, gRPC, JSON-RPC)
- **Auto-detection**: Automatically identifies the protocol from a URL
- **Built-in adapters**: OpenAPI 3.x support included out of the box
- **Plugin architecture**: Extend with additional protocol adapters via Python entry points
- **Reusable auth**: Configure credentials once, bind to endpoints, reuse across invocations
- **Production-ready**: Not just for demo endpoints — supports real provider integration with flexible auth primitives

## Installation

```bash
uv add sol
```

## Usage

```bash
# Discover available operations
sol <url> -h

# Inspect a specific operation
sol <url> <operation> -h

# Invoke an operation
sol <url> <operation> key=value

# Use with authentication
sol <url> <operation> key=value --credential my-api-key
```

## Authentication & Credentials

Sol is designed for **real provider integration**, not just demo endpoints. It provides reusable auth and binding primitives:

### Supported Auth Modes

- **Bearer token** — `Authorization: Bearer <token>`
- **API key** — Configurable in header or query parameter
- **Multi-field credentials** — For signed API requests (HMAC, Ed25519)
- **OAuth2** — Device code, authorization code, refresh tokens (for MCP HTTP and others)
- **Secret sources** — Literal values, environment variables, or external secret providers

### Auth Model

- **Credentials** store authentication material (tokens, API keys, secrets)
- **Bindings** match endpoints and select which credential to use

This makes auth configuration a **reusable asset** — configure once, bind to patterns, invoke without embedding secrets in every command.

### Example: API Key Authentication

```bash
# Store a credential
sol auth set my-api-key --secret "sk-..."

# Bind it to an endpoint pattern
sol auth bind my-api-key --host api.example.com

# Invoke — credential auto-applied
sol api.example.com/v1/openapi.json getUser id=123
```

### Example: OAuth2 Flow

```bash
# Start OAuth device code flow
sol auth oauth login my-provider

# Credential stored, bound, and auto-refreshed on expiry
sol my-provider.com/api listResources
```

See [Architecture docs](docs/architecture.md) for full auth system details.

## Plugin Ecosystem

Install additional protocol adapters as needed:

```bash
uv add sol-graphql    # GraphQL support
uv add sol-grpc       # gRPC support
uv add sol-mcp        # MCP (Model Context Protocol) support
```

Adapters are discovered automatically via Python entry points — no configuration required.

## Documentation

- [Architecture](docs/architecture.md) — System overview, core abstractions, data flow, plugin system, auth model, and hook lifecycle
- [Plugin Guide](docs/plugin-guide.md) — Step-by-step tutorial for building a satellite adapter package

## Development

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management

### Getting Started

```bash
git clone <repo-url>
cd sol
uv sync
```

### Justfile Commands

| Command | Description |
|---|---|
| `just install` | Install dependencies and sync the project (`uv sync`) |
| `just check` | Run linting (ruff) and type checking (mypy) |
| `just test` | Run the test suite (`uv run pytest`) |
| `just build` | Build the distribution package |
| `just clean-build` | Remove build artifacts and rebuild |

### Running Commands

```bash
# Run Sol directly
uv run sol --help

# Run linting and type checks
just check

# Run the test suite
just test

# Build the package
just build
```

## License

MIT
