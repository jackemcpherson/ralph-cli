"""Unit tests for SkillLoader service.

Focused tests for skill loading functionality:
- Locating skill paths on disk
- Error handling for missing skills
- Multiple skill loading
"""

from pathlib import Path

import pytest

from ralph.services.skill_loader import SkillLoader, SkillNotFoundError


class TestSkillNotFoundError:
    """Tests for SkillNotFoundError exception."""

    def test_exception_has_clear_error_message(self, tmp_path: Path) -> None:
        """Test that SkillNotFoundError provides a clear error message."""
        skill_path = tmp_path / "skills" / "my-skill" / "SKILL.md"
        error = SkillNotFoundError("my-skill", skill_path)

        assert "my-skill" in str(error)
        assert str(skill_path) in str(error)
        assert error.skill_name == "my-skill"
        assert error.skill_path == skill_path


class TestSkillLoader:
    """Tests for SkillLoader functionality."""

    def test_load_returns_skill_path(self, tmp_path: Path) -> None:
        """Test that load returns skill path for existing skill."""
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "my-skill"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("---\nname: my-skill\n---\n\n# My Skill\n\nSome content.")

        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load("my-skill")

        assert isinstance(result, Path)
        assert result == skill_file
        assert result.exists()

    def test_load_raises_for_missing_skill(self, tmp_path: Path) -> None:
        """Test that load raises SkillNotFoundError for missing skill."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        loader = SkillLoader(skills_dir=skills_dir)

        with pytest.raises(SkillNotFoundError) as exc_info:
            loader.load("nonexistent-skill")

        assert exc_info.value.skill_name == "nonexistent-skill"

    def test_load_raises_for_missing_skill_md(self, tmp_path: Path) -> None:
        """Test that load raises SkillNotFoundError when SKILL.md is missing."""
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "incomplete-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "README.md").write_text("# Not the right file")

        loader = SkillLoader(skills_dir=skills_dir)

        with pytest.raises(SkillNotFoundError):
            loader.load("incomplete-skill")

    def test_load_returns_correct_path_structure(self, tmp_path: Path) -> None:
        """Test that load returns path with expected structure."""
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Test")

        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load("test-skill")

        assert result.name == "SKILL.md"
        assert result.parent.name == "test-skill"

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

        assert result_a.parent.name == "skill-a"
        assert result_b.parent.name == "skill-b"
        assert result_c.parent.name == "skill-c"
