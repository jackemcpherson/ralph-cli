"""Tests for ralph prd command."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ralph.cli import app
from ralph.commands.prd import (
    _build_non_interactive_prd_prompt,
    _build_prd_prompt,
    _check_file_modified,
    _get_file_mtime,
)
from ralph.services import ClaudeError
from tests.conftest import normalize_paths


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
            assert "plans/SPEC.md" in normalize_paths(prompt)
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

            assert "plans/SPEC.md" in normalize_paths(result.output)
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

                def create_spec_file(_prompt: str, *, skip_permissions: bool = False) -> int:
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
            assert "was not modified" in result.output
            assert "cancelled" in result.output or "no changes" in result.output
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

            assert normalize_paths(custom_output) in normalize_paths(result.output)

            # Verify the prompt includes the custom path
            call_args = mock_instance.run_interactive.call_args
            prompt = call_args[0][0]
            assert "CUSTOM_SPEC.md" in normalize_paths(prompt)
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


class TestPrdSkipPermissions:
    """Tests for skip_permissions functionality in prd command."""

    def test_prd_passes_skip_permissions_true(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that prd calls run_interactive with skip_permissions=True."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["prd"])

            # Verify run_interactive was called with skip_permissions=True
            call_kwargs = mock_instance.run_interactive.call_args.kwargs
            assert call_kwargs.get("skip_permissions") is True
        finally:
            os.chdir(original_cwd)

    def test_prd_displays_permissions_message(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that prd displays info message about auto-approved permissions."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd"])

            assert "auto-approved permissions" in result.output
        finally:
            os.chdir(original_cwd)


class TestBuildPrdPrompt:
    """Tests for the _build_prd_prompt helper function."""

    def test_prompt_includes_output_path(self) -> None:
        """Test that prompt includes the output path."""
        output_path = Path("/project/plans/SPEC.md")
        prompt = _build_prd_prompt(output_path)

        assert normalize_paths(str(output_path)) in normalize_paths(prompt)

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


class TestPrdFileFlag:
    """Tests for the --file flag in prd command."""

    def test_prd_with_file_runs_non_interactive(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that --file triggers non-interactive mode."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            # Create a feature description file
            feature_file = initialized_project / "feature.txt"
            feature_file.write_text("Add a user authentication system")

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("output", 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd", "--file", "feature.txt"])

            # Verify run_print_mode was called, not run_interactive
            mock_instance.run_print_mode.assert_called_once()
            mock_instance.run_interactive.assert_not_called()
            assert "Non-Interactive PRD Generation" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_with_file_reads_file_contents(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that --file reads and uses file contents as feature description."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            feature_description = "Build a REST API with authentication"
            feature_file = initialized_project / "feature.txt"
            feature_file.write_text(feature_description)

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("output", 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["prd", "-f", "feature.txt"])

            # Verify the prompt includes the feature description from file
            call_args = mock_instance.run_print_mode.call_args
            prompt = call_args[0][0]
            assert feature_description in prompt
        finally:
            os.chdir(original_cwd)

    def test_prd_with_file_error_when_file_not_exists(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that --file shows error when file doesn't exist."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            result = runner.invoke(app, ["prd", "--file", "nonexistent.txt"])

            assert result.exit_code == 1
            assert "File not found" in result.output
            assert "nonexistent.txt" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_with_file_error_when_file_empty(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that --file shows error when file is empty."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            # Create an empty file
            feature_file = initialized_project / "empty.txt"
            feature_file.write_text("")

            result = runner.invoke(app, ["prd", "--file", "empty.txt"])

            assert result.exit_code == 1
            assert "File is empty" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_with_file_displays_feature_description(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that --file displays the feature description in output."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            feature_description = "Implement user dashboard with analytics"
            feature_file = initialized_project / "feature.txt"
            feature_file.write_text(feature_description)

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("output", 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd", "--file", "feature.txt"])

            assert feature_description in result.output
            assert "Generating PRD for:" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_with_file_success_creates_file(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that --file shows success when PRD file is created."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            feature_file = initialized_project / "feature.txt"
            feature_file.write_text("Build feature X")
            spec_path = initialized_project / "plans" / "SPEC.md"

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()

                def create_spec_file(_prompt: str) -> tuple[str, int]:
                    spec_path.write_text("# Feature Spec\n")
                    return ("output", 0)

                mock_instance.run_print_mode.side_effect = create_spec_file
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd", "--file", "feature.txt"])

            assert result.exit_code == 0
            assert "PRD saved to" in result.output
            assert "Next steps" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_with_file_strips_whitespace(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that --file strips whitespace from file contents."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            feature_description = "Build a feature"
            feature_file = initialized_project / "feature.txt"
            # File has leading/trailing whitespace
            feature_file.write_text(f"  \n  {feature_description}  \n  ")

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_print_mode.return_value = ("output", 0)
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["prd", "--file", "feature.txt"])

            # Verify the prompt includes the stripped feature description
            call_args = mock_instance.run_print_mode.call_args
            prompt = call_args[0][0]
            assert feature_description in prompt
            # Verify no leading/trailing whitespace
            assert "  \n  Build a feature" not in prompt
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

        assert normalize_paths(str(output_path)) in normalize_paths(prompt)

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


class TestPrdMutualExclusivity:
    """Tests for mutual exclusivity of --input and --file flags."""

    def test_prd_error_when_both_input_and_file_provided(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that prd shows error when both --input and --file are provided."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            # Create a feature description file
            feature_file = initialized_project / "feature.txt"
            feature_file.write_text("Feature from file")

            result = runner.invoke(
                app, ["prd", "--input", "Feature from input", "--file", "feature.txt"]
            )

            assert result.exit_code == 1
            assert "Cannot use both --input and --file" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_mutual_exclusivity_error_is_actionable(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that mutual exclusivity error message is clear and actionable."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            feature_file = initialized_project / "feature.txt"
            feature_file.write_text("Feature from file")

            result = runner.invoke(app, ["prd", "-i", "Feature from input", "-f", "feature.txt"])

            # Error message should explain what to do
            assert "--input" in result.output
            assert "--file" in result.output
            assert "but not both" in result.output or "at the same time" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_mutual_exclusivity_exits_nonzero(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that mutual exclusivity error exits with non-zero code."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            feature_file = initialized_project / "feature.txt"
            feature_file.write_text("Feature from file")

            result = runner.invoke(app, ["prd", "--input", "Input text", "--file", "feature.txt"])

            # Must exit with non-zero code
            assert result.exit_code != 0
            assert result.exit_code == 1
        finally:
            os.chdir(original_cwd)

    def test_prd_mutual_exclusivity_does_not_call_claude(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that Claude is not invoked when both flags are provided."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            feature_file = initialized_project / "feature.txt"
            feature_file.write_text("Feature from file")

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["prd", "--input", "Input text", "--file", "feature.txt"])

            # Claude should never be called
            mock_instance.run_interactive.assert_not_called()
            mock_instance.run_print_mode.assert_not_called()
        finally:
            os.chdir(original_cwd)


class TestGetFileMtime:
    """Tests for the _get_file_mtime helper function."""

    def test_returns_mtime_when_file_exists(self, tmp_path: Path) -> None:
        """Test that _get_file_mtime returns mtime when file exists."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mtime = _get_file_mtime(test_file)

        assert mtime is not None
        assert isinstance(mtime, float)
        assert mtime > 0

    def test_returns_none_when_file_not_exists(self, tmp_path: Path) -> None:
        """Test that _get_file_mtime returns None when file doesn't exist."""
        test_file = tmp_path / "nonexistent.txt"

        mtime = _get_file_mtime(test_file)

        assert mtime is None


