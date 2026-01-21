"""Pydantic models for reviewer configuration.

This module defines data models for configuring code reviewers
that run as part of the Ralph review loop.
"""

from enum import Enum

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
