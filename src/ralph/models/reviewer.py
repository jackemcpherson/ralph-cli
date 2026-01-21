"""Pydantic models for reviewer configuration.

This module defines data models for configuring code reviewers
that run as part of the Ralph review loop.
"""

import re
from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ReviewerLevel(str, Enum):
    """Severity level for a reviewer.

    Determines how reviewer results affect the iteration workflow.

    Values:
        blocking: Reviewer failures must be fixed before proceeding.
        warning: Reviewer issues are reported but don't block progress.
        suggestion: Reviewer feedback is optional/advisory.
    """

    blocking = "blocking"
    warning = "warning"
    suggestion = "suggestion"


class ReviewerConfig(BaseModel):
    """Configuration for a single code reviewer.

    Defines a reviewer's settings including which skill to use,
    its severity level, and optional language filtering.

    Attributes:
        name: Display name of the reviewer.
        skill: Skill path to invoke for this reviewer.
        level: Severity level (blocking, warning, suggestion).
        languages: Optional list of languages this reviewer applies to.
            If None, the reviewer applies to all projects.
    """

    name: str = Field(..., description="Display name of the reviewer")
    skill: str = Field(..., description="Skill path to invoke for this reviewer")
    level: ReviewerLevel = Field(..., description="Severity level")
    languages: list[str] | None = Field(
        default=None,
        description="Languages this reviewer applies to (None = all)",
    )


class ReviewerConfigs(BaseModel):
    """Container for reviewer configuration definitions.

    Holds a list of reviewer configs parsed from CLAUDE.md.

    Attributes:
        reviewers: List of reviewer configuration definitions.
    """

    reviewers: list[ReviewerConfig] = Field(
        default_factory=list, description="List of reviewer configurations"
    )


_REVIEWERS_PATTERN = re.compile(
    r"<!--\s*RALPH:REVIEWERS:START\s*-->\s*"
    r"```yaml\s*\n"
    r"(.*?)"
    r"```\s*\n"
    r"<!--\s*RALPH:REVIEWERS:END\s*-->",
    re.DOTALL,
)


def get_default_reviewers() -> list[ReviewerConfig]:
    """Return the default reviewer configuration.

    Used when CLAUDE.md does not contain RALPH:REVIEWERS markers.

    Returns:
        List of default ReviewerConfig objects.
    """
    return [
        ReviewerConfig(
            name="test-quality",
            skill="reviewers/test-quality",
            level=ReviewerLevel.blocking,
        ),
        ReviewerConfig(
            name="code-simplifier",
            skill="reviewers/code-simplifier",
            level=ReviewerLevel.blocking,
        ),
        ReviewerConfig(
            name="python-code",
            skill="reviewers/language/python",
            level=ReviewerLevel.blocking,
            languages=["python"],
        ),
        ReviewerConfig(
            name="github-actions",
            skill="reviewers/github-actions",
            level=ReviewerLevel.warning,
        ),
        ReviewerConfig(
            name="repo-structure",
            skill="reviewers/repo-structure",
            level=ReviewerLevel.warning,
        ),
        ReviewerConfig(
            name="release",
            skill="reviewers/release",
            level=ReviewerLevel.blocking,
        ),
    ]


def parse_reviewer_configs(content: str) -> list[ReviewerConfig]:
    """Parse reviewer configurations from CLAUDE.md content.

    Extracts the YAML block between RALPH:REVIEWERS:START and RALPH:REVIEWERS:END
    markers and validates it against the ReviewerConfig model.

    Args:
        content: The content of a CLAUDE.md file

    Returns:
        List of ReviewerConfig objects from the YAML block, or default
        reviewers if the markers are missing or content is malformed.
    """
    match = _REVIEWERS_PATTERN.search(content)
    if not match:
        return get_default_reviewers()

    yaml_content = match.group(1)
    try:
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            return get_default_reviewers()
        configs = ReviewerConfigs.model_validate(data)
        if not configs.reviewers:
            return get_default_reviewers()
        return configs.reviewers
    except (yaml.YAMLError, ValueError):
        return get_default_reviewers()


def load_reviewer_configs(path: Path) -> list[ReviewerConfig]:
    """Load reviewer configurations from a CLAUDE.md file.

    Args:
        path: Path to the CLAUDE.md file

    Returns:
        List of ReviewerConfig objects from the YAML block, or default
        reviewers if the file doesn't exist or content is malformed.
    """
    if not path.exists():
        return get_default_reviewers()

    content = path.read_text(encoding="utf-8")
    return parse_reviewer_configs(content)
