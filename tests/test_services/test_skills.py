"""Tests for Skills service."""

from pathlib import Path

from ralph.services.skills import SkillInfo, SkillsService, SkillSyncResult, SyncStatus


class TestSyncStatus:
    """Tests for SyncStatus enum."""

    def test_status_values(self) -> None:
        """Test that all expected status values exist."""
        assert SyncStatus.CREATED.value == "created"
        assert SyncStatus.UPDATED.value == "updated"
        assert SyncStatus.SKIPPED.value == "skipped"
        assert SyncStatus.INVALID.value == "invalid"


class TestSkillInfo:
    """Tests for SkillInfo model."""

    def test_skill_info_creation(self, tmp_path: Path) -> None:
        """Test that SkillInfo can be created with valid data."""
        info = SkillInfo(
            name="test-skill",
            description="A test skill",
            path=tmp_path / "test-skill",
        )

        assert info.name == "test-skill"
        assert info.description == "A test skill"
        assert info.path == tmp_path / "test-skill"


class TestSkillSyncResult:
    """Tests for SkillSyncResult model."""

    def test_sync_result_success(self, tmp_path: Path) -> None:
        """Test SkillSyncResult for successful sync."""
        result = SkillSyncResult(
            skill_name="test-skill",
            status=SyncStatus.CREATED,
            source_path=tmp_path / "src",
            target_path=tmp_path / "target",
        )

        assert result.skill_name == "test-skill"
        assert result.status == SyncStatus.CREATED
        assert result.error is None

    def test_sync_result_with_error(self, tmp_path: Path) -> None:
        """Test SkillSyncResult with error."""
        result = SkillSyncResult(
            skill_name="test-skill",
            status=SyncStatus.SKIPPED,
            source_path=tmp_path / "src",
            error="Permission denied",
        )

        assert result.status == SyncStatus.SKIPPED
        assert result.error == "Permission denied"
        assert result.target_path is None


class TestSkillsServiceInit:
    """Tests for SkillsService initialization."""

    def test_default_target_dir(self, tmp_path: Path) -> None:
        """Test that default target_dir is ~/.claude/skills/."""
        service = SkillsService(skills_dir=tmp_path)

        assert service.target_dir == Path.home() / ".claude" / "skills"

    def test_custom_target_dir(self, tmp_path: Path) -> None:
        """Test that target_dir can be customized."""
        custom_target = tmp_path / "custom_target"
        service = SkillsService(skills_dir=tmp_path, target_dir=custom_target)

        assert service.target_dir == custom_target


