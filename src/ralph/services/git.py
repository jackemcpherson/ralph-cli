"""Git service for branch management and commits.

This module provides a service for Git operations including branch
management, commits, and repository inspection using subprocess.
"""

import logging
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class GitError(Exception):
    """Exception raised for Git operation failures.

    Raised when a git command fails or git is not available.
    """


class GitService(BaseModel):
    """Service for Git operations.

    Provides methods for branch management, commits, and repository inspection.
    All operations use subprocess with proper error handling.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    working_dir: Path | None = None

    def _run(
        self, args: list[str], check: bool = True, capture_output: bool = True
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command with proper error handling.

        Args:
            args: Git command arguments (without 'git' prefix).
            check: Whether to raise on non-zero exit code.
            capture_output: Whether to capture stdout/stderr.

        Returns:
            CompletedProcess with command results.

        Raises:
            GitError: If the command fails and check=True.
        """
        cmd = ["git", *args]
        try:
            result = subprocess.run(
                cmd,
                cwd=self.working_dir,
                capture_output=capture_output,
                text=True,
                check=check,
            )
            return result
        except subprocess.CalledProcessError as e:
            raise GitError(f"Git command failed: {' '.join(cmd)}\n{e.stderr}") from e
        except FileNotFoundError as e:
            raise GitError("Git is not installed or not in PATH") from e

    def get_current_branch(self) -> str:
        """Get the name of the current branch.

        Returns:
            The current branch name.

        Raises:
            GitError: If not in a git repository or command fails.
        """
        result = self._run(["branch", "--show-current"])
        return result.stdout.strip()

    def get_default_branch(self) -> str:
        """Detect the default branch (main or master).

        Checks for 'main' first, then falls back to 'master'.
        If neither exists locally, checks remote HEAD branch.

        Returns:
            The default branch name ('main' or 'master').
        """
        result = self._run(["branch", "--list", "main"], check=False)
        if result.stdout.strip():
            return "main"

        result = self._run(["branch", "--list", "master"], check=False)
        if result.stdout.strip():
            return "master"

        result = self._run(["remote", "show", "origin"], check=False)
        if "HEAD branch:" in result.stdout:
            for line in result.stdout.splitlines():
                if "HEAD branch:" in line:
                    return line.split(":")[-1].strip()

        return "main"

    def branch_exists(self, name: str) -> bool:
        """Check if a branch exists locally.

        Args:
            name: Branch name to check.

        Returns:
            True if the branch exists, False otherwise.
        """
        result = self._run(["branch", "--list", name], check=False)
        return bool(result.stdout.strip())

    def checkout_or_create_branch(self, name: str, base: str | None = None) -> bool:
        """Switch to a branch, creating it if it doesn't exist.

        Args:
            name: Branch name to checkout or create.
            base: Base branch for new branch (defaults to default branch).

        Returns:
            True if branch was created, False if it already existed.

        Raises:
            GitError: If checkout or creation fails.
        """
        if self.branch_exists(name):
            self._run(["checkout", name])
            return False

        if base is None:
            base = self.get_default_branch()

        self._run(["checkout", "-b", name, base])
        return True

    def commit(self, message: str, add_all: bool = False) -> str:
        """Create a commit with the given message.

        Args:
            message: Commit message.
            add_all: Whether to stage all changes before committing.

        Returns:
            The commit hash.

        Raises:
            GitError: If there are no changes to commit or commit fails.
        """
        if add_all:
            self._run(["add", "-A"])

        self._run(["commit", "-m", message])

        result = self._run(["rev-parse", "HEAD"])
        return result.stdout.strip()

    def has_changes(self) -> bool:
        """Check if there are uncommitted changes.

        Returns:
            True if there are staged or unstaged changes.
        """
        result = self._run(["status", "--porcelain"], check=False)
        return bool(result.stdout.strip())

    def stage_files(self, files: list[str]) -> None:
        """Stage specific files for commit.

        Args:
            files: List of file paths to stage.

        Raises:
            GitError: If staging fails.
        """
        if files:
            self._run(["add", *files])
