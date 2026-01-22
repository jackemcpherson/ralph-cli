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
        assert (target_dir / "new-skill" / "SKILL.md").exists()

        result = service.sync_skill(skills_dir / "new-skill")
        assert result.status == SyncStatus.UPDATED

    def test_sync_preserves_nested_structure(self, tmp_path: Path) -> None:
        """Test sync preserves nested directory structure."""
        skills_dir = tmp_path / "skills"
        target_dir = tmp_path / "target"
        _create_skill(skills_dir / "ralph" / "prd", "ralph-prd")
        _create_skill(skills_dir / "reviewers" / "language" / "python", "python-reviewer")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)
        results = service.sync_all()

        assert len(results) == 2
        assert all(r.status == SyncStatus.CREATED for r in results)
        assert (target_dir / "ralph" / "prd" / "SKILL.md").exists()
        assert (target_dir / "reviewers" / "language" / "python" / "SKILL.md").exists()

    def test_sync_returns_invalid_for_missing_frontmatter(self, tmp_path: Path) -> None:
        """Test sync returns INVALID for skills without frontmatter."""
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "invalid"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# No frontmatter")

        service = SkillsService(skills_dir=skills_dir, target_dir=tmp_path / "target")
        result = service.sync_skill(skill_dir)

        assert result.status == SyncStatus.INVALID


class TestManifest:
    """Tests for manifest handling."""

    def test_sync_writes_v2_manifest(self, tmp_path: Path) -> None:
        """Test sync creates v2 manifest with full paths."""
        skills_dir = tmp_path / "skills"
        target_dir = tmp_path / "target"
        _create_skill(skills_dir / "ralph" / "prd", "ralph-prd")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)
        service.sync_all()

        manifest_data = json.loads((target_dir / ".ralph-manifest.json").read_text())
        assert manifest_data["version"] == MANIFEST_VERSION
        assert "ralph/prd" in manifest_data["installed"]


class TestRemoveSkills:
    """Tests for skill removal."""

    def test_remove_deletes_skills_and_cleans_empty_parents(self, tmp_path: Path) -> None:
        """Test remove_skills deletes skills and cleans up empty parent directories."""
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

        manifest = Manifest(installed=["ralph-managed"], syncedAt="2026-01-01T00:00:00+00:00")
        save_manifest(manifest, target_dir / ".ralph-manifest.json")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)
        service.remove_skills()

        assert not (target_dir / "ralph-managed").exists()
        assert (target_dir / "user-created").exists()


def _create_skill(skill_dir: Path, name: str) -> None:
    """Create a skill directory with valid frontmatter."""
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f'---\nname: "{name}"\ndescription: "Skill {name}"\n---\n')
