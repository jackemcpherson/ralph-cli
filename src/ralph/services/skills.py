"""Skills sync service for Ralph CLI.

This module provides services for managing and syncing Claude Code skills
from bundled package resources or a local skills directory to the global
~/.claude/skills/ directory.
"""

import logging
import re
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime
from enum import Enum
from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ralph.models.manifest import MANIFEST_VERSION, Manifest, load_manifest, save_manifest

logger = logging.getLogger(__name__)

BUNDLED_SKILLS = [
    "ralph/iteration",
    "ralph/prd",
    "ralph/tasks",
    "reviewers/code-simplifier",
    "reviewers/github-actions",
    "reviewers/language/python",
    "reviewers/release",
    "reviewers/repo-structure",
    "reviewers/test-quality",
]


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
        path: Path to the skill directory (None for package skills).
        relative_path: Relative path from skills root (e.g., "ralph/prd").
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    path: Path | None = None
    relative_path: str = ""


class SkillSyncResult(BaseModel):
    """Result of a skill sync operation.

    Contains the outcome and details of syncing a single skill.

    Attributes:
        skill_name: Name of the skill that was synced (from frontmatter).
        status: The sync status outcome.
        source_path: Path to the source skill directory (may be "package:" for bundled).
        target_path: Path to the target skill file (if synced).
        error: Error message if sync failed.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    skill_name: str
    status: SyncStatus
    source_path: Path | str
    target_path: Path | None = None
    error: str | None = None


class SkillsService(BaseModel):
    """Service for managing and syncing Claude Code skills.

    Provides methods to list, validate, and sync skills from either bundled
    package resources or a local skills/ directory to the global
    ~/.claude/skills/ directory.

    When skills_dir is None, skills are synced from bundled package resources.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    skills_dir: Path | None = None
    target_dir: Path = Path.home() / ".claude" / "skills"

    def list_local_skills(self) -> list[Path]:
        """Find all skill directories in the local skills/ directory.

        Skills are identified by the presence of a SKILL.md file.
        Supports nested directory structures like ralph/prd/ or
        reviewers/language/python/.

        Returns:
            List of paths to skill directories containing SKILL.md files.
        """
        if self.skills_dir is None or not self.skills_dir.exists():
            return []

        skill_paths: list[Path] = []

        for skill_md in self.skills_dir.rglob("SKILL.md"):
            skill_paths.append(skill_md.parent)

        return sorted(skill_paths, key=lambda p: str(p))

    def list_bundled_skills(self) -> Iterator[str]:
        """Iterate over bundled skill paths.

        Yields:
            Skill paths like 'ralph/iteration', 'reviewers/test-quality'.
        """
        yield from BUNDLED_SKILLS

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

        try:
            if self.skills_dir:
                relative_path = skill_path.relative_to(self.skills_dir).as_posix()
            else:
                relative_path = skill_path.name
        except ValueError:
            relative_path = skill_path.name

        return SkillInfo(
            name=str(name),
            description=str(description),
            path=skill_path,
            relative_path=relative_path,
        )

    def _validate_bundled_skill(self, skill_name: str) -> SkillInfo | None:
        """Validate a bundled skill has required frontmatter.

        Args:
            skill_name: The skill path (e.g., 'ralph/prd').

        Returns:
            SkillInfo if valid, None if invalid or not found.
        """
        skill_parts = skill_name.split("/")
        package_path = "ralph.skills"
        for part in skill_parts:
            package_path += f".{part.replace('-', '_')}"

        try:
            resource_files = files(package_path)
            skill_file = resource_files.joinpath("SKILL.md")

            if not skill_file.is_file():
                return None

            content = skill_file.read_text(encoding="utf-8")
            frontmatter = self._parse_frontmatter(content)

            if frontmatter is None:
                return None

            name = frontmatter.get("name")
            description = frontmatter.get("description")

            if not name or not description:
                return None

            return SkillInfo(
                name=str(name),
                description=str(description),
                path=None,
                relative_path=skill_name,
            )
        except (ModuleNotFoundError, TypeError):
            return None

    def sync_skill(self, skill_path: Path) -> SkillSyncResult:
        """Sync a single skill from filesystem to the global skills directory.

        Creates a skill directory at ~/.claude/skills/{skill_name}/ containing
        the SKILL.md file. The skill name is parsed from the frontmatter.

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

        target_dir = self.target_dir / skill_info.name
        target_file = target_dir / "SKILL.md"
        status = SyncStatus.UPDATED if target_dir.exists() else SyncStatus.CREATED

        try:
            target_dir.mkdir(parents=True, exist_ok=True)

            source_file = skill_path / "SKILL.md"
            content = source_file.read_text(encoding="utf-8")
            target_file.write_text(content, encoding="utf-8")

            return SkillSyncResult(
                skill_name=skill_info.name,
                status=status,
                source_path=skill_path,
                target_path=target_dir,
            )
        except OSError as e:
            return SkillSyncResult(
                skill_name=skill_info.name,
                status=SyncStatus.SKIPPED,
                source_path=skill_path,
                error=str(e),
            )

    def _sync_bundled_skill(self, skill_name: str) -> SkillSyncResult:
        """Sync a single bundled skill to the global skills directory.

        Creates a skill directory at ~/.claude/skills/{skill_name}/ containing
        the SKILL.md file. The skill name is parsed from the frontmatter.

        Args:
            skill_name: The skill path (e.g., 'ralph/prd').

        Returns:
            SkillSyncResult with the sync status and details.
        """
        skill_info = self._validate_bundled_skill(skill_name)

        if skill_info is None:
            return SkillSyncResult(
                skill_name=skill_name,
                status=SyncStatus.INVALID,
                source_path=f"package:ralph.skills.{skill_name}",
                error="Missing or invalid SKILL.md frontmatter",
            )

        target_dir = self.target_dir / skill_info.name
        target_file = target_dir / "SKILL.md"
        status = SyncStatus.UPDATED if target_dir.exists() else SyncStatus.CREATED

        skill_parts = skill_name.split("/")
        package_path = "ralph.skills"
        for part in skill_parts:
            package_path += f".{part.replace('-', '_')}"

        try:
            resource_files = files(package_path)
            skill_file = resource_files.joinpath("SKILL.md")
            content = skill_file.read_text(encoding="utf-8")

            target_dir.mkdir(parents=True, exist_ok=True)
            target_file.write_text(content, encoding="utf-8")

            return SkillSyncResult(
                skill_name=skill_info.name,
                status=status,
                source_path=f"package:{package_path}",
                target_path=target_dir,
            )
        except (OSError, ModuleNotFoundError) as e:
            return SkillSyncResult(
                skill_name=skill_info.name,
                status=SyncStatus.SKIPPED,
                source_path=f"package:{package_path}",
                error=str(e),
            )

    def sync_all(self) -> list[SkillSyncResult]:
        """Sync all valid skills to the global skills directory.

        When skills_dir is None, syncs bundled package skills.
        When skills_dir is set, syncs from the local filesystem.

        Before syncing, cleans up old flat-structure skills from v1 manifests.
        After syncing, writes a manifest file to track installed skills.

        Returns:
            List of SkillSyncResult for each skill processed.
        """
        self._cleanup_old_skills()

        results: list[SkillSyncResult] = []

        if self.skills_dir is None:
            for skill_name in self.list_bundled_skills():
                result = self._sync_bundled_skill(skill_name)
                results.append(result)
        else:
            skill_paths = self.list_local_skills()
            for skill_path in skill_paths:
                result = self.sync_skill(skill_path)
                results.append(result)

        self._write_manifest(results)

        return results

    def _cleanup_old_skills(self) -> list[str]:
        """Clean up old skills from previous manifest versions.

        Reads the existing manifest and removes skills installed with old formats:
        - Version 1: flat directory names like "ralph-prd"
        - Version 2: nested directory paths like "ralph/prd"

        Returns:
            List of old skill names that were removed.
        """
        manifest_path = self.target_dir / ".ralph-manifest.json"
        manifest = load_manifest(manifest_path)

        if manifest is None:
            return []

        if manifest.version >= MANIFEST_VERSION:
            return []

        removed: list[str] = []

        for skill_name in manifest.installed:
            skill_dir = self.target_dir / skill_name
            if skill_dir.exists() and skill_dir.is_dir():
                try:
                    shutil.rmtree(skill_dir)
                    removed.append(skill_name)
                    # For v2 nested paths like "ralph/prd", clean up empty parents
                    if "/" in skill_name:
                        self._cleanup_empty_parents(skill_dir.parent)
                    logger.info(f"Cleaned up old skill: {skill_name}")
                except OSError as e:
                    logger.warning(f"Failed to remove old skill {skill_name}: {e}")

        return removed

    def _write_manifest(self, results: list[SkillSyncResult]) -> None:
        """Write a manifest file to track installed skills.

        Creates a .ralph-manifest.json file in the target directory
        containing the list of successfully installed skill names.
        Uses manifest version 3 which stores flat skill names from frontmatter.

        Args:
            results: List of sync results to extract installed skills from.
        """
        installed_skills: list[str] = []
        for result in results:
            if result.status in (SyncStatus.CREATED, SyncStatus.UPDATED):
                installed_skills.append(result.skill_name)

        manifest = Manifest(
            version=MANIFEST_VERSION,
            installed=sorted(installed_skills),
            syncedAt=datetime.now(UTC).isoformat(),
        )

        self.target_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = self.target_dir / ".ralph-manifest.json"
        save_manifest(manifest, manifest_path)

    def remove_skills(self) -> list[str]:
        """Remove skills listed in the manifest file.

        Reads the .ralph-manifest.json file from the target directory and
        removes the skill directories that are listed in it. Then
        deletes the manifest file itself.

        Handles all manifest versions:
        - v1: flat directory names like "ralph-prd"
        - v2: nested directory paths like "ralph/prd"
        - v3: flat directory names like "ralph-iteration" (skill name from frontmatter)

        This operation is idempotent - no error if skills are already removed.

        Returns:
            List of skill names that were removed.
        """
        manifest_path = self.target_dir / ".ralph-manifest.json"
        manifest = load_manifest(manifest_path)

        if manifest is None:
            return []

        removed: list[str] = []

        for skill_name in manifest.installed:
            skill_dir = self.target_dir / skill_name
            if skill_dir.exists() and skill_dir.is_dir():
                try:
                    shutil.rmtree(skill_dir)
                    removed.append(skill_name)
                    # For v2 nested paths like "ralph/prd", clean up empty parents
                    if "/" in skill_name:
                        self._cleanup_empty_parents(skill_dir.parent)
                except OSError as e:
                    logger.warning(f"Failed to remove skill {skill_name}: {e}")

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
                if directory.exists() and not any(directory.iterdir()):
                    directory.rmdir()
                    logger.debug(f"Removed empty directory: {directory}")
                else:
                    break
            except OSError:
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
