"""Tests for SkillsService."""

import json
from pathlib import Path

from ralph.models.manifest import MANIFEST_VERSION, Manifest, save_manifest
from ralph.services.skills import SkillsService, SyncStatus


class TestSkillsServiceBasics:
    """Tests for SkillsService basic operations."""

    def test_list_skills_finds_valid_skills(self, tmp_path: Path) -> None:
        """Test list_local_skills finds directories with valid SKILL.md."""
        skills_dir = tmp_path / "skills"
        _create_skill(skills_dir / "valid-skill", "valid-skill")
        (skills_dir / "not-a-skill").mkdir(parents=True)
        (skills_dir / "not-a-skill" / "README.md").write_text("# Not a skill")

        service = SkillsService(skills_dir=skills_dir)
        result = service.list_local_skills()

        assert len(result) == 1
        assert result[0].name == "valid-skill"

    def test_list_skills_finds_nested_skills(self, tmp_path: Path) -> None:
        """Test list_local_skills finds nested skills like ralph/prd."""
        skills_dir = tmp_path / "skills"
        _create_skill(skills_dir / "flat-skill", "flat-skill")
        _create_skill(skills_dir / "ralph" / "prd", "ralph-prd")
        _create_skill(skills_dir / "reviewers" / "language" / "python", "python-reviewer")

        service = SkillsService(skills_dir=skills_dir)
        result = service.list_local_skills()

        assert len(result) == 3


class TestSkillSync:
    """Tests for skill syncing."""

    def test_sync_creates_and_updates_skills(self, tmp_path: Path) -> None:
        """Test sync creates new skills and updates existing ones."""
        skills_dir = tmp_path / "skills"
        target_dir = tmp_path / "target"
        _create_skill(skills_dir / "new-skill", "new-skill")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        result = service.sync_skill(skills_dir / "new-skill")
        assert result.status == SyncStatus.CREATED
        assert result.skill_name == "new-skill"
        assert (target_dir / "new-skill" / "SKILL.md").exists()

        result = service.sync_skill(skills_dir / "new-skill")
        assert result.status == SyncStatus.UPDATED

    def test_sync_creates_flat_dirs_from_nested_source(self, tmp_path: Path) -> None:
        """Test sync creates flat skill directories using names from frontmatter."""
        skills_dir = tmp_path / "skills"
        target_dir = tmp_path / "target"
        _create_skill(skills_dir / "ralph" / "prd", "ralph-prd")
        _create_skill(skills_dir / "reviewers" / "language" / "python", "python-reviewer")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)
        results = service.sync_all()

        assert len(results) == 2
        assert all(r.status == SyncStatus.CREATED for r in results)
        # Skills are saved as flat directories with names from frontmatter
        assert (target_dir / "ralph-prd" / "SKILL.md").exists()
        assert (target_dir / "python-reviewer" / "SKILL.md").exists()
        # No nested source structure in target
        assert not (target_dir / "ralph" / "prd").exists()
        assert not (target_dir / "reviewers").exists()

    def test_sync_returns_invalid_for_missing_frontmatter(self, tmp_path: Path) -> None:
        """Test sync returns INVALID for skills without frontmatter."""
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "invalid"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# No frontmatter")

        service = SkillsService(skills_dir=skills_dir, target_dir=tmp_path / "target")
        result = service.sync_skill(skill_dir)

        assert result.status == SyncStatus.INVALID

    def test_sync_preserves_full_content(self, tmp_path: Path) -> None:
        """Test sync preserves the full SKILL.md content including body."""
        skills_dir = tmp_path / "skills"
        target_dir = tmp_path / "target"
        skill_dir = skills_dir / "test-skill"
        skill_dir.mkdir(parents=True)

        full_content = """---
name: "test-skill"
description: "A test skill"
---

# Test Skill

This is the skill body with instructions.

## Section 1

Some content here.
"""
        (skill_dir / "SKILL.md").write_text(full_content)

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)
        result = service.sync_skill(skill_dir)

        assert result.status == SyncStatus.CREATED
        synced_content = (target_dir / "test-skill" / "SKILL.md").read_text()
        assert synced_content == full_content


class TestManifest:
    """Tests for manifest handling."""

    def test_sync_writes_v3_manifest(self, tmp_path: Path) -> None:
        """Test sync creates v3 manifest with skill names from frontmatter."""
        skills_dir = tmp_path / "skills"
        target_dir = tmp_path / "target"
        _create_skill(skills_dir / "ralph" / "prd", "ralph-prd")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)
        service.sync_all()

        manifest_data = json.loads((target_dir / ".ralph-manifest.json").read_text())
        assert manifest_data["version"] == MANIFEST_VERSION
        # Manifest stores skill names from frontmatter, not paths
        assert "ralph-prd" in manifest_data["installed"]


