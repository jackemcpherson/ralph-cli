"""Tests for Git service."""

import subprocess
from pathlib import Path

import pytest

from ralph.services.git import GitError, GitService


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository for testing.

    Returns:
        Path to the temporary git repo.
    """
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    # Configure git user for commits
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create initial commit so we have a branch
    test_file = tmp_path / "README.md"
    test_file.write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Rename default branch to 'main' for consistency
    subprocess.run(
        ["git", "branch", "-M", "main"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    return tmp_path


@pytest.fixture
def git_service(temp_git_repo: Path) -> GitService:
    """Create a GitService instance for a temporary repo.

    Returns:
        GitService configured for the temp repo.
    """
    return GitService(working_dir=temp_git_repo)


class TestGetCurrentBranch:
    """Tests for get_current_branch() method."""

    def test_returns_current_branch_name(self, git_service: GitService) -> None:
        """get_current_branch returns the correct branch name."""
        result = git_service.get_current_branch()
        assert result == "main"

    def test_returns_feature_branch_name(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """get_current_branch returns the correct name after switching branches."""
        # Create and checkout a feature branch
        subprocess.run(
            ["git", "checkout", "-b", "feature/test"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        result = git_service.get_current_branch()
        assert result == "feature/test"

    def test_raises_git_error_for_non_repo(self, tmp_path: Path) -> None:
        """get_current_branch raises GitError when not in a git repo."""
        service = GitService(working_dir=tmp_path)

        with pytest.raises(GitError):
            service.get_current_branch()


class TestGetDefaultBranch:
    """Tests for get_default_branch() method."""

    def test_returns_main_when_main_exists(self, git_service: GitService) -> None:
        """get_default_branch returns 'main' when main branch exists."""
        result = git_service.get_default_branch()
        assert result == "main"

    def test_returns_master_when_only_master_exists(self, temp_git_repo: Path) -> None:
        """get_default_branch returns 'master' when only master exists."""
        # Rename main to master
        subprocess.run(
            ["git", "branch", "-m", "main", "master"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        service = GitService(working_dir=temp_git_repo)
        result = service.get_default_branch()
        assert result == "master"

    def test_returns_main_when_neither_exists(self, tmp_path: Path) -> None:
        """get_default_branch defaults to 'main' when neither main nor master."""
        # Initialize repo without renaming branch
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create a branch with different name
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "-M", "develop"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        service = GitService(working_dir=tmp_path)
        # When neither main nor master exists, defaults to "main"
        result = service.get_default_branch()
        assert result == "main"


class TestBranchExists:
    """Tests for branch_exists() method."""

    def test_returns_true_for_existing_branch(self, git_service: GitService) -> None:
        """branch_exists returns True for an existing branch."""
        result = git_service.branch_exists("main")
        assert result is True

    def test_returns_false_for_nonexistent_branch(self, git_service: GitService) -> None:
        """branch_exists returns False for a branch that doesn't exist."""
        result = git_service.branch_exists("nonexistent-branch")
        assert result is False


