---
name: sol-skill-creator
description: Create protocol adapter packages for Sol. Use when defining a new protocol adapter and you need reusable templates, validation rules, and anti-pattern guidance based on Sol's adapter architecture.
---

# Sol Skill Creator

Use this skill to design and standardize protocol adapter packages built on top of `sol`.

## Prerequisites

- `sol` skill is available as the base execution contract.
- Target adapter scope is clear (protocol name, URL detection, operation model, auth requirements).

## Output Contract

An adapter package created with this skill should include:

- `adapter.py` — Main adapter implementation
- `pyproject.toml` — Package metadata with entry point
- `tests/` — Unit tests for adapter
- `README.md` — Usage documentation

Optional files are allowed only when they add real reusable value.

## Core Workflow

1. Start from user-provided protocol input:
   - record protocol name (e.g., "graphql", "grpc")
   - identify URL detection strategy (scheme-based, content probing)
2. Discover protocol behavior before drafting code:
   - search official docs to confirm endpoint patterns
   - test with manual HTTP calls to understand request/response format
   - identify schema discovery mechanism (if any)
3. Detect authentication requirement explicitly:
   - probe with minimal call and inspect response
   - if auth-protected, record required model (bearer, API key, custom)
   - document auth header format
4. Fix the adapter interface:
   - protocol name (`protocol_name()`)
   - detection priority (`priority()`)
   - URL pattern (`can_handle()`)
   - operation discovery strategy (fixed catalog vs. dynamic)
5. Implement adapter methods:
   - `can_handle()`: URL detection logic
   - `list_operations()`: Return available operations
   - `describe_operation()`: Return operation details
   - `execute()`: Perform actual API call
6. Add comprehensive tests:
   - protocol detection tests
   - operation discovery tests
   - execution tests with mocked responses
   - auth header injection tests
7. Register via entry point in `pyproject.toml`:
   - `[project.entry-points.'sol.adapters']`
   - `myprotocol = "sol_myprotocol.adapter:MyProtocolAdapter"`
8. Write `README.md` with usage examples
9. Test installation and verify `sol <url> -h` works

## Hard Rules

- Protocol name must be unique (one protocol = one adapter).
- All `Adapter` ABC methods must be implemented.
- `can_handle()` must be deterministic and fast.
- `execute()` must inject `auth_headers` into HTTP requests.
- Tests must achieve 80%+ coverage.
- Entry point must match protocol name.
- Do not assume URL format; probe and verify.
- Do not hardcode credentials; use `auth_headers` parameter.

## Reference Files (Load On Demand)

- Step-by-step implementation flow:
  - `references/workflow.md`
- Copy-ready adapter templates:
  - `references/templates.md`
- Validation checklist and anti-patterns:
  - `references/validation-rules.md`

## See Also

- Base execution and auth guidance:
  - `skills/sol/SKILL.md`
- Sol adapter interface:
  - `src/sol/adapter.py` in Sol repo
- OpenAPI adapter reference:
  - `src/sol/adapters/openapi/adapter.py` in Sol repo