class TestUpgradeFromV2:
    """Tests for upgrading from v2 nested structure."""

    def test_sync_cleans_up_v2_nested_directories(self, tmp_path: Path) -> None:
        """Test sync cleans up old v2 nested directories before creating v3 flat dirs."""
        skills_dir = tmp_path / "skills"
        target_dir = tmp_path / "target"

        # Create old v2 nested structure
        (target_dir / "ralph" / "prd").mkdir(parents=True)
        (target_dir / "ralph" / "prd" / "SKILL.md").write_text("old content")

        # Create v2 manifest
        old_manifest = Manifest(
            version=2, installed=["ralph/prd"], syncedAt="2026-01-01T00:00:00+00:00"
        )
        save_manifest(old_manifest, target_dir / ".ralph-manifest.json")

        # Create source skill with same name
        _create_skill(skills_dir / "ralph" / "prd", "ralph-prd")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)
        results = service.sync_all()

        # Old nested structure should be cleaned up
        assert not (target_dir / "ralph" / "prd").exists()
        # New flat directory should exist
        assert (target_dir / "ralph-prd" / "SKILL.md").exists()
        assert len(results) == 1
        assert results[0].status == SyncStatus.CREATED


class TestRemoveSkills:
    """Tests for skill removal."""

    def test_remove_deletes_v3_skill_directories(self, tmp_path: Path) -> None:
        """Test remove_skills deletes v3 skill directories."""
        skills_dir = tmp_path / "skills"
        target_dir = tmp_path / "target"

        (target_dir / "ralph-prd").mkdir(parents=True)
        (target_dir / "ralph-prd" / "SKILL.md").write_text("content")
        (target_dir / "code-simplifier").mkdir(parents=True)
        (target_dir / "code-simplifier" / "SKILL.md").write_text("content")

        manifest = Manifest(
            version=3,
            installed=["ralph-prd", "code-simplifier"],
            syncedAt="2026-01-01T00:00:00+00:00",
        )
        save_manifest(manifest, target_dir / ".ralph-manifest.json")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)
        result = service.remove_skills()

        assert sorted(result) == ["code-simplifier", "ralph-prd"]
        assert not (target_dir / "ralph-prd").exists()
        assert not (target_dir / "code-simplifier").exists()
        assert not (target_dir / ".ralph-manifest.json").exists()

    def test_remove_deletes_v2_nested_directories(self, tmp_path: Path) -> None:
        """Test remove_skills deletes v2 nested directories and cleans empty parents."""
        skills_dir = tmp_path / "skills"
        target_dir = tmp_path / "target"

        (target_dir / "ralph" / "prd").mkdir(parents=True)
        (target_dir / "ralph" / "prd" / "SKILL.md").write_text("content")

        manifest = Manifest(
            version=2, installed=["ralph/prd"], syncedAt="2026-01-01T00:00:00+00:00"
        )
        save_manifest(manifest, target_dir / ".ralph-manifest.json")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)
        result = service.remove_skills()

        assert result == ["ralph/prd"]
        assert not (target_dir / "ralph").exists()
        assert not (target_dir / ".ralph-manifest.json").exists()

    def test_remove_preserves_non_manifest_skills(self, tmp_path: Path) -> None:
        """Test remove_skills preserves skills not in manifest."""
        skills_dir = tmp_path / "skills"
        target_dir = tmp_path / "target"

        (target_dir / "ralph-managed").mkdir(parents=True)
        (target_dir / "ralph-managed" / "SKILL.md").write_text("content")
        (target_dir / "user-created").mkdir(parents=True)
        (target_dir / "user-created" / "SKILL.md").write_text("user content")

        manifest = Manifest(
            version=3, installed=["ralph-managed"], syncedAt="2026-01-01T00:00:00+00:00"
        )
        save_manifest(manifest, target_dir / ".ralph-manifest.json")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)
        service.remove_skills()

        assert not (target_dir / "ralph-managed").exists()
        assert (target_dir / "user-created").exists()


def _create_skill(skill_dir: Path, name: str) -> None:
    """Create a skill directory with valid frontmatter."""
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f'---\nname: "{name}"\ndescription: "Skill {name}"\n---\n')
