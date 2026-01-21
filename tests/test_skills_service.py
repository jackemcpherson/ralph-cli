"""Unit tests for SkillsService.

Focused tests for skills syncing functionality:
- Listing local skills
- Validating skill frontmatter
- Syncing skills to target directory
- Manifest handling during sync
- Removing skills
- Nested directory structure support
"""

import json
from pathlib import Path

from ralph.models.manifest import MANIFEST_VERSION, Manifest, save_manifest
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


def create_skill(skill_dir: Path, name: str, description: str | None = None) -> None:
    """Create a skill directory with valid SKILL.md frontmatter.

    Args:
        skill_dir: Directory where the skill should be created.
        name: Name of the skill for the frontmatter.
        description: Optional description. Defaults to "Skill {name}".
    """
    skill_dir.mkdir(exist_ok=True)
    desc = description or f"Skill {name}"
    (skill_dir / "SKILL.md").write_text(f'---\nname: "{name}"\ndescription: "{desc}"\n---\n')


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
            create_skill(skills_dir / name, name)

        target_dir = tmp_path / "target"
        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        results = service.sync_all()

        assert len(results) == 2
        assert all(r.status == SyncStatus.CREATED for r in results)
        assert (target_dir / "skill-a").exists()
        assert (target_dir / "skill-b").exists()

    def test_sync_overwrites_modified_target_file(self, tmp_path: Path) -> None:
        """Test that sync overwrites target file even if modified locally."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill_dir = skills_dir / "my-skill"
        skill_dir.mkdir()
        source_content = '---\nname: "my-skill"\ndescription: "Source version"\n---\n'
        (skill_dir / "SKILL.md").write_text(source_content)

        # Create existing skill in target with different content
        target_dir = tmp_path / "target"
        target_skill = target_dir / "my-skill"
        target_skill.mkdir(parents=True)
        (target_skill / "SKILL.md").write_text("Modified locally by user")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        result = service.sync_skill(skill_dir)

        assert result.status == SyncStatus.UPDATED
        synced_content = (target_skill / "SKILL.md").read_text()
        assert synced_content == source_content
        assert "Modified locally" not in synced_content


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


class TestNestedSkillsListing:
    """Tests for listing nested skill directories."""

    def test_list_finds_two_level_nested_skills(self, tmp_path: Path) -> None:
        """Test that list_local_skills finds skills in nested directories like ralph/prd."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create nested skill at ralph/prd
        nested_skill = skills_dir / "ralph" / "prd"
        nested_skill.mkdir(parents=True)
        (nested_skill / "SKILL.md").write_text(
            '---\nname: "ralph-prd"\ndescription: "PRD skill"\n---\n'
        )

        service = SkillsService(skills_dir=skills_dir)
        result = service.list_local_skills()

        assert len(result) == 1
        assert result[0] == nested_skill

    def test_list_finds_three_level_nested_skills(self, tmp_path: Path) -> None:
        """Test that list_local_skills finds deeply nested skills like reviewers/language/python."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create deeply nested skill
        deep_skill = skills_dir / "reviewers" / "language" / "python"
        deep_skill.mkdir(parents=True)
        (deep_skill / "SKILL.md").write_text(
            '---\nname: "python-reviewer"\ndescription: "Python code reviewer"\n---\n'
        )

        service = SkillsService(skills_dir=skills_dir)
        result = service.list_local_skills()

        assert len(result) == 1
        assert result[0] == deep_skill

    def test_list_finds_mixed_flat_and_nested_skills(self, tmp_path: Path) -> None:
        """Test that both flat and nested skills are found."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create flat skill
        flat_skill = skills_dir / "flat-skill"
        flat_skill.mkdir()
        (flat_skill / "SKILL.md").write_text(
            '---\nname: "flat-skill"\ndescription: "A flat skill"\n---\n'
        )

        # Create nested skill
        nested_skill = skills_dir / "ralph" / "prd"
        nested_skill.mkdir(parents=True)
        (nested_skill / "SKILL.md").write_text(
            '---\nname: "ralph-prd"\ndescription: "PRD skill"\n---\n'
        )

        service = SkillsService(skills_dir=skills_dir)
        result = service.list_local_skills()

        assert len(result) == 2
        result_names = {p.name for p in result}
        assert result_names == {"flat-skill", "prd"}


