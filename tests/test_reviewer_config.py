"""Tests for ReviewerConfig model and parsing."""

from pathlib import Path

from ralph.models import (
    ReviewerConfig,
    ReviewerLevel,
    get_default_reviewers,
    load_reviewer_configs,
    parse_reviewer_configs,
)


class TestReviewerConfig:
    """Tests for ReviewerConfig model."""

    def test_creates_config_with_all_fields(self) -> None:
        """Test ReviewerConfig creation with all fields."""
        config = ReviewerConfig(
            name="python-code",
            skill="reviewers/language/python",
            level=ReviewerLevel.blocking,
            languages=["python"],
        )

        assert config.name == "python-code"
        assert config.skill == "reviewers/language/python"
        assert config.level == ReviewerLevel.blocking
        assert config.languages == ["python"]

    def test_languages_defaults_to_none(self) -> None:
        """Test languages field defaults to None."""
        config = ReviewerConfig(
            name="test",
            skill="reviewers/test",
            level=ReviewerLevel.warning,
        )

        assert config.languages is None

    def test_level_accepts_string(self) -> None:
        """Test level field accepts string that maps to enum."""
        config = ReviewerConfig(
            name="test",
            skill="reviewers/test",
            level="blocking",  # type: ignore[arg-type]
        )

        assert config.level == ReviewerLevel.blocking


class TestGetDefaultReviewers:
    """Tests for default reviewer configuration."""

    def test_returns_expected_reviewers(self) -> None:
        """Test default reviewers contain expected configuration."""
        reviewers = get_default_reviewers()
        reviewer_map = {r.name: r for r in reviewers}

        assert len(reviewers) == 6
        assert "test-quality" in reviewer_map
        assert "code-simplifier" in reviewer_map
        assert "python-code" in reviewer_map
        assert "github-actions" in reviewer_map
        assert "repo-structure" in reviewer_map
        assert "release" in reviewer_map

        assert reviewer_map["python-code"].languages == ["python"]
        assert reviewer_map["test-quality"].level == ReviewerLevel.blocking
        assert reviewer_map["github-actions"].level == ReviewerLevel.warning


class TestParseReviewerConfigs:
    """Tests for parsing reviewer configs from CLAUDE.md."""

    def test_parses_valid_reviewers_block(self) -> None:
        """Test parsing a valid reviewers block."""
        content = """<!-- RALPH:REVIEWERS:START -->
```yaml
reviewers:
  - name: test-quality
    skill: reviewers/test-quality
    level: blocking
  - name: code-simplifier
    skill: reviewers/code-simplifier
    level: warning
    languages: [python, go]
```
<!-- RALPH:REVIEWERS:END -->
"""
        reviewers = parse_reviewer_configs(content)

        assert len(reviewers) == 2
        assert reviewers[0].name == "test-quality"
        assert reviewers[0].level == ReviewerLevel.blocking
        assert reviewers[1].name == "code-simplifier"
        assert reviewers[1].languages == ["python", "go"]

    def test_returns_defaults_when_no_markers(self) -> None:
        """Test returns defaults when markers not found."""
        content = "# Just some content without reviewer config"

        reviewers = parse_reviewer_configs(content)

        assert len(reviewers) == len(get_default_reviewers())

    def test_returns_defaults_on_malformed_yaml(self) -> None:
        """Test returns defaults on malformed YAML."""
        content = """<!-- RALPH:REVIEWERS:START -->
```yaml
reviewers:
  - name: test
    skill: [this is invalid yaml
```
<!-- RALPH:REVIEWERS:END -->
"""
        reviewers = parse_reviewer_configs(content)

        assert len(reviewers) == len(get_default_reviewers())


class TestLoadReviewerConfigs:
    """Tests for loading reviewer configs from file."""

    def test_loads_from_file(self, tmp_path: Path) -> None:
        """Test loading reviewer configs from a file."""
        content = """<!-- RALPH:REVIEWERS:START -->
```yaml
reviewers:
  - name: custom-reviewer
    skill: reviewers/custom
    level: suggestion
```
<!-- RALPH:REVIEWERS:END -->
"""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(content)

        reviewers = load_reviewer_configs(claude_md)

        assert len(reviewers) == 1
        assert reviewers[0].name == "custom-reviewer"
        assert reviewers[0].level == ReviewerLevel.suggestion

    def test_returns_defaults_for_nonexistent_file(self, tmp_path: Path) -> None:
        """Test returns defaults when file doesn't exist."""
        reviewers = load_reviewer_configs(tmp_path / "nonexistent.md")

        assert len(reviewers) == len(get_default_reviewers())
