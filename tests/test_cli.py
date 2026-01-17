"""Integration tests for Ralph CLI commands."""

import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ralph import __version__
from ralph.cli import app


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


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
def python_project(temp_project: Path) -> Path:
    """Create a temporary Python project with pyproject.toml.

    Args:
        temp_project: Temporary project directory.

    Returns:
        Path to the Python project directory.
    """
    (temp_project / "pyproject.toml").write_text("[project]\nname = 'test-project'\n")
    return temp_project


@pytest.fixture
def skills_dir(temp_project: Path) -> Path:
    """Create a skills directory with a valid skill.

    Args:
        temp_project: Temporary project directory.

    Returns:
        Path to the skills directory.
    """
    skills_path = temp_project / "skills"
    skills_path.mkdir()

    skill_path = skills_path / "test-skill"
    skill_path.mkdir()
    (skill_path / "SKILL.md").write_text(
        '---\nname: "test-skill"\ndescription: "A test skill"\n---\n\n# Test Skill\n'
    )

    return skills_path


class TestCliHelp:
    """Tests for CLI help and basic functionality."""

    def test_help_shows_all_commands(self, runner: CliRunner) -> None:
        """Test that --help shows all registered commands."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "init" in result.output
        assert "prd" in result.output
        assert "tasks" in result.output
        assert "once" in result.output
        assert "loop" in result.output
        assert "sync" in result.output

    def test_help_shows_app_description(self, runner: CliRunner) -> None:
        """Test that --help shows the application description."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "Ralph CLI" in result.output
        assert "autonomous" in result.output.lower()

    def test_help_shows_version_option(self, runner: CliRunner) -> None:
        """Test that --help mentions the version option."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        # Strip ANSI codes as Rich may insert escape codes between dashes
        assert "--version" in strip_ansi(result.output)

    def test_no_args_shows_help(self, runner: CliRunner) -> None:
        """Test that running with no arguments shows help.

        Note: Typer's no_args_is_help=True returns exit code 2.
        """
        result = runner.invoke(app, [])

        # Typer returns exit code 2 for no_args_is_help behavior
        assert result.exit_code == 2
        assert "init" in result.output
        assert "prd" in result.output

    def test_command_help_shows_description(self, runner: CliRunner) -> None:
        """Test that command-specific help shows description."""
        result = runner.invoke(app, ["init", "--help"])

        assert result.exit_code == 0
        assert "Scaffold" in result.output or "scaffold" in result.output


class TestCliVersion:
    """Tests for CLI version display."""

    def test_version_shows_version_number(self, runner: CliRunner) -> None:
        """Test that --version shows the package version."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_short_flag_works(self, runner: CliRunner) -> None:
        """Test that -V also shows the version."""
        result = runner.invoke(app, ["-V"])

        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_format_includes_name(self, runner: CliRunner) -> None:
        """Test that version output includes the app name."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "ralph" in result.output


class TestInitIntegration:
    """Integration tests for ralph init command."""

    def test_init_creates_all_ralph_files(self, runner: CliRunner, python_project: Path) -> None:
        """Test that init creates all required Ralph workflow files."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init"])

            assert result.exit_code == 0

            # Verify plans directory and files
            assert (python_project / "plans").is_dir()
            assert (python_project / "plans" / "SPEC.md").is_file()
            assert (python_project / "plans" / "TASKS.json").is_file()
            assert (python_project / "plans" / "PROGRESS.txt").is_file()

            # Verify root files
            assert (python_project / "CLAUDE.md").is_file()
            assert (python_project / "AGENTS.md").is_file()
        finally:
            os.chdir(original_cwd)

    def test_init_creates_valid_tasks_json(self, runner: CliRunner, python_project: Path) -> None:
        """Test that init creates a valid TASKS.json file."""
        import json

        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init"])

            assert result.exit_code == 0

            # Verify TASKS.json is valid JSON
            tasks_file = python_project / "plans" / "TASKS.json"
            content = tasks_file.read_text()
            tasks_data = json.loads(content)

            # Verify structure
            assert "project" in tasks_data
            assert "branchName" in tasks_data
            assert "userStories" in tasks_data
        finally:
            os.chdir(original_cwd)

    def test_init_claude_md_contains_quality_checks(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that init creates CLAUDE.md with quality check markers."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
                mock_instance = MagicMock()
                mock_instance.run_interactive.return_value = 0
                mock_claude.return_value = mock_instance

                result = runner.invoke(app, ["init"])

            assert result.exit_code == 0

            # Verify CLAUDE.md contains quality check markers
            claude_md = (python_project / "CLAUDE.md").read_text()
            assert "RALPH:CHECKS:START" in claude_md
            assert "RALPH:CHECKS:END" in claude_md
            assert "checks:" in claude_md
        finally:
            os.chdir(original_cwd)

    def test_init_with_skip_claude_flag(self, runner: CliRunner, python_project: Path) -> None:
        """Test that --skip-claude flag prevents Claude invocation."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with patch("ralph.commands.init_cmd.ClaudeService") as mock_claude:
                result = runner.invoke(app, ["init", "--skip-claude"])

            assert result.exit_code == 0
            # Claude should not have been instantiated
            mock_claude.assert_not_called()

            # Files should still be created
            assert (python_project / "CLAUDE.md").is_file()
        finally:
            os.chdir(original_cwd)


class TestSyncIntegration:
    """Integration tests for ralph sync command."""

    def test_sync_copies_skill_to_target(
        self, runner: CliRunner, python_project: Path, skills_dir: Path, tmp_path: Path
    ) -> None:
        """Test that sync actually copies skills to target directory."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            # Create a custom target directory
            target_dir = tmp_path / "claude_skills"

            with patch("ralph.commands.sync.SkillsService") as mock_service_cls:
                # Create a real service instance with custom target
                from ralph.services import SkillSyncResult, SyncStatus

                mock_service = MagicMock()
                mock_service.list_local_skills.return_value = [skills_dir / "test-skill"]
                mock_service.target_dir = target_dir

                mock_result = SkillSyncResult(
                    skill_name="test-skill",
                    status=SyncStatus.CREATED,
                    source_path=skills_dir / "test-skill",
                    target_path=target_dir / "test-skill",
                )
                mock_service.sync_all.return_value = [mock_result]
                mock_service_cls.return_value = mock_service

                result = runner.invoke(app, ["sync"])

            assert result.exit_code == 0
            assert "test-skill" in result.output
            assert "Synced 1 skill" in result.output
        finally:
            os.chdir(original_cwd)

    def test_sync_with_custom_skills_directory(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that sync --skills-dir uses custom directory."""
        custom_skills = tmp_path / "my-skills"
        custom_skills.mkdir()

        skill_path = custom_skills / "custom-skill"
        skill_path.mkdir()
        (skill_path / "SKILL.md").write_text(
            '---\nname: "custom-skill"\ndescription: "A custom skill"\n---\n'
        )

        with patch("ralph.commands.sync.SkillsService") as mock_service_cls:
            from ralph.services import SkillSyncResult, SyncStatus

            mock_service = MagicMock()
            mock_service.list_local_skills.return_value = [skill_path]
            mock_service.target_dir = tmp_path / "target"

            mock_result = SkillSyncResult(
                skill_name="custom-skill",
                status=SyncStatus.CREATED,
                source_path=skill_path,
                target_path=tmp_path / "target" / "custom-skill",
            )
            mock_service.sync_all.return_value = [mock_result]
            mock_service_cls.return_value = mock_service

            result = runner.invoke(app, ["sync", "--skills-dir", str(custom_skills)])

        assert result.exit_code == 0

        # Verify SkillsService was called with custom path
        mock_service_cls.assert_called_once()
        call_kwargs = mock_service_cls.call_args[1]
        assert call_kwargs["skills_dir"] == custom_skills

    def test_sync_displays_summary(
        self, runner: CliRunner, python_project: Path, skills_dir: Path
    ) -> None:
        """Test that sync displays a summary after completion."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with patch("ralph.commands.sync.SkillsService") as mock_service_cls:
                from ralph.services import SkillSyncResult, SyncStatus

                mock_service = MagicMock()
                mock_service.list_local_skills.return_value = [skills_dir / "test-skill"]
                mock_service.target_dir = Path.home() / ".claude" / "skills"

                mock_result = SkillSyncResult(
                    skill_name="test-skill",
                    status=SyncStatus.CREATED,
                    source_path=skills_dir / "test-skill",
                    target_path=Path.home() / ".claude" / "skills" / "test-skill",
                )
                mock_service.sync_all.return_value = [mock_result]
                mock_service_cls.return_value = mock_service

                result = runner.invoke(app, ["sync"])

            assert result.exit_code == 0
            assert "Synced" in result.output
            # Summary should show counts
            assert "Created" in result.output or "created" in result.output
        finally:
            os.chdir(original_cwd)

    def test_sync_handles_no_skills_directory(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that sync handles missing skills directory gracefully."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            result = runner.invoke(app, ["sync"])

            assert result.exit_code == 0
            assert "Skills directory not found" in result.output
        finally:
            os.chdir(original_cwd)


class TestCommandsExist:
    """Tests to verify all commands are properly registered."""

    def test_init_command_registered(self, runner: CliRunner) -> None:
        """Test that init command is accessible."""
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        assert "init" in result.output.lower() or "scaffold" in result.output.lower()

    def test_prd_command_registered(self, runner: CliRunner) -> None:
        """Test that prd command is accessible."""
        result = runner.invoke(app, ["prd", "--help"])
        assert result.exit_code == 0
        assert "prd" in result.output.lower() or "interactively" in result.output.lower()

    def test_tasks_command_registered(self, runner: CliRunner) -> None:
        """Test that tasks command is accessible."""
        result = runner.invoke(app, ["tasks", "--help"])
        assert result.exit_code == 0
        # tasks command should show spec file argument info
        assert "spec" in result.output.lower() or "file" in result.output.lower()

    def test_once_command_registered(self, runner: CliRunner) -> None:
        """Test that once command is accessible."""
        result = runner.invoke(app, ["once", "--help"])
        assert result.exit_code == 0
        assert "iteration" in result.output.lower() or "once" in result.output.lower()

    def test_loop_command_registered(self, runner: CliRunner) -> None:
        """Test that loop command is accessible."""
        result = runner.invoke(app, ["loop", "--help"])
        assert result.exit_code == 0
        assert "iteration" in result.output.lower() or "loop" in result.output.lower()

    def test_sync_command_registered(self, runner: CliRunner) -> None:
        """Test that sync command is accessible."""
        result = runner.invoke(app, ["sync", "--help"])
        assert result.exit_code == 0
        assert "sync" in result.output.lower() or "skill" in result.output.lower()


class TestErrorHandling:
    """Tests for CLI error handling."""

    def test_unknown_command_shows_error(self, runner: CliRunner) -> None:
        """Test that unknown commands show an error message."""
        result = runner.invoke(app, ["unknown-command"])

        assert result.exit_code != 0
        # Should suggest similar commands or show error
        assert "No such command" in result.output or "Error" in result.output

    def test_invalid_option_shows_error(self, runner: CliRunner) -> None:
        """Test that invalid options show an error message."""
        result = runner.invoke(app, ["--invalid-option"])

        assert result.exit_code != 0

    def test_tasks_without_file_shows_error(self, runner: CliRunner) -> None:
        """Test that tasks command without file shows error."""
        result = runner.invoke(app, ["tasks"])

        # Should fail because spec file is required
        assert result.exit_code != 0
