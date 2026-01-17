"""Tests for ralph prd command."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ralph.cli import app
from ralph.commands.prd import _build_non_interactive_prd_prompt, _build_prd_prompt
from ralph.services import ClaudeError


@pytest.fixture
def runner() -> CliRunner:
    """Create a CliRunner for testing commands."""
    return CliRunner()


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory.

    Args:
        tmp_path: pytest's built-in tmp_path fixture.

    Returns:
        Path to the temporary project directory.
    """
    return tmp_path


@pytest.fixture
def initialized_project(temp_project: Path) -> Path:
    """Create a temporary project with plans/ directory.

    Args:
        temp_project: Temporary project directory.

    Returns:
        Path to the initialized project directory.
    """
    plans_dir = temp_project / "plans"
    plans_dir.mkdir()
    return temp_project


class TestPrdCommand:
    """Tests for the prd command."""

    def test_prd_requires_plans_directory(self, runner: CliRunner, temp_project: Path) -> None:
        """Test that prd fails if plans/ directory doesn't exist."""
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project)

            result = runner.invoke(app, ["prd"])

            assert result.exit_code == 1
            assert "plans/ directory not found" in result.output
            assert "ralph init" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_displays_informational_message(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that prd displays informational message before launching Claude."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd"])

            assert "Interactive PRD Creation" in result.output
            assert "Product Requirements Document" in result.output
            assert "Tips for a good PRD session" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_launches_claude_interactively(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that prd launches Claude Code in interactive mode."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["prd"])

            # Verify ClaudeService was called correctly
            mock_claude.assert_called_once()
            mock_instance.run_interactive.assert_called_once()

            # Verify the prompt was passed
            call_args = mock_instance.run_interactive.call_args
            prompt = call_args[0][0]
            assert "Product Requirements Document" in prompt
        finally:
            os.chdir(original_cwd)

    def test_prd_includes_prd_prompt(self, runner: CliRunner, initialized_project: Path) -> None:
        """Test that prd includes proper prompt for PRD creation."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["prd"])

            call_args = mock_instance.run_interactive.call_args
            prompt = call_args[0][0]

            # Verify prompt includes key elements
            assert "clarifying questions" in prompt
            assert "Overview" in prompt
            assert "Goals" in prompt
            assert "Requirements" in prompt
            assert "plans/SPEC.md" in prompt
        finally:
            os.chdir(original_cwd)

    def test_prd_shows_output_path(self, runner: CliRunner, initialized_project: Path) -> None:
        """Test that prd shows the output path."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd"])

            assert "plans/SPEC.md" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_success_with_file_created(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that prd shows success message when file is created."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            # Create the SPEC.md file to simulate Claude creating it
            spec_path = initialized_project / "plans" / "SPEC.md"

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()

                def create_spec_file(_prompt: str) -> int:
                    spec_path.write_text("# Feature Spec\n")
                    return 0

                mock_instance.run_interactive.side_effect = create_spec_file
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd"])

            assert result.exit_code == 0
            assert "PRD saved to" in result.output
            assert "Next steps" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_warning_when_file_not_created(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that prd shows warning when file is not created."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd"])

            # File was not created
            assert "was not created" in result.output
            assert "cancelled" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_handles_nonzero_exit_code(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that prd handles non-zero exit code from Claude."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 1
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd"])

            assert result.exit_code == 1
            assert "non-zero" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_handles_claude_error(self, runner: CliRunner, initialized_project: Path) -> None:
        """Test that prd handles ClaudeError gracefully."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.side_effect = ClaudeError("Claude not installed")
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd"])

            assert result.exit_code == 1
            assert "Failed to launch Claude Code" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_notes_existing_spec(self, runner: CliRunner, initialized_project: Path) -> None:
        """Test that prd notes when SPEC.md already exists."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            # Create existing SPEC.md
            spec_path = initialized_project / "plans" / "SPEC.md"
            spec_path.write_text("# Existing Spec\n")

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd"])

            assert "already exists" in result.output
            assert "update or expand" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_with_custom_output_path(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that prd accepts custom output path."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            custom_output = "plans/CUSTOM_SPEC.md"

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd", "--output", custom_output])

            assert custom_output in result.output

            # Verify the prompt includes the custom path
            call_args = mock_instance.run_interactive.call_args
            prompt = call_args[0][0]
            assert "CUSTOM_SPEC.md" in prompt
        finally:
            os.chdir(original_cwd)

    def test_prd_with_verbose_flag(self, runner: CliRunner, initialized_project: Path) -> None:
        """Test that prd passes verbose flag to ClaudeService."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["prd", "--verbose"])

            # Verify ClaudeService was created with verbose=True
            call_kwargs = mock_claude.call_args.kwargs
            assert call_kwargs.get("verbose") is True
        finally:
            os.chdir(original_cwd)


class TestBuildPrdPrompt:
    """Tests for the _build_prd_prompt helper function."""

    def test_prompt_includes_output_path(self) -> None:
        """Test that prompt includes the output path."""
        output_path = Path("/project/plans/SPEC.md")
        prompt = _build_prd_prompt(output_path)

        assert str(output_path) in prompt

    def test_prompt_includes_prd_structure(self) -> None:
        """Test that prompt includes PRD structure guidance."""
        prompt = _build_prd_prompt(Path("plans/SPEC.md"))

        assert "Overview" in prompt
        assert "Goals" in prompt
        assert "Non-Goals" in prompt
        assert "Requirements" in prompt
        assert "Technical Considerations" in prompt
        assert "Success Criteria" in prompt

    def test_prompt_asks_clarifying_questions(self) -> None:
        """Test that prompt asks for clarifying questions."""
        prompt = _build_prd_prompt(Path("plans/SPEC.md"))

        assert "clarifying questions" in prompt
        assert "what feature" in prompt.lower()


class TestPrdInputFlag:
    """Tests for the --input flag in prd command."""

    def test_prd_with_input_runs_non_interactive(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that --input triggers non-interactive mode."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("output", 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd", "--input", "Add a user authentication system"])

            # Verify run_print_mode was called, not run_interactive
            mock_instance.run_print_mode.assert_called_once()
            mock_instance.run_interactive.assert_not_called()
            assert "Non-Interactive PRD Generation" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_with_input_uses_print_mode(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that --input uses run_print_mode instead of run_interactive."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("output", 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["prd", "-i", "Build a REST API"])

            # Verify ClaudeService.run_print_mode was called
            mock_instance.run_print_mode.assert_called_once()
        finally:
            os.chdir(original_cwd)

    def test_prd_with_input_includes_feature_description(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that --input includes feature description in prompt."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            feature_description = "Add a dark mode toggle feature"

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("output", 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["prd", "--input", feature_description])

            # Verify the prompt includes the feature description
            call_args = mock_instance.run_print_mode.call_args
            prompt = call_args[0][0]
            assert feature_description in prompt
        finally:
            os.chdir(original_cwd)

    def test_prd_with_input_displays_feature_description(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that --input displays the feature description in output."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            feature_description = "Implement user dashboard"

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("output", 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd", "--input", feature_description])

            assert feature_description in result.output
            assert "Generating PRD for:" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_with_input_success_creates_file(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that --input shows success when file is created."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            spec_path = initialized_project / "plans" / "SPEC.md"

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()

                def create_spec_file(_prompt: str) -> tuple[str, int]:
                    spec_path.write_text("# Feature Spec\n")
                    return ("output", 0)

                mock_instance.run_print_mode.side_effect = create_spec_file
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd", "--input", "Build feature X"])

            assert result.exit_code == 0
            assert "PRD saved to" in result.output
            assert "Next steps" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_with_input_handles_claude_error(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that --input handles ClaudeError gracefully."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.side_effect = ClaudeError("Claude not found")
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd", "--input", "Some feature"])

            assert result.exit_code == 1
            assert "Failed to run Claude Code" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_with_input_handles_nonzero_exit(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that --input handles non-zero exit code from Claude."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("error", 1)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd", "--input", "Some feature"])

            assert result.exit_code == 1
            assert "non-zero" in result.output
        finally:
            os.chdir(original_cwd)


class TestBuildNonInteractivePrdPrompt:
    """Tests for the _build_non_interactive_prd_prompt helper function."""

    def test_prompt_includes_feature_description(self) -> None:
        """Test that prompt includes the feature description."""
        feature = "Add user authentication with OAuth2"
        prompt = _build_non_interactive_prd_prompt(Path("plans/SPEC.md"), feature)

        assert feature in prompt

    def test_prompt_includes_output_path(self) -> None:
        """Test that prompt includes the output path."""
        output_path = Path("/project/plans/SPEC.md")
        prompt = _build_non_interactive_prd_prompt(output_path, "Some feature")

        assert str(output_path) in prompt

    def test_prompt_includes_prd_structure(self) -> None:
        """Test that prompt includes PRD structure guidance."""
        prompt = _build_non_interactive_prd_prompt(Path("plans/SPEC.md"), "Feature X")

        assert "Overview" in prompt
        assert "Goals" in prompt
        assert "Non-Goals" in prompt
        assert "Requirements" in prompt
        assert "Technical Considerations" in prompt
        assert "Success Criteria" in prompt

    def test_prompt_does_not_ask_clarifying_questions(self) -> None:
        """Test that non-interactive prompt doesn't ask for clarifying questions."""
        prompt = _build_non_interactive_prd_prompt(Path("plans/SPEC.md"), "Feature X")

        # Non-interactive mode should NOT ask for clarifying questions
        assert "clarifying questions" not in prompt
        assert "what feature I want to build" not in prompt