class TestCheckoutOrCreateBranch:
    """Tests for checkout_or_create_branch() method."""

    def test_checks_out_existing_branch(self, git_service: GitService, temp_git_repo: Path) -> None:
        """checkout_or_create_branch checks out existing branch and returns False."""
        # Create a feature branch first
        subprocess.run(
            ["git", "branch", "feature/existing"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        result = git_service.checkout_or_create_branch("feature/existing")
        assert result is False  # Branch already existed
        assert git_service.get_current_branch() == "feature/existing"

    def test_creates_new_branch_from_default(self, git_service: GitService) -> None:
        """checkout_or_create_branch creates new branch and returns True."""
        result = git_service.checkout_or_create_branch("feature/new-branch")
        assert result is True  # Branch was created
        assert git_service.get_current_branch() == "feature/new-branch"

    def test_creates_new_branch_from_specified_base(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """checkout_or_create_branch creates branch from specified base."""
        # Create a develop branch with a different commit
        subprocess.run(
            ["git", "checkout", "-b", "develop"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )
        test_file = temp_git_repo / "develop.txt"
        test_file.write_text("develop content")
        subprocess.run(["git", "add", "."], cwd=temp_git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Develop commit"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Go back to main
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Create feature branch from develop
        result = git_service.checkout_or_create_branch("feature/from-develop", "develop")
        assert result is True
        assert git_service.get_current_branch() == "feature/from-develop"

        # Verify it was created from develop (develop.txt should exist)
        assert (temp_git_repo / "develop.txt").exists()

    def test_raises_git_error_for_invalid_base(self, git_service: GitService) -> None:
        """checkout_or_create_branch raises GitError for invalid base branch."""
        with pytest.raises(GitError):
            git_service.checkout_or_create_branch("feature/new", "nonexistent-base")


class TestCommit:
    """Tests for commit() method."""

    def test_creates_commit_with_message(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Commit creates a commit with the specified message."""
        # Create a new file
        test_file = temp_git_repo / "new_file.txt"
        test_file.write_text("new content")

        # Stage and commit
        git_service.stage_files(["new_file.txt"])
        commit_hash = git_service.commit("Test commit message")

        # Verify commit was created
        assert len(commit_hash) == 40  # Full SHA hash

        # Verify commit message
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == "Test commit message"

    def test_creates_commit_with_add_all(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Commit with add_all=True stages all changes automatically."""
        # Create multiple new files
        (temp_git_repo / "file1.txt").write_text("content 1")
        (temp_git_repo / "file2.txt").write_text("content 2")

        # Commit with add_all
        commit_hash = git_service.commit("Commit all files", add_all=True)

        # Verify commit was created
        assert len(commit_hash) == 40

        # Verify both files are in the commit
        result = subprocess.run(
            ["git", "show", "--name-only", "--format="],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
            text=True,
        )
        assert "file1.txt" in result.stdout
        assert "file2.txt" in result.stdout

    def test_raises_git_error_when_nothing_to_commit(self, git_service: GitService) -> None:
        """Commit raises GitError when there are no changes to commit."""
        with pytest.raises(GitError):
            git_service.commit("Empty commit")

    def test_commit_message_format_with_special_characters(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """Commit handles messages with special characters."""
        test_file = temp_git_repo / "test.txt"
        test_file.write_text("test")
        git_service.stage_files(["test.txt"])

        message = "feat: [US-001] - Test commit with 'quotes' and \"double quotes\""
        commit_hash = git_service.commit(message)

        # Verify message was preserved
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == message
        assert len(commit_hash) == 40


class TestHasChanges:
    """Tests for has_changes() method."""

    def test_returns_false_when_clean(self, git_service: GitService) -> None:
        """has_changes returns False when working directory is clean."""
        result = git_service.has_changes()
        assert result is False

    def test_returns_true_with_unstaged_changes(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """has_changes returns True when there are unstaged modifications."""
        # Modify an existing file
        readme = temp_git_repo / "README.md"
        readme.write_text("Modified content")

        result = git_service.has_changes()
        assert result is True

    def test_returns_true_with_untracked_files(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """has_changes returns True when there are untracked files."""
        # Create a new untracked file
        new_file = temp_git_repo / "untracked.txt"
        new_file.write_text("untracked content")

        result = git_service.has_changes()
        assert result is True

    def test_returns_true_with_staged_changes(
        self, git_service: GitService, temp_git_repo: Path
    ) -> None:
        """has_changes returns True when there are staged changes."""
        # Create and stage a new file
        new_file = temp_git_repo / "staged.txt"
        new_file.write_text("staged content")
        subprocess.run(
            ["git", "add", "staged.txt"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        result = git_service.has_changes()
        assert result is True


class TestStageFiles:
    """Tests for stage_files() method."""

    def test_stages_single_file(self, git_service: GitService, temp_git_repo: Path) -> None:
        """stage_files stages a single file correctly."""
        # Create a new file
        new_file = temp_git_repo / "new.txt"
        new_file.write_text("new content")

        git_service.stage_files(["new.txt"])

        # Verify file is staged
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
            text=True,
        )
        assert "new.txt" in result.stdout

    def test_stages_multiple_files(self, git_service: GitService, temp_git_repo: Path) -> None:
        """stage_files stages multiple files correctly."""
        # Create multiple files
        (temp_git_repo / "file1.txt").write_text("content 1")
        (temp_git_repo / "file2.txt").write_text("content 2")
        (temp_git_repo / "file3.txt").write_text("content 3")

        git_service.stage_files(["file1.txt", "file2.txt", "file3.txt"])

        # Verify all files are staged
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
            text=True,
        )
        assert "file1.txt" in result.stdout
        assert "file2.txt" in result.stdout
        assert "file3.txt" in result.stdout

    def test_does_nothing_with_empty_list(self, git_service: GitService) -> None:
        """stage_files does nothing when given an empty list."""
        # Should not raise an error
        git_service.stage_files([])

    def test_raises_git_error_for_nonexistent_file(self, git_service: GitService) -> None:
        """stage_files raises GitError for files that don't exist."""
        with pytest.raises(GitError):
            git_service.stage_files(["nonexistent_file.txt"])


class TestGitServiceRun:
    """Tests for the _run() internal method."""

    def test_raises_git_error_for_invalid_command(self, git_service: GitService) -> None:
        """_run raises GitError for invalid git commands."""
        with pytest.raises(GitError) as exc_info:
            git_service._run(["invalid-command"])

        assert "Git command failed" in str(exc_info.value)

    def test_does_not_raise_when_check_false(self, git_service: GitService) -> None:
        """_run does not raise when check=False for failing commands."""
        # This command will fail but should not raise
        result = git_service._run(["branch", "--list", "nonexistent"], check=False)
        assert result.returncode == 0  # git branch --list always returns 0
        assert result.stdout.strip() == ""


class TestGitError:
    """Tests for GitError exception."""

    def test_git_error_message(self) -> None:
        """GitError stores and displays the error message."""
        error = GitError("Test error message")
        assert str(error) == "Test error message"

    def test_git_error_inheritance(self) -> None:
        """GitError is an Exception subclass."""
        assert issubclass(GitError, Exception)


class TestGitServiceWorkingDir:
    """Tests for GitService working_dir configuration."""

    def test_default_working_dir_is_none(self) -> None:
        """GitService defaults to None working_dir (uses current directory)."""
        service = GitService()
        assert service.working_dir is None

    def test_custom_working_dir(self, temp_git_repo: Path) -> None:
        """GitService can be configured with a custom working directory."""
        service = GitService(working_dir=temp_git_repo)
        assert service.working_dir == temp_git_repo

    def test_working_dir_is_used_for_commands(self, temp_git_repo: Path) -> None:
        """GitService uses working_dir for all git commands."""
        service = GitService(working_dir=temp_git_repo)

        # Create a file in temp_git_repo and verify service can see it
        test_file = temp_git_repo / "working_dir_test.txt"
        test_file.write_text("test")

        # Service should detect changes in its working_dir
        assert service.has_changes() is True
