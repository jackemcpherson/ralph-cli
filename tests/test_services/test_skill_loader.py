"""Tests for SkillLoader service."""

from pathlib import Path

import pytest

from ralph.services.skill_loader import SkillLoader, SkillNotFoundError


class TestSkillNotFoundError:
    """Tests for SkillNotFoundError exception."""

    def test_exception_message(self, tmp_path: Path) -> None:
        """Test that SkillNotFoundError has a clear error message."""
        skill_path = tmp_path / "skills" / "my-skill" / "SKILL.md"
        error = SkillNotFoundError("my-skill", skill_path)

        assert "my-skill" in str(error)
        assert str(skill_path) in str(error)
        assert "not found" in str(error).lower()

    def test_exception_attributes(self, tmp_path: Path) -> None:
        """Test that SkillNotFoundError stores skill_name and skill_path."""
        skill_path = tmp_path / "skills" / "test-skill" / "SKILL.md"
        error = SkillNotFoundError("test-skill", skill_path)

        assert error.skill_name == "test-skill"
        assert error.skill_path == skill_path


class TestSkillLoaderInit:
    """Tests for SkillLoader initialization."""

    def test_init_with_path(self, tmp_path: Path) -> None:
        """Test that SkillLoader can be initialized with a skills directory."""
        loader = SkillLoader(skills_dir=tmp_path / "skills")

        assert loader.skills_dir == tmp_path / "skills"


class TestSkillLoaderLoad:
    """Tests for SkillLoader.load method."""

    def test_load_existing_skill(self, tmp_path: Path) -> None:
        """Test that load returns skill content for existing skill."""
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "my-skill"
        skill_dir.mkdir(parents=True)
        skill_content = "---\nname: my-skill\n---\n\n# My Skill\n\nSome content."
        (skill_dir / "SKILL.md").write_text(skill_content)

        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load("my-skill")

        assert result == skill_content

    def test_load_raises_for_missing_skill_directory(self, tmp_path: Path) -> None:
        """Test that load raises SkillNotFoundError for missing skill directory."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        loader = SkillLoader(skills_dir=skills_dir)

        with pytest.raises(SkillNotFoundError) as exc_info:
            loader.load("nonexistent-skill")

        assert exc_info.value.skill_name == "nonexistent-skill"
        assert "nonexistent-skill" in str(exc_info.value)

    def test_load_raises_for_missing_skill_md(self, tmp_path: Path) -> None:
        """Test that load raises SkillNotFoundError when SKILL.md is missing."""
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "incomplete-skill"
        skill_dir.mkdir(parents=True)
        # Create directory but no SKILL.md file
        (skill_dir / "README.md").write_text("# Not the right file")

        loader = SkillLoader(skills_dir=skills_dir)

        with pytest.raises(SkillNotFoundError) as exc_info:
            loader.load("incomplete-skill")

        assert exc_info.value.skill_name == "incomplete-skill"

    def test_load_raises_for_nonexistent_skills_dir(self, tmp_path: Path) -> None:
        """Test that load raises SkillNotFoundError when skills_dir doesn't exist."""
        nonexistent_dir = tmp_path / "nonexistent" / "skills"

        loader = SkillLoader(skills_dir=nonexistent_dir)

        with pytest.raises(SkillNotFoundError) as exc_info:
            loader.load("any-skill")

        assert exc_info.value.skill_name == "any-skill"

    def test_load_returns_full_content(self, tmp_path: Path) -> None:
        """Test that load returns the complete file content."""
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "full-skill"
        skill_dir.mkdir(parents=True)
        skill_content = """---
name: full-skill
description: A full skill with lots of content
---

# Full Skill

This is a comprehensive skill with:

- Multiple sections
- Code examples
- Detailed instructions

## Section 1

Some detailed content here.

## Section 2

More content with special characters: éàü
"""
        (skill_dir / "SKILL.md").write_text(skill_content, encoding="utf-8")

        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load("full-skill")

        assert result == skill_content
        assert "éàü" in result  # Verify UTF-8 handling

    def test_load_multiple_skills(self, tmp_path: Path) -> None:
        """Test that loader can load multiple different skills."""
        skills_dir = tmp_path / "skills"

        for name in ["skill-a", "skill-b", "skill-c"]:
            skill_dir = skills_dir / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"# Skill {name}\n\nContent for {name}.")

        loader = SkillLoader(skills_dir=skills_dir)

        result_a = loader.load("skill-a")
        result_b = loader.load("skill-b")
        result_c = loader.load("skill-c")

        assert "skill-a" in result_a
        assert "skill-b" in result_b
        assert "skill-c" in result_c
