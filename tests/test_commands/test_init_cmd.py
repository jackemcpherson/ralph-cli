"""Tests for ralph init command."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ralph.cli import app
from ralph.commands.init_cmd import _check_existing_files


class TestInitCommand:
    """Tests for the init command."""

    def test_init_creates_ralph_files(self, runner: CliRunner, python_project: Path) -> None:
        """Test that init creates all Ralph workflow files."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            # Mock ClaudeService to avoid actually calling Claude
            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
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

            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
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

            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
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

            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
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

            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
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

            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
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

            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
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

            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
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

            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
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

            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
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

            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
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

            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
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

            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
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

            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init", "--force"])

            assert result.exit_code == 0
            assert "Skipped CHANGELOG.md" in result.output
            assert "already exists" in result.output
        finally:
            os.chdir(original_cwd)