class TestCheckFileModified:
    """Tests for the _check_file_modified helper function."""

    def test_shows_success_when_file_created(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that _check_file_modified shows success when file is newly created."""
        output_path = tmp_path / "SPEC.md"
        output = Path("plans/SPEC.md")

        # Simulate file created by Claude
        output_path.write_text("# New PRD")

        _check_file_modified(output_path, output, mtime_before=None)

        captured = capsys.readouterr()
        assert "PRD saved to" in captured.out
        assert "Next steps" in captured.out

    def test_shows_success_when_file_modified(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that _check_file_modified shows success when file is modified."""
        import time

        output_path = tmp_path / "SPEC.md"
        output = Path("plans/SPEC.md")

        # Create initial file
        output_path.write_text("# Initial PRD")
        mtime_before = _get_file_mtime(output_path)

        # Wait a tiny bit and modify file
        time.sleep(0.01)
        output_path.write_text("# Modified PRD")

        _check_file_modified(output_path, output, mtime_before)

        captured = capsys.readouterr()
        assert "PRD saved to" in captured.out
        assert "Next steps" in captured.out

    def test_shows_warning_when_file_not_created(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that _check_file_modified shows warning when file was not created."""
        output_path = tmp_path / "SPEC.md"
        output = Path("plans/SPEC.md")

        # File doesn't exist and was never created
        _check_file_modified(output_path, output, mtime_before=None)

        captured = capsys.readouterr()
        assert "was not modified" in captured.out
        assert "cancelled" in captured.out or "no changes" in captured.out

    def test_shows_warning_when_file_not_modified(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that _check_file_modified shows warning when file was not modified."""
        output_path = tmp_path / "SPEC.md"
        output = Path("plans/SPEC.md")

        # Create file before
        output_path.write_text("# PRD Content")
        mtime_before = _get_file_mtime(output_path)

        # Don't modify the file - mtime stays the same
        _check_file_modified(output_path, output, mtime_before)

        captured = capsys.readouterr()
        assert "was not modified" in captured.out


class TestPrdFileModificationDetection:
    """Integration tests for file modification detection in prd command."""

    def test_prd_detects_file_modification_interactive(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that interactive prd detects when file is modified."""
        import time

        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            # Create an existing SPEC.md file
            spec_path = initialized_project / "plans" / "SPEC.md"
            spec_path.write_text("# Initial Spec\n")

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()

                def modify_spec_file(_prompt: str, *, skip_permissions: bool = False) -> int:
                    time.sleep(0.01)  # Ensure mtime changes
                    spec_path.write_text("# Modified Spec\n")
                    return 0

                mock_instance.run_interactive.side_effect = modify_spec_file
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd"])

            assert result.exit_code == 0
            assert "PRD saved to" in result.output
            assert "Next steps" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_detects_no_modification_interactive(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that interactive prd detects when file is not modified."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            # Create an existing SPEC.md file
            spec_path = initialized_project / "plans" / "SPEC.md"
            spec_path.write_text("# Initial Spec\n")

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                # Claude returns success but doesn't modify the file
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd"])

            assert result.exit_code == 0
            assert "was not modified" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_detects_file_modification_non_interactive(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that non-interactive prd detects when file is modified."""
        import time

        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            # Create an existing SPEC.md file
            spec_path = initialized_project / "plans" / "SPEC.md"
            spec_path.write_text("# Initial Spec\n")

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()

                def modify_spec_file(_prompt: str) -> tuple[str, int]:
                    time.sleep(0.01)  # Ensure mtime changes
                    spec_path.write_text("# Modified Spec\n")
                    return ("output", 0)

                mock_instance.run_print_mode.side_effect = modify_spec_file
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd", "--input", "Add a feature"])

            assert result.exit_code == 0
            assert "PRD saved to" in result.output
            assert "Next steps" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_detects_no_modification_non_interactive(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that non-interactive prd detects when file is not modified."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            # Create an existing SPEC.md file
            spec_path = initialized_project / "plans" / "SPEC.md"
            spec_path.write_text("# Initial Spec\n")

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                # Claude returns success but doesn't modify the file
                mock_instance.run_print_mode.return_value = ("output", 0)
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd", "--input", "Add a feature"])

            assert result.exit_code == 0
            assert "was not modified" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_exits_zero_when_file_not_modified(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that prd exits with code 0 even when file is not modified."""
        original_cwd = os.getcwd()
        try:
            os.chdir(initialized_project)

            # Create an existing SPEC.md file
            spec_path = initialized_project / "plans" / "SPEC.md"
            spec_path.write_text("# Initial Spec\n")

            with patch("ralph.commands.prd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["prd"])

            # Exit code should be 0 even when file wasn't modified
            assert result.exit_code == 0
        finally:
            os.chdir(original_cwd)
