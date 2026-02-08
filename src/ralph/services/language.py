"""Language detection service for identifying project languages.

This module provides functionality to auto-detect programming languages
used in a project based on marker files like pyproject.toml, package.json, etc.
"""

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class Language(str, Enum):
    """Programming languages that can be detected."""

    python = "python"
    javascript = "javascript"
    typescript = "typescript"
    go = "go"
    rust = "rust"
    bicep = "bicep"


_LANGUAGE_MARKERS: dict[str, set[Language]] = {
    "pyproject.toml": {Language.python},
    "setup.py": {Language.python},
    "requirements.txt": {Language.python},
    "package.json": {Language.javascript},
    "tsconfig.json": {Language.typescript},
    "go.mod": {Language.go},
    "Cargo.toml": {Language.rust},
}

_LANGUAGE_PATTERNS: dict[str, set[Language]] = {
    "**/*.bicep": {Language.bicep},
}


class LanguageDetector(BaseModel):
    """Service for detecting programming languages in a project.

    Detects languages based on the presence of marker files in the project root.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    project_root: Path

    def detect(self) -> set[Language]:
        """Detect all programming languages used in the project.

        Scans the project root for language marker files and glob patterns,
        returning a set of all detected languages.

        Returns:
            Set of detected Language values. May be empty if no markers found.
        """
        detected: set[Language] = set()

        for marker_file, languages in _LANGUAGE_MARKERS.items():
            marker_path = self.project_root / marker_file
            if marker_path.exists():
                detected.update(languages)

        for pattern, languages in _LANGUAGE_PATTERNS.items():
            matches = list(self.project_root.glob(pattern))
            if matches:
                detected.update(languages)

        return detected

    def has_language(self, language: Language) -> bool:
        """Check if a specific language is detected in the project.

        Args:
            language: The language to check for.

        Returns:
            True if the language is detected, False otherwise.
        """
        return language in self.detect()


def detect_languages(project_root: Path) -> set[Language]:
    """Detect all programming languages in a project directory.

    Convenience function that creates a LanguageDetector and detects languages.

    Args:
        project_root: Path to the project root directory.

    Returns:
        Set of detected Language values.
    """
    detector = LanguageDetector(project_root=project_root)
    return detector.detect()
