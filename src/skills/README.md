# Skills Directory

This is a namespace package directory for Sol skill plugins.

Skill packages are installed separately (e.g., `pip install sol-openapi`) and discovered
automatically via Python entry points. Each skill provides a protocol adapter that Sol
uses to discover, inspect, and invoke API operations.

## How it works

Skill packages register themselves in their `pyproject.toml`:

```toml
[project.entry-points."sol.adapters"]
openapi = "sol_openapi:OpenAPIAdapter"
```

Sol scans `importlib.metadata.entry_points(group="sol.adapters")` at runtime to find
all installed adapters. No configuration needed — install the package and it's available.

## Creating a skill

See the plugin development guide for step-by-step instructions on creating a new
protocol adapter.
