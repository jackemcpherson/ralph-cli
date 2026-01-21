"""Skill content loader service for Ralph CLI.

This module provides a service for loading skill content from disk,
enabling commands to delegate prompt logic to skill files.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class SkillNotFoundError(Exception):
    """Raised when a requested skill file cannot be found.

    Attributes:
        skill_name: The name of the skill that was not found.
        skill_path: The path where the skill was expected.
    """

    def __init__(self, skill_name: str, skill_path: Path) -> None:
        """Initialize SkillNotFoundError.

        Args:
            skill_name: The name of the skill that was not found.
            skill_path: The path where the skill was expected.
        """
        self.skill_name = skill_name
        self.skill_path = skill_path
        super().__init__(f"Skill '{skill_name}' not found. Expected at: {skill_path}")


class SkillLoader(BaseModel):
    """Service for loading skill content from disk.

    Reads skill definitions from the skills directory, allowing
    commands to delegate prompt generation to skill files.

    Attributes:
        skills_dir: Path to the skills directory containing skill subdirectories.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    skills_dir: Path

    def load(self, skill_name: str) -> str:
        """Load skill content from disk.

        Reads the SKILL.md file from the specified skill's directory
        and returns its content as a string.

        Args:
            skill_name: The name of the skill directory to load (e.g., 'ralph-prd').

        Returns:
            The content of the skill's SKILL.md file as a string.

        Raises:
            SkillNotFoundError: If the skill directory or SKILL.md file does not exist.
        """
        skill_path = self.skills_dir / skill_name / "SKILL.md"

        if not skill_path.exists():
            raise SkillNotFoundError(skill_name, skill_path)

        return skill_path.read_text(encoding="utf-8")
