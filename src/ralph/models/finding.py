"""Pydantic models for structured review findings.

This module defines data models for parsing structured findings from
reviewer output so the fix loop can process them programmatically.
"""

import re
from enum import Enum

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    """Review verdict indicating whether code passed or needs work.

    Values:
        PASSED: Code passed the review with no issues.
        NEEDS_WORK: Code has issues that need to be addressed.
    """

    PASSED = "PASSED"
    NEEDS_WORK = "NEEDS_WORK"


class Finding(BaseModel):
    """A single finding from a code reviewer.

    Represents an issue identified during code review with enough
    context for the fix loop to resolve it.

    Attributes:
        id: Unique finding identifier (e.g., FINDING-001).
        category: Category of the issue (e.g., "Type Safety", "Code Style").
        file_path: Path to the file containing the issue.
        line_number: Line number where the issue occurs.
        issue: Detailed description of the problem.
        suggestion: Recommended fix for the issue.
    """

    id: str = Field(..., description="Unique finding identifier (e.g., FINDING-001)")
    category: str = Field(..., description="Category of the issue")
    file_path: str = Field(..., description="Path to the file containing the issue")
    line_number: int | None = Field(default=None, description="Line number where the issue occurs")
    issue: str = Field(..., description="Detailed description of the problem")
    suggestion: str = Field(..., description="Recommended fix for the issue")


class ReviewOutput(BaseModel):
    """Structured output from a code reviewer.

    Contains the verdict and any findings identified during review.

    Attributes:
        verdict: Whether the code passed or needs work.
        findings: List of issues found during review (empty if passed).
    """

    verdict: Verdict = Field(..., description="Review verdict (PASSED or NEEDS_WORK)")
    findings: list[Finding] = Field(
        default_factory=list, description="List of findings (empty if passed)"
    )


# Pattern to extract verdict from markdown
_VERDICT_PATTERN = re.compile(
    r"###\s*Verdict:\s*(PASSED|NEEDS_WORK)",
    re.IGNORECASE,
)

# Pattern to extract individual findings from markdown
# Matches format like:
# 1. **FINDING-001**: Category - Brief description
#    - File: path/to/file.py:123
#    - Issue: Description
#    - Suggestion: Fix recommendation
_FINDING_PATTERN = re.compile(
    r"\d+\.\s*\*\*([^*]+)\*\*:\s*([^-\n]+)\s*-\s*[^\n]*\n"
    r"\s*-\s*File:\s*([^\n:]+)(?::(\d+))?\n"
    r"\s*-\s*Issue:\s*([^\n]+(?:\n(?!\s*-\s*(?:Suggestion|File):)[^\n]*)*)\n"
    r"\s*-\s*Suggestion:\s*([^\n]+(?:\n(?!\s*(?:\d+\.\s*\*\*|---|\[Review))[^\n]*)*)",
    re.MULTILINE,
)


def parse_review_output(text: str) -> ReviewOutput:
    """Parse structured review output from markdown text.

    Extracts the verdict and findings from the reviewer's markdown output
    following the structured format defined in SPEC.md.

    Args:
        text: The markdown text output from a reviewer

    Returns:
        ReviewOutput with verdict and parsed findings
    """
    # Extract verdict
    verdict_match = _VERDICT_PATTERN.search(text)
    if verdict_match:
        verdict_str = verdict_match.group(1).upper()
        verdict = Verdict(verdict_str)
    else:
        # Default to PASSED if no verdict found (legacy behavior)
        verdict = Verdict.PASSED

    # If passed, return immediately with no findings
    if verdict == Verdict.PASSED:
        return ReviewOutput(verdict=verdict, findings=[])

    # Extract findings
    findings: list[Finding] = []
    for match in _FINDING_PATTERN.finditer(text):
        finding_id = match.group(1).strip()
        category = match.group(2).strip()
        file_path = match.group(3).strip()
        line_number_str = match.group(4)
        issue = match.group(5).strip()
        suggestion = match.group(6).strip()

        # Parse line number if present
        line_number = int(line_number_str) if line_number_str else None

        findings.append(
            Finding(
                id=finding_id,
                category=category,
                file_path=file_path,
                line_number=line_number,
                issue=issue,
                suggestion=suggestion,
            )
        )

    return ReviewOutput(verdict=verdict, findings=findings)
