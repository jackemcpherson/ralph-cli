"""Project scaffolding service for Ralph CLI.

This module provides services for scaffolding Ralph workflow files
including plans directory, CLAUDE.md, AGENTS.md, and related files.
"""

import logging
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ralph.utils import ensure_dir, write_file

logger = logging.getLogger(__name__)


# Template for fresh PROGRESS.txt file
PROGRESS_TEMPLATE = """# Ralph Progress Log

## Codebase Patterns

(Add reusable patterns discovered during iterations here)

---

## Log

(Iteration entries will be appended below)

---
"""

# Guidelines for CHANGELOG.md (shared between CLAUDE.md and AGENTS.md)
CHANGELOG_GUIDELINES = """## CHANGELOG.md

This project maintains a CHANGELOG.md for persistent memory across feature cycles.

**When to update:**
- New features or capabilities added
- Bug fixes that affect user-facing behavior
- Breaking changes or API modifications
- Performance improvements with measurable impact
- Security fixes
- Deprecations of existing functionality

**When NOT to update:**
- Internal refactoring with no behavior change
- Test additions or modifications
- Documentation-only changes
- Code style/formatting changes
- Dependency updates (unless they fix security issues or change behavior)
- Work-in-progress commits during a feature branch

**How to update:**
1. Add entries under the `[Unreleased]` section
2. Use the appropriate category: Added, Changed, Deprecated, Removed, Fixed, Security
3. Write entries from the user's perspective (what changed for them)
4. Be concise but specific (include context like file names or feature areas)"""


class ProjectType(Enum):
    """Detected project type based on marker files.

    Used to determine which quality check template to generate.

    Attributes:
        PYTHON: Python project (pyproject.toml, setup.py, requirements.txt).
        NODEJS: Node.js project (package.json).
        GO: Go project (go.mod).
        RUST: Rust project (Cargo.toml).
        UNKNOWN: No recognized project markers found.
    """

    PYTHON = "python"
    NODEJS = "nodejs"
    GO = "go"
    RUST = "rust"
    UNKNOWN = "unknown"


class ScaffoldService(BaseModel):
    """Service for scaffolding Ralph project files.

    Provides methods to create the plans/ directory structure,
    placeholder files, and configuration files for the Ralph workflow.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    project_root: Path

    def detect_project_type(self) -> ProjectType:
        """Detect the project type based on marker files.

        Checks for common project configuration files to identify
        the type of project (Python, Node.js, Go, Rust).

        Returns:
            The detected ProjectType, or UNKNOWN if none matched.
        """
        markers = {
            ProjectType.PYTHON: ["pyproject.toml", "setup.py", "requirements.txt"],
            ProjectType.NODEJS: ["package.json"],
            ProjectType.GO: ["go.mod"],
            ProjectType.RUST: ["Cargo.toml"],
        }

        for project_type, files in markers.items():
            for marker_file in files:
                if (self.project_root / marker_file).exists():
                    return project_type

        return ProjectType.UNKNOWN

    def create_plans_directory(self) -> Path:
        """Create the plans/ directory structure.

        Returns:
            Path to the created plans/ directory.
        """
        plans_dir = self.project_root / "plans"
        ensure_dir(plans_dir)
        return plans_dir

    def create_spec_placeholder(self) -> Path:
        """Create a placeholder SPEC.md file in plans/.

        Returns:
            Path to the created SPEC.md file.
        """
        spec_path = self.project_root / "plans" / "SPEC.md"
        content = """# Feature Specification

## Overview

[Describe the feature or project you want to build]

## Goals

- [Goal 1]
- [Goal 2]

## Non-Goals

- [What this feature will NOT do]

## Requirements

### Functional Requirements

1. [Requirement 1]
2. [Requirement 2]

### Non-Functional Requirements

- [Performance, security, or other constraints]

## Technical Design

### Architecture

[Describe the high-level architecture]

### Data Models

[Describe any data structures or database schemas]

### API Design

[Describe any APIs or interfaces]

## Implementation Notes

