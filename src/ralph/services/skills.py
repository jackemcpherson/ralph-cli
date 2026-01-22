"""Skills sync service for Ralph CLI.

This module provides services for managing and syncing Claude Code skills
from a local skills directory to the global ~/.claude/skills/ directory.
"""

import logging
import re
import shutil
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ralph.models.manifest import MANIFEST_VERSION, Manifest, load_manifest, save_manifest

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Status of a skill sync operation.

    Indicates the outcome of attempting to sync a single skill.

    Attributes:
        CREATED: Skill was newly created in the target directory.
        UPDATED: Existing skill was updated with new content.
        SKIPPED: Skill sync was skipped due to an error.
        INVALID: Skill was invalid (missing required frontmatter).
    """

    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    INVALID = "invalid"


class SkillInfo(BaseModel):
    """Information about a validated skill.

    Contains metadata extracted from a skill's SKILL.md frontmatter.

    Attributes:
        name: The skill name from frontmatter.
        description: The skill description from frontmatter.
        path: Path to the skill directory.
        relative_path: Relative path from skills root (e.g., "ralph/prd").
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    path: Path
    relative_path: str = ""


class SkillSyncResult(BaseModel):
    """Result of a skill sync operation.

    Contains the outcome and details of syncing a single skill.

    Attributes:
        skill_name: Name of the skill that was synced.
        status: The sync status outcome.
        source_path: Path to the source skill directory.
        target_path: Path to the target skill directory (if synced).
        error: Error message if sync failed.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    skill_name: str
    status: SyncStatus
    source_path: Path
    target_path: Path | None = None
    error: str | None = None


class SkillsService(BaseModel):
    """Service for managing and syncing Claude Code skills.

    Provides methods to list, validate, and sync skills from a local
    skills/ directory to the global ~/.claude/skills/ directory.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    skills_dir: Path
    target_dir: Path = Path.home() / ".claude" / "skills"

    def list_local_skills(self) -> list[Path]:
        """Find all skill directories in the local skills/ directory.

        Skills are identified by the presence of a SKILL.md file.
        Supports nested directory structures like ralph/prd/ or
        reviewers/language/python/.

        Returns:
            List of paths to skill directories containing SKILL.md files.
        """
        if not self.skills_dir.exists():
            return []

        skill_paths: list[Path] = []

        # Recursively find all SKILL.md files
        for skill_md in self.skills_dir.rglob("SKILL.md"):
            skill_paths.append(skill_md.parent)

        return sorted(skill_paths, key=lambda p: str(p))

    def validate_skill(self, skill_path: Path) -> SkillInfo | None:
        """Validate a skill directory has required frontmatter.

        Checks that the SKILL.md file exists and contains valid YAML
        frontmatter with 'name' and 'description' fields.

        Args:
            skill_path: Path to the skill directory.

        Returns:
            SkillInfo if valid, None if invalid or missing required fields.
        """
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            return None

        try:
            content = skill_md.read_text(encoding="utf-8")
        except OSError:
            return None

        frontmatter = self._parse_frontmatter(content)
        if frontmatter is None:
            return None

        name = frontmatter.get("name")
        description = frontmatter.get("description")

        if not name or not description:
            return None

        # Calculate relative path from skills_dir (e.g., "ralph/prd")
        # Always use forward slashes for cross-platform consistency in manifest
        try:
            relative_path = skill_path.relative_to(self.skills_dir).as_posix()
        except ValueError:
            # skill_path is not under skills_dir, use the directory name
            relative_path = skill_path.name

        return SkillInfo(
            name=str(name),
            description=str(description),
            path=skill_path,
            relative_path=relative_path,
        )

    def sync_skill(self, skill_path: Path) -> SkillSyncResult:
        """Sync a single skill to the global skills directory.

        Copies the skill directory to ~/.claude/skills/, preserving the
        nested directory structure. For example, skills/ralph/prd/ is
        synced to ~/.claude/skills/ralph/prd/.

        Args:
            skill_path: Path to the skill directory to sync.

        Returns:
            SkillSyncResult with the sync status and details.
        """
        skill_info = self.validate_skill(skill_path)

        if skill_info is None:
            return SkillSyncResult(
                skill_name=skill_path.name,
                status=SyncStatus.INVALID,
                source_path=skill_path,
                error="Missing or invalid SKILL.md frontmatter (requires 'name' and 'description')",
            )

        # Use the relative path to preserve nested structure
        target_path = self.target_dir / skill_info.relative_path
        status = SyncStatus.UPDATED if target_path.exists() else SyncStatus.CREATED

        try:
            # Ensure parent directories exist (for nested paths like ralph/prd)
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Remove existing skill directory if it exists
            if target_path.exists():
                shutil.rmtree(target_path)

            # Copy the skill directory
            shutil.copytree(skill_path, target_path)

            return SkillSyncResult(
                skill_name=skill_info.relative_path,
                status=status,
                source_path=skill_path,
                target_path=target_path,
            )
        except OSError as e:
            return SkillSyncResult(
                skill_name=skill_info.relative_path,
                status=SyncStatus.SKIPPED,
                source_path=skill_path,
                error=str(e),
            )

    def sync_all(self) -> list[SkillSyncResult]:
        """Sync all valid skills to the global skills directory.

        Iterates through all skills in the local skills/ directory,
        validates them, and syncs valid ones to ~/.claude/skills/.
        Before syncing, cleans up old flat-structure skills from v1 manifests.
        After syncing, writes a manifest file to track installed skills.

        Returns:
            List of SkillSyncResult for each skill processed.
        """
        # Clean up old flat-structure skills from v1 manifests
        self._cleanup_old_flat_skills()

        results: list[SkillSyncResult] = []

        skill_paths = self.list_local_skills()

        for skill_path in skill_paths:
            result = self.sync_skill(skill_path)
            results.append(result)

        # Write manifest with successfully installed skills
        self._write_manifest(results)

        return results

    def _cleanup_old_flat_skills(self) -> list[str]:
        """Clean up old flat-structure skills from version 1 manifests.

        Reads the existing manifest and removes any skills that were
        installed with the old flat naming convention (e.g., "ralph-prd"
        instead of "ralph/prd").

        Returns:
            List of old skill names that were removed.
        """
        manifest_path = self.target_dir / ".ralph-manifest.json"
        manifest = load_manifest(manifest_path)

        if manifest is None:
            return []

        # Only clean up if manifest is version 1 (or has no version field)
        if manifest.version >= MANIFEST_VERSION:
            return []

        removed: list[str] = []

        for skill_name in manifest.installed:
            # Skip if it looks like a nested path (contains /)
            if "/" in skill_name:
                continue

            skill_dir = self.target_dir / skill_name
            if skill_dir.exists() and skill_dir.is_dir():
                try:
                    shutil.rmtree(skill_dir)
                    removed.append(skill_name)
                    logger.info(f"Cleaned up old flat-structure skill: {skill_name}")
                except OSError as e:
                    logger.warning(f"Failed to remove old skill {skill_name}: {e}")

        return removed

    def _write_manifest(self, results: list[SkillSyncResult]) -> None:
        """Write a manifest file to track installed skills.

        Creates a .ralph-manifest.json file in the target directory
        containing the list of successfully installed skill paths.
        Uses manifest version 2 which stores full nested paths.

        Args:
            results: List of sync results to extract installed skills from.
        """
        # Extract successfully installed skill paths (e.g., "ralph/prd")
        installed_skills: list[str] = []
        for result in results:
            if result.status in (SyncStatus.CREATED, SyncStatus.UPDATED):
                # Use the skill_name which is now the relative path
                installed_skills.append(result.skill_name)

        # Create manifest with current timestamp and version 2
        manifest = Manifest(
            version=MANIFEST_VERSION,
            installed=sorted(installed_skills),
            syncedAt=datetime.now(UTC).isoformat(),
        )

        # Ensure target directory exists
        self.target_dir.mkdir(parents=True, exist_ok=True)

        # Write manifest file
        manifest_path = self.target_dir / ".ralph-manifest.json"
        save_manifest(manifest, manifest_path)

    def remove_skills(self) -> list[str]:
        """Remove skills listed in the manifest file.

        Reads the .ralph-manifest.json file from the target directory and
        removes only the skill directories that are listed in it. Then
        deletes the manifest file itself.

        Handles both v1 (flat names like "ralph-prd") and v2 (nested paths
        like "ralph/prd") manifest formats.

        This operation is idempotent - no error if skills are already removed.

        Returns:
            List of skill paths that were removed.
        """
        manifest_path = self.target_dir / ".ralph-manifest.json"
        manifest = load_manifest(manifest_path)

        if manifest is None:
            # No manifest found - nothing to remove
            return []

        removed: list[str] = []

        for skill_path in manifest.installed:
            # skill_path can be either flat ("ralph-prd") or nested ("ralph/prd")
            skill_dir = self.target_dir / skill_path
            if skill_dir.exists() and skill_dir.is_dir():
                try:
                    shutil.rmtree(skill_dir)
                    removed.append(skill_path)

                    # Clean up empty parent directories for nested paths
                    self._cleanup_empty_parents(skill_dir.parent)
                except OSError as e:
                    logger.warning(f"Failed to remove skill {skill_path}: {e}")

        # Remove the manifest file
        try:
            manifest_path.unlink()
        except OSError as e:
            logger.debug(f"Could not remove manifest file: {e}")

        return removed

    def _cleanup_empty_parents(self, directory: Path) -> None:
        """Remove empty parent directories up to target_dir.

        After removing a nested skill like ralph/prd, this cleans up
        the empty ralph/ directory if no other skills remain.

        Args:
            directory: Starting directory to check for emptiness.
        """
        while directory != self.target_dir and directory.is_relative_to(self.target_dir):
            try:
                # Only remove if directory is empty
                if directory.exists() and not any(directory.iterdir()):
                    directory.rmdir()
                    logger.debug(f"Removed empty directory: {directory}")
                else:
                    # Stop if directory is not empty
                    break
            except OSError:
                # Stop on any error
                break
            directory = directory.parent

    def _parse_frontmatter(self, content: str) -> dict[str, str] | None:
        """Parse YAML frontmatter from a markdown file.

        Extracts the frontmatter between --- delimiters at the start of
        the file and parses it as simple key: value pairs.

        Args:
            content: The full content of the markdown file.

        Returns:
            Dictionary of frontmatter key-value pairs, or None if no
            valid frontmatter found.
        """
        pattern = r"^---\s*\n(.*?)\n---"
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return None

        frontmatter_text = match.group(1)
        result: dict[str, str] = {}

        for line in frontmatter_text.split("\n"):
            line = line.strip()
            if not line or ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            if value and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]

            result[key] = value

        return result
