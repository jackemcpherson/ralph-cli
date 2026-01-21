"""Integration tests for ralph prd automation (--input and --file flags).

These tests verify that ralph prd correctly handles non-interactive mode
with --input and --file flags, and enforces mutual exclusivity.
"""

import os
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ralph.cli import app


@pytest.fixture
def runner() -> CliRunner:
    """Create a CliRunner for testing commands."""
    return CliRunner()


def _create_ralph_prd_skill(project_root: Path) -> None:
    """Create the ralph-prd skill directory with SKILL.md file."""
    skill_dir = project_root / "skills" / "ralph-prd"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        """---
name: ralph-prd
description: Test PRD skill
---

# Ralph PRD Creation Skill

You are helping create a Product Requirements Document (PRD).

## Output Format

Write the PRD with these sections:
- Overview
- Goals
- Non-Goals
- Requirements
- Technical Considerations
- Success Criteria
"""
    )


@pytest.fixture
def project_with_plans(tmp_path: Path) -> Path:
    """Create a project directory with plans/ directory and ralph-prd skill."""
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()
    _create_ralph_prd_skill(tmp_path)
    return tmp_path


@pytest.fixture
def project_with_spec(tmp_path: Path) -> Path:
    """Create a project directory with plans/ directory, existing SPEC.md, and ralph-prd skill."""
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()

    spec_file = plans_dir / "SPEC.md"
    spec_file.write_text("# Existing PRD\n\nSome existing content.\n")

    _create_ralph_prd_skill(tmp_path)
    return tmp_path