class TestListLocalSkills:
    """Tests for list_local_skills method."""

    def test_returns_empty_for_nonexistent_dir(self, tmp_path: Path) -> None:
        """Test that nonexistent skills dir returns empty list."""
        service = SkillsService(skills_dir=tmp_path / "nonexistent")

        result = service.list_local_skills()

        assert result == []

    def test_returns_empty_for_empty_dir(self, tmp_path: Path) -> None:
        """Test that empty skills dir returns empty list."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        service = SkillsService(skills_dir=skills_dir)

        result = service.list_local_skills()

        assert result == []

    def test_returns_empty_for_dir_without_skill_md(self, tmp_path: Path) -> None:
        """Test that directories without SKILL.md are not included."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "not-a-skill").mkdir()
        (skills_dir / "not-a-skill" / "README.md").write_text("# Not a skill")

        service = SkillsService(skills_dir=skills_dir)
        result = service.list_local_skills()

        assert result == []

    def test_finds_skill_with_skill_md(self, tmp_path: Path) -> None:
        """Test that directories with SKILL.md are found."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill_dir = skills_dir / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---")

        service = SkillsService(skills_dir=skills_dir)
        result = service.list_local_skills()

        assert len(result) == 1
        assert result[0] == skill_dir

    def test_finds_multiple_skills(self, tmp_path: Path) -> None:
        """Test that multiple skills are found."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        for name in ["alpha-skill", "beta-skill", "gamma-skill"]:
            skill_dir = skills_dir / name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\n---")

        service = SkillsService(skills_dir=skills_dir)
        result = service.list_local_skills()

        assert len(result) == 3
        # Should be sorted alphabetically
        assert result[0].name == "alpha-skill"
        assert result[1].name == "beta-skill"
        assert result[2].name == "gamma-skill"

    def test_ignores_files_in_skills_dir(self, tmp_path: Path) -> None:
        """Test that regular files in skills dir are ignored."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "not-a-dir.txt").write_text("Just a file")

        service = SkillsService(skills_dir=skills_dir)
        result = service.list_local_skills()

        assert result == []


class TestValidateSkill:
    """Tests for validate_skill method."""

    def test_returns_none_for_missing_skill_md(self, tmp_path: Path) -> None:
        """Test that missing SKILL.md returns None."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()

        service = SkillsService(skills_dir=tmp_path)
        result = service.validate_skill(skill_dir)

        assert result is None

    def test_returns_none_for_missing_frontmatter(self, tmp_path: Path) -> None:
        """Test that SKILL.md without frontmatter returns None."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# My Skill\n\nNo frontmatter here.")

        service = SkillsService(skills_dir=tmp_path)
        result = service.validate_skill(skill_dir)

        assert result is None

    def test_returns_none_for_missing_name(self, tmp_path: Path) -> None:
        """Test that frontmatter without 'name' returns None."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text('---\ndescription: "A skill"\n---\n')

        service = SkillsService(skills_dir=tmp_path)
        result = service.validate_skill(skill_dir)

        assert result is None

    def test_returns_none_for_missing_description(self, tmp_path: Path) -> None:
        """Test that frontmatter without 'description' returns None."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text('---\nname: "my-skill"\n---\n')

        service = SkillsService(skills_dir=tmp_path)
        result = service.validate_skill(skill_dir)

        assert result is None

    def test_returns_skill_info_for_valid_skill(self, tmp_path: Path) -> None:
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
        assert result.path == skill_dir


class TestParseFrontmatter:
    """Tests for _parse_frontmatter method."""

    def test_returns_none_for_no_frontmatter(self, tmp_path: Path) -> None:
        """Test that content without frontmatter returns None."""
        service = SkillsService(skills_dir=tmp_path)

        result = service._parse_frontmatter("# Just a heading\n\nSome content.")

        assert result is None

    def test_returns_none_for_invalid_frontmatter(self, tmp_path: Path) -> None:
        """Test that incomplete frontmatter returns None."""
        service = SkillsService(skills_dir=tmp_path)

        # Missing closing ---
        result = service._parse_frontmatter("---\nname: test\nMore content")

        assert result is None

    def test_parses_simple_frontmatter(self, tmp_path: Path) -> None:
        """Test parsing simple key: value frontmatter."""
        service = SkillsService(skills_dir=tmp_path)
        content = "---\nname: test\ndescription: A test\n---\n\nContent"

        result = service._parse_frontmatter(content)

        assert result is not None
        assert result["name"] == "test"
        assert result["description"] == "A test"

    def test_parses_quoted_values(self, tmp_path: Path) -> None:
        """Test parsing quoted values in frontmatter."""
        service = SkillsService(skills_dir=tmp_path)
        content = "---\nname: \"quoted-name\"\ndescription: 'single quoted'\n---\n"

        result = service._parse_frontmatter(content)

        assert result is not None
        assert result["name"] == "quoted-name"
        assert result["description"] == "single quoted"

    def test_handles_empty_lines_in_frontmatter(self, tmp_path: Path) -> None:
        """Test that empty lines in frontmatter are handled."""
        service = SkillsService(skills_dir=tmp_path)
        content = "---\nname: test\n\ndescription: A test\n---\n"

        result = service._parse_frontmatter(content)

        assert result is not None
        assert result["name"] == "test"
        assert result["description"] == "A test"

    def test_handles_whitespace_around_values(self, tmp_path: Path) -> None:
        """Test that whitespace around values is trimmed."""
        service = SkillsService(skills_dir=tmp_path)
        content = "---\nname:    test   \ndescription:   A test   \n---\n"

        result = service._parse_frontmatter(content)

        assert result is not None
        assert result["name"] == "test"
        assert result["description"] == "A test"


class TestSyncSkill:
    """Tests for sync_skill method."""

    def test_returns_invalid_for_invalid_skill(self, tmp_path: Path) -> None:
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
        assert "frontmatter" in result.error.lower()

    def test_creates_new_skill(self, tmp_path: Path) -> None:
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
        assert result.target_path == target_dir / "new-skill"
        assert (target_dir / "new-skill" / "SKILL.md").exists()

    def test_updates_existing_skill(self, tmp_path: Path) -> None:
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
        # Content should be updated
        new_content = (target_skill / "SKILL.md").read_text()
        assert "Updated content" in new_content

    def test_copies_all_files_in_skill_dir(self, tmp_path: Path) -> None:
        """Test that all files in skill directory are copied."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill_dir = skills_dir / "multi-file-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            '---\nname: "multi-file"\ndescription: "Has multiple files"\n---\n'
        )
        (skill_dir / "helper.md").write_text("# Helper content")
        (skill_dir / "examples").mkdir()
        (skill_dir / "examples" / "example.txt").write_text("Example")

        target_dir = tmp_path / "target"
        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        result = service.sync_skill(skill_dir)

        assert result.status == SyncStatus.CREATED
        assert (target_dir / "multi-file-skill" / "SKILL.md").exists()
        assert (target_dir / "multi-file-skill" / "helper.md").exists()
        assert (target_dir / "multi-file-skill" / "examples" / "example.txt").exists()


class TestSyncAll:
    """Tests for sync_all method."""

    def test_syncs_all_valid_skills(self, tmp_path: Path) -> None:
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

    def test_returns_empty_for_no_skills(self, tmp_path: Path) -> None:
        """Test that sync_all returns empty list when no skills exist."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        target_dir = tmp_path / "target"
        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        results = service.sync_all()

        assert results == []

    def test_reports_invalid_skills(self, tmp_path: Path) -> None:
        """Test that sync_all reports invalid skills."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Valid skill
        valid_skill = skills_dir / "valid-skill"
        valid_skill.mkdir()
        (valid_skill / "SKILL.md").write_text('---\nname: "valid"\ndescription: "Valid"\n---\n')

        # Invalid skill
        invalid_skill = skills_dir / "invalid-skill"
        invalid_skill.mkdir()
        (invalid_skill / "SKILL.md").write_text("# No frontmatter")

        target_dir = tmp_path / "target"
        service = SkillsService(skills_dir=skills_dir, target_dir=target_dir)

        results = service.sync_all()

        assert len(results) == 2
        statuses = {r.skill_name: r.status for r in results}
        assert statuses["invalid-skill"] == SyncStatus.INVALID
        assert statuses["valid"] == SyncStatus.CREATED
