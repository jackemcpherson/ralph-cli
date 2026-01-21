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


class TestSkillLoaderNestedPaths:
    """Tests for SkillLoader nested path support."""

    def test_load_nested_path_two_levels(self, tmp_path: Path) -> None:
        """Test that load works with two-level nested paths like ralph/prd."""
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "ralph" / "prd"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("---\nname: ralph-prd\n---\n\n# PRD Skill")

        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load("ralph/prd")

        assert result == skill_file
        assert result.exists()

    def test_load_nested_path_three_levels(self, tmp_path: Path) -> None:
        """Test that load works with three-level nested paths like reviewers/language/python."""
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "reviewers" / "language" / "python"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("---\nname: python-code-reviewer\n---\n\n# Python Reviewer")

        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load("reviewers/language/python")

        assert result == skill_file
        assert result.exists()

    def test_load_nested_path_preserves_structure(self, tmp_path: Path) -> None:
        """Test that nested path loading returns correct path structure."""
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "reviewers" / "code-simplifier"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Code Simplifier")

        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load("reviewers/code-simplifier")

        assert result.name == "SKILL.md"
        assert result.parent.name == "code-simplifier"
        assert result.parent.parent.name == "reviewers"

    def test_load_nested_raises_for_missing_skill(self, tmp_path: Path) -> None:
        """Test that load raises SkillNotFoundError for missing nested skill."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        loader = SkillLoader(skills_dir=skills_dir)

        with pytest.raises(SkillNotFoundError) as exc_info:
            loader.load("ralph/nonexistent")

        assert exc_info.value.skill_name == "ralph/nonexistent"

    def test_load_nested_raises_for_partial_path(self, tmp_path: Path) -> None:
        """Test that load raises when parent exists but skill doesn't."""
        skills_dir = tmp_path / "skills"
        (skills_dir / "ralph").mkdir(parents=True)

        loader = SkillLoader(skills_dir=skills_dir)

        with pytest.raises(SkillNotFoundError):
            loader.load("ralph/prd")

    def test_load_multiple_nested_skills(self, tmp_path: Path) -> None:
        """Test that loader can load multiple nested skills."""
        skills_dir = tmp_path / "skills"

        nested_skills = [
            "ralph/prd",
            "ralph/tasks",
            "ralph/iteration",
            "reviewers/code-simplifier",
            "reviewers/test-quality",
        ]

        for skill_path in nested_skills:
            skill_dir = skills_dir / skill_path
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"# Skill {skill_path}")

        loader = SkillLoader(skills_dir=skills_dir)

        for skill_path in nested_skills:
            result = loader.load(skill_path)
            assert result.exists()
            assert result.name == "SKILL.md"


class TestSkillLoaderGetContent:
    """Tests for SkillLoader.get_content() method."""

    def test_get_content_returns_file_content(self, tmp_path: Path) -> None:
        """Test that get_content returns the skill file content."""
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "my-skill"
        skill_dir.mkdir(parents=True)
        expected_content = "---\nname: my-skill\n---\n\n# My Skill\n\nSome content."
        (skill_dir / "SKILL.md").write_text(expected_content)

        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.get_content("my-skill")

        assert result == expected_content

    def test_get_content_nested_path(self, tmp_path: Path) -> None:
        """Test that get_content works with nested paths."""
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "ralph" / "prd"
        skill_dir.mkdir(parents=True)
        expected_content = "---\nname: ralph-prd\ndescription: PRD skill\n---\n\n# PRD Content"
        (skill_dir / "SKILL.md").write_text(expected_content)

        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.get_content("ralph/prd")

        assert result == expected_content

    def test_get_content_raises_for_missing_skill(self, tmp_path: Path) -> None:
        """Test that get_content raises SkillNotFoundError for missing skill."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        loader = SkillLoader(skills_dir=skills_dir)

        with pytest.raises(SkillNotFoundError):
            loader.get_content("nonexistent")

    def test_get_content_deeply_nested(self, tmp_path: Path) -> None:
        """Test that get_content works with deeply nested paths."""
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "reviewers" / "language" / "python"
        skill_dir.mkdir(parents=True)
        expected_content = "# Python Code Reviewer\n\nReview Python code quality."
        (skill_dir / "SKILL.md").write_text(expected_content)

        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.get_content("reviewers/language/python")

        assert result == expected_content
