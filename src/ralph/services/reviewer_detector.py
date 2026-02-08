"""Reviewer detection service for analyzing project characteristics.

This module provides functionality to analyze a project and determine
which code reviewers should be configured based on project contents.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ralph.models.reviewer import ReviewerConfig, ReviewerLevel


class ReviewerDetector(BaseModel):
    """Service for detecting which reviewers should be configured for a project.

    Analyzes the project directory to determine which reviewers are applicable
    based on file types, directory structure, and project configuration.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    project_root: Path

    def detect_reviewers(self) -> list[ReviewerConfig]:
        """Detect which reviewers should be configured for this project.

        Analyzes the project to find:
        - Python files → python-code reviewer
        - Bicep files → bicep reviewer
        - GitHub Actions workflows → github-actions reviewer
        - Test files → test-quality reviewer
        - CHANGELOG.md → release reviewer
        - Always includes: code-simplifier, repo-structure

        Returns:
            List of ReviewerConfig objects for detected reviewers.
        """
        reviewers: list[ReviewerConfig] = []

        reviewers.append(
            ReviewerConfig(
                name="code-simplifier",
                skill="reviewers/code-simplifier",
                level=ReviewerLevel.blocking,
            )
        )
        reviewers.append(
            ReviewerConfig(
                name="repo-structure",
                skill="reviewers/repo-structure",
                level=ReviewerLevel.warning,
            )
        )

        if self._has_python_files():
            reviewers.append(
                ReviewerConfig(
                    name="python-code",
                    skill="reviewers/language/python",
                    level=ReviewerLevel.blocking,
                    languages=["python"],
                )
            )

        if self._has_bicep_files():
            reviewers.append(
                ReviewerConfig(
                    name="bicep",
                    skill="reviewers/language/bicep",
                    level=ReviewerLevel.blocking,
                    languages=["bicep"],
                )
            )

        if self._has_github_actions():
            reviewers.append(
                ReviewerConfig(
                    name="github-actions",
                    skill="reviewers/github-actions",
                    level=ReviewerLevel.warning,
                )
            )

        if self._has_test_files():
            reviewers.append(
                ReviewerConfig(
                    name="test-quality",
                    skill="reviewers/test-quality",
                    level=ReviewerLevel.blocking,
                )
            )

        if self._has_changelog():
            reviewers.append(
                ReviewerConfig(
                    name="release",
                    skill="reviewers/release",
                    level=ReviewerLevel.blocking,
                )
            )

        return reviewers

    def _has_python_files(self) -> bool:
        """Check if the project contains Python files."""
        matches = list(self.project_root.glob("**/*.py"))
        return len(matches) > 0

    def _has_bicep_files(self) -> bool:
        """Check if the project contains Bicep files."""
        matches = list(self.project_root.glob("**/*.bicep"))
        return len(matches) > 0

    def _has_github_actions(self) -> bool:
        """Check if the project has GitHub Actions workflows."""
        workflows_dir = self.project_root / ".github" / "workflows"
        if not workflows_dir.exists():
            return False
        matches = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
        return len(matches) > 0

    def _has_test_files(self) -> bool:
        """Check if the project contains test files (test_*.py or *_test.py)."""
        test_prefix_matches = list(self.project_root.glob("**/test_*.py"))
        test_suffix_matches = list(self.project_root.glob("**/*_test.py"))
        return len(test_prefix_matches) > 0 or len(test_suffix_matches) > 0

    def _has_changelog(self) -> bool:
        """Check if the project has a CHANGELOG.md file."""
        changelog_path = self.project_root / "CHANGELOG.md"
        return changelog_path.exists()


def detect_reviewers(project_root: Path) -> list[ReviewerConfig]:
    """Detect which reviewers should be configured for a project.

    Convenience function that creates a ReviewerDetector and detects reviewers.

    Args:
        project_root: Path to the project root directory.

    Returns:
        List of ReviewerConfig objects for detected reviewers.
    """
    detector = ReviewerDetector(project_root=project_root)
    return detector.detect_reviewers()
