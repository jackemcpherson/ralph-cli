"""Unit tests for ReviewerConfig model.

Focused tests for reviewer configuration functionality:
- ReviewerLevel enum values
- ReviewerConfig model creation and validation
"""

import pytest
from pydantic import ValidationError

from ralph.models import ReviewerConfig, ReviewerLevel


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