class TestNestedSkillSync:
    """Tests for syncing nested skill directories."""

    def test_sync_creates_nested_target_structure(self, tmp_path: Path) -> None:
        """Test that sync preserves nested directory structure in target."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create nested skill at ralph/prd
        nested_skill = skills_dir / "ralph" / "prd"
        nested_skill.mkdir(parents=True)
        (nested_skill / "SKILL.md").write_text(
            '---\nname: "ralph-prd"\ndescription: "PRD skill"\n---\n'
        )

        target_dir = tmp_path / "target"
        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        result = service.sync_skill(nested_skill)

        assert result.status == SyncStatus.CREATED
        assert result.skill_name == "ralph/prd"
        assert (target_dir / "ralph" / "prd" / "SKILL.md").exists()

    def test_sync_all_mirrors_nested_structure(self, tmp_path: Path) -> None:
        """Test that sync_all preserves nested structure for all skills."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create multiple nested skills
        for path in ["ralph/prd", "ralph/tasks", "reviewers/language/python"]:
            skill_dir = skills_dir / path
            skill_dir.mkdir(parents=True)
            name = path.replace("/", "-")
            (skill_dir / "SKILL.md").write_text(
                f'---\nname: "{name}"\ndescription: "Skill {name}"\n---\n'
            )

        target_dir = tmp_path / "target"
        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        results = service.sync_all()

        assert len(results) == 3
        assert all(r.status == SyncStatus.CREATED for r in results)
        assert (target_dir / "ralph" / "prd" / "SKILL.md").exists()
        assert (target_dir / "ralph" / "tasks" / "SKILL.md").exists()
        assert (target_dir / "reviewers" / "language" / "python" / "SKILL.md").exists()

    def test_sync_updates_existing_nested_skill(self, tmp_path: Path) -> None:
        """Test that existing nested skill is updated correctly."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create nested skill
        nested_skill = skills_dir / "ralph" / "prd"
        nested_skill.mkdir(parents=True)
        (nested_skill / "SKILL.md").write_text(
            '---\nname: "ralph-prd"\ndescription: "Updated description"\n---\n'
        )

        # Create existing skill in target
        target_dir = tmp_path / "target"
        target_skill = target_dir / "ralph" / "prd"
        target_skill.mkdir(parents=True)
        (target_skill / "SKILL.md").write_text("old content")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        result = service.sync_skill(nested_skill)

        assert result.status == SyncStatus.UPDATED
        new_content = (target_skill / "SKILL.md").read_text()
        assert "Updated description" in new_content


class TestManifestVersion2:
    """Tests for version 2 manifest with nested paths."""

    def test_manifest_includes_version_2(self, tmp_path: Path) -> None:
        """Test that manifest file has version 2."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        skill_dir = skills_dir / "ralph" / "prd"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            '---\nname: "ralph-prd"\ndescription: "PRD skill"\n---\n'
        )

        target_dir = tmp_path / "target"
        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        service.sync_all()

        manifest_path = target_dir / ".ralph-manifest.json"
        manifest_data = json.loads(manifest_path.read_text())

        assert manifest_data.get("version") == MANIFEST_VERSION
        assert MANIFEST_VERSION == 2

    def test_manifest_stores_full_nested_paths(self, tmp_path: Path) -> None:
        """Test that manifest stores full paths like ralph/prd."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create nested skills
        for path in ["ralph/prd", "reviewers/code-simplifier"]:
            skill_dir = skills_dir / path
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f'---\nname: "{path}"\ndescription: "Skill"\n---\n')

        target_dir = tmp_path / "target"
        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        service.sync_all()

        manifest_path = target_dir / ".ralph-manifest.json"
        manifest_data = json.loads(manifest_path.read_text())

        assert "ralph/prd" in manifest_data["installed"]
        assert "reviewers/code-simplifier" in manifest_data["installed"]


class TestOldFlatSkillCleanup:
    """Tests for cleaning up old flat-structure skills during sync."""

    def test_sync_cleans_up_old_flat_skills_from_v1_manifest(self, tmp_path: Path) -> None:
        """Test that old flat-structure skills are removed when upgrading from v1."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create new nested skill
        nested_skill = skills_dir / "ralph" / "prd"
        nested_skill.mkdir(parents=True)
        (nested_skill / "SKILL.md").write_text(
            '---\nname: "ralph-prd"\ndescription: "PRD skill"\n---\n'
        )

        # Create target with old flat-structure skills and v1 manifest
        target_dir = tmp_path / "target"
        old_skill = target_dir / "ralph-prd"
        old_skill.mkdir(parents=True)
        (old_skill / "SKILL.md").write_text("old content")

        # Create v1 manifest (no version field defaults to 1)
        manifest = Manifest(
            installed=["ralph-prd", "ralph-tasks"],
            syncedAt="2026-01-01T00:00:00+00:00",
        )
        save_manifest(manifest, target_dir / ".ralph-manifest.json")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        service.sync_all()

        # Old flat skill should be removed
        assert not (target_dir / "ralph-prd").exists()
        # New nested skill should exist
        assert (target_dir / "ralph" / "prd" / "SKILL.md").exists()

    def test_sync_preserves_skills_when_manifest_is_v2(self, tmp_path: Path) -> None:
        """Test that skills are not cleaned up when manifest is already v2."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create nested skill
        nested_skill = skills_dir / "ralph" / "prd"
        nested_skill.mkdir(parents=True)
        (nested_skill / "SKILL.md").write_text(
            '---\nname: "ralph-prd"\ndescription: "PRD skill"\n---\n'
        )

        # Create target with v2 manifest
        target_dir = tmp_path / "target"
        existing_skill = target_dir / "ralph" / "prd"
        existing_skill.mkdir(parents=True)
        (existing_skill / "SKILL.md").write_text("existing content")

        # Create v2 manifest
        manifest = Manifest(
            version=2,
            installed=["ralph/prd"],
            syncedAt="2026-01-01T00:00:00+00:00",
        )
        save_manifest(manifest, target_dir / ".ralph-manifest.json")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        service.sync_all()

        # Nested skill should still exist (updated)
        assert (target_dir / "ralph" / "prd" / "SKILL.md").exists()


class TestRemoveNestedSkills:
    """Tests for removing nested skill directories."""

    def test_remove_deletes_nested_skills(self, tmp_path: Path) -> None:
        """Test that nested skills are removed correctly."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Create nested skills in target
        (target_dir / "ralph" / "prd").mkdir(parents=True)
        (target_dir / "ralph" / "prd" / "SKILL.md").write_text("content")
        (target_dir / "reviewers" / "code-simplifier").mkdir(parents=True)
        (target_dir / "reviewers" / "code-simplifier" / "SKILL.md").write_text("content")

        # Create v2 manifest
        manifest = Manifest(
            version=2,
            installed=["ralph/prd", "reviewers/code-simplifier"],
            syncedAt="2026-01-01T00:00:00+00:00",
        )
        save_manifest(manifest, target_dir / ".ralph-manifest.json")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        result = service.remove_skills()

        assert set(result) == {"ralph/prd", "reviewers/code-simplifier"}
        assert not (target_dir / "ralph" / "prd").exists()
        assert not (target_dir / "reviewers" / "code-simplifier").exists()

    def test_remove_cleans_up_empty_parent_directories(self, tmp_path: Path) -> None:
        """Test that empty parent directories are removed after skill removal."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Create nested skill - the only one under ralph/
        (target_dir / "ralph" / "prd").mkdir(parents=True)
        (target_dir / "ralph" / "prd" / "SKILL.md").write_text("content")

        # Create v2 manifest
        manifest = Manifest(
            version=2,
            installed=["ralph/prd"],
            syncedAt="2026-01-01T00:00:00+00:00",
        )
        save_manifest(manifest, target_dir / ".ralph-manifest.json")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        service.remove_skills()

        # Parent directory should also be removed since it's empty
        assert not (target_dir / "ralph").exists()

    def test_remove_preserves_non_empty_parent_directories(self, tmp_path: Path) -> None:
        """Test that parent directories with other skills are preserved."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Create two nested skills under ralph/
        (target_dir / "ralph" / "prd").mkdir(parents=True)
        (target_dir / "ralph" / "prd" / "SKILL.md").write_text("content")
        (target_dir / "ralph" / "tasks").mkdir(parents=True)
        (target_dir / "ralph" / "tasks" / "SKILL.md").write_text("content")

        # Create v2 manifest listing only one skill
        manifest = Manifest(
            version=2,
            installed=["ralph/prd"],
            syncedAt="2026-01-01T00:00:00+00:00",
        )
        save_manifest(manifest, target_dir / ".ralph-manifest.json")

        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        service.remove_skills()

        # ralph/prd should be removed
        assert not (target_dir / "ralph" / "prd").exists()
        # ralph/ directory should still exist (has tasks/)
        assert (target_dir / "ralph").exists()
        # ralph/tasks should still exist
        assert (target_dir / "ralph" / "tasks").exists()


