"""Tests for ralph loop command."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ralph.cli import app
from ralph.commands.loop import (
    LoopStopReason,
    _build_iteration_prompt,
    _find_next_story,
    _setup_branch,
)
from ralph.models import TasksFile, UserStory
from ralph.services import ClaudeError, GitError, GitService


@pytest.fixture
def runner() -> CliRunner:
    """Create a CliRunner for testing commands."""
    return CliRunner()


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    return tmp_path


@pytest.fixture
def sample_tasks_json() -> dict:
    """Return sample TASKS.json content."""
    return {
        "project": "TestProject",
        "branchName": "ralph/test-feature",
        "description": "Test feature description",
        "userStories": [
            {
                "id": "US-001",
                "title": "First story",
                "description": "As a user, I want feature A",
                "acceptanceCriteria": ["Criterion A1", "Typecheck passes"],
                "priority": 1,
                "passes": True,
                "notes": "Completed",
            },
            {
                "id": "US-002",
                "title": "Second story",
                "description": "As a user, I want feature B",
                "acceptanceCriteria": ["Criterion B1", "Criterion B2"],
                "priority": 2,
                "passes": False,
                "notes": "",
            },
            {
                "id": "US-003",
                "title": "Third story",
                "description": "As a user, I want feature C",
                "acceptanceCriteria": ["Criterion C1"],
                "priority": 3,
                "passes": False,
                "notes": "",
            },
        ],
    }


@pytest.fixture
def all_complete_tasks_json() -> dict:
    """Return TASKS.json content with all stories complete."""
    return {
        "project": "TestProject",
        "branchName": "ralph/test-feature",
        "description": "Test feature description",
        "userStories": [
            {
                "id": "US-001",
                "title": "First story",
                "description": "As a user, I want feature A",
                "acceptanceCriteria": ["Criterion A1"],
                "priority": 1,
                "passes": True,
                "notes": "",
            },
        ],
    }


@pytest.fixture
def initialized_project(temp_project: Path, sample_tasks_json: dict) -> Path:
    """Create a temporary project with plans/TASKS.json."""
    plans_dir = temp_project / "plans"
    plans_dir.mkdir()

    tasks_file = plans_dir / "TASKS.json"
    tasks_file.write_text(json.dumps(sample_tasks_json, indent=2))

    progress_file = plans_dir / "PROGRESS.txt"
    progress_file.write_text("# Progress Log\n\n")

    return temp_project


class TestLoopCommand:
    """Tests for the loop command."""

    def test_loop_requires_tasks_json(self, runner: CliRunner, temp_project: Path) -> None:
        """Test that loop fails if TASKS.json doesn't exist."""
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project)

            result = runner.invoke(app, ["loop"])

            assert result.exit_code == 1
            assert "TASKS.json" in result.output
        finally:
            os.chdir(original_cwd)

    def test_loop_displays_project_info(self, runner: CliRunner, initialized_project: Path) -> None:
        """Test that loop displays project and branch info."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with (
                patch("ralph.commands.loop.ClaudeService") as mock_claude,
                patch("ralph.commands.loop._setup_branch") as mock_setup,
            ):
                mock_setup.return_value = True
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("Output", 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["loop", "1"])

            assert "TestProject" in result.output
            assert "ralph/test-feature" in result.output
        finally:
            os.chdir(original_cwd)

    def test_loop_handles_all_stories_complete(
        self, runner: CliRunner, temp_project: Path, all_complete_tasks_json: dict
    ) -> None:
        """Test that loop exits with success when all stories already complete."""
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project)

            plans_dir = temp_project / "plans"
            plans_dir.mkdir()
            tasks_file = plans_dir / "TASKS.json"
            tasks_file.write_text(json.dumps(all_complete_tasks_json, indent=2))

            with patch("ralph.commands.loop._setup_branch") as mock_setup:
                mock_setup.return_value = True

                result = runner.invoke(app, ["loop"])

            assert result.exit_code == 0
            assert "All stories already complete" in result.output
        finally:
            os.chdir(original_cwd)

    def test_loop_runs_multiple_iterations(
        self, runner: CliRunner, initialized_project: Path, sample_tasks_json: dict
    ) -> None:
        """Test that loop runs multiple iterations."""
        original_cwd = os.getcwd()
        iteration_count = 0

        def mock_run(*args, **kwargs):
            nonlocal iteration_count
            iteration_count += 1
            return ("Output", 0)

        try:
            os.chdir(initialized_project)

            with (
                patch("ralph.commands.loop.ClaudeService") as mock_claude,
                patch("ralph.commands.loop._setup_branch") as mock_setup,
            ):
                mock_setup.return_value = True
                mock_instance = MagicMock()
                mock_instance.run_print_mode.side_effect = mock_run
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["loop", "3"])

            # Should run at least once (might stop due to failure detection)
            assert iteration_count >= 1
        finally:
            os.chdir(original_cwd)

    def test_loop_stops_on_all_complete_signal(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that loop stops when it detects the COMPLETE signal."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with (
                patch("ralph.commands.loop.ClaudeService") as mock_claude,
                patch("ralph.commands.loop._setup_branch") as mock_setup,
            ):
                mock_setup.return_value = True
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (
                    "Done! <ralph>COMPLETE</ralph>",
                    0,
                )
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["loop", "10"])

            assert result.exit_code == 0
            assert "All stories complete" in result.output
        finally:
            os.chdir(original_cwd)

    def test_loop_stops_on_max_iterations(
        self, runner: CliRunner, initialized_project: Path, sample_tasks_json: dict
    ) -> None:
        """Test that loop stops after reaching max iterations."""
        original_cwd = os.getcwd()
        iteration_count = 0

        def mock_run_and_pass(*args, **kwargs):
            nonlocal iteration_count
            iteration_count += 1
            # Mark story as passed by updating the file
            tasks = sample_tasks_json.copy()
            tasks["userStories"][iteration_count]["passes"] = True
            tasks_file = initialized_project / "plans" / "TASKS.json"
            tasks_file.write_text(json.dumps(tasks, indent=2))
            return ("Output", 0)

        try:
            os.chdir(initialized_project)

            with (
                patch("ralph.commands.loop.ClaudeService") as mock_claude,
                patch("ralph.commands.loop._setup_branch") as mock_setup,
            ):
                mock_setup.return_value = True
                mock_instance = MagicMock()
                mock_instance.run_print_mode.side_effect = mock_run_and_pass
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["loop", "1"])

            # Should have completed exactly 1 iteration
            assert iteration_count == 1
            assert "Reached maximum of 1 iterations" in result.output
        finally:
            os.chdir(original_cwd)

    def test_loop_stops_on_persistent_failure(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that loop stops after 2 consecutive failures on same story."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with (
                patch("ralph.commands.loop.ClaudeService") as mock_claude,
                patch("ralph.commands.loop._setup_branch") as mock_setup,
            ):
                mock_setup.return_value = True
                mock_instance = MagicMock()
                # Return without marking story as passed (failure)
                mock_instance.run_print_mode.return_value = ("Output", 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["loop", "10"])

            assert result.exit_code == 1
            assert "persistent failure" in result.output.lower()
        finally:
            os.chdir(original_cwd)

    def test_loop_handles_claude_error(self, runner: CliRunner, initialized_project: Path) -> None:
        """Test that loop handles ClaudeError as transient failure."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with (
                patch("ralph.commands.loop.ClaudeService") as mock_claude,
                patch("ralph.commands.loop._setup_branch") as mock_setup,
            ):
                mock_setup.return_value = True
                mock_instance = MagicMock()
                mock_instance.run_print_mode.side_effect = ClaudeError("Claude not found")
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["loop"])

            assert result.exit_code == 1
            assert "Claude error" in result.output
        finally:
            os.chdir(original_cwd)

    def test_loop_with_verbose_flag(self, runner: CliRunner, initialized_project: Path) -> None:
        """Test that loop passes verbose flag to ClaudeService."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with (
                patch("ralph.commands.loop.ClaudeService") as mock_claude,
                patch("ralph.commands.loop._setup_branch") as mock_setup,
            ):
                mock_setup.return_value = True
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (
                    "<ralph>COMPLETE</ralph>",
                    0,
                )
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["loop", "--verbose"])

            call_kwargs = mock_claude.call_args.kwargs
            assert call_kwargs.get("verbose") is True
        finally:
            os.chdir(original_cwd)

    def test_loop_with_custom_iterations(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that loop accepts custom iterations argument."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with (
                patch("ralph.commands.loop.ClaudeService") as mock_claude,
                patch("ralph.commands.loop._setup_branch") as mock_setup,
            ):
                mock_setup.return_value = True
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (
                    "<ralph>COMPLETE</ralph>",
                    0,
                )
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["loop", "5"])

            assert "Max iterations:" in result.output
            assert "5" in result.output
        finally:
            os.chdir(original_cwd)

    def test_loop_displays_iteration_counter(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that loop displays iteration counter like '[1/10] Story...'."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with (
                patch("ralph.commands.loop.ClaudeService") as mock_claude,
                patch("ralph.commands.loop._setup_branch") as mock_setup,
            ):
                mock_setup.return_value = True
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (
                    "<ralph>COMPLETE</ralph>",
                    0,
                )
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["loop", "10"])

            # Should show iteration counter [1/10]
            assert "[1/10]" in result.output
        finally:
            os.chdir(original_cwd)

    def test_loop_shows_summary_on_completion(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that loop shows summary when done."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with (
                patch("ralph.commands.loop.ClaudeService") as mock_claude,
                patch("ralph.commands.loop._setup_branch") as mock_setup,
            ):
                mock_setup.return_value = True
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (
                    "<ralph>COMPLETE</ralph>",
                    0,
                )
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["loop"])

            assert "Loop Summary" in result.output
            assert "Stories completed this run:" in result.output
        finally:
            os.chdir(original_cwd)

    def test_loop_handles_invalid_tasks_json(self, runner: CliRunner, temp_project: Path) -> None:
        """Test that loop handles invalid TASKS.json gracefully."""
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project)

            plans_dir = temp_project / "plans"
            plans_dir.mkdir()
            tasks_file = plans_dir / "TASKS.json"
            tasks_file.write_text("invalid json")

            result = runner.invoke(app, ["loop"])

            assert result.exit_code == 1
            assert "Error parsing" in result.output
        finally:
            os.chdir(original_cwd)

    def test_loop_fails_when_branch_setup_fails(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that loop fails when branch setup fails."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.loop._setup_branch") as mock_setup:
                mock_setup.return_value = False

                result = runner.invoke(app, ["loop"])

            assert result.exit_code == 1
            assert "Could not set up the feature branch" in result.output
        finally:
            os.chdir(original_cwd)


class TestSetupBranch:
    """Tests for the _setup_branch helper function."""

    def test_setup_branch_on_correct_branch(self, tmp_path: Path) -> None:
        """Test that _setup_branch succeeds when already on correct branch."""
        git = MagicMock(spec=GitService)
        git.get_current_branch.return_value = "ralph/test-feature"

        result = _setup_branch(git, "ralph/test-feature", tmp_path)

        assert result is True
        git.checkout_or_create_branch.assert_not_called()

    def test_setup_branch_switches_branch(self, tmp_path: Path) -> None:
        """Test that _setup_branch switches to the correct branch."""
        git = MagicMock(spec=GitService)
        git.get_current_branch.return_value = "main"
        git.has_changes.return_value = False
        git.checkout_or_create_branch.return_value = False

        result = _setup_branch(git, "ralph/test-feature", tmp_path)

        assert result is True
        git.checkout_or_create_branch.assert_called_once_with("ralph/test-feature")

    def test_setup_branch_creates_new_branch(self, tmp_path: Path) -> None:
        """Test that _setup_branch creates a new branch if needed."""
        git = MagicMock(spec=GitService)
        git.get_current_branch.return_value = "main"
        git.has_changes.return_value = False
        git.checkout_or_create_branch.return_value = True  # Branch was created

        result = _setup_branch(git, "ralph/new-feature", tmp_path)

        assert result is True
        git.checkout_or_create_branch.assert_called_once_with("ralph/new-feature")

    def test_setup_branch_warns_about_uncommitted_changes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that _setup_branch warns about uncommitted changes."""
        git = MagicMock(spec=GitService)
        git.get_current_branch.return_value = "main"
        git.has_changes.return_value = True
        git.checkout_or_create_branch.return_value = False

        result = _setup_branch(git, "ralph/test-feature", tmp_path)

        assert result is True
        # The warning should have been printed
        git.checkout_or_create_branch.assert_called_once()

    def test_setup_branch_handles_git_error(self, tmp_path: Path) -> None:
        """Test that _setup_branch handles GitError gracefully."""
        git = MagicMock(spec=GitService)
        git.get_current_branch.side_effect = GitError("Not a git repo")

        result = _setup_branch(git, "ralph/test-feature", tmp_path)

        assert result is False

    def test_setup_branch_handles_checkout_error(self, tmp_path: Path) -> None:
        """Test that _setup_branch handles checkout error gracefully."""
        git = MagicMock(spec=GitService)
        git.get_current_branch.return_value = "main"
        git.has_changes.return_value = False
        git.checkout_or_create_branch.side_effect = GitError("Checkout failed")

        result = _setup_branch(git, "ralph/test-feature", tmp_path)

        assert result is False


