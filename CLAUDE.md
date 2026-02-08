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

## Reviewers

<!-- RALPH:REVIEWERS:START -->
```yaml
reviewers:
  - name: test-quality
    skill: reviewers/test-quality
    level: blocking
  - name: code-simplifier
    skill: reviewers/code-simplifier
    level: blocking
  - name: python-code
    skill: reviewers/language/python
    languages: [python]
    level: blocking
  - name: github-actions
    skill: reviewers/github-actions
    level: warning
  - name: repo-structure
    skill: reviewers/repo-structure
    level: warning
  - name: release
    skill: reviewers/release
    level: blocking
```
<!-- RALPH:REVIEWERS:END -->

Reviewers run automatically after `ralph loop` completes all stories. Configure the review pipeline above.

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
│       ├── skills/             # Bundled skill definitions (packaged)
│       │   ├── ralph/          # Core workflow skills
│       │   │   ├── iteration/
│       │   │   ├── prd/
│       │   │   └── tasks/
│       │   └── reviewers/      # Review pipeline skills
│       │       ├── code_simplifier/
│       │       ├── github_actions/
│       │       ├── language/
│       │       │   ├── bicep/
│       │       │   └── python/
│       │       ├── release/
│       │       ├── repo_structure/
│       │       └── test_quality/
│       └── utils/              # Console and file utilities
└── tests/
```

**Note:** Skills are bundled with the package for immediate use after `pip install ralph-cli`. Use `ralph sync` to copy them to `~/.claude/skills/` for native Claude Code integration.

## Codebase Patterns

(Keep in sync with AGENTS.md)

- Use Pydantic `BaseModel` for all classes, NOT stdlib `@dataclass` - this is a Pydantic project
- Use `ConfigDict(arbitrary_types_allowed=True)` when fields use types like `Path` or `TextIO`
- Use Pydantic `alias` with `populate_by_name=True` when JSON uses camelCase but Python should use snake_case
- Use `by_alias=True` in `model_dump_json()` to serialize back to the original JSON format
- Import `Iterator`, `Sequence`, etc. from `collections.abc` instead of `typing` (ruff UP035)
- Use `X | None` instead of `Optional[X]` for type annotations (ruff UP045)
- Use `ClassVar[T]` from `typing` for class-level constants in Pydantic `BaseModel` classes to avoid them being treated as fields
- When calling Typer command functions directly (not through CLI), pass all Option parameters explicitly since Typer defaults are not applied programmatically
- **Prompt construction**: Use `@filepath` notation with `build_skill_prompt()` to reference bundled skill files directly, reducing token usage. The function uses `SkillLoader.get_path()` to get the actual filesystem path to SKILL.md files. Example: `build_skill_prompt("ralph/prd", context)` produces `@/path/to/skills/ralph/prd/SKILL.md`

## Project-Specific Instructions

### Commands

The CLI provides these commands:
- `ralph init` - Scaffold a project for Ralph workflow
- `ralph prd` - Interactive PRD creation with Claude
- `ralph tasks <spec>` - Convert spec to TASKS.json
- `ralph once` - Execute single iteration
- `ralph loop [n]` - Run n iterations (default: 10)
- `ralph review` - Run the review pipeline with automatic configuration
- `ralph sync` - Sync skills to ~/.claude/skills/

### Key Design Decisions

1. **Subprocess for Claude Code**: Invoke `claude` CLI via subprocess, not as a library
2. **Streaming output**: Default shows text output; `--verbose` shows full JSON
3. **Branch management**: Auto-create/checkout branches from TASKS.json branchName
4. **Memory system**: PROGRESS.txt is append-only; CLAUDE.md/AGENTS.md get pattern updates

### Linear Integration

This project tracks work in [Linear](https://linear.app/jmcptest) under the **Ralph CLI** team (identifier: `RAL`).

**Hierarchy:** Project (release) > Parent Issue (feature/epic) > Sub-issue (user story)

**GitHub integration is configured with:**
- **Branch/PR linking** — PRs referencing `RAL-XX` identifiers auto-link to Linear issues
- **Magic words** — Commits with `RAL-XX` get linked via webhook
- **Public repo linkbacks** — Linear adds comments on linked GitHub PRs
- **Bidirectional GitHub Issues sync** — Issues sync between `jackemcpherson/ralph-cli` and the Ralph CLI team (note: syncs new activity, does not back-import existing issues)

**When creating PRs:**
- Reference Linear identifiers in the PR body (e.g., `RAL-1`, `RAL-15`) for automatic linking
- Use `Closes #XX` for GitHub issues to auto-close on merge
- Linear issues should be updated to Done when their stories pass

**When completing a feature branch:**
1. Mark all completed stories as Done in Linear
2. Mark parent issues as Done when all sub-issues complete
3. Update the Linear project status to Completed after release

### Release Process

When merging a release PR:
1. Update version in `pyproject.toml` and `src/ralph/__init__.py`
2. Add changelog entry to `CHANGELOG.md`
3. Merge the PR to main
4. Create and push a git tag: `git tag vX.Y.Z && git push origin vX.Y.Z`
5. Create a GitHub Release from the tag with notes from CHANGELOG.md
6. Update the Linear project description (link to release) and set status to Completed
7. Clean up local and remote feature branches: `git branch -d <branch> && git fetch --prune`

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

**Reviewer configuration in CLAUDE.md:**
- Parsed from YAML between `<!-- RALPH:REVIEWERS:START -->` and `<!-- RALPH:REVIEWERS:END -->`
- Each reviewer has: name, skill (path), level (blocking/warning/suggestion)
- Optional `languages` field filters reviewer to specific languages (e.g., `[python]`)
- Levels: `blocking` = must pass, `warning` = logged (enforced with `--strict`), `suggestion` = informational
- Default reviewers used when markers not present
