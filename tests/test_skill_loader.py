"""Unit tests for SkillLoader service.

Focused tests for skill loading functionality:
- Loading skill content from disk
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

    def test_load_returns_skill_content(self, tmp_path: Path) -> None:
        """Test that load returns skill content for existing skill."""
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "my-skill"
        skill_dir.mkdir(parents=True)
        skill_content = "---\nname: my-skill\n---\n\n# My Skill\n\nSome content."
        (skill_dir / "SKILL.md").write_text(skill_content)

        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load("my-skill")

        assert result == skill_content

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

    def test_load_handles_utf8_content(self, tmp_path: Path) -> None:
        """Test that load correctly handles UTF-8 content."""
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "utf8-skill"
        skill_dir.mkdir(parents=True)
        skill_content = "---\nname: utf8\n---\n\nSpecial chars: éàü 日本語 🚀"
        (skill_dir / "SKILL.md").write_text(skill_content, encoding="utf-8")

        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load("utf8-skill")

        assert "éàü" in result
        assert "日本語" in result
        assert "🚀" in result

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
