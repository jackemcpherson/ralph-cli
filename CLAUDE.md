# Project Instructions

## Overview

Ralph CLI - A Python CLI tool that implements the Ralph autonomous iteration pattern for Claude Code. This project wraps the entire autonomous coding workflow with proper project structure, intuitive commands, and a polished terminal experience.

## Ralph Workflow

This project is configured for Ralph—an autonomous iteration loop that completes user stories from `plans/TASKS.json`.

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

<!-- RALPH:CHECKS:START -->
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
<!-- RALPH:CHECKS:END -->

Run all checks before committing. Fix any failures before proceeding.

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
│   ├── ralph-prd/
│   ├── ralph-tasks/
│   └── ralph-iteration/
└── tests/
```

## Codebase Patterns

(Add patterns discovered during development here. Keep in sync with AGENTS.md.)

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

### File Formats

**TASKS.json schema:**
- `project`: string
- `branchName`: string (e.g., "ralph/feature-name")
- `description`: string
- `userStories`: array of {id, title, description, acceptanceCriteria[], priority, passes, notes}

**Quality checks in CLAUDE.md:**
- Parsed from YAML between `<!-- RALPH:CHECKS:START -->` and `<!-- RALPH:CHECKS:END -->`
- Each check has: name, command, required (boolean)
