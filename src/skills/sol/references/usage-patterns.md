# Sol Usage Patterns

## Common Workflows

### Discovery Flow

```bash
# 1. Discover operations
sol https://petstore3.swagger.io/api/v3 -h

# 2. Inspect specific operation
sol https://petstore3.swagger.io/api/v3 getPetById -h

# 3. Execute
sol https://petstore3.swagger.io/api/v3 getPetById petId=1
```

### Auth Setup Flow

```bash
# 1. Create credential
sol auth set prod-key --type bearer --secret "sk-xxxxxxxxxxxx"

# 2. Bind with alias
sol auth bind https://api.production.example.com prod-key --alias prod

# 3. Verify
sol auth bindings | grep prod

# 4. Use
sol myapi://prod listUsers
```

### Multi-Environment Pattern

```bash
# Setup credentials
sol auth set dev-key --secret "dev-token"
sol auth set staging-key --secret "staging-token"
sol auth set prod-key --secret "prod-token"

# Bind with aliases
sol auth bind https://api-dev.example.com dev-key --alias dev
sol auth bind https://api-staging.example.com staging-key --alias staging
sol auth bind https://api-prod.example.com prod-key --alias prod

# Switch environments easily
sol myapi://dev getStatus
sol myapi://staging getStatus
sol myapi://prod getStatus
```

## Input Patterns

### Simple Parameters

```bash
# String
sol <url> createUser name=alice

# Number
sol <url> getPage limit=10 offset=20

# Boolean
sol <url> updateSettings enabled=true debug=false

# Multiple params
sol <url> searchUsers name=alice age=30 active=true
```

### Nested Objects

```bash
# Dot notation
sol <url> updateProfile user.name=alice user.email=alice@example.com

# Equivalent JSON
sol <url> updateProfile '{"user":{"name":"alice","email":"alice@example.com"}}'
```

### Arrays

```bash
# Comma-separated
sol <url> getTags tags=alpha,beta,gamma

# JSON array
sol <url> getTags '{"tags":["alpha","beta","gamma"]}'
```

### Complex Payloads

```bash
# From file
sol <url> createResource "$(cat payload.json)"

# Inline with jq
sol <url> createResource "$(echo '{}' | jq '.name="test" | .type="demo"')"
```

## Output Parsing

### Extract Data

```bash
# Get data field
sol <url> <operation> | jq '.data'

# Get specific field
sol <url> getUser id=123 | jq '.data.name'

# Get array element
sol <url> listUsers | jq '.data.users[0]'
```

### Error Handling

```bash
# Check success
if sol <url> <operation> | jq -e '.ok'; then
  echo "Success"
else
  echo "Failed"
fi

# Extract error
ERROR=$(sol <url> <operation> | jq -r '.error.message')
echo "Error: $ERROR"
```

### Chaining Operations

```bash
# Get first user ID, then fetch details
USER_ID=$(sol <url> listUsers | jq -r '.data.users[0].id')
sol <url> getUser id=$USER_ID
```

## Best Practices

### Security

- ✅ Store credentials with `sol auth set`, never hardcode
- ✅ Use environment variables: `sol auth set key --secret "$API_TOKEN"`
- ✅ Rotate credentials regularly
- ✅ Use different credentials for dev/staging/prod
- ❌ Never commit credentials to git

### Organization

- ✅ Use descriptive aliases: `prod`, `staging`, `us-west`
- ✅ Consistent naming: `<env>-<region>` or `<service>-<env>`
- ❌ Avoid generic names: `api`, `test`, `temp`

### Performance

- ✅ Use cache for expensive read operations
- ✅ Skip cache for write operations: `--no-cache`
- ✅ Batch operations when possible
- ✅ Use aliases to reduce URL parsing overhead

### Debugging

- ✅ Check `sol auth bindings` when auth fails
- ✅ Use `jq '.error'` to extract error details
- ✅ Verify protocol detection with `sol <url> -h`
- ✅ Test with simple operations first
