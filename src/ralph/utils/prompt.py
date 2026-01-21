"""Prompt building utilities for Ralph CLI.

This module provides utilities for building prompts with @file references
to Claude Code skills.
"""

from pathlib import Path

from ralph.services.skill_loader import SkillLoader, SkillNotFoundError


def build_skill_prompt(project_root: Path, skill_name: str, context: str) -> str:
    """Build a prompt with @file reference to a skill.

    Creates a prompt that references a skill file using Claude Code's
    native @file syntax, followed by context for the session.

    Args:
        project_root: Project root directory.
        skill_name: Skill name (e.g., 'ralph-prd').
        context: Context section to append.

    Returns:
        Prompt string with @file reference.

    Raises:
        SkillNotFoundError: If skill doesn't exist.
    """
    skills_dir = project_root / "skills"
    loader = SkillLoader(skills_dir=skills_dir)
    skill_path = loader.load(skill_name)
    relative_path = skill_path.relative_to(project_root)

    # Use forward slashes for @file references (cross-platform consistency)
    return f"Follow the instructions in @{relative_path.as_posix()}\n\n{context}"


__all__ = ["build_skill_prompt", "SkillNotFoundError"]
