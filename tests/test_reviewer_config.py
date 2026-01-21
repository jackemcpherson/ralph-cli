"""Unit tests for ReviewerConfig model.

Focused tests for reviewer configuration functionality:
- ReviewerLevel enum values
- ReviewerConfig model creation and validation
- Parsing reviewer configurations from CLAUDE.md
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from ralph.models import (
    ReviewerConfig,
    ReviewerConfigs,
    ReviewerLevel,
    get_default_reviewers,
    load_reviewer_configs,
    parse_reviewer_configs,
)


class TestReviewerLevel:
    """Tests for the ReviewerLevel enum."""

    def test_reviewer_level_blocking_value(self) -> None:
        """Test blocking level has correct value."""
        assert ReviewerLevel.blocking.value == "blocking"

    def test_reviewer_level_warning_value(self) -> None:
        """Test warning level has correct value."""
        assert ReviewerLevel.warning.value == "warning"

    def test_reviewer_level_suggestion_value(self) -> None:
        """Test suggestion level has correct value."""
        assert ReviewerLevel.suggestion.value == "suggestion"

    def test_reviewer_level_is_str_enum(self) -> None:
        """Test ReviewerLevel inherits from str and can be compared as string."""
        assert ReviewerLevel.blocking == "blocking"
        assert ReviewerLevel.warning == "warning"
        assert ReviewerLevel.suggestion == "suggestion"

    def test_reviewer_level_all_values(self) -> None:
        """Test all expected enum values exist."""
        values = {level.value for level in ReviewerLevel}
        assert values == {"blocking", "warning", "suggestion"}


class TestReviewerConfig:
    """Tests for the ReviewerConfig model."""

    def test_reviewer_config_with_all_fields(self) -> None:
        """Test ReviewerConfig with all fields provided."""
        config = ReviewerConfig(
            name="Python Code Reviewer",
            skill="reviewers/language/python",
            level=ReviewerLevel.blocking,
            languages=["python"],
        )

        assert config.name == "Python Code Reviewer"
        assert config.skill == "reviewers/language/python"
        assert config.level == ReviewerLevel.blocking
        assert config.languages == ["python"]

    def test_reviewer_config_languages_defaults_to_none(self) -> None:
        """Test languages field defaults to None when not provided."""
        config = ReviewerConfig(
            name="Code Simplifier",
            skill="reviewers/code-simplifier",
            level=ReviewerLevel.warning,
        )

        assert config.languages is None

    def test_reviewer_config_with_multiple_languages(self) -> None:
        """Test ReviewerConfig with multiple languages."""
        config = ReviewerConfig(
            name="Multi-language Reviewer",
            skill="reviewers/multi",
            level=ReviewerLevel.suggestion,
            languages=["python", "javascript", "typescript"],
        )

        assert config.languages == ["python", "javascript", "typescript"]
        assert len(config.languages) == 3

    def test_reviewer_config_with_empty_languages_list(self) -> None:
        """Test ReviewerConfig accepts empty languages list."""
        config = ReviewerConfig(
            name="Test Reviewer",
            skill="reviewers/test",
            level=ReviewerLevel.blocking,
            languages=[],
        )

        assert config.languages == []

    def test_reviewer_config_level_accepts_string(self) -> None:
        """Test level field accepts string that maps to enum."""
        config = ReviewerConfig(
            name="Test Reviewer",
            skill="reviewers/test",
            level="blocking",  # type: ignore[arg-type]
        )

        assert config.level == ReviewerLevel.blocking

    def test_reviewer_config_requires_name(self) -> None:
        """Test name field is required."""
        with pytest.raises(ValidationError) as exc_info:
            ReviewerConfig(
                skill="reviewers/test",
                level=ReviewerLevel.blocking,
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)

    def test_reviewer_config_requires_skill(self) -> None:
        """Test skill field is required."""
        with pytest.raises(ValidationError) as exc_info:
            ReviewerConfig(
                name="Test Reviewer",
                level=ReviewerLevel.blocking,
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("skill",) for error in errors)

    def test_reviewer_config_requires_level(self) -> None:
        """Test level field is required."""
        with pytest.raises(ValidationError) as exc_info:
            ReviewerConfig(
                name="Test Reviewer",
                skill="reviewers/test",
            )  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("level",) for error in errors)

    def test_reviewer_config_invalid_level_raises_error(self) -> None:
        """Test invalid level value raises ValidationError."""
        with pytest.raises(ValidationError):
            ReviewerConfig(
                name="Test Reviewer",
                skill="reviewers/test",
                level="invalid_level",  # type: ignore[arg-type]
            )

    def test_reviewer_config_serialization(self) -> None:
        """Test ReviewerConfig can be serialized to dict."""
        config = ReviewerConfig(
            name="Python Reviewer",
            skill="reviewers/python",
            level=ReviewerLevel.blocking,
            languages=["python"],
        )

        data = config.model_dump()

        assert data["name"] == "Python Reviewer"
        assert data["skill"] == "reviewers/python"
        assert data["level"] == ReviewerLevel.blocking
        assert data["languages"] == ["python"]

    def test_reviewer_config_from_dict(self) -> None:
        """Test ReviewerConfig can be created from dict."""
        data = {
            "name": "Test Reviewer",
            "skill": "reviewers/test",
            "level": "warning",
            "languages": ["go", "rust"],
        }

        config = ReviewerConfig.model_validate(data)

        assert config.name == "Test Reviewer"
        assert config.skill == "reviewers/test"
        assert config.level == ReviewerLevel.warning
        assert config.languages == ["go", "rust"]


class TestReviewerConfigs:
    """Tests for the ReviewerConfigs container model."""

    def test_reviewer_configs_with_reviewers(self) -> None:
        """Test ReviewerConfigs with a list of reviewers."""
        configs = ReviewerConfigs(
            reviewers=[
                ReviewerConfig(
                    name="Test Reviewer",
                    skill="reviewers/test",
                    level=ReviewerLevel.blocking,
                ),
            ]
        )

        assert len(configs.reviewers) == 1
        assert configs.reviewers[0].name == "Test Reviewer"

    def test_reviewer_configs_defaults_to_empty_list(self) -> None:
        """Test ReviewerConfigs defaults to empty list."""
        configs = ReviewerConfigs()
        assert configs.reviewers == []


class TestGetDefaultReviewers:
    """Tests for the get_default_reviewers function."""

    def test_get_default_reviewers_returns_list(self) -> None:
        """Test get_default_reviewers returns a list of ReviewerConfig."""
        reviewers = get_default_reviewers()

        assert isinstance(reviewers, list)
        assert len(reviewers) > 0
        assert all(isinstance(r, ReviewerConfig) for r in reviewers)

    def test_get_default_reviewers_contains_expected_reviewers(self) -> None:
        """Test default reviewers contain expected reviewer names."""
        reviewers = get_default_reviewers()
        names = [r.name for r in reviewers]

        assert "test-quality" in names
        assert "code-simplifier" in names
        assert "python-code" in names
        assert "github-actions" in names
        assert "repo-structure" in names
        assert "release" in names

    def test_get_default_reviewers_python_code_has_language_filter(self) -> None:
        """Test python-code reviewer has python language filter."""
        reviewers = get_default_reviewers()
        python_reviewer = next(r for r in reviewers if r.name == "python-code")

        assert python_reviewer.languages == ["python"]

    def test_get_default_reviewers_levels_are_correct(self) -> None:
        """Test default reviewers have correct levels."""
        reviewers = get_default_reviewers()
        reviewer_map = {r.name: r for r in reviewers}

        assert reviewer_map["test-quality"].level == ReviewerLevel.blocking
        assert reviewer_map["code-simplifier"].level == ReviewerLevel.blocking
        assert reviewer_map["python-code"].level == ReviewerLevel.blocking
        assert reviewer_map["github-actions"].level == ReviewerLevel.warning
        assert reviewer_map["repo-structure"].level == ReviewerLevel.warning
        assert reviewer_map["release"].level == ReviewerLevel.blocking


class TestParseReviewerConfigs:
    """Tests for the parse_reviewer_configs function."""

    def test_parse_valid_reviewers_block(self) -> None:
        """Test parsing a valid reviewers block."""
        content = """# Project Instructions

