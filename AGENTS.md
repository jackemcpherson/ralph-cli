# Agent Instructions

## Overview

Ralph CLI - A Python CLI tool that implements the Ralph autonomous iteration pattern for Claude Code. This project wraps the entire autonomous coding workflow with proper project structure, intuitive commands, and a polished terminal experience.

## Ralph Workflow

**Key files:**
- `plans/SPEC.md` - Feature specification
- `plans/TASKS.json` - Task list with completion status
- `plans/PROGRESS.txt` - Append-only iteration log

**Iteration process:**
1. Read `plans/TASKS.json` and pick highest-priority incomplete story
2. Read `plans/PROGRESS.txt` for context and patterns
3. Implement the story following acceptance criteria
4. Run quality checks defined in `CLAUDE.md`
5. Commit on success: `feat: [Story ID] - [Story Title]`
6. Update TASKS.json (`passes: true`) and append to PROGRESS.txt
7. Update CLAUDE.md and AGENTS.md with discovered patterns

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| CLI Framework | Typer |
| Terminal UI | Rich |
| Data Validation | Pydantic |
| Package Management | uv |
| Linting/Formatting | ruff |
| Type Checking | pyright |
| Testing | pytest |

## Project Structure

```
ralph_cli/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── AGENTS.md
├── plans/
│   ├── SPEC.md
│   ├── TASKS.json
│   └── PROGRESS.txt
├── src/
│   └── ralph/
│       ├── __init__.py
│       ├── cli.py              # Typer app, command definitions
│       ├── commands/           # Command implementations
│       ├── models/             # Pydantic models
│       ├── services/           # Business logic (Claude, Git, etc.)
│       └── utils/              # Console and file utilities
├── skills/                     # Claude Code skill definitions
│   ├── ralph-prd/              # PRD creation skill
│   ├── ralph-tasks/            # Task breakdown skill
│   ├── ralph-iteration/        # Iteration execution skill
│   ├── python-code-reviewer/   # Python code review
│   ├── repo-structure-reviewer/# Repository structure review
│   ├── github-actions-reviewer/# CI/CD workflow review
│   └── test-quality-reviewer/  # Test quality review
└── tests/
```

## Codebase Patterns

(Keep in sync with CLAUDE.md)

- Use Pydantic `BaseModel` for all classes, NOT stdlib `@dataclass` - this is a Pydantic project
- Use `ConfigDict(arbitrary_types_allowed=True)` when fields use types like `Path` or `TextIO`
- Use Pydantic `alias` with `populate_by_name=True` when JSON uses camelCase but Python should use snake_case
- Use `by_alias=True` in `model_dump_json()` to serialize back to the original JSON format
- Import `Iterator`, `Sequence`, etc. from `collections.abc` instead of `typing` (ruff UP035)
- Use `X | None` instead of `Optional[X]` for type annotations (ruff UP045)
- Use `ClassVar[T]` from `typing` for class-level constants in Pydantic `BaseModel` classes to avoid them being treated as fields
- When calling Typer command functions directly (not through CLI), pass all Option parameters explicitly since Typer defaults are not applied programmatically

## Project-Specific Instructions

### Commands

The CLI provides these commands:
- `ralph init` - Scaffold a project for Ralph workflow
- `ralph prd` - Interactive PRD creation with Claude
- `ralph tasks <spec>` - Convert spec to TASKS.json
- `ralph once` - Execute single iteration
- `ralph loop [n]` - Run n iterations (default: 10)
- `ralph sync` - Sync skills to ~/.claude/skills/

### Key Design Decisions

1. **Subprocess for Claude Code**: Invoke `claude` CLI via subprocess, not as a library
2. **Streaming output**: Default shows text output; `--verbose` shows full JSON
3. **Branch management**: Auto-create/checkout branches from TASKS.json branchName
4. **Memory system**: PROGRESS.txt is append-only; CLAUDE.md/AGENTS.md get pattern updates

### Release Process

When merging a release PR:
1. Update version in `pyproject.toml` and `src/ralph/__init__.py`
2. Add changelog entry to `CHANGELOG.md`
3. Merge the PR to main
4. Create and push a git tag: `git tag vX.Y.Z && git push origin vX.Y.Z`

Tags must match the version in pyproject.toml (e.g., `v1.2.6` for version `1.2.6`).

### File Formats

**TASKS.json schema:**
- `project`: string
- `branchName`: string (e.g., "ralph/feature-name")
- `description`: string
- `userStories`: array of {id, title, description, acceptanceCriteria[], priority, passes, notes}

**Quality checks in CLAUDE.md:**
- Parsed from YAML between `<!-- RALPH:CHECKS:START -->` and `<!-- RALPH:CHECKS:END -->`
- Each check has: name, command, required (boolean)
