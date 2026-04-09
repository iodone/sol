# Sol development tasks

# Install dependencies and sync the project
install:
    uv sync

# Run linting (ruff) and type checking (mypy)
check:
    uv run ruff check src/
    uv run mypy src/

# Run the test suite
test:
    uv run pytest

# Build the distribution package
build:
    uv build

# Format code with black
format:
    uv run black src/ tests/

# Remove build artifacts and rebuild
clean-build:
    rm -rf dist/ build/ src/*.egg-info
    uv build
