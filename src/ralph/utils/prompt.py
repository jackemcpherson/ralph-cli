"""Prompt building utilities for Ralph CLI.

This module provides utilities for building prompts with skill content.
Uses @filepath notation for skill content to reduce token usage.
"""

from pathlib import Path

from ralph.services.skill_loader import SkillLoader, SkillNotFoundError


def build_skill_prompt(
    skill_name: str,
    context: str,
    skills_dir: Path | None = None,
) -> str:
    """Build a prompt using @filepath reference for skill content.

    Uses @filepath notation to reference the bundled skill file directly,
    reducing token usage when invoking Claude. The context is kept inline
    since it's usually smaller and session-specific.

    Args:
        skill_name: Skill name (e.g., 'ralph/prd', 'reviewers/test-quality').
        context: Context section to append.
        skills_dir: Optional custom skills directory. If None, uses bundled skills.

    Returns:
        Prompt string with @filepath reference for skill content.

    Raises:
        SkillNotFoundError: If skill doesn't exist.
    """
    loader = SkillLoader(skills_dir=skills_dir)
    skill_path = loader.get_path(skill_name)

    return f"""Follow these instructions:

@{skill_path}

{context}"""


__all__ = ["build_skill_prompt", "SkillNotFoundError"]