class TestSkillInfoRelativePath:
    """Tests for SkillInfo relative_path field."""

    def test_validate_skill_sets_relative_path_for_nested_skill(self, tmp_path: Path) -> None:
        """Test that validate_skill sets correct relative_path for nested skills."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        skill_dir = skills_dir / "ralph" / "prd"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            '---\nname: "ralph-prd"\ndescription: "PRD skill"\n---\n'
        )

        service = SkillsService(skills_dir=skills_dir)
        result = service.validate_skill(skill_dir)

        assert result is not None
        assert result.relative_path == "ralph/prd"

    def test_validate_skill_sets_relative_path_for_flat_skill(self, tmp_path: Path) -> None:
        """Test that validate_skill sets correct relative_path for flat skills."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        skill_dir = skills_dir / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text('---\nname: "my-skill"\ndescription: "My skill"\n---\n')

        service = SkillsService(skills_dir=skills_dir)
        result = service.validate_skill(skill_dir)

        assert result is not None
        assert result.relative_path == "my-skill"

    def test_validate_skill_sets_relative_path_for_deeply_nested_skill(
        self, tmp_path: Path
    ) -> None:
        """Test that validate_skill sets correct relative_path for deeply nested skills."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        skill_dir = skills_dir / "reviewers" / "language" / "python"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            '---\nname: "python-reviewer"\ndescription: "Python reviewer"\n---\n'
        )

        service = SkillsService(skills_dir=skills_dir)
        result = service.validate_skill(skill_dir)

        assert result is not None
        assert result.relative_path == "reviewers/language/python"