[Any additional notes for implementation]
"""
        write_file(spec_path, content)
        return spec_path

    def create_tasks_placeholder(self) -> Path:
        """Create a placeholder TASKS.json file in plans/.

        Returns:
            Path to the created TASKS.json file.
        """
        tasks_path = self.project_root / "plans" / "TASKS.json"
        content = """{
  "project": "ProjectName",
  "branchName": "ralph/feature-name",
  "description": "Description of the feature being implemented",
  "userStories": [
    {
      "id": "US-001",
      "title": "First user story",
      "description": "As a [user], I want [feature] so that [benefit]",
      "acceptanceCriteria": [
        "Criterion 1",
        "Criterion 2"
      ],
      "priority": 1,
      "passes": false,
      "notes": ""
    }
  ]
}
"""
        write_file(tasks_path, content)
        return tasks_path

    def create_progress_placeholder(self) -> Path:
        """Create a placeholder PROGRESS.txt file in plans/.

        Returns:
            Path to the created PROGRESS.txt file.
        """
        progress_path = self.project_root / "plans" / "PROGRESS.txt"
        write_file(progress_path, PROGRESS_TEMPLATE)
        return progress_path

    def create_claude_md(self, project_name: str | None = None) -> Path:
        """Create a CLAUDE.md file with quality checks template.

        Args:
            project_name: Optional project name (defaults to directory name).

        Returns:
            Path to the created CLAUDE.md file.
        """
        if project_name is None:
            project_name = self.project_root.name

        project_type = self.detect_project_type()
        checks_yaml = self._get_quality_checks_yaml(project_type)

        claude_md_path = self.project_root / "CLAUDE.md"
        content = f"""# Project Instructions

## Overview

{project_name} - [Add project description here]

## Ralph Workflow

This project is configured for Ralph—an autonomous iteration loop that completes \
user stories from `plans/TASKS.json`.

**Key files:**
- `plans/SPEC.md` - Feature specification
- `plans/TASKS.json` - Task list with completion status
- `plans/PROGRESS.txt` - Append-only iteration log

**Iteration process:**
1. Pick highest-priority story where `passes: false`
2. Implement the story
3. Run quality checks (below)
4. Fix any failures and re-run (up to 3 attempts)
5. Commit with message: `feat: [Story ID] - [Story Title]`
6. Update TASKS.json to mark `passes: true`
7. Append summary to PROGRESS.txt
8. Update this file and AGENTS.md with any discovered patterns

## Quality Checks

{checks_yaml}

Run all checks before committing. Fix any failures before proceeding.

## Technology Stack