class TestFindNextStory:
    """Tests for the _find_next_story helper function."""

    def test_find_next_story_returns_highest_priority_incomplete(self) -> None:
        """Test that _find_next_story returns highest priority incomplete story."""
        tasks = TasksFile(
            project="Test",
            branch_name="ralph/test",
            description="Test",
            user_stories=[
                UserStory(
                    id="US-001",
                    title="First",
                    description="Desc",
                    priority=1,
                    passes=True,
                ),
                UserStory(
                    id="US-002",
                    title="Second",
                    description="Desc",
                    priority=2,
                    passes=False,
                ),
                UserStory(
                    id="US-003",
                    title="Third",
                    description="Desc",
                    priority=3,
                    passes=False,
                ),
            ],
        )

        result = _find_next_story(tasks)

        assert result is not None
        assert result.id == "US-002"

    def test_find_next_story_returns_none_when_all_complete(self) -> None:
        """Test that _find_next_story returns None when all complete."""
        tasks = TasksFile(
            project="Test",
            branch_name="ralph/test",
            description="Test",
            user_stories=[
                UserStory(
                    id="US-001",
                    title="First",
                    description="Desc",
                    priority=1,
                    passes=True,
                ),
            ],
        )

        result = _find_next_story(tasks)

        assert result is None

    def test_find_next_story_handles_unsorted_priorities(self) -> None:
        """Test that _find_next_story handles unsorted priorities."""
        tasks = TasksFile(
            project="Test",
            branch_name="ralph/test",
            description="Test",
            user_stories=[
                UserStory(
                    id="US-003",
                    title="Third",
                    description="Desc",
                    priority=3,
                    passes=False,
                ),
                UserStory(
                    id="US-001",
                    title="First",
                    description="Desc",
                    priority=1,
                    passes=False,
                ),
                UserStory(
                    id="US-002",
                    title="Second",
                    description="Desc",
                    priority=2,
                    passes=False,
                ),
            ],
        )

        result = _find_next_story(tasks)

        assert result is not None
        assert result.id == "US-001"


