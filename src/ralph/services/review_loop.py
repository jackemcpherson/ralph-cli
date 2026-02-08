"""Review loop execution service.

This module provides a service for executing configured code reviewers
in order as part of the Ralph post-story review loop.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict

from ralph.models.finding import ReviewOutput, Verdict, parse_review_output
from ralph.models.reviewer import ReviewerConfig, ReviewerLevel
from ralph.services.claude import ClaudeService
from ralph.services.fix_loop import FixLoopService
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
        review_output: Parsed ReviewOutput with verdict and findings when available.
    """

    reviewer_name: str
    success: bool
    skipped: bool
    attempts: int
    error: str | None = None
    review_output: ReviewOutput | None = None


class ReviewLoopService(BaseModel):
    """Service for executing the review loop after stories complete.

    Runs configured reviewers in order, handling language filtering,
    retry logic for blocking reviewers, and progress logging.

    Attributes:
        project_root: Path to the project root directory.
        skills_dir: Optional path to the skills directory. If None, uses
            bundled package skills.
        verbose: Whether to show verbose output.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    project_root: Path
    skills_dir: Path | None = None
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
        if reviewer.languages is None:
            return True

        if not reviewer.languages:
            return True

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
            skill_content = skill_loader.get_content(reviewer.skill)
        except SkillNotFoundError as e:
            logger.error(f"Skill not found for reviewer {reviewer.name}: {e}")
            return ReviewerResult(
                reviewer_name=reviewer.name,
                success=False,
                skipped=False,
                attempts=0,
                error=f"Skill not found: {reviewer.skill}",
            )

        prompt = self._build_reviewer_prompt(reviewer, skill_content)

        attempts_allowed = max_retries if enforced else 1
        last_output: str = ""

        for attempt in range(1, attempts_allowed + 1):
            logger.info(f"Running reviewer {reviewer.name} (attempt {attempt}/{attempts_allowed})")

            try:
                claude = ClaudeService(
                    working_dir=self.project_root,
                    verbose=self.verbose,
                )
                output_text, exit_code = claude.run_print_mode(
                    prompt,
                    stream=True,
                    skip_permissions=True,
                    append_system_prompt=ClaudeService.AUTONOMOUS_MODE_PROMPT,
                )
                last_output = output_text

                # Parse structured output to extract verdict and findings
                review_output = parse_review_output(output_text)

                if exit_code == 0:
                    return ReviewerResult(
                        reviewer_name=reviewer.name,
                        success=True,
                        skipped=False,
                        attempts=attempt,
                        review_output=review_output,
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

        # Parse last output for final result (may contain findings even on failure)
        review_output = parse_review_output(last_output) if last_output else None

        return ReviewerResult(
            reviewer_name=reviewer.name,
            success=False,
            skipped=False,
            attempts=attempts_allowed,
            error=f"Failed after {attempts_allowed} attempts",
            review_output=review_output,
        )

    def should_run_fix_loop(
        self, reviewer: ReviewerConfig, strict: bool, *, was_language_filtered: bool
    ) -> bool:
        """Determine if the fix loop should run for a reviewer.

        Fix loop runs for:
        - blocking reviewers (always)
        - warning and suggestion reviewers when strict=True

        Fix loop is skipped for:
        - language-filtered reviewers (even if they have findings)

        Args:
            reviewer: The reviewer configuration.
            strict: Whether strict mode is enabled.
            was_language_filtered: Whether this reviewer was language-filtered.

        Returns:
            True if fix loop should run, False otherwise.
        """
        # Skip fix loop for language-filtered reviewers
        if was_language_filtered:
            return False

        # Blocking reviewers always get fix loop
        if reviewer.level == ReviewerLevel.blocking:
            return True

        # In strict mode, all levels get fix loop
        if strict:
            return True

        return False

    def run_review_loop(
        self,
        reviewers: list[ReviewerConfig],
        detected_languages: set[Language],
        *,
        strict: bool = False,
        no_fix: bool = False,
        progress_path: Path | None = None,
        on_fix_step: Callable[[int, int, str], None] | None = None,
    ) -> list[ReviewerResult]:
        """Execute the full review loop with all configured reviewers.

        After each reviewer completes, if the verdict is NEEDS_WORK and the
        reviewer is eligible for auto-fix, the fix loop will automatically
        run to attempt to resolve findings. When no_fix is True, the fix
        loop is skipped and findings are reported without code modifications.

        Args:
            reviewers: List of reviewer configurations to execute in order.
            detected_languages: Set of languages detected in the project.
            strict: Whether to enforce warning-level reviewers.
            no_fix: Whether to skip automated fixes for review findings.
            progress_path: Optional path to PROGRESS.txt for logging.
            on_fix_step: Optional callback for fix progress (step, total, finding_id).
                Called before each fix attempt to enable console output.

        Returns:
            List of ReviewerResult objects for each reviewer.
        """
        results: list[ReviewerResult] = []

        for reviewer in reviewers:
            was_language_filtered = not self.should_run_reviewer(reviewer, detected_languages)

            if was_language_filtered:
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

            enforced = self.is_enforced(reviewer, strict)

            result = self.run_reviewer(reviewer, enforced=enforced)
            results.append(result)

            if progress_path:
                self._append_review_summary(progress_path, reviewer, result)

            # Run fix loop if reviewer returned NEEDS_WORK and is eligible
            if (
                result.review_output
                and result.review_output.verdict == Verdict.NEEDS_WORK
                and result.review_output.findings
                and self.should_run_fix_loop(reviewer, strict, was_language_filtered=False)
            ):
                if no_fix:
                    logger.info("[Fix] Skipped (--no-fix)")
                else:
                    logger.info(
                        f"Running fix loop for {reviewer.name} "
                        f"({len(result.review_output.findings)} findings)"
                    )

                    fix_service = FixLoopService(
                        project_root=self.project_root,
                        reviewer_name=reviewer.name,
                        verbose=self.verbose,
                    )

                    fix_service.run_fix_loop(
                        result.review_output.findings,
                        progress_path=progress_path,
                        on_fix_step=on_fix_step,
                    )

            if result.success:
                logger.info(f"Reviewer {reviewer.name} completed successfully")
            elif result.skipped:
                logger.info(f"Reviewer {reviewer.name} skipped")
            else:
                logger.warning(f"Reviewer {reviewer.name} failed after {result.attempts} attempts")

        return results

    def _build_reviewer_prompt(self, reviewer: ReviewerConfig, skill_content: str) -> str:
        """Build the prompt for running a reviewer.

        Args:
            reviewer: The reviewer configuration.
            skill_content: The content of the reviewer's SKILL.md file.

        Returns:
            The formatted prompt string.
        """
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

        Logs the full structured format when findings are available,
        otherwise logs a simple summary line.

        Args:
            progress_path: Path to PROGRESS.txt.
            reviewer: The reviewer configuration.
            result: The result of the reviewer execution.
        """
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

        # For skipped reviewers, use simple format
        if result.skipped:
            status = "skipped (language filter)"
            level_val = reviewer.level.value
            note = f"\n[Review Loop] {timestamp} - {reviewer.name} ({level_val}): {status}\n"
            try:
                with open(progress_path, "a", encoding="utf-8") as f:
                    f.write(note)
            except OSError as e:
                logger.warning(f"Could not append review summary: {e}")
            return

        # Build structured format when review_output is available
        if result.review_output:
            verdict_str = result.review_output.verdict.value
            lines = [
                f"\n[Review] {timestamp} - {reviewer.name} ({reviewer.level.value})",
                "",
                f"### Verdict: {verdict_str}",
            ]

            if result.review_output.findings:
                lines.append("")
                lines.append("### Findings")
                lines.append("")
                for i, finding in enumerate(result.review_output.findings, 1):
                    file_loc = finding.file_path
                    if finding.line_number:
                        file_loc += f":{finding.line_number}"
                    brief = finding.issue[:50] + "..." if len(finding.issue) > 50 else finding.issue
                    lines.append(f"{i}. **{finding.id}**: {finding.category} - {brief}")
                    lines.append(f"   - File: {file_loc}")
                    lines.append(f"   - Issue: {finding.issue}")
                    lines.append(f"   - Suggestion: {finding.suggestion}")
                    lines.append("")

            lines.append("---")
            lines.append("")
            note = "\n".join(lines)
        else:
            # Fallback to simple format when no structured output
            if result.success:
                status = "passed"
            else:
                status = f"failed after {result.attempts} attempts"
                if result.error:
                    status += f" ({result.error})"
            level_val = reviewer.level.value
            note = f"\n[Review Loop] {timestamp} - {reviewer.name} ({level_val}): {status}\n"

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
    )

    return [
        reviewer
        for reviewer in reviewers
        if service.should_run_reviewer(reviewer, detected_languages)
    ]
