"""Unit tests for SkillsService.

Focused tests for skills syncing functionality:
- Listing local skills
- Validating skill frontmatter
- Syncing skills to target directory
- Manifest handling during sync
- Removing skills
"""

import json
from pathlib import Path

from ralph.models.manifest import Manifest, save_manifest
from ralph.services.skills import SkillsService, SyncStatus


class TestSkillsServiceBasics:
    """Tests for SkillsService initialization and basic operations."""

    def test_default_target_dir(self, tmp_path: Path) -> None:
        """Test that default target_dir is ~/.claude/skills/."""
        service = SkillsService(skills_dir=tmp_path)
        assert service.target_dir == Path.home() / ".claude" / "skills"

    def test_list_skills_returns_directories_with_skill_md(self, tmp_path: Path) -> None:
        """Test that list_local_skills finds directories with SKILL.md."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create valid skill
        skill_dir = skills_dir / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---")

        # Create non-skill directory
        (skills_dir / "not-a-skill").mkdir()
        (skills_dir / "not-a-skill" / "README.md").write_text("# Not a skill")

        service = SkillsService(skills_dir=skills_dir)
        result = service.list_local_skills()

        assert len(result) == 1
        assert result[0].name == "my-skill"

    def test_list_skills_returns_empty_for_nonexistent_dir(self, tmp_path: Path) -> None:
        """Test that nonexistent skills dir returns empty list."""
        service = SkillsService(skills_dir=tmp_path / "nonexistent")
        result = service.list_local_skills()
        assert result == []


class TestSkillValidation:
    """Tests for skill validation."""

    def test_validate_valid_skill(self, tmp_path: Path) -> None:
        """Test that valid SKILL.md returns SkillInfo."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            '---\nname: "my-skill"\ndescription: "A great skill"\n---\n\n# My Skill'
        )

        service = SkillsService(skills_dir=tmp_path)
        result = service.validate_skill(skill_dir)

        assert result is not None
        assert result.name == "my-skill"
        assert result.description == "A great skill"

    def test_validate_returns_none_for_missing_frontmatter(self, tmp_path: Path) -> None:
        """Test that SKILL.md without frontmatter returns None."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# My Skill\n\nNo frontmatter here.")

        service = SkillsService(skills_dir=tmp_path)
        result = service.validate_skill(skill_dir)

        assert result is None

    def test_validate_returns_none_for_missing_name(self, tmp_path: Path) -> None:
        """Test that frontmatter without 'name' returns None."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text('---\ndescription: "A skill"\n---\n')

        service = SkillsService(skills_dir=tmp_path)
        result = service.validate_skill(skill_dir)

        assert result is None


class TestSkillSync:
    """Tests for skill syncing."""

    def test_sync_creates_new_skill(self, tmp_path: Path) -> None:
        """Test that new skill is created with CREATED status."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill_dir = skills_dir / "new-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            '---\nname: "new-skill"\ndescription: "A new skill"\n---\n'
        )

        target_dir = tmp_path / "target"
        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        result = service.sync_skill(skill_dir)

        assert result.status == SyncStatus.CREATED
        assert (target_dir / "new-skill" / "SKILL.md").exists()

    def test_sync_updates_existing_skill(self, tmp_path: Path) -> None:
        """Test that existing skill is updated with UPDATED status."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill_dir = skills_dir / "existing-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            '---\nname: "existing-skill"\ndescription: "Updated content"\n---\n'
        )

        # Create existing skill in target
        target_dir = tmp_path / "target"
        target_skill = target_dir / "existing-skill"
        target_skill.mkdir(parents=True)
        (target_skill / "SKILL.md").write_text("old content")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        result = service.sync_skill(skill_dir)

        assert result.status == SyncStatus.UPDATED
        new_content = (target_skill / "SKILL.md").read_text()
        assert "Updated content" in new_content

    def test_sync_returns_invalid_for_invalid_skill(self, tmp_path: Path) -> None:
        """Test that invalid skill returns INVALID status."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill_dir = skills_dir / "invalid-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# No frontmatter")

        target_dir = tmp_path / "target"
        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        result = service.sync_skill(skill_dir)

        assert result.status == SyncStatus.INVALID
        assert result.error is not None

    def test_sync_all_syncs_multiple_skills(self, tmp_path: Path) -> None:
        """Test that sync_all syncs all valid skills."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        for name in ["skill-a", "skill-b"]:
            skill_dir = skills_dir / name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                f'---\nname: "{name}"\ndescription: "Skill {name}"\n---\n'
            )

        target_dir = tmp_path / "target"
        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        results = service.sync_all()

        assert len(results) == 2
        assert all(r.status == SyncStatus.CREATED for r in results)
        assert (target_dir / "skill-a").exists()
        assert (target_dir / "skill-b").exists()


class TestManifestWriting:
    """Tests for manifest file writing during sync."""

    def test_sync_all_writes_manifest(self, tmp_path: Path) -> None:
        """Test that sync_all creates a .ralph-manifest.json file."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        skill_dir = skills_dir / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            '---\nname: "test-skill"\ndescription: "A test skill"\n---\n'
        )

        target_dir = tmp_path / "target"
        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        service.sync_all()

        manifest_path = target_dir / ".ralph-manifest.json"
        assert manifest_path.exists()

        manifest_data = json.loads(manifest_path.read_text())
        assert "installed" in manifest_data
        assert "test-skill" in manifest_data["installed"]
        assert "syncedAt" in manifest_data


class TestRemoveSkills:
    """Tests for remove_skills method."""

    def test_remove_returns_empty_when_no_manifest(self, tmp_path: Path) -> None:
        """Test that remove_skills returns empty list when no manifest exists."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        result = service.remove_skills()

        assert result == []

    def test_remove_deletes_skills_in_manifest(self, tmp_path: Path) -> None:
        """Test that remove_skills deletes skills listed in manifest."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Create skill directories in target
        (target_dir / "skill-a").mkdir()
        (target_dir / "skill-a" / "SKILL.md").write_text("content")
        (target_dir / "skill-b").mkdir()
        (target_dir / "skill-b" / "SKILL.md").write_text("content")

        # Create manifest
        manifest = Manifest(
            installed=["skill-a", "skill-b"],
            syncedAt="2026-01-01T00:00:00+00:00",
        )
        save_manifest(manifest, target_dir / ".ralph-manifest.json")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        result = service.remove_skills()

        assert set(result) == {"skill-a", "skill-b"}
        assert not (target_dir / "skill-a").exists()
        assert not (target_dir / "skill-b").exists()
        assert not (target_dir / ".ralph-manifest.json").exists()

    def test_remove_preserves_non_manifest_skills(self, tmp_path: Path) -> None:
        """Test that remove_skills never deletes skills not in manifest."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Create skills - one in manifest, one not
        (target_dir / "ralph-skill").mkdir()
        (target_dir / "ralph-skill" / "SKILL.md").write_text("content")
        (target_dir / "user-skill").mkdir()
        (target_dir / "user-skill" / "SKILL.md").write_text("user content")

        # Manifest only lists ralph-skill
        manifest = Manifest(
            installed=["ralph-skill"],
            syncedAt="2026-01-01T00:00:00+00:00",
        )
        save_manifest(manifest, target_dir / ".ralph-manifest.json")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        service.remove_skills()

        # User skill should still exist
        assert (target_dir / "user-skill").exists()