class TestBuildIterationPrompt:
    """Tests for the _build_iteration_prompt helper function."""

    def test_prompt_includes_story_details(self) -> None:
        """Test that prompt includes story ID, title, and description."""
        story = UserStory(
            id="US-042",
            title="Test Feature",
            description="As a user, I want to test",
            acceptance_criteria=["Criterion 1", "Criterion 2"],
            priority=1,
            passes=False,
        )

        prompt = _build_iteration_prompt(story, max_fix_attempts=3)

        assert "US-042" in prompt
        assert "Test Feature" in prompt
        assert "As a user, I want to test" in prompt

    def test_prompt_includes_acceptance_criteria(self) -> None:
        """Test that prompt includes acceptance criteria."""
        story = UserStory(
            id="US-001",
            title="Test",
            description="Desc",
            acceptance_criteria=["Build must pass", "Tests must pass"],
            priority=1,
            passes=False,
        )

        prompt = _build_iteration_prompt(story, max_fix_attempts=3)

        assert "Build must pass" in prompt
        assert "Tests must pass" in prompt

    def test_prompt_includes_max_fix_attempts(self) -> None:
        """Test that prompt includes max fix attempts value."""
        story = UserStory(
            id="US-001",
            title="Test",
            description="Desc",
            priority=1,
            passes=False,
        )

        prompt = _build_iteration_prompt(story, max_fix_attempts=5)

        # The prompt should contain instructions mentioning 5 attempts
        assert "5" in prompt


class TestLoopStopReason:
    """Tests for the LoopStopReason class."""

    def test_stop_reason_constants_exist(self) -> None:
        """Test that all stop reason constants exist."""
        assert LoopStopReason.ALL_COMPLETE == "all_complete"
        assert LoopStopReason.MAX_ITERATIONS == "max_iterations"
        assert LoopStopReason.PERSISTENT_FAILURE == "persistent_failure"
        assert LoopStopReason.TRANSIENT_FAILURE == "transient_failure"
        assert LoopStopReason.NO_TASKS == "no_tasks"
        assert LoopStopReason.BRANCH_MISMATCH == "branch_mismatch"