class TestPrdInputFlagIntegration:
    """Integration tests for ralph prd --input flag."""

    def test_prd_input_invokes_claude_in_print_mode(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that ralph prd --input invokes Claude in print mode."""
        original_cwd = os.getcwd()
        captured_args: list[str] = []

        def mock_popen(args: list[str], **kwargs):
            captured_args.extend(args)
            mock_process = MagicMock()
            mock_process.stdout = StringIO("PRD generated successfully")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_plans)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                result = runner.invoke(app, ["prd", "--input", "Add user authentication"])

            # Should use --print mode for non-interactive
            assert "--print" in captured_args
            assert result.exit_code == 0
        finally:
            os.chdir(original_cwd)

    def test_prd_input_displays_non_interactive_header(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that ralph prd --input displays the non-interactive header."""
        original_cwd = os.getcwd()

        def mock_popen(args: list[str], **kwargs):
            mock_process = MagicMock()
            mock_process.stdout = StringIO("PRD created")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_plans)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                result = runner.invoke(app, ["prd", "--input", "Add dark mode toggle"])

            assert "Non-Interactive PRD Generation" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_input_shows_feature_description(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that ralph prd --input displays the feature description."""
        original_cwd = os.getcwd()
        feature = "Implement user dashboard with analytics"

        def mock_popen(args: list[str], **kwargs):
            mock_process = MagicMock()
            mock_process.stdout = StringIO("Done")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_plans)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                result = runner.invoke(app, ["prd", "--input", feature])

            assert feature in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_input_includes_feature_in_prompt(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that ralph prd --input passes feature description to Claude."""
        original_cwd = os.getcwd()
        captured_args: list[str] = []
        feature = "Add real-time notifications"

        def mock_popen(args: list[str], **kwargs):
            captured_args.extend(args)
            mock_process = MagicMock()
            mock_process.stdout = StringIO("PRD written")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_plans)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                runner.invoke(app, ["prd", "--input", feature])

            # Find the prompt argument (comes after --print)
            print_index = captured_args.index("--print")
            prompt = captured_args[print_index + 1]

            # Verify prompt contains feature description
            assert feature in prompt
        finally:
            os.chdir(original_cwd)

    def test_prd_input_detects_file_modification(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that ralph prd --input detects when SPEC.md is created."""
        original_cwd = os.getcwd()

        def mock_popen_creates_file(args: list[str], **kwargs):
            # Simulate Claude creating the SPEC.md file
            spec_file = project_with_plans / "plans" / "SPEC.md"
            spec_file.write_text("# Generated PRD\n\n## Overview\n...")

            mock_process = MagicMock()
            mock_process.stdout = StringIO("PRD created successfully")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_plans)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen_creates_file),
            ):
                result = runner.invoke(app, ["prd", "--input", "New feature"])

            assert "PRD saved to" in result.output
            assert result.exit_code == 0
        finally:
            os.chdir(original_cwd)

    def test_prd_input_handles_claude_error(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that ralph prd --input handles Claude errors gracefully."""
        original_cwd = os.getcwd()

        def mock_popen_error(args: list[str], **kwargs):
            raise FileNotFoundError("claude not found")

        try:
            os.chdir(project_with_plans)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen_error),
            ):
                result = runner.invoke(app, ["prd", "--input", "Some feature"])

            assert result.exit_code == 1
            assert "Failed to run Claude" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_input_handles_nonzero_exit_code(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that ralph prd --input handles non-zero exit code from Claude."""
        original_cwd = os.getcwd()

        def mock_popen_failure(args: list[str], **kwargs):
            mock_process = MagicMock()
            mock_process.stdout = StringIO("Error occurred")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 1  # Non-zero exit
            return mock_process

        try:
            os.chdir(project_with_plans)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen_failure),
            ):
                result = runner.invoke(app, ["prd", "--input", "Feature"])

            # Should exit with non-zero code
            assert result.exit_code != 0
            assert "non-zero" in result.output.lower()
        finally:
            os.chdir(original_cwd)


class TestPrdFileFlagIntegration:
    """Integration tests for ralph prd --file flag."""

    def test_prd_file_invokes_claude_in_print_mode(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that ralph prd --file invokes Claude in print mode."""
        original_cwd = os.getcwd()
        captured_args: list[str] = []

        # Create feature description file
        feature_file = project_with_plans / "feature.txt"
        feature_file.write_text("Add comprehensive user profile management")

        def mock_popen(args: list[str], **kwargs):
            captured_args.extend(args)
            mock_process = MagicMock()
            mock_process.stdout = StringIO("PRD generated")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_plans)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                result = runner.invoke(app, ["prd", "--file", "feature.txt"])

            assert "--print" in captured_args
            assert result.exit_code == 0
        finally:
            os.chdir(original_cwd)

    def test_prd_file_displays_non_interactive_header(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that ralph prd --file displays the non-interactive header."""
        original_cwd = os.getcwd()

        # Create feature description file
        feature_file = project_with_plans / "feature.txt"
        feature_file.write_text("Add export functionality")

        def mock_popen(args: list[str], **kwargs):
            mock_process = MagicMock()
            mock_process.stdout = StringIO("Done")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_plans)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                result = runner.invoke(app, ["prd", "--file", "feature.txt"])

            assert "Non-Interactive PRD Generation" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_file_reads_file_contents(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that ralph prd --file reads and uses file contents."""
        original_cwd = os.getcwd()
        captured_args: list[str] = []
        file_content = "Build a REST API for inventory management"

        # Create feature description file
        feature_file = project_with_plans / "feature.txt"
        feature_file.write_text(file_content)

        def mock_popen(args: list[str], **kwargs):
            captured_args.extend(args)
            mock_process = MagicMock()
            mock_process.stdout = StringIO("PRD written")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_plans)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                runner.invoke(app, ["prd", "--file", "feature.txt"])

            # Find the prompt argument
            print_index = captured_args.index("--print")
            prompt = captured_args[print_index + 1]

            # Verify file content is in the prompt
            assert file_content in prompt
        finally:
            os.chdir(original_cwd)

    def test_prd_file_error_when_file_not_exists(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that ralph prd --file shows error for non-existent file."""
        original_cwd = os.getcwd()

        try:
            os.chdir(project_with_plans)

            result = runner.invoke(app, ["prd", "--file", "nonexistent.txt"])

            assert result.exit_code == 1
            assert "File not found" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_file_error_when_file_empty(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that ralph prd --file shows error for empty file."""
        original_cwd = os.getcwd()

        # Create empty file
        empty_file = project_with_plans / "empty.txt"
        empty_file.write_text("")

        try:
            os.chdir(project_with_plans)

            result = runner.invoke(app, ["prd", "--file", "empty.txt"])

            assert result.exit_code == 1
            assert "File is empty" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_file_strips_whitespace(self, runner: CliRunner, project_with_plans: Path) -> None:
        """Test that ralph prd --file strips whitespace from file contents."""
        original_cwd = os.getcwd()
        captured_args: list[str] = []
        feature_content = "Create payment processing module"

        # Create file with leading/trailing whitespace
        feature_file = project_with_plans / "feature.txt"
        feature_file.write_text(f"\n\n  {feature_content}  \n\n")

        def mock_popen(args: list[str], **kwargs):
            captured_args.extend(args)
            mock_process = MagicMock()
            mock_process.stdout = StringIO("Done")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_plans)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                runner.invoke(app, ["prd", "--file", "feature.txt"])

            # Find the prompt argument
            print_index = captured_args.index("--print")
            prompt = captured_args[print_index + 1]

            # Feature content should be in prompt (stripped)
            assert feature_content in prompt
        finally:
            os.chdir(original_cwd)

    def test_prd_file_detects_file_modification(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that ralph prd --file detects when SPEC.md is created."""
        original_cwd = os.getcwd()

        # Create feature description file
        feature_file = project_with_plans / "feature.txt"
        feature_file.write_text("Add reporting dashboard")

        def mock_popen_creates_file(args: list[str], **kwargs):
            # Simulate Claude creating the SPEC.md file
            spec_file = project_with_plans / "plans" / "SPEC.md"
            spec_file.write_text("# Reporting Dashboard PRD\n\n## Overview\n...")

            mock_process = MagicMock()
            mock_process.stdout = StringIO("PRD created")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_plans)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen_creates_file),
            ):
                result = runner.invoke(app, ["prd", "--file", "feature.txt"])

            assert "PRD saved to" in result.output
            assert result.exit_code == 0
        finally:
            os.chdir(original_cwd)

    def test_prd_file_handles_claude_error(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that ralph prd --file handles Claude errors gracefully."""
        original_cwd = os.getcwd()

        # Create feature description file
        feature_file = project_with_plans / "feature.txt"
        feature_file.write_text("Some feature description")

        def mock_popen_error(args: list[str], **kwargs):
            raise FileNotFoundError("claude not found")

        try:
            os.chdir(project_with_plans)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen_error),
            ):
                result = runner.invoke(app, ["prd", "--file", "feature.txt"])

            assert result.exit_code == 1
            assert "Failed to run Claude" in result.output
        finally:
            os.chdir(original_cwd)