## Reviewers

<!-- RALPH:REVIEWERS:START -->
```yaml
reviewers:
  - name: test-quality
    skill: reviewers/test-quality
    level: blocking
  - name: code-simplifier
    skill: reviewers/code-simplifier
    level: warning
```
<!-- RALPH:REVIEWERS:END -->
"""
        reviewers = parse_reviewer_configs(content)

        assert len(reviewers) == 2
        assert reviewers[0].name == "test-quality"
        assert reviewers[0].level == ReviewerLevel.blocking
        assert reviewers[1].name == "code-simplifier"
        assert reviewers[1].level == ReviewerLevel.warning

    def test_parse_reviewers_missing_markers_returns_defaults(self) -> None:
        """Test parsing content without markers returns defaults."""
        content = """# Project Instructions

Just some regular content without reviewer configuration.
"""
        reviewers = parse_reviewer_configs(content)
        default_reviewers = get_default_reviewers()

        assert len(reviewers) == len(default_reviewers)
        assert reviewers[0].name == default_reviewers[0].name

    def test_parse_reviewers_with_languages_filter(self) -> None:
        """Test parsing reviewers with languages filter."""
        content = """<!-- RALPH:REVIEWERS:START -->
```yaml
reviewers:
  - name: python-code
    skill: reviewers/language/python
    level: blocking
    languages: [python]
```
<!-- RALPH:REVIEWERS:END -->
"""
        reviewers = parse_reviewer_configs(content)

        assert len(reviewers) == 1
        assert reviewers[0].languages == ["python"]

    def test_parse_reviewers_malformed_yaml_returns_defaults(self) -> None:
        """Test parsing malformed YAML gracefully returns defaults."""
        content = """<!-- RALPH:REVIEWERS:START -->