[Update this section with your project's technology stack]

## Project Structure

[Add your project's directory structure here]

## Codebase Patterns

(Keep in sync with AGENTS.md)

[Add discovered patterns here as you iterate]

{CHANGELOG_GUIDELINES}

## Project-Specific Instructions

[Add any project-specific instructions here]
"""
        write_file(claude_md_path, content)
        return claude_md_path

    def create_changelog(self) -> Path:
        """Create a CHANGELOG.md file following Keep a Changelog format.

        The template includes an Unreleased section with standard category
        headers (Added, Changed, Deprecated, Removed, Fixed, Security).

        Returns:
            Path to the created CHANGELOG.md file.
        """
        changelog_path = self.project_root / "CHANGELOG.md"
        content = """# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security
"""
        write_file(changelog_path, content)
        return changelog_path

    def create_agents_md(self, project_name: str | None = None) -> Path:
        """Create an AGENTS.md file with Ralph workflow instructions.

        Args:
            project_name: Optional project name (defaults to directory name).

        Returns:
            Path to the created AGENTS.md file.
        """
        if project_name is None:
            project_name = self.project_root.name

        agents_md_path = self.project_root / "AGENTS.md"
        content = f"""# Agent Instructions

## Overview

{project_name} - [Add project description here]

This file contains instructions for AI agents working on this codebase.
It is kept in sync with CLAUDE.md.

## Ralph Workflow

This project uses the Ralph autonomous iteration pattern.

**Key files:**
- `plans/SPEC.md` - Feature specification
- `plans/TASKS.json` - Task list with completion status
- `plans/PROGRESS.txt` - Append-only iteration log
- `CLAUDE.md` - Claude-specific instructions and quality checks

**Iteration process:**
1. Read `plans/TASKS.json` to find the highest-priority incomplete story
2. Implement the story following acceptance criteria
3. Run quality checks defined in `CLAUDE.md`
4. Fix any failures and re-run (up to 3 attempts)
5. Commit with message: `feat: [Story ID] - [Story Title]`
6. Update `plans/TASKS.json` to mark `passes: true`
7. Append summary to `plans/PROGRESS.txt`
8. Update CLAUDE.md and this file with any discovered patterns

## Codebase Patterns

(Keep in sync with CLAUDE.md)

[Add discovered patterns here as you iterate]

{CHANGELOG_GUIDELINES}

## Guidelines

- Always read `plans/PROGRESS.txt` first to understand patterns from previous iterations
- Check CLAUDE.md for quality checks and project-specific instructions
- Work on ONE story per iteration
- Commit after each successful story
- Keep all quality checks passing
"""
        write_file(agents_md_path, content)
        return agents_md_path

    def scaffold_all(
        self, project_name: str | None = None, skip_changelog: bool = False
    ) -> dict[str, Path]:
        """Create all Ralph workflow files.

        Args:
            project_name: Optional project name (defaults to directory name).
            skip_changelog: If True, skip creating CHANGELOG.md (e.g., if it already exists).

        Returns:
            Dictionary mapping file type to created path.
        """
        self.create_plans_directory()

        result: dict[str, Path] = {
            "plans_dir": self.project_root / "plans",
            "spec": self.create_spec_placeholder(),
            "tasks": self.create_tasks_placeholder(),
            "progress": self.create_progress_placeholder(),
            "claude_md": self.create_claude_md(project_name),
            "agents_md": self.create_agents_md(project_name),
        }

        if not skip_changelog:
            result["changelog"] = self.create_changelog()

        return result

    def _get_quality_checks_yaml(self, project_type: ProjectType) -> str:
        """Get the quality checks YAML block for a project type.

        Args:
            project_type: The detected project type.

        Returns:
            YAML block with appropriate quality checks.
        """
        checks_by_type = {
            ProjectType.PYTHON: """<!-- RALPH:CHECKS:START -->
```yaml
checks:
  - name: typecheck
    command: uv run pyright
    required: true
  - name: lint
    command: uv run ruff check .
    required: true
  - name: format
    command: uv run ruff format --check .
    required: true
  - name: test
    command: uv run pytest
    required: true
```
<!-- RALPH:CHECKS:END -->""",
            ProjectType.NODEJS: """<!-- RALPH:CHECKS:START -->
```yaml
checks:
  - name: typecheck
    command: npm run typecheck
    required: true
  - name: lint
    command: npm run lint
    required: true
  - name: format
    command: npm run format:check
    required: true
  - name: test
    command: npm test
    required: true
```
<!-- RALPH:CHECKS:END -->""",
            ProjectType.GO: """<!-- RALPH:CHECKS:START -->
```yaml
checks:
  - name: build
    command: go build ./...
    required: true
  - name: vet
    command: go vet ./...
    required: true
  - name: lint
    command: golangci-lint run
    required: true
  - name: test
    command: go test ./...
    required: true
```
<!-- RALPH:CHECKS:END -->""",
            ProjectType.RUST: """<!-- RALPH:CHECKS:START -->
```yaml
checks:
  - name: build
    command: cargo build
    required: true
  - name: clippy
    command: cargo clippy -- -D warnings
    required: true
  - name: format
    command: cargo fmt --check
    required: true
  - name: test
    command: cargo test
    required: true
```
<!-- RALPH:CHECKS:END -->""",
        }

        default_checks = """<!-- RALPH:CHECKS:START -->
```yaml
checks:
  - name: lint
    command: echo "Configure your lint command"
    required: true
  - name: test
    command: echo "Configure your test command"
    required: true
```
<!-- RALPH:CHECKS:END -->"""

        return checks_by_type.get(project_type, default_checks)