class TestPrdMutualExclusivityIntegration:
    """Integration tests for ralph prd --input and --file mutual exclusivity."""

    def test_prd_error_when_both_input_and_file_provided(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that ralph prd shows error when both --input and --file are provided."""
        original_cwd = os.getcwd()

        # Create a file for --file flag
        feature_file = project_with_plans / "feature.txt"
        feature_file.write_text("File content")

        try:
            os.chdir(project_with_plans)

            result = runner.invoke(app, ["prd", "--input", "Direct input", "--file", "feature.txt"])

            assert "Cannot use both --input and --file" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_mutual_exclusivity_exits_nonzero(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that mutual exclusivity error exits with code 1."""
        original_cwd = os.getcwd()

        # Create a file for --file flag
        feature_file = project_with_plans / "feature.txt"
        feature_file.write_text("File content")

        try:
            os.chdir(project_with_plans)

            result = runner.invoke(app, ["prd", "--input", "Input text", "--file", "feature.txt"])

            assert result.exit_code == 1
        finally:
            os.chdir(original_cwd)

    def test_prd_mutual_exclusivity_does_not_call_claude(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that Claude is never invoked when both flags are provided."""
        original_cwd = os.getcwd()
        claude_called = False

        # Create a file for --file flag
        feature_file = project_with_plans / "feature.txt"
        feature_file.write_text("File content")

        def mock_popen(args: list[str], **kwargs):
            nonlocal claude_called
            claude_called = True
            mock_process = MagicMock()
            mock_process.stdout = StringIO("")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_plans)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen),
            ):
                runner.invoke(app, ["prd", "--input", "Input", "--file", "feature.txt"])

            assert not claude_called, "Claude should not be invoked when both flags provided"
        finally:
            os.chdir(original_cwd)

    def test_prd_mutual_exclusivity_shows_guidance(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test that the mutual exclusivity error provides actionable guidance."""
        original_cwd = os.getcwd()

        # Create a file for --file flag
        feature_file = project_with_plans / "feature.txt"
        feature_file.write_text("File content")

        try:
            os.chdir(project_with_plans)

            result = runner.invoke(app, ["prd", "--input", "Input text", "--file", "feature.txt"])

            # Error message should guide the user
            assert "--input" in result.output.lower() or "input" in result.output.lower()
            assert "--file" in result.output.lower() or "file" in result.output.lower()
        finally:
            os.chdir(original_cwd)


class TestPrdAutomationCompleteWorkflow:
    """End-to-end workflow tests for PRD automation."""

    def test_prd_input_complete_workflow_creates_spec(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test complete workflow: --input flag creates SPEC.md."""
        original_cwd = os.getcwd()

        def mock_popen_creates_spec(args: list[str], **kwargs):
            # Simulate Claude creating a full SPEC.md
            spec_content = """# User Authentication PRD

## Overview
This document describes the requirements for adding user authentication.

## Goals
- Secure user authentication
- Session management

## Non-Goals
- OAuth integration (future phase)

## Requirements
- User registration
- User login
- Password reset

## Technical Considerations
- Use bcrypt for password hashing
- JWT for session tokens

## Success Criteria
- Users can register and login
- Sessions persist across page reloads
"""
            spec_file = project_with_plans / "plans" / "SPEC.md"
            spec_file.write_text(spec_content)

            mock_process = MagicMock()
            mock_process.stdout = StringIO("PRD created and saved to plans/SPEC.md")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_plans)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen_creates_spec),
            ):
                result = runner.invoke(
                    app, ["prd", "--input", "Add user authentication to the app"]
                )

            # Verify success
            assert result.exit_code == 0
            assert "PRD saved to" in result.output

            # Verify file was created
            spec_file = project_with_plans / "plans" / "SPEC.md"
            assert spec_file.exists()
            assert "User Authentication PRD" in spec_file.read_text()
        finally:
            os.chdir(original_cwd)

    def test_prd_file_complete_workflow_creates_spec(
        self, runner: CliRunner, project_with_plans: Path
    ) -> None:
        """Test complete workflow: --file flag creates SPEC.md from file."""
        original_cwd = os.getcwd()

        # Create detailed feature file
        feature_content = """Feature: Shopping Cart

Add a shopping cart feature that allows users to:
- Add products to cart
- Update quantities
- Remove items
- View cart total
- Proceed to checkout

The cart should persist between sessions and work across devices for logged-in users.
"""
        feature_file = project_with_plans / "shopping_cart_feature.md"
        feature_file.write_text(feature_content)

        def mock_popen_creates_spec(args: list[str], **kwargs):
            # Verify the feature content was passed to Claude
            prompt = args[args.index("--print") + 1] if "--print" in args else ""
            assert "Shopping Cart" in prompt

            spec_file = project_with_plans / "plans" / "SPEC.md"
            spec_file.write_text("# Shopping Cart PRD\n\n## Overview\n...")

            mock_process = MagicMock()
            mock_process.stdout = StringIO("PRD created")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_plans)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen_creates_spec),
            ):
                result = runner.invoke(app, ["prd", "--file", "shopping_cart_feature.md"])

            assert result.exit_code == 0
            assert "PRD saved to" in result.output
        finally:
            os.chdir(original_cwd)

    def test_prd_input_updates_existing_spec(
        self, runner: CliRunner, project_with_spec: Path
    ) -> None:
        """Test that --input can update an existing SPEC.md."""
        original_cwd = os.getcwd()

        def mock_popen_updates_spec(args: list[str], **kwargs):
            # Update the existing spec file
            spec_file = project_with_spec / "plans" / "SPEC.md"
            existing_content = spec_file.read_text()
            spec_file.write_text(existing_content + "\n\n## New Section\n\nAdded content.")

            mock_process = MagicMock()
            mock_process.stdout = StringIO("PRD updated")
            mock_process.stderr = StringIO("")
            mock_process.wait.return_value = 0
            return mock_process

        try:
            os.chdir(project_with_spec)

            with (
                patch("shutil.which", return_value="/usr/bin/claude"),
                patch("subprocess.Popen", side_effect=mock_popen_updates_spec),
            ):
                result = runner.invoke(
                    app, ["prd", "--input", "Add more requirements to the existing PRD"]
                )

            assert result.exit_code == 0
            assert "PRD saved to" in result.output

            # Verify file was updated
            spec_file = project_with_spec / "plans" / "SPEC.md"
            content = spec_file.read_text()
            assert "Existing PRD" in content  # Original content
            assert "New Section" in content  # Added content
        finally:
            os.chdir(original_cwd)
