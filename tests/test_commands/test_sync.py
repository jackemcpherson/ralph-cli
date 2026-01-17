"""Tests for ralph sync command."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ralph.cli import app


@pytest.fixture
def skills_dir(python_project: Path) -> Path:
    """Create a skills directory in the temporary project.

    Args:
        python_project: Temporary Python project directory.

    Returns:
        Path to the skills directory.
    """
    skills_path = python_project / "skills"
    skills_path.mkdir()
    return skills_path


@pytest.fixture
def valid_skill(skills_dir: Path) -> Path:
    """Create a valid skill with frontmatter.

    Args:
        skills_dir: Skills directory.

    Returns:
        Path to the skill directory.
    """
    skill_path = skills_dir / "test-skill"
    skill_path.mkdir()
    (skill_path / "SKILL.md").write_text(
        '---\nname: "test-skill"\ndescription: "A test skill"\n---\n\n# Test Skill\n'
    )
    return skill_path


@pytest.fixture
def invalid_skill(skills_dir: Path) -> Path:
    """Create a skill with missing frontmatter.

    Args:
        skills_dir: Skills directory.

    Returns:
        Path to the skill directory.
    """
    skill_path = skills_dir / "invalid-skill"
    skill_path.mkdir()
    (skill_path / "SKILL.md").write_text("# Invalid Skill\n\nNo frontmatter here.\n")
    return skill_path


@pytest.fixture
def mock_target_dir(tmp_path: Path) -> Path:
    """Create a mock target directory for skills.

    Args:
        tmp_path: pytest's built-in tmp_path fixture.

    Returns:
        Path to the mock target directory.
    """
    target = tmp_path / ".claude" / "skills"
    target.mkdir(parents=True)
    return target


class TestSyncCommand:
    """Tests for the sync command."""

    def test_sync_shows_warning_when_no_skills_dir(
        self, runner: CliRunner, python_project: Path
    ) -> None:
        """Test that sync shows helpful message when skills/ doesn't exist."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            result = runner.invoke(app, ["sync"])

            assert result.exit_code == 0
            assert "Skills directory not found" in result.output
            assert "SKILL.md" in result.output
        finally:
            os.chdir(original_cwd)

    def test_sync_shows_warning_when_no_skills_found(
        self, runner: CliRunner, python_project: Path, skills_dir: Path
    ) -> None:
        """Test that sync shows message when skills/ exists but is empty."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            result = runner.invoke(app, ["sync"])

            assert result.exit_code == 0
            assert "No skills found" in result.output
        finally:
            os.chdir(original_cwd)

    def test_sync_syncs_valid_skill(
        self,
        runner: CliRunner,
        python_project: Path,
        valid_skill: Path,
        mock_target_dir: Path,
    ) -> None:
        """Test that sync copies valid skills to target directory."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            # Mock the target directory in SkillsService
            with patch("ralph.commands.sync.SkillsService") as mock_service_cls:
                mock_service = mock_service_cls.return_value
                mock_service.list_local_skills.return_value = [valid_skill]
                mock_service.target_dir = mock_target_dir

                # Create a mock result
                from ralph.services import SkillSyncResult, SyncStatus

                mock_result = SkillSyncResult(
                    skill_name="test-skill",
                    status=SyncStatus.CREATED,
                    source_path=valid_skill,
                    target_path=mock_target_dir / "test-skill",
                )
                mock_service.sync_all.return_value = [mock_result]

                result = runner.invoke(app, ["sync"])

            assert result.exit_code == 0
            assert "test-skill" in result.output
            assert "created" in result.output
            assert "Synced 1 skill" in result.output
        finally:
            os.chdir(original_cwd)

    def test_sync_shows_updated_status(
        self,
        runner: CliRunner,
        python_project: Path,
        valid_skill: Path,
        mock_target_dir: Path,
    ) -> None:
        """Test that sync shows 'updated' for existing skills."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with patch("ralph.commands.sync.SkillsService") as mock_service_cls:
                mock_service = mock_service_cls.return_value
                mock_service.list_local_skills.return_value = [valid_skill]
                mock_service.target_dir = mock_target_dir

                from ralph.services import SkillSyncResult, SyncStatus

                mock_result = SkillSyncResult(
                    skill_name="test-skill",
                    status=SyncStatus.UPDATED,
                    source_path=valid_skill,
                    target_path=mock_target_dir / "test-skill",
                )
                mock_service.sync_all.return_value = [mock_result]

                result = runner.invoke(app, ["sync"])

            assert result.exit_code == 0
            assert "updated" in result.output
        finally:
            os.chdir(original_cwd)

    def test_sync_shows_invalid_skill_warning(
        self,
        runner: CliRunner,
        python_project: Path,
        invalid_skill: Path,
        mock_target_dir: Path,
    ) -> None:
        """Test that sync shows warning for invalid skills."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with patch("ralph.commands.sync.SkillsService") as mock_service_cls:
                mock_service = mock_service_cls.return_value
                mock_service.list_local_skills.return_value = [invalid_skill]
                mock_service.target_dir = mock_target_dir

                from ralph.services import SkillSyncResult, SyncStatus

                mock_result = SkillSyncResult(
                    skill_name="invalid-skill",
                    status=SyncStatus.INVALID,
                    source_path=invalid_skill,
                    error="Missing frontmatter",
                )
                mock_service.sync_all.return_value = [mock_result]

                result = runner.invoke(app, ["sync"])

            assert result.exit_code == 0
            assert "invalid" in result.output.lower()
            assert "Skipped 1 invalid skill" in result.output
        finally:
            os.chdir(original_cwd)

    def test_sync_with_custom_skills_dir(
        self, runner: CliRunner, tmp_path: Path, mock_target_dir: Path
    ) -> None:
        """Test that sync --skills-dir uses custom directory."""
        custom_skills_dir = tmp_path / "my-skills"
        custom_skills_dir.mkdir()

        skill_path = custom_skills_dir / "my-skill"
        skill_path.mkdir()
        (skill_path / "SKILL.md").write_text(
            '---\nname: "my-skill"\ndescription: "My skill"\n---\n'
        )

        with patch("ralph.commands.sync.SkillsService") as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.list_local_skills.return_value = [skill_path]
            mock_service.target_dir = mock_target_dir

            from ralph.services import SkillSyncResult, SyncStatus

            mock_result = SkillSyncResult(
                skill_name="my-skill",
                status=SyncStatus.CREATED,
                source_path=skill_path,
                target_path=mock_target_dir / "my-skill",
            )
            mock_service.sync_all.return_value = [mock_result]

            result = runner.invoke(app, ["sync", "--skills-dir", str(custom_skills_dir)])

        assert result.exit_code == 0
        # Verify SkillsService was initialized with custom path
        mock_service_cls.assert_called_once()
        call_kwargs = mock_service_cls.call_args[1]
        assert call_kwargs["skills_dir"] == custom_skills_dir

    def test_sync_fails_on_error(
        self,
        runner: CliRunner,
        python_project: Path,
        valid_skill: Path,
        mock_target_dir: Path,
    ) -> None:
        """Test that sync fails with non-zero exit on sync error."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with patch("ralph.commands.sync.SkillsService") as mock_service_cls:
                mock_service = mock_service_cls.return_value
                mock_service.list_local_skills.return_value = [valid_skill]
                mock_service.target_dir = mock_target_dir

                from ralph.services import SkillSyncResult, SyncStatus

                mock_result = SkillSyncResult(
                    skill_name="test-skill",
                    status=SyncStatus.SKIPPED,
                    source_path=valid_skill,
                    error="Permission denied",
                )
                mock_service.sync_all.return_value = [mock_result]

                result = runner.invoke(app, ["sync"])

            assert result.exit_code == 1
            assert "Failed to sync" in result.output
        finally:
            os.chdir(original_cwd)

    def test_sync_displays_source_and_target(
        self,
        runner: CliRunner,
        python_project: Path,
        valid_skill: Path,
        mock_target_dir: Path,
    ) -> None:
        """Test that sync displays source and target directories."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with patch("ralph.commands.sync.SkillsService") as mock_service_cls:
                mock_service = mock_service_cls.return_value
                mock_service.list_local_skills.return_value = [valid_skill]
                mock_service.target_dir = mock_target_dir

                from ralph.services import SkillSyncResult, SyncStatus

                mock_result = SkillSyncResult(
                    skill_name="test-skill",
                    status=SyncStatus.CREATED,
                    source_path=valid_skill,
                    target_path=mock_target_dir / "test-skill",
                )
                mock_service.sync_all.return_value = [mock_result]

                result = runner.invoke(app, ["sync"])

            assert result.exit_code == 0
            assert "Syncing skills from" in result.output
            assert "Target directory" in result.output
        finally:
            os.chdir(original_cwd)

    def test_sync_multiple_skills(
        self,
        runner: CliRunner,
        python_project: Path,
        skills_dir: Path,
        mock_target_dir: Path,
    ) -> None:
        """Test that sync handles multiple skills correctly."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            # Create multiple skills
            skill1 = skills_dir / "skill-one"
            skill1.mkdir()
            (skill1 / "SKILL.md").write_text(
                '---\nname: "skill-one"\ndescription: "First skill"\n---\n'
            )

            skill2 = skills_dir / "skill-two"
            skill2.mkdir()
            (skill2 / "SKILL.md").write_text(
                '---\nname: "skill-two"\ndescription: "Second skill"\n---\n'
            )

            with patch("ralph.commands.sync.SkillsService") as mock_service_cls:
                mock_service = mock_service_cls.return_value
                mock_service.list_local_skills.return_value = [skill1, skill2]
                mock_service.target_dir = mock_target_dir

                from ralph.services import SkillSyncResult, SyncStatus

                mock_results = [
                    SkillSyncResult(
                        skill_name="skill-one",
                        status=SyncStatus.CREATED,
                        source_path=skill1,
                        target_path=mock_target_dir / "skill-one",
                    ),
                    SkillSyncResult(
                        skill_name="skill-two",
                        status=SyncStatus.UPDATED,
                        source_path=skill2,
                        target_path=mock_target_dir / "skill-two",
                    ),
                ]
                mock_service.sync_all.return_value = mock_results

                result = runner.invoke(app, ["sync"])

            assert result.exit_code == 0
            assert "skill-one" in result.output
            assert "skill-two" in result.output
            assert "Synced 2 skill" in result.output
            assert "Created: 1" in result.output
            assert "Updated: 1" in result.output
        finally:
            os.chdir(original_cwd)

    def test_sync_shows_no_skills_synced_when_all_invalid(
        self,
        runner: CliRunner,
        python_project: Path,
        invalid_skill: Path,
        mock_target_dir: Path,
    ) -> None:
        """Test that sync shows message when no valid skills exist."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            with patch("ralph.commands.sync.SkillsService") as mock_service_cls:
                mock_service = mock_service_cls.return_value
                mock_service.list_local_skills.return_value = [invalid_skill]
                mock_service.target_dir = mock_target_dir

                from ralph.services import SkillSyncResult, SyncStatus

                mock_result = SkillSyncResult(
                    skill_name="invalid-skill",
                    status=SyncStatus.INVALID,
                    source_path=invalid_skill,
                    error="Missing frontmatter",
                )
                mock_service.sync_all.return_value = [mock_result]

                result = runner.invoke(app, ["sync"])

            assert result.exit_code == 0
            assert "No skills were synced" in result.output
        finally:
            os.chdir(original_cwd)


class TestSyncIntegration:
    """Integration tests for sync command without mocking SkillsService."""

    def test_sync_actually_copies_skill(
        self, runner: CliRunner, python_project: Path, valid_skill: Path, tmp_path: Path
    ) -> None:
        """Test that sync actually copies skill files to target directory."""
        original_cwd = os.getcwd()
        try:
            os.chdir(python_project)

            # Create a custom target directory for testing
            target_dir = tmp_path / "target_skills"

            # Actually run the sync using the real service with custom target_dir
            from ralph.services import SkillsService

            service = SkillsService(
                skills_dir=python_project / "skills",
                target_dir=target_dir,
            )

            results = service.sync_all()

            assert len(results) == 1
            assert results[0].status.value == "created"

            # Verify files were actually copied
            copied_skill = target_dir / "test-skill"
            assert copied_skill.exists()
            assert (copied_skill / "SKILL.md").exists()
        finally:
            os.chdir(original_cwd)
