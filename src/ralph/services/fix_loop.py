"""Fix loop service for automatic finding resolution.

This module provides a service for orchestrating fix attempts with retry logic
to automatically resolve review findings.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict

from ralph.models.finding import Finding
from ralph.services.claude import ClaudeService
from ralph.services.git import GitError, GitService

logger = logging.getLogger(__name__)


class FixResult(NamedTuple):
    """Result of a single fix attempt.

    Attributes:
        finding_id: ID of the finding that was attempted.
        success: Whether the fix was successful.
        attempts: Number of attempts made (1-3).
        error: Error message if the fix failed.
    """

    finding_id: str
    success: bool
    attempts: int
    error: str | None = None


class FixLoopService(BaseModel):
    """Service for orchestrating fix attempts with retry logic.

    Iterates through review findings, attempts to fix each one (up to 3 retries),
    commits successful fixes, and logs progress to PROGRESS.txt.

    Attributes:
        project_root: Path to the project root directory.
        reviewer_name: Name of the reviewer that identified the findings.
        verbose: Whether to show verbose output.
        max_retries: Maximum number of fix attempts per finding.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    project_root: Path
    reviewer_name: str
    verbose: bool = False
    max_retries: int = 3

    def _build_fix_prompt(self, finding: Finding) -> str:
        """Build a prompt for fixing a single finding.

        Args:
            finding: The finding to fix.

        Returns:
            The formatted prompt string.
        """
        line_info = f" at line {finding.line_number}" if finding.line_number else ""
        return f"""You are fixing a code review finding.

## Finding Details

- **ID**: {finding.id}
- **Category**: {finding.category}
- **File**: {finding.file_path}{line_info}
- **Issue**: {finding.issue}
- **Suggestion**: {finding.suggestion}

## Your Task

1. Read the file mentioned in the finding
2. Understand the issue described
3. Apply the suggested fix (or an equivalent solution)
4. Verify the fix is correct

Make only the minimal changes needed to address this specific finding.
Do not make unrelated changes or refactor surrounding code.

Begin fixing now."""

    def attempt_fix(self, finding: Finding) -> tuple[bool, str | None]:
        """Attempt to fix a single finding by invoking Claude.

        Args:
            finding: The finding to fix.

        Returns:
            Tuple of (success, error_message). Success is True if the fix
            was applied successfully, False otherwise.
        """
        prompt = self._build_fix_prompt(finding)

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
                return True, None
            return False, f"Claude exited with code {exit_code}"

        except Exception as e:
            logger.error(f"Error attempting fix for {finding.id}: {e}")
            return False, str(e)

    def _commit_fix(self, finding: Finding) -> str | None:
        """Create a commit for a successful fix.

        Args:
            finding: The finding that was fixed.

        Returns:
            The commit hash if successful, None if no changes to commit.
        """
        git = GitService(working_dir=self.project_root)

        if not git.has_changes():
            logger.info(f"No changes to commit for {finding.id}")
            return None

        # Format: fix(review): [reviewer] - [finding-id] - [description]
        # Truncate description to keep commit message reasonable
        description = finding.issue[:50] + "..." if len(finding.issue) > 50 else finding.issue
        message = f"fix(review): {self.reviewer_name} - {finding.id} - {description}"

        try:
            commit_hash = git.commit(message, add_all=True)
            logger.info(f"Committed fix for {finding.id}: {commit_hash[:8]}")
            return commit_hash
        except GitError as e:
            logger.error(f"Failed to commit fix for {finding.id}: {e}")
            return None

    def _log_fix_success(
        self,
        progress_path: Path,
        finding: Finding,
        attempts: int,
    ) -> None:
        """Log a successful fix to PROGRESS.txt.

        Args:
            progress_path: Path to PROGRESS.txt.
            finding: The finding that was fixed.
            attempts: Number of attempts it took.
        """
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

        entry = f"""
[Review Fix] {timestamp} - {self.reviewer_name}/{finding.id}

### What was fixed
- {finding.issue}

### Files changed
- {finding.file_path}

### Attempts
{attempts} of {self.max_retries}

---
"""
        try:
            with open(progress_path, "a", encoding="utf-8") as f:
                f.write(entry)
        except OSError as e:
            logger.warning(f"Could not append fix success log: {e}")

    def _log_fix_failure(
        self,
        progress_path: Path,
        finding: Finding,
        error: str | None,
    ) -> None:
        """Log a failed fix to PROGRESS.txt.

        Args:
            progress_path: Path to PROGRESS.txt.
            finding: The finding that could not be fixed.
            error: The error message or reason for failure.
        """
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

        reason = error or "Unknown error"
        entry = f"""
[Review Fix Failed] {timestamp} - {self.reviewer_name}/{finding.id}

### Issue
- {finding.issue}

### Attempts
{self.max_retries} of {self.max_retries} (exhausted)

### Reason
{reason}

---
"""
        try:
            with open(progress_path, "a", encoding="utf-8") as f:
                f.write(entry)
        except OSError as e:
            logger.warning(f"Could not append fix failure log: {e}")

    def run_fix_loop(
        self,
        findings: list[Finding],
        *,
        progress_path: Path | None = None,
    ) -> list[FixResult]:
        """Iterate through findings and attempt to fix each one.

        Args:
            findings: List of findings to fix.
            progress_path: Optional path to PROGRESS.txt for logging.

        Returns:
            List of FixResult objects for each finding.
        """
        results: list[FixResult] = []

        for finding in findings:
            last_error: str | None = None

            for attempt in range(1, self.max_retries + 1):
                logger.info(
                    f"Attempting fix for {finding.id} (attempt {attempt}/{self.max_retries})"
                )

                success, error = self.attempt_fix(finding)

                if success:
                    # Commit the fix
                    self._commit_fix(finding)

                    # Log success
                    if progress_path:
                        self._log_fix_success(progress_path, finding, attempt)

                    results.append(
                        FixResult(
                            finding_id=finding.id,
                            success=True,
                            attempts=attempt,
                        )
                    )
                    break

                last_error = error
                logger.warning(
                    f"Fix attempt {attempt}/{self.max_retries} failed for {finding.id}: {error}"
                )

            else:
                # All retries exhausted
                logger.error(f"Failed to fix {finding.id} after {self.max_retries} attempts")

                if progress_path:
                    self._log_fix_failure(progress_path, finding, last_error)

                results.append(
                    FixResult(
                        finding_id=finding.id,
                        success=False,
                        attempts=self.max_retries,
                        error=last_error,
                    )
                )

        return results
