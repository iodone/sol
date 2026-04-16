# Sol

Universal API CLI — discover, inspect, and invoke any protocol through a single interface.

Sol provides a unified command-line interface for working with APIs across protocols (OpenAPI, GraphQL, gRPC, JSON-RPC, MCP). Protocol support is fully pluggable, and sol ships with built-in OpenAPI support.

## Design Philosophy

Sol keeps the top-level interaction pattern simple and consistent:

1. **Discover** what capabilities a host exposes
2. **Inspect** the input shape of a specific operation
3. **Invoke** with structured parameters
4. **Reuse** the same pattern across different protocols

This turns remote interfaces into **stable command entry points** rather than a collection of protocol-specific request styles. The goal is to make APIs feel like well-structured CLI commands, not ad-hoc HTTP calls.

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

### Skills Installation

Sol includes skills for AI agents (Alma, etc.). Skills are automatically installed to `~/.agents/skills/` during package installation.

If skills are not installed automatically, run:

```bash
sol-install-skills
```

This installs:
- `sol` — Sol CLI usage guide for agents
- `sol-skill-creator` — Protocol adapter development guide

## Quick Start

### Discover → Inspect → Invoke

```bash
# 1. Discover available operations
sol echo://prod -h

# 2. Inspect a specific operation
sol echo://prod send -h

# 3. Invoke with structured parameters
sol echo://prod send message="Hello from us-west"
```

### Multi-Region Setup (with Auth Aliases)

```bash
# Configure credentials for each region
sol auth set us-key --secret "us-token-xxx"
sol auth set eu-key --secret "eu-token-xxx"
sol auth set prod-key --secret "prod-token-xxx"

# Bind each credential to its host with a short alias
sol auth bind us-key --host echo-us.example.com --alias us
sol auth bind eu-key --host echo-eu.example.com --alias eu
sol auth bind prod-key --host echo.example.com --alias prod

# Use aliases directly — credentials are auto-applied
sol echo://us send message="Hello from US"
sol echo://eu send message="Hello from EU"
sol echo://prod send message="Hello from prod"

# No need to specify --credential or full hostnames
# Sol automatically matches alias → host → credential
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
- **Aliases** provide short names for frequently-used hosts

This makes auth configuration a **reusable asset** — configure once, bind to patterns, invoke without embedding secrets in every command.

### Example: API Key Authentication

```bash
# Store a credential
sol auth set my-api-key --secret "sk-..."

# Bind it to an endpoint pattern with an alias
sol auth bind my-api-key --host api.example.com --alias api

# Invoke — credential auto-applied
sol echo://api getUser id=123
```

### Example: OAuth2 Flow

```bash
# Start OAuth device code flow
sol auth oauth login my-provider

# Credential stored, bound, and auto-refreshed on expiry
sol my-provider.com/api listResources
```

See [Architecture docs](docs/architecture.md) for full auth system details.

## Usage Patterns

Sol supports multiple URL patterns:

| Pattern | Example | Use Case |
|---------|---------|----------|
| Full URL | `sol https://api.example.com/spec getUser id=123` | Production APIs, real endpoints |
| Alias | `sol echo://prod send message="Hello"` | Frequently-used hosts with credentials |
| Protocol hint | `sol echo://test greet name=Alice` | Testing, explicit protocol routing |

See [Usage Guide](docs/usage-guide.md) for detailed examples.

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
