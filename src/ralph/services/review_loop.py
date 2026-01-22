"""Review loop execution service.

This module provides a service for executing configured code reviewers
in order as part of the Ralph post-story review loop.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict

from ralph.models.reviewer import ReviewerConfig, ReviewerLevel
from ralph.services.claude import ClaudeService
from ralph.services.language import Language
from ralph.services.skill_loader import SkillLoader, SkillNotFoundError

logger = logging.getLogger(__name__)


class ReviewerResult(NamedTuple):
    """Result of a single reviewer execution.

    Attributes:
        reviewer_name: Name of the reviewer that was executed.
        success: Whether the reviewer completed successfully.
        skipped: Whether the reviewer was skipped (e.g., language mismatch).
        attempts: Number of attempts made (1-3 for blocking reviewers).
        error: Error message if the reviewer failed.
    """

    reviewer_name: str
    success: bool
    skipped: bool
    attempts: int
    error: str | None = None


class ReviewLoopService(BaseModel):
    """Service for executing the review loop after stories complete.

    Runs configured reviewers in order, handling language filtering,
    retry logic for blocking reviewers, and progress logging.

    Attributes:
        project_root: Path to the project root directory.
        skills_dir: Path to the skills directory.
        verbose: Whether to show verbose output.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    project_root: Path
    skills_dir: Path
    verbose: bool = False

    def should_run_reviewer(
        self, reviewer: ReviewerConfig, detected_languages: set[Language]
    ) -> bool:
        """Determine if a reviewer should run based on language filtering.

        Args:
            reviewer: The reviewer configuration to check.
            detected_languages: Set of languages detected in the project.

        Returns:
            True if the reviewer should run, False if it should be skipped.
        """
        # Reviewers without language filter always run
        if reviewer.languages is None:
            return True

        # Empty language list is treated as "no filter" - always runs
        if not reviewer.languages:
            return True

        # Check if any of the reviewer's languages match detected languages
        detected_language_values = {lang.value for lang in detected_languages}
        return any(lang in detected_language_values for lang in reviewer.languages)

    def is_enforced(self, reviewer: ReviewerConfig, strict: bool) -> bool:
        """Determine if a reviewer's failures should be enforced.

        Args:
            reviewer: The reviewer configuration.
            strict: Whether strict mode is enabled.

        Returns:
            True if reviewer failures should block progress, False otherwise.
        """
        if reviewer.level == ReviewerLevel.blocking:
            return True
        if reviewer.level == ReviewerLevel.warning and strict:
            return True
        return False

    def run_reviewer(
        self,
        reviewer: ReviewerConfig,
        *,
        max_retries: int = 3,
        enforced: bool = False,
    ) -> ReviewerResult:
        """Execute a single reviewer with retry logic.

        Args:
            reviewer: The reviewer configuration to execute.
            max_retries: Maximum number of retry attempts for enforced reviewers.
            enforced: Whether failures should trigger retries.

        Returns:
            ReviewerResult indicating the outcome of the reviewer execution.
        """
        skill_loader = SkillLoader(skills_dir=self.skills_dir)

        try:
            skill_path = skill_loader.load(reviewer.skill)
        except SkillNotFoundError as e:
            logger.error(f"Skill not found for reviewer {reviewer.name}: {e}")
            return ReviewerResult(
                reviewer_name=reviewer.name,
                success=False,
                skipped=False,
                attempts=0,
                error=f"Skill not found: {reviewer.skill}",
            )

        prompt = self._build_reviewer_prompt(reviewer, skill_path)

        # Non-enforced reviewers only get one attempt
        attempts_allowed = max_retries if enforced else 1

        for attempt in range(1, attempts_allowed + 1):
            logger.info(f"Running reviewer {reviewer.name} (attempt {attempt}/{attempts_allowed})")

            try:
                claude = ClaudeService(
                    working_dir=self.project_root,
                    verbose=self.verbose,
                )
                _, exit_code = claude.run_print_mode(
                    prompt,
                    stream=True,
                    skip_permissions=True,
                    append_system_prompt=ClaudeService.AUTONOMOUS_MODE_PROMPT,
                )

                if exit_code == 0:
                    return ReviewerResult(
                        reviewer_name=reviewer.name,
                        success=True,
                        skipped=False,
                        attempts=attempt,
                    )

                logger.warning(
                    f"Reviewer {reviewer.name} failed with exit code {exit_code} "
                    f"(attempt {attempt}/{attempts_allowed})"
                )

            except Exception as e:
                logger.error(f"Error running reviewer {reviewer.name}: {e}")
                if attempt == attempts_allowed:
                    return ReviewerResult(
                        reviewer_name=reviewer.name,
                        success=False,
                        skipped=False,
                        attempts=attempt,
                        error=str(e),
                    )

        # All retries exhausted
        return ReviewerResult(
            reviewer_name=reviewer.name,
            success=False,
            skipped=False,
            attempts=attempts_allowed,
            error=f"Failed after {attempts_allowed} attempts",
        )

    def run_review_loop(
        self,
        reviewers: list[ReviewerConfig],
        detected_languages: set[Language],
        *,
        strict: bool = False,
        progress_path: Path | None = None,
    ) -> list[ReviewerResult]:
        """Execute the full review loop with all configured reviewers.

        Args:
            reviewers: List of reviewer configurations to execute in order.
            detected_languages: Set of languages detected in the project.
            strict: Whether to enforce warning-level reviewers.
            progress_path: Optional path to PROGRESS.txt for logging.

        Returns:
            List of ReviewerResult objects for each reviewer.
        """
        results: list[ReviewerResult] = []

        for reviewer in reviewers:
            # Check language filtering
            if not self.should_run_reviewer(reviewer, detected_languages):
                logger.info(
                    f"Skipping reviewer {reviewer.name} (language filter: {reviewer.languages})"
                )
                result = ReviewerResult(
                    reviewer_name=reviewer.name,
                    success=True,
                    skipped=True,
                    attempts=0,
                )
                results.append(result)

                if progress_path:
                    self._append_review_summary(progress_path, reviewer, result)

                continue

            # Determine if enforced
            enforced = self.is_enforced(reviewer, strict)

            # Run the reviewer
            result = self.run_reviewer(reviewer, enforced=enforced)
            results.append(result)

            # Append summary to progress file
            if progress_path:
                self._append_review_summary(progress_path, reviewer, result)

            # Log the result
            if result.success:
                logger.info(f"Reviewer {reviewer.name} completed successfully")
            elif result.skipped:
                logger.info(f"Reviewer {reviewer.name} skipped")
            else:
                logger.warning(f"Reviewer {reviewer.name} failed after {result.attempts} attempts")

        return results

    def _build_reviewer_prompt(self, reviewer: ReviewerConfig, skill_path: Path) -> str:
        """Build the prompt for running a reviewer.

        Args:
            reviewer: The reviewer configuration.
            skill_path: Path to the reviewer's SKILL.md file.

        Returns:
            The formatted prompt string.
        """
        skill_content = skill_path.read_text(encoding="utf-8")

        return f"""You are a code reviewer running the {reviewer.name} review.

## Review Instructions

{skill_content}

## Your Task

1. Analyze the codebase according to the review instructions above
2. Identify any issues that need to be addressed
3. Make the necessary changes to fix the issues
4. Verify your changes are correct

If no issues are found, simply confirm the codebase passes this review.

Begin the review now."""

    def _append_review_summary(
        self,
        progress_path: Path,
        reviewer: ReviewerConfig,
        result: ReviewerResult,
    ) -> None:
        """Append a review summary to PROGRESS.txt.

        Args:
            progress_path: Path to PROGRESS.txt.
            reviewer: The reviewer configuration.
            result: The result of the reviewer execution.
        """
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

        if result.skipped:
            status = "skipped (language filter)"
        elif result.success:
            status = "passed"
        else:
            status = f"failed after {result.attempts} attempts"
            if result.error:
                status += f" ({result.error})"

        note = f"\n[Review Loop] {timestamp} - {reviewer.name} ({reviewer.level.value}): {status}\n"

        try:
            with open(progress_path, "a", encoding="utf-8") as f:
                f.write(note)
        except OSError as e:
            logger.warning(f"Could not append review summary: {e}")


def filter_reviewers_by_language(
    reviewers: list[ReviewerConfig],
    detected_languages: set[Language],
) -> list[ReviewerConfig]:
    """Filter reviewers based on detected project languages.

    Convenience function that returns only reviewers that should run
    for the detected languages.

    Args:
        reviewers: List of all configured reviewers.
        detected_languages: Set of languages detected in the project.

    Returns:
        List of reviewers that should run.
    """
    service = ReviewLoopService(
        project_root=Path.cwd(),
        skills_dir=Path.cwd() / "skills",
    )

    return [
        reviewer
        for reviewer in reviewers
        if service.should_run_reviewer(reviewer, detected_languages)
    ]
