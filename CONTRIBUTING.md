# Contributing to Ralph CLI

Thank you for your interest in contributing to Ralph CLI! This document provides guidelines and instructions for contributing.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/jackemcpherson/ralph-cli.git
   cd ralph-cli
   ```

2. **Install uv** (if not already installed)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Install dependencies**
   ```bash
   uv pip install -e ".[dev]"
   ```

4. **Verify your setup**
   ```bash
   ralph --version
   uv run pytest
   ```

## Code Standards

### Style Guidelines

- Follow PEP 8 style guidelines
- Use type hints for all function signatures
- Write Google-style docstrings for all public functions and classes
- Maximum line length is 100 characters

### Quality Checks

Before submitting a pull request, ensure all checks pass:

```bash
# Type checking
uv run pyright

# Linting
uv run ruff check .

# Formatting
uv run ruff format .

# Tests
uv run pytest
```

## Making Changes

1. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clear, concise commit messages
   - Include tests for new functionality
   - Update documentation as needed

3. **Run quality checks**
   ```bash
   uv run pyright && uv run ruff check . && uv run pytest
   ```

4. **Submit a pull request**
   - Provide a clear description of the changes
   - Reference any related issues

## Project Structure

```
ralph-cli/
├── src/ralph/           # Source code
│   ├── cli.py          # CLI entry point
│   ├── commands/       # Command implementations
│   ├── models/         # Pydantic models
│   ├── services/       # Business logic
│   └── utils/          # Utilities
├── tests/              # Test files
├── skills/             # Claude Code skill definitions
└── plans/              # Ralph workflow files
```

## Reporting Issues

When reporting issues, please include:

- A clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Your Python version and OS

## Questions?

Feel free to open an issue for any questions about contributing.
