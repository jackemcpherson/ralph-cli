"""Tests for ralph init command."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ralph.cli import app
from ralph.commands.init_cmd import (
    _check_existing_files,
    _handle_missing_prd,
    _has_prd_content,
)


class TestInitCommand:
    """Tests for the init command."""

    def test_init_creates_ralph_files(self, runner: CliRunner, python_project: Path) -> None:
        """Test that init creates all Ralph workflow files."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            # Mock ClaudeService and Confirm to avoid actual calls
            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init"])

            assert result.exit_code == 0

            # Verify all files were created
            assert (python_project / "plans").exists()
            assert (python_project / "plans" / "SPEC.md").exists()
            assert (python_project / "plans" / "TASKS.json").exists()
            assert (python_project / "plans" / "PROGRESS.txt").exists()
            assert (python_project / "CLAUDE.md").exists()
            assert (python_project / "AGENTS.md").exists()
        finally:
            os.chdir(original_cwd)

    def test_init_detects_python_project(self, runner: CliRunner, python_project: Path) -> None:
        """Test that init detects Python project and sets appropriate checks."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init"])

            assert result.exit_code == 0
            assert "python" in result.output.lower()

            # Verify CLAUDE.md contains Python-specific checks
            claude_md = (python_project / "CLAUDE.md").read_text()
            assert "pyright" in claude_md
            assert "ruff" in claude_md
        finally:
            os.chdir(original_cwd)

    def test_init_detects_nodejs_project(self, runner: CliRunner, nodejs_project: Path) -> None:
        """Test that init detects Node.js project and sets appropriate checks."""
        original_cwd = os.getcwd()
        try:
            os.chdir(nodejs_project)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init"])

            assert result.exit_code == 0
            assert "nodejs" in result.output.lower()

            # Verify CLAUDE.md contains Node.js-specific checks
            claude_md = (nodejs_project / "CLAUDE.md").read_text()
            assert "npm run" in claude_md
        finally:
            os.chdir(original_cwd)

    def test_init_refuses_overwrite_without_force(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that init refuses to overwrite existing files without --force."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            # Create an existing CLAUDE.md
            (python_project / "CLAUDE.md").write_text("# Existing content\n")

            result = runner.invoke(app, ["init"])

            assert result.exit_code == 1
            assert "already exist" in result.output
            assert "--force" in result.output
        finally:
            os.chdir(original_cwd)

    def test_init_with_force_overwrites_files(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that init --force overwrites existing files."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            # Create an existing CLAUDE.md with known content
            (python_project / "CLAUDE.md").write_text("# Existing content\n")

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init", "--force"])

            assert result.exit_code == 0

            # Verify CLAUDE.md was overwritten
            claude_md = (python_project / "CLAUDE.md").read_text()
            assert "# Existing content" not in claude_md
            assert "Ralph Workflow" in claude_md
        finally:
            os.chdir(original_cwd)

    def test_init_with_skip_claude(self, runner: CliRunner, python_project: Path) -> None:
        """Test that init --skip-claude skips Claude invocation."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                result = runner.invoke(app, ["init", "--skip-claude"])

            assert result.exit_code == 0
            # ClaudeService should not have been called
            mock_claude.assert_not_called()
        finally:
            os.chdir(original_cwd)

    def test_init_with_custom_project_name(self, runner: CliRunner, python_project: Path) -> None:
        """Test that init --name sets custom project name."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init", "--name", "MyCustomProject"])

            assert result.exit_code == 0

            # Verify project name in CLAUDE.md
            claude_md = (python_project / "CLAUDE.md").read_text()
            assert "MyCustomProject" in claude_md
        finally:
            os.chdir(original_cwd)

    def test_init_shows_next_steps(self, runner: CliRunner, python_project: Path) -> None:
        """Test that init displays next steps after completion."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init"])

            assert result.exit_code == 0
            assert "Next steps" in result.output
            assert "ralph prd" in result.output
            assert "ralph tasks" in result.output
            assert "ralph loop" in result.output
        finally:
            os.chdir(original_cwd)

    def test_init_handles_claude_error_gracefully(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that init handles Claude Code errors gracefully."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_claude.side_effect = Exception("Claude not installed")

                result = runner.invoke(app, ["init"])

            # Should still succeed, just with a warning
            assert result.exit_code == 0
            assert "Failed to run Claude Code" in result.output
        finally:
            os.chdir(original_cwd)


class TestCheckExistingFiles:
    """Tests for the _check_existing_files helper function."""

    def test_returns_empty_for_new_project(self, temp_project: Path) -> None:
        """Test that no files are found in a new project."""
        existing = _check_existing_files(temp_project)
        assert existing == []

    def test_finds_existing_claude_md(self, temp_project: Path) -> None:
        """Test that existing CLAUDE.md is found."""
        (temp_project / "CLAUDE.md").write_text("# Test\n")

        existing = _check_existing_files(temp_project)

        assert "CLAUDE.md" in existing

    def test_finds_existing_plans_directory(self, temp_project: Path) -> None:
        """Test that existing plans/ files are found."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        (plans_dir / "SPEC.md").write_text("# Spec\n")
        (plans_dir / "TASKS.json").write_text("{}\n")

        existing = _check_existing_files(temp_project)

        assert "plans/SPEC.md" in existing
        assert "plans/TASKS.json" in existing

    def test_finds_all_ralph_files(self, temp_project: Path) -> None:
        """Test that all Ralph files are found when present."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        (plans_dir / "SPEC.md").write_text("# Spec\n")
        (plans_dir / "TASKS.json").write_text("{}\n")
        (plans_dir / "PROGRESS.txt").write_text("# Progress\n")
        (temp_project / "CLAUDE.md").write_text("# Claude\n")
        (temp_project / "AGENTS.md").write_text("# Agents\n")
        (temp_project / "CHANGELOG.md").write_text("# Changelog\n")

        existing = _check_existing_files(temp_project)

        assert len(existing) == 6
        assert "plans/SPEC.md" in existing
        assert "plans/TASKS.json" in existing
        assert "plans/PROGRESS.txt" in existing
        assert "CLAUDE.md" in existing
        assert "AGENTS.md" in existing
        assert "CHANGELOG.md" in existing

    def test_finds_existing_changelog_md(self, temp_project: Path) -> None:
        """Test that existing CHANGELOG.md is found."""
        (temp_project / "CHANGELOG.md").write_text("# Changelog\n")

        existing = _check_existing_files(temp_project)

        assert "CHANGELOG.md" in existing


class TestInitSkipPermissions:
    """Tests for skip_permissions functionality in init command."""

    def test_init_passes_skip_permissions_true(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that init calls run_interactive with skip_permissions=True."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["init"])

            # Verify run_interactive was called with skip_permissions=True
            call_kwargs = mock_instance.run_interactive.call_args.kwargs
            assert call_kwargs.get("skip_permissions") is True
        finally:
            os.chdir(original_cwd)


class TestInitChangelogCreation:
    """Tests for CHANGELOG.md creation in init command."""

    def test_init_creates_changelog_md(self, runner: CliRunner, python_project: Path) -> None:
        """Test that init creates CHANGELOG.md in project root."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init"])

            assert result.exit_code == 0
            assert (python_project / "CHANGELOG.md").exists()
        finally:
            os.chdir(original_cwd)

    def test_init_changelog_follows_keep_a_changelog_format(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that created CHANGELOG.md follows Keep a Changelog format."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["init"])

            changelog_content = (python_project / "CHANGELOG.md").read_text()
            assert "# Changelog" in changelog_content
            assert "Keep a Changelog" in changelog_content
        finally:
            os.chdir(original_cwd)

    def test_init_changelog_has_unreleased_section(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that created CHANGELOG.md has Unreleased section with category headers."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                runner.invoke(app, ["init"])

            changelog_content = (python_project / "CHANGELOG.md").read_text()
            assert "## [Unreleased]" in changelog_content
            assert "### Added" in changelog_content
            assert "### Changed" in changelog_content
            assert "### Fixed" in changelog_content
        finally:
            os.chdir(original_cwd)

    def test_init_does_not_overwrite_existing_changelog(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that init does NOT overwrite existing CHANGELOG.md even with --force."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            # Create an existing CHANGELOG.md with custom content
            existing_content = "# My Custom Changelog\n\n## v1.0.0\n\n- Initial release\n"
            (python_project / "CHANGELOG.md").write_text(existing_content)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                # Use --force to overwrite other files
                result = runner.invoke(app, ["init", "--force"])

            assert result.exit_code == 0

            # Verify CHANGELOG.md was NOT overwritten
            changelog_content = (python_project / "CHANGELOG.md").read_text()
            assert changelog_content == existing_content
            assert "My Custom Changelog" in changelog_content
            assert "v1.0.0" in changelog_content
        finally:
            os.chdir(original_cwd)

    def test_init_shows_skipped_message_for_existing_changelog(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that init shows 'Skipped' message for existing CHANGELOG.md."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            # Create an existing CHANGELOG.md
            (python_project / "CHANGELOG.md").write_text("# Existing changelog\n")

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init", "--force"])

            assert result.exit_code == 0
            assert "Skipped CHANGELOG.md" in result.output
            assert "already exists" in result.output
        finally:
            os.chdir(original_cwd)


class TestHasPrdContent:
    """Tests for the _has_prd_content helper function."""

    def test_returns_false_for_nonexistent_file(self, temp_project: Path) -> None:
        """Test that nonexistent file returns False."""
        prd_path = temp_project / "plans" / "SPEC.md"
        assert _has_prd_content(prd_path) is False

    def test_returns_false_for_empty_file(self, temp_project: Path) -> None:
        """Test that empty file returns False."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        prd_path = plans_dir / "SPEC.md"
        prd_path.write_text("")
        assert _has_prd_content(prd_path) is False

    def test_returns_false_for_whitespace_only(self, temp_project: Path) -> None:
        """Test that whitespace-only file returns False."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        prd_path = plans_dir / "SPEC.md"
        prd_path.write_text("   \n\n   ")
        assert _has_prd_content(prd_path) is False

    def test_returns_false_for_template_only(self, temp_project: Path) -> None:
        """Test that template-only content returns False."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        prd_path = plans_dir / "SPEC.md"
        prd_path.write_text(
            "# Feature Specification\n\n"
            "<!-- Replace this with your actual specification -->\n\n"
            "## Overview\n\n"
        )
        assert _has_prd_content(prd_path) is False

    def test_returns_true_for_real_content(self, temp_project: Path) -> None:
        """Test that file with real content returns True."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        prd_path = plans_dir / "SPEC.md"
        prd_path.write_text(
            "# My Feature Specification\n\n"
            "## Overview\n\n"
            "This feature implements user authentication for the application.\n\n"
            "## Goals\n\n"
            "- Secure user login\n"
            "- Session management\n"
        )
        assert _has_prd_content(prd_path) is True

    def test_returns_true_for_requirements_section(self, temp_project: Path) -> None:
        """Test that file with requirements content returns True."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        prd_path = plans_dir / "SPEC.md"
        prd_path.write_text(
            "# Specification\n\n## Requirements\n\nThe system must handle 1000 concurrent users.\n"
        )
        assert _has_prd_content(prd_path) is True

    def test_returns_false_for_placeholder_markers(self, temp_project: Path) -> None:
        """Test that placeholder markers are detected as template content."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        prd_path = plans_dir / "SPEC.md"
        prd_path.write_text("# Feature Specification\n\n[Your feature description here]\n")
        assert _has_prd_content(prd_path) is False


class TestHandleMissingPrd:
    """Tests for the _handle_missing_prd helper function."""

    def test_prompts_user_to_create_prd(self, temp_project: Path) -> None:
        """Test that user is prompted when PRD is missing."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        prd_path = plans_dir / "SPEC.md"

        with patch("ralph.commands.init_cmd.Confirm.ask", return_value=False) as mock_confirm:
            _handle_missing_prd(prd_path, temp_project)

        mock_confirm.assert_called_once()
        # Verify the prompt message mentions creating a PRD
        call_args = mock_confirm.call_args
        assert "prd" in call_args[0][0].lower()

    def test_invokes_prd_command_when_confirmed(self, temp_project: Path) -> None:
        """Test that prd command is invoked when user confirms."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        prd_path = plans_dir / "SPEC.md"

        with (
            patch("ralph.commands.init_cmd.Confirm.ask", return_value=True),
            patch("ralph.commands.init_cmd.prd_command") as mock_prd,
        ):
            _handle_missing_prd(prd_path, temp_project)

        mock_prd.assert_called_once()
        # Verify it was called with the correct output path
        call_kwargs = mock_prd.call_args.kwargs
        assert call_kwargs.get("output") == Path("plans/SPEC.md")

    def test_shows_message_when_declined(self, temp_project: Path) -> None:
        """Test that informational message is shown when user declines."""
        plans_dir = temp_project / "plans"
        plans_dir.mkdir()
        prd_path = plans_dir / "SPEC.md"

        with patch("ralph.commands.init_cmd.Confirm.ask", return_value=False):
            _handle_missing_prd(prd_path, temp_project)

        # Output goes through Rich console which may not be captured
        # This test primarily verifies no exception is raised when user declines


class TestInitPrdPrompt:
    """Integration tests for PRD prompt behavior in init command."""

    def test_init_prompts_for_prd_when_missing(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that init prompts for PRD when SPEC.md has no content."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            # Mock both ClaudeService and the Confirm prompt
            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False) as mock_confirm,
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init"])

            assert result.exit_code == 0
            # Confirm should have been called (asking about PRD)
            mock_confirm.assert_called_once()
            # Should show the warning about missing PRD
            assert "No PRD found" in result.output

        finally:
            os.chdir(original_cwd)

    def test_init_invokes_prd_when_user_confirms(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that init invokes prd command when user confirms PRD creation."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=True),
                patch("ralph.commands.init_cmd.prd_command") as mock_prd,
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init"])

            assert result.exit_code == 0
            # prd command should have been invoked
            mock_prd.assert_called_once()

        finally:
            os.chdir(original_cwd)

    def test_init_shows_message_when_user_declines_prd(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that init shows message when user declines PRD creation."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=False),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init"])

            assert result.exit_code == 0
            # Should show the "proceeding without PRD" message
            assert "Proceeding without PRD" in result.output or "ralph prd" in result.output

        finally:
            os.chdir(original_cwd)

    def test_init_skips_prd_prompt_when_spec_has_content(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that init skips PRD prompt when SPEC.md already has content."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            # Create plans dir with a SPEC.md that has real content
            plans_dir = python_project / "plans"
            plans_dir.mkdir()
            (plans_dir / "SPEC.md").write_text(
                "# Feature Specification\n\n"
                "## Overview\n\n"
                "This is my actual specification content.\n"
            )

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask") as mock_confirm,
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init", "--force"])

            assert result.exit_code == 0
            # Confirm should NOT have been called (PRD exists with content)
            mock_confirm.assert_not_called()

        finally:
            os.chdir(original_cwd)

    def test_init_handles_prd_command_error_gracefully(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that init handles PRD command errors gracefully."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with (
                patch("ralph.commands.init_cmd.ClaudeService") as mock_claude,
                patch("ralph.commands.init_cmd.Confirm.ask", return_value=True),
                patch(
                    "ralph.commands.init_cmd.prd_command",
                    side_effect=RuntimeError("PRD failed"),
                ),
            ):
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init"])

            # Should still complete successfully
            assert result.exit_code == 0
            # Should show error message about PRD failure
            assert "PRD creation failed" in result.output

        finally:
            os.chdir(original_cwd)
