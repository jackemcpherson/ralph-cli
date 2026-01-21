"""Tests for ralph once command."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ralph.cli import app
from ralph.commands.once import (
    _build_prompt_from_skill,
    _find_next_story,
)
from ralph.models import TasksFile, UserStory
from ralph.services import ClaudeError, SkillNotFoundError


@pytest.fixture
def initialized_project_with_skill(initialized_project: Path) -> Path:
    """Create an initialized project with ralph-iteration skill.

    Args:
        initialized_project: Initialized project with plans/TASKS.json.

    Returns:
        Path to the project directory with skill added.
    """
    # Create skills directory with ralph-iteration skill
    skills_dir = initialized_project / "skills" / "ralph-iteration"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: ralph-iteration\ndescription: Test iteration skill\n---\n\n"
        "# Ralph Iteration Skill\n\nYou are an autonomous coding agent.\n"
    )
    return initialized_project


class TestOnceCommand:
    """Tests for the once command."""

    def test_once_requires_tasks_json(self, runner: CliRunner, temp_project: Path) -> None:
        """Test that once fails if TASKS.json doesn't exist."""
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project)

            result = runner.invoke(app, ["once"])

            assert result.exit_code == 1
            assert "TASKS.json" in result.output
        finally:
            os.chdir(original_cwd)

    def test_once_displays_story_info(
        self, runner: CliRunner, initialized_project_with_skill: Path
    ) -> None:
        """Test that once displays the story to implement."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_skill)

            with patch("ralph.commands.once.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("Output", 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["once"])

            # Should show the next incomplete story (US-002)
            assert "US-002" in result.output
            assert "Second story" in result.output
        finally:
            os.chdir(original_cwd)

    def test_once_picks_highest_priority_incomplete_story(
        self, runner: CliRunner, initialized_project_with_skill: Path
    ) -> None:
        """Test that once picks the highest priority incomplete story."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_skill)

            with patch("ralph.commands.once.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("Output", 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["once"])

                # Verify prompt includes US-002 (priority 2, first incomplete)
                call_args = mock_instance.run_print_mode.call_args
                prompt = call_args[0][0]
                assert "US-002" in prompt
                assert "Second story" in prompt
        finally:
            os.chdir(original_cwd)

    def test_once_exits_when_all_stories_complete(
        self, runner: CliRunner, temp_project: Path, all_complete_tasks_json: dict
    ) -> None:
        """Test that once exits with success when all stories complete."""
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project)

            plans_dir = temp_project / "plans"
            plans_dir.mkdir()
            tasks_file = plans_dir / "TASKS.json"
            tasks_file.write_text(json.dumps(all_complete_tasks_json, indent=2))

            result = runner.invoke(app, ["once"])

            assert result.exit_code == 0
            assert "All stories complete" in result.output
        finally:
            os.chdir(original_cwd)

    def test_once_runs_claude_in_print_mode(
        self, runner: CliRunner, initialized_project_with_skill: Path
    ) -> None:
        """Test that once runs Claude in print mode with streaming."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_skill)

            with patch("ralph.commands.once.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("Output", 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["once"])

            mock_claude.assert_called_once()
            mock_instance.run_print_mode.assert_called_once()

            # Verify stream=True
            call_kwargs = mock_instance.run_print_mode.call_args.kwargs
            assert call_kwargs.get("stream") is True
        finally:
            os.chdir(original_cwd)

    def test_once_handles_claude_error(
        self, runner: CliRunner, initialized_project_with_skill: Path
    ) -> None:
        """Test that once handles ClaudeError gracefully."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_skill)

            with patch("ralph.commands.once.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.side_effect = ClaudeError("Claude not found")
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["once"])

            assert result.exit_code == 1
            assert "Failed to run Claude" in result.output
        finally:
            os.chdir(original_cwd)

    def test_once_shows_remaining_count(
        self, runner: CliRunner, initialized_project_with_skill: Path
    ) -> None:
        """Test that once shows remaining story count."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_skill)

            with patch("ralph.commands.once.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("Output", 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["once"])

            # Should show 2 remaining (US-002 and US-003)
            assert "Stories remaining: 2" in result.output
        finally:
            os.chdir(original_cwd)

    def test_once_detects_all_complete_signal(
        self, runner: CliRunner, initialized_project_with_skill: Path
    ) -> None:
        """Test that once detects the <ralph>COMPLETE</ralph> signal."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_skill)

            with patch("ralph.commands.once.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = (
                    "Done! <ralph>COMPLETE</ralph>",
                    0,
                )
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["once"])

            assert "All stories are now complete" in result.output
        finally:
            os.chdir(original_cwd)

    def test_once_with_verbose_flag(
        self, runner: CliRunner, initialized_project_with_skill: Path
    ) -> None:
        """Test that once passes verbose flag to ClaudeService."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_skill)

            with patch("ralph.commands.once.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("Output", 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["once", "--verbose"])

            call_kwargs = mock_claude.call_args.kwargs
            assert call_kwargs.get("verbose") is True
        finally:
            os.chdir(original_cwd)

    def test_once_includes_max_fix_attempts_in_prompt(
        self, runner: CliRunner, initialized_project_with_skill: Path
    ) -> None:
        """Test that once includes max-fix-attempts in the prompt."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_skill)

            with patch("ralph.commands.once.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("Output", 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["once", "--max-fix-attempts", "5"])

                call_args = mock_instance.run_print_mode.call_args
                prompt = call_args[0][0]

                # The prompt should mention the max fix attempts
                assert "5" in prompt
        finally:
            os.chdir(original_cwd)

    def test_once_detects_story_passed(
        self, runner: CliRunner, initialized_project_with_skill: Path, sample_tasks_json: dict
    ) -> None:
        """Test that once detects when a story passes."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_skill)

            # Simulate Claude marking the story as passed
            updated_tasks = sample_tasks_json.copy()
            updated_tasks["userStories"][1]["passes"] = True

            def update_tasks_file(*args, **kwargs):
                tasks_file = initialized_project_with_skill / "plans" / "TASKS.json"
                tasks_file.write_text(json.dumps(updated_tasks, indent=2))
                return ("Output", 0)

            with patch("ralph.commands.once.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.side_effect = update_tasks_file
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["once"])

            assert result.exit_code == 0
            assert "completed successfully" in result.output
        finally:
            os.chdir(original_cwd)

    def test_once_handles_invalid_tasks_json(self, runner: CliRunner, temp_project: Path) -> None:
        """Test that once handles invalid TASKS.json gracefully."""
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project)

            plans_dir = temp_project / "plans"
            plans_dir.mkdir()
            tasks_file = plans_dir / "TASKS.json"
            tasks_file.write_text("invalid json")

            result = runner.invoke(app, ["once"])

            assert result.exit_code == 1
            assert "Error parsing" in result.output
        finally:
            os.chdir(original_cwd)

    def test_once_passes_skip_permissions_true(
        self, runner: CliRunner, initialized_project_with_skill: Path
    ) -> None:
        """Test that once passes skip_permissions=True to ClaudeService."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_skill)

            with patch("ralph.commands.once.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("Output", 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["once"])

            # Verify skip_permissions=True was passed
            call_kwargs = mock_instance.run_print_mode.call_args.kwargs
            assert call_kwargs.get("skip_permissions") is True
        finally:
            os.chdir(original_cwd)

    def test_once_displays_permissions_message(
        self, runner: CliRunner, initialized_project_with_skill: Path
    ) -> None:
        """Test that once displays the auto-approved permissions message."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project_with_skill)

            with patch("ralph.commands.once.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("Output", 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["once"])

            # Verify the permissions message is displayed
            assert "auto-approved permissions" in result.output
            assert "autonomous iteration" in result.output
        finally:
            os.chdir(original_cwd)

    def test_once_handles_skill_not_found(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that once handles missing skill gracefully."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            # No skill directory, so skill won't be found
            result = runner.invoke(app, ["once"])

            assert result.exit_code == 1
            assert "Skill not found" in result.output
        finally:
            os.chdir(original_cwd)


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


class TestBuildPromptFromSkill:
    """Tests for the _build_prompt_from_skill helper function."""

    @pytest.fixture
    def skill_project(self, tmp_path: Path) -> Path:
        """Create a project with ralph-iteration skill.

        Args:
            tmp_path: pytest's built-in tmp_path fixture.

        Returns:
            Path to the project directory with skill.
        """
        skills_dir = tmp_path / "skills" / "ralph-iteration"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: ralph-iteration\ndescription: Iteration skill\n---\n\n"
            "# Ralph Iteration Skill\n\n"
            "Run quality checks.\n"
            "Update TASKS.json and PROGRESS.txt.\n"
            "Output <ralph>COMPLETE</ralph> when done.\n"
        )
        return tmp_path

    def test_prompt_includes_story_details(self, skill_project: Path) -> None:
        """Test that prompt includes story ID, title, and description."""
        story = UserStory(
            id="US-042",
            title="Test Feature",
            description="As a user, I want to test",
            acceptance_criteria=["Criterion 1", "Criterion 2"],
            priority=1,
            passes=False,
        )

        prompt = _build_prompt_from_skill(skill_project, story, max_fix_attempts=3)

        assert "US-042" in prompt
        assert "Test Feature" in prompt
        assert "As a user, I want to test" in prompt

    def test_prompt_includes_acceptance_criteria(self, skill_project: Path) -> None:
        """Test that prompt includes acceptance criteria."""
        story = UserStory(
            id="US-001",
            title="Test",
            description="Desc",
            acceptance_criteria=["Build must pass", "Tests must pass"],
            priority=1,
            passes=False,
        )

        prompt = _build_prompt_from_skill(skill_project, story, max_fix_attempts=3)

        assert "Build must pass" in prompt
        assert "Tests must pass" in prompt

    def test_prompt_includes_max_fix_attempts(self, skill_project: Path) -> None:
        """Test that prompt includes max fix attempts value."""
        story = UserStory(
            id="US-001",
            title="Test",
            description="Desc",
            priority=1,
            passes=False,
        )

        prompt = _build_prompt_from_skill(skill_project, story, max_fix_attempts=5)

        # The prompt should contain instructions mentioning 5 attempts
        assert "5" in prompt

    def test_prompt_loads_skill_content(self, skill_project: Path) -> None:
        """Test that prompt includes skill content."""
        story = UserStory(
            id="US-001",
            title="Test",
            description="Desc",
            priority=1,
            passes=False,
        )

        prompt = _build_prompt_from_skill(skill_project, story, max_fix_attempts=3)

        # Check for skill content elements
        assert "Ralph Iteration Skill" in prompt
        assert "quality checks" in prompt.lower()
        assert "<ralph>COMPLETE</ralph>" in prompt

    def test_prompt_includes_context_section(self, skill_project: Path) -> None:
        """Test that prompt includes context section."""
        story = UserStory(
            id="US-001",
            title="Test",
            description="Desc",
            priority=1,
            passes=False,
        )

        prompt = _build_prompt_from_skill(skill_project, story, max_fix_attempts=3)

        # Check for context section
        assert "## Context for This Session" in prompt
        assert "## Current Story" in prompt

    def test_raises_when_skill_not_found(self, tmp_path: Path) -> None:
        """Test that _build_prompt_from_skill raises SkillNotFoundError."""
        story = UserStory(
            id="US-001",
            title="Test",
            description="Desc",
            priority=1,
            passes=False,
        )

        with pytest.raises(SkillNotFoundError):
            _build_prompt_from_skill(tmp_path, story, max_fix_attempts=3)


class TestOnceBoundaryConditions:
    """Boundary condition tests for the once command."""

    def test_find_next_story_with_empty_stories(self) -> None:
        """Test that _find_next_story handles empty userStories array."""
        tasks = TasksFile(
            project="EmptyTest",
            branch_name="ralph/empty",
            description="Empty stories test",
            user_stories=[],
        )

        result = _find_next_story(tasks)

        assert result is None

    def test_once_with_empty_stories_array(self, runner: CliRunner, temp_project: Path) -> None:
        """Test that once handles an empty userStories array gracefully."""
        import json
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project)

            plans_dir = temp_project / "plans"
            plans_dir.mkdir()

            tasks_data = {
                "project": "EmptyStoriesProject",
                "branchName": "ralph/empty-stories",
                "description": "A project with no stories",
                "userStories": [],
            }
            tasks_file = plans_dir / "TASKS.json"
            tasks_file.write_text(json.dumps(tasks_data, indent=2))

            result = runner.invoke(app, ["once"])

            assert result.exit_code == 0
            assert "All stories complete" in result.output
        finally:
            os.chdir(original_cwd)
