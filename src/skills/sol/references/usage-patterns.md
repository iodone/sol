# Sol Usage Patterns

## Common Workflows

### Discovery Flow

```bash
# 1. Check protocol detection
sol <url> -h

# 2. Browse operations
# Output shows: operation_id, display_name, description

# 3. Inspect specific operation
sol <url> <operation> -h

# 4. Execute with minimal args
sol <url> <operation> required_param=value
```

### Auth Flow

```bash
# 1. Create credential
sol auth set my-cred --type bearer --secret "token123"

# 2. Bind to URL
sol auth bind https://api.example.com my-cred

# 3. Verify binding
sol auth bindings

# 4. Use automatically
sol https://api.example.com/v1 list_users
# Auth headers attached automatically
```

### Alias Flow

```bash
# 1. Create binding with alias
sol auth bind https://api-gateway.dptest.pt.xiaomi.com datum-ws --alias staging

# 2. Use short alias
sol datum://staging catalog.list service=iceberg

# Equivalent to:
sol datum://api-gateway.dptest.pt.xiaomi.com catalog.list service=iceberg
```

## Input Patterns

### Key-Value (Preferred)

```bash
# Simple params
sol <url> <operation> name=alice age=30

# Nested objects (flattened)
sol <url> <operation> user.name=alice user.age=30

# Arrays (comma-separated)
sol <url> <operation> tags=alpha,beta,gamma

# Boolean
sol <url> <operation> enabled=true archived=false

# Numbers
sol <url> <operation> limit=100 offset=20
```

### JSON Payload

```bash
# Bare JSON positional
sol <url> <operation> '{"name":"alice","age":30}'

# From file
sol <url> <operation> "$(cat payload.json)"

# Inline with jq
sol <url> <operation> "$(echo '{}' | jq '.name="alice"')"
```

## Output Parsing

### Success Path

```bash
# Extract data field
sol <url> <operation> | jq '.data'

# Extract specific field
sol <url> <operation> | jq '.data.items[0].name'

# Check if successful
sol <url> <operation> | jq '.ok' # → true
```

### Error Handling

```bash
# Check error code
sol <url> <operation> | jq '.error.code' # → "AUTH_FAILED"

# Get error message
sol <url> <operation> | jq '.error.message'

# Full error context
sol <url> <operation> | jq '.error'
```

### Metadata

```bash
# Response time
sol <url> <operation> | jq '.meta.duration_ms'

# Cache status
sol <url> <operation> | jq '.meta.cached'

# Protocol version
sol <url> <operation> | jq '.meta.version'
```

## Advanced Patterns

### Chaining Operations

```bash
# Get catalog list, then query first catalog
CATALOG=$(sol datum://staging catalog.list service=iceberg | jq -r '.data[0]')
sol datum://staging table.list catalog=$CATALOG database=default
```

### Conditional Execution

```bash
# Only proceed if successful
if sol <url> <operation> | jq -e '.ok'; then
    echo "Success"
else
    echo "Failed"
fi
```

### Batch Processing

```bash
# Process multiple items
for item in $(jq -r '.[]' items.json); do
    sol <url> create_item name=$item
done
```

### Debug Mode

```bash
# Show full request/response
sol <url> <operation> --verbose

# Skip cache
sol <url> <operation> --no-cache

# Explicit credential
sol <url> <operation> --credential my-other-cred
```

## Protocol-Specific Patterns

### OpenAPI

```bash
# Auto-discover from spec URL
sol https://petstore3.swagger.io/api/v3 -h

# List all operations
sol https://petstore3.swagger.io/api/v3 -h | grep "│"

# Execute with path params
sol https://api.github.com/repos/owner/repo get_repo owner=octocat repo=Hello-World
```

### Datum

```bash
# List catalogs
sol datum://staging catalog.list service=iceberg

# List databases in catalog
sol datum://staging database.list catalog=iceberg_prod

# Get table DDL
sol datum://staging table.create_ddl catalog=iceberg_prod database=default table=users
```

## Error Recovery

### Auth Issues

```bash
# Problem: No auth headers attached
# Solution: Check binding
sol auth bindings | grep <host>

# If no match, create binding
sol auth bind <url> <credential> --alias <short-name>
```

### URL Normalization Issues

```bash
# Problem: Custom scheme not recognized
# Solution: Check binding has correct scheme
sol auth bindings

# Ensure binding includes scheme:
# http://host → forces http://
# https://host → forces https://
```

### Cache Staleness

```bash
# Problem: Getting old data
# Solution: Clear cache
sol cache clear

# Or skip cache for one call
sol <url> <operation> --no-cache
```

## Performance Tips

1. **Use aliases**: Shorter URLs, faster typing
2. **Cache aggressively**: Set `cache_ttl` in config
3. **Batch operations**: Group related calls
4. **Parallelize**: Use `&` for concurrent calls
5. **Filter early**: Use `jq` to extract only what you need

## Security Best Practices

1. **Never commit secrets**: Use env vars or keychain
2. **Use custom auth for non-standard tokens**: Avoid bearer workarounds
3. **Rotate credentials**: Update regularly
4. **Audit bindings**: Review `sol auth bindings` periodically
5. **Scope credentials**: Use different creds for dev/prod
