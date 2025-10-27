# ulint

A linter for Umbrel apps written in Python.

[![PyPI version](https://badge.fury.io/py/umbrel-linter-python.svg)](https://badge.fury.io/py/umbrel-linter-python)

## Features

- **YAML Validation**: validation of `umbrel-app.yml` and `umbrel-app-store.yml` files
- **Docker Compose Validation**: validation of Docker Compose files with security checks
- **Directory Structure Validation**: validation of proper app directory structure
- **Security Checks**: validation of potential security vulnerabilities


## Installation

### Installation via uv

```bash
# using uv tool
uv tool install ulint

# using uvx
uvx ulint --help

# using pipx
pipx install ulint

# using pip
pip install ulint
```
### Build from Source

This project uses [uv](https://github.com/astral-sh/uv) as the package manager. Make sure you have uv installed, then:

```bash
# Clone the repository
git clone http://github.com/Mr-Sunglasses/ulint
cd ulint                

# Install dependencies
uv sync

# Install the package in development mode
uv pip install -e .
```

## Usage

### Command Line Interface

```bash
# Lint all apps in a directory
ulint lint /path/to/app-store

# Lint a specific app
umbrel-linter lint /path/to/app-store --app my-app

# Lint with specific options
umbrel-linter lint /path/to/app-store \
    --log-level error \
    --strict \
    --skip-architectures \
    --format json
```

### Available Commands

- `lint`: Main linting command
- `version`: Show version information
- `config`: Show configuration information

### Command Options

- `--app, -a`: Specific app ID to lint
- `--log-level, -l`: Log level (error, warning, info)
- `--strict, -s`: Treat warnings as errors
- `--skip-architectures`: Skip checking Docker image architectures
- `--new-submission`: This is a new app submission
- `--pr-url`: Pull request URL for new submissions
- `--store-type`: App store type (official, community)
- `--format, -f`: Output format (rich, json, plain)
- `--verbose, -v`: Verbose output

### Programmatic Usage

```python
from umbrel_linter import UmbrelLinter
from umbrel_linter.core.models import LinterConfig, LintingContext
from pathlib import Path

# Create linter with configuration
config = LinterConfig(
    check_image_architectures=True,
    log_level="warning",
    strict_mode=False
)

linter = UmbrelLinter(config)

# Lint a specific app
result = linter.lint_app(Path("/path/to/app-store"), "my-app")

# Check results
if result.has_errors():
    print(f"Found {result.total_errors} errors")
    for error in result.errors:
        print(f"{error.severity}: {error.title} - {error.message}")
```

## Configuration

The linter can be configured through the `LinterConfig` class:

```python
from umbrel_linter.core.models import LinterConfig, Severity

config = LinterConfig(
    check_image_architectures=True,  # Check Docker image architectures
    log_level=Severity.WARNING,      # Minimum log level
    strict_mode=False,               # Treat warnings as errors
    ignore_patterns=["*.tmp"]        # File patterns to ignore
)
```

## Error Types

The linter identifies various types of issues:

### YAML Validation Errors
- Invalid YAML syntax
- Missing required fields
- Invalid field types
- Schema validation failures

### Docker Compose Validation Errors
- Invalid image names and tags
- Security vulnerabilities (Docker socket mounting, root user)
- Invalid volume mounts
- Missing required files/directories
- Invalid port mappings
- Incorrect app proxy configuration

### Directory Structure Errors
- Empty directories without `.gitkeep` files
- Missing required files

### Security Warnings
- Docker socket mounting
- Root user usage
- Host network mode
- Insecure volume mounts

## Development

### Setting up Development Environment

```bash
# Install development dependencies
uv sync --dev

# Run tests
uv run pytest

# Run linting
uv run ruff check .
uv run black .

# Run type checking
uv run mypy .
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=umbrel_linter

# Run specific test file
uv run pytest tests/test_models.py
```

### Code Quality

The project uses several tools for code quality:

- **Black**: Code formatting
- **Ruff**: Fast Python linter
- **MyPy**: Static type checking
- **Pytest**: Testing framework

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.