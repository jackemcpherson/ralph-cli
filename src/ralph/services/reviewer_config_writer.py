"""Service for writing reviewer configuration to CLAUDE.md files.

This module provides functionality to read and write the RALPH:REVIEWERS
section in CLAUDE.md files, preserving all other content.
"""

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ralph.models.reviewer import ReviewerConfig

_REVIEWERS_START_MARKER = "<!-- RALPH:REVIEWERS:START -->"
_REVIEWERS_END_MARKER = "<!-- RALPH:REVIEWERS:END -->"
_PROJECT_SPECIFIC_HEADING = "## Project-Specific Instructions"

_REVIEWERS_PATTERN = re.compile(
    r"<!--\s*RALPH:REVIEWERS:START\s*-->\s*"
    r"```yaml\s*\n"
    r".*?"
    r"```\s*\n"
    r"<!--\s*RALPH:REVIEWERS:END\s*-->",
    re.DOTALL,
)


def _format_reviewer_yaml(reviewers: list[ReviewerConfig]) -> str:
    """Format reviewer configs as YAML for CLAUDE.md.

    Args:
        reviewers: List of reviewer configurations to format.

    Returns:
        Formatted YAML string wrapped in markers.
    """
    lines = ["reviewers:"]
    for reviewer in reviewers:
        lines.append(f"  - name: {reviewer.name}")
        lines.append(f"    skill: {reviewer.skill}")
        if reviewer.languages:
            langs = ", ".join(reviewer.languages)
            lines.append(f"    languages: [{langs}]")
        lines.append(f"    level: {reviewer.level.value}")

    yaml_content = "\n".join(lines)
    return f"{_REVIEWERS_START_MARKER}\n```yaml\n{yaml_content}\n```\n{_REVIEWERS_END_MARKER}"


class ReviewerConfigWriter(BaseModel):
    """Service for writing reviewer configuration to CLAUDE.md files.

    Provides methods to check for existing configuration and to write
    or update the RALPH:REVIEWERS section while preserving other content.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: Path

    def has_reviewer_config(self) -> bool:
        """Check if the CLAUDE.md file contains RALPH:REVIEWERS markers.

        Returns:
            True if the markers exist, False otherwise.
        """
        if not self.path.exists():
            return False

        content = self.path.read_text(encoding="utf-8")
        return _REVIEWERS_PATTERN.search(content) is not None

    def write_reviewer_config(self, reviewers: list[ReviewerConfig]) -> None:
        """Write or update the RALPH:REVIEWERS section in CLAUDE.md.

        If the markers already exist, replaces the content between them.
        If the markers don't exist, inserts a new section:
        - Before '## Project-Specific Instructions' if that heading exists
        - At the end of the file otherwise

        Args:
            reviewers: List of reviewer configurations to write.
        """
        formatted_config = _format_reviewer_yaml(reviewers)

        if not self.path.exists():
            section = f"## Reviewers\n\n{formatted_config}\n"
            self.path.write_text(section, encoding="utf-8")
            return

        content = self.path.read_text(encoding="utf-8")

        if _REVIEWERS_PATTERN.search(content):
            new_content = _REVIEWERS_PATTERN.sub(formatted_config, content)
            self.path.write_text(new_content, encoding="utf-8")
            return

        section_to_insert = f"\n## Reviewers\n\n{formatted_config}\n"

        if _PROJECT_SPECIFIC_HEADING in content:
            new_content = content.replace(
                _PROJECT_SPECIFIC_HEADING,
                f"{section_to_insert}\n{_PROJECT_SPECIFIC_HEADING}",
            )
        else:
            new_content = content.rstrip() + "\n" + section_to_insert

        self.path.write_text(new_content, encoding="utf-8")


def has_reviewer_config(path: Path) -> bool:
    """Check if a CLAUDE.md file contains RALPH:REVIEWERS markers.

    Convenience function that creates a ReviewerConfigWriter and checks.

    Args:
        path: Path to the CLAUDE.md file.

    Returns:
        True if the markers exist, False otherwise.
    """
    writer = ReviewerConfigWriter(path=path)
    return writer.has_reviewer_config()


def write_reviewer_config(path: Path, reviewers: list[ReviewerConfig]) -> None:
    """Write or update the RALPH:REVIEWERS section in a CLAUDE.md file.

    Convenience function that creates a ReviewerConfigWriter and writes.

    Args:
        path: Path to the CLAUDE.md file.
        reviewers: List of reviewer configurations to write.
    """
    writer = ReviewerConfigWriter(path=path)
    writer.write_reviewer_config(reviewers)
