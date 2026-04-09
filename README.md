# Sol

Universal API CLI — discover, inspect, and invoke any protocol through a single interface.

Sol provides a unified command-line interface for working with APIs across protocols (OpenAPI, GraphQL, gRPC, JSON-RPC, MCP). Protocol support is fully pluggable — the core ships with zero adapters, and each protocol is added via satellite packages.

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
```

## Plugin Ecosystem

Install protocol adapters as needed:

```bash
uv add sol-openapi    # OpenAPI / Swagger support
uv add sol-graphql    # GraphQL support
uv add sol-grpc       # gRPC support
```

Adapters are discovered automatically via Python entry points — no configuration required.

## Documentation

- [Architecture](docs/architecture.md) — System overview, core abstractions, data flow, plugin system, and hook lifecycle
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