```yaml
reviewers:
  - name: test-quality
    skill: [this is invalid yaml
    level: blocking
```
<!-- RALPH:REVIEWERS:END -->
"""
        reviewers = parse_reviewer_configs(content)
        default_reviewers = get_default_reviewers()

        assert len(reviewers) == len(default_reviewers)

    def test_parse_reviewers_invalid_structure_returns_defaults(self) -> None:
        """Test parsing valid YAML with invalid structure returns defaults."""
        content = """<!-- RALPH:REVIEWERS:START -->
```yaml
not_reviewers:
  - name: test-quality
    skill: reviewers/test-quality
    level: blocking
```
<!-- RALPH:REVIEWERS:END -->
"""
        reviewers = parse_reviewer_configs(content)
        default_reviewers = get_default_reviewers()

        assert len(reviewers) == len(default_reviewers)

    def test_parse_reviewers_empty_list_returns_defaults(self) -> None:
        """Test parsing empty reviewers list returns defaults."""
        content = """<!-- RALPH:REVIEWERS:START -->
```yaml
reviewers: []
```
<!-- RALPH:REVIEWERS:END -->
"""
        reviewers = parse_reviewer_configs(content)
        default_reviewers = get_default_reviewers()

        assert len(reviewers) == len(default_reviewers)

    def test_parse_reviewers_with_all_levels(self) -> None:
        """Test parsing reviewers with all severity levels."""
        content = """<!-- RALPH:REVIEWERS:START -->
```yaml
reviewers:
  - name: blocker
    skill: reviewers/blocker
    level: blocking
  - name: warner
    skill: reviewers/warner
    level: warning
  - name: suggester
    skill: reviewers/suggester
    level: suggestion
```
<!-- RALPH:REVIEWERS:END -->
"""
        reviewers = parse_reviewer_configs(content)

        assert len(reviewers) == 3
        assert reviewers[0].level == ReviewerLevel.blocking
        assert reviewers[1].level == ReviewerLevel.warning
        assert reviewers[2].level == ReviewerLevel.suggestion


class TestLoadReviewerConfigs:
    """Tests for the load_reviewer_configs function."""

    def test_load_reviewer_configs_from_file(self, tmp_path: Path) -> None:
        """Test loading reviewer configs from a file."""
        content = """# CLAUDE.md

<!-- RALPH:REVIEWERS:START -->
```yaml
reviewers:
  - name: test-quality
    skill: reviewers/test-quality
    level: blocking
```
<!-- RALPH:REVIEWERS:END -->
"""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(content)

        reviewers = load_reviewer_configs(claude_md)

        assert len(reviewers) == 1
        assert reviewers[0].name == "test-quality"

    def test_load_reviewer_configs_nonexistent_file_returns_defaults(self, tmp_path: Path) -> None:
        """Test loading from nonexistent file returns defaults."""
        claude_md = tmp_path / "nonexistent.md"

        reviewers = load_reviewer_configs(claude_md)
        default_reviewers = get_default_reviewers()

        assert len(reviewers) == len(default_reviewers)

    def test_load_reviewer_configs_file_without_markers_returns_defaults(
        self, tmp_path: Path
    ) -> None:
        """Test loading from file without markers returns defaults."""
        content = """# CLAUDE.md

No reviewer configuration here.
"""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(content)

        reviewers = load_reviewer_configs(claude_md)
        default_reviewers = get_default_reviewers()

        assert len(reviewers) == len(default_reviewers)
