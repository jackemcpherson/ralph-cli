"""Unit tests for QualityCheck model and parsing.

Focused tests for quality check functionality:
- QualityCheck model creation
- Parsing quality checks from CLAUDE.md
"""

from pathlib import Path

from ralph.models import (
    QualityCheck,
    load_quality_checks,
    parse_quality_checks,
)


class TestQualityCheck:
    """Tests for the QualityCheck model."""

    def test_quality_check_creation(self) -> None:
        """Test QualityCheck with all fields provided."""
        check = QualityCheck(
            name="typecheck",
            command="uv run pyright",
            required=True,
        )

        assert check.name == "typecheck"
        assert check.command == "uv run pyright"
        assert check.required is True

    def test_quality_check_required_defaults_to_true(self) -> None:
        """Test QualityCheck required field defaults to True."""
        check = QualityCheck(name="lint", command="uv run ruff check .")
        assert check.required is True


class TestParseQualityChecks:
    """Tests for the parse_quality_checks function."""

    def test_parse_valid_checks_block(self) -> None:
        """Test parsing a valid quality checks block."""
        content = """# Project Instructions

## Quality Checks

<!-- RALPH:CHECKS:START -->
```yaml
checks:
  - name: typecheck
    command: uv run pyright
    required: true
  - name: lint
    command: uv run ruff check .
    required: true
```
<!-- RALPH:CHECKS:END -->
"""
        checks = parse_quality_checks(content)

        assert len(checks.checks) == 2
        assert checks.checks[0].name == "typecheck"
        assert checks.checks[1].name == "lint"

    def test_parse_checks_missing_markers_returns_empty(self) -> None:
        """Test parsing content without markers returns empty."""
        content = """# Project Instructions

Just some regular content without quality checks.
"""
        checks = parse_quality_checks(content)
        assert checks.checks == []

    def test_parse_checks_with_optional_check(self) -> None:
        """Test parsing checks with required=false."""
        content = """<!-- RALPH:CHECKS:START -->
```yaml
checks:
  - name: coverage
    command: uv run pytest --cov
    required: false
```
<!-- RALPH:CHECKS:END -->
"""
        checks = parse_quality_checks(content)

        assert len(checks.checks) == 1
        assert checks.checks[0].required is False


class TestLoadQualityChecks:
    """Tests for the load_quality_checks function."""

    def test_load_quality_checks_from_file(self, tmp_path: Path) -> None:
        """Test loading quality checks from a file."""
        content = """# CLAUDE.md

<!-- RALPH:CHECKS:START -->
```yaml
checks:
  - name: typecheck
    command: uv run pyright
```
<!-- RALPH:CHECKS:END -->
"""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(content)

        checks = load_quality_checks(claude_md)

        assert len(checks.checks) == 1
        assert checks.checks[0].name == "typecheck"

    def test_load_quality_checks_nonexistent_file_returns_empty(self, tmp_path: Path) -> None:
        """Test loading from nonexistent file returns empty checks."""
        claude_md = tmp_path / "nonexistent.md"

        checks = load_quality_checks(claude_md)

        assert checks.checks == []
