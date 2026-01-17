# Ralph CLI Specification

## Metadata

- **Status:** Draft
- **Version:** 1.0.0
- **Last Updated:** 2025-01-17
- **Owner:** To be assigned

---

## 1. Context and Goals

### 1.1 Problem Statement

AI coding agents have context limits that prevent completing large features in a single session. The existing Ralph implementation (for Amp) solves this by breaking work into small, autonomous iterations—but it relies on a fragmented mix of bash scripts and manual commands that is difficult to maintain, extend, and use.

Developers need a clean, unified CLI tool that implements the Ralph autonomous iteration pattern for Claude Code, with proper project structure, intuitive commands, and a polished terminal experience.

### 1.2 Business and Product Goals

1. Provide a single, well-designed Python CLI (`ralph`) that wraps the entire autonomous coding workflow
2. Integrate natively with Claude Code's skill system for maintainable, version-controlled prompts
3. Enable developers to go from idea → PRD → tasks → implementation with minimal friction
4. Maintain memory across iterations via structured files (`PROGRESS.txt`, `CLAUDE.md`, `AGENTS.md`)
5. Deliver a polished TUI experience using Rich, with sensible defaults and clear feedback

### 1.3 User Personas and Stories

#### Persona: Solo Developer

A developer working on personal or small-team projects who wants to leverage AI for autonomous feature implementation without babysitting each step.

**Stories:**

- As a developer, I want to run `ralph init` in my project so that I have the correct file structure for autonomous iteration.
- As a developer, I want to run `ralph prd` to interactively create a detailed specification with Claude's help.
- As a developer, I want to run `ralph tasks SPEC.md` to automatically convert my specification into executable tasks.
- As a developer, I want to run `ralph loop` and walk away, trusting that Ralph will complete as many stories as possible.
- As a developer, I want to run `ralph sync` to update my global Claude Code skills from my local repo.

#### Persona: AI-Assisted Workflow Enthusiast

A developer experimenting with AI-driven development patterns who wants fine-grained control over the iteration process.

**Stories:**

- As a developer, I want to run `ralph once` to execute a single iteration so I can review progress incrementally.
- As a developer, I want to pass `--verbose` to see the full JSON stream from Claude Code for debugging.
- As a developer, I want to configure max fix attempts so I can tune how persistent Ralph is when tests fail.

### 1.4 Scope

#### In Scope

| Area | Details |
|------|---------|
| CLI Commands | `init`, `prd`, `tasks`, `once`, `loop`, `sync` |
| Skills | `ralph-prd`, `ralph-tasks`, `ralph-iteration` installed to `~/.claude/skills/` |
| Project Scaffolding | `plans/` directory, `CLAUDE.md`, `AGENTS.md`, placeholder files |
| Task Format | `TASKS.json` following original Ralph `prd.json` schema |
| Quality Checks | Defined in `CLAUDE.md` (hybrid structured + natural language) |
| Error Handling | Fix loop with configurable retry attempts |
| Branch Management | Automatic branch creation, checkout, and commits |
| Memory System | `PROGRESS.txt` (append-only), `CLAUDE.md` + `AGENTS.md` (pattern updates) |
| TUI | Minimal Rich styling; `--verbose` for full JSON stream |

#### Out of Scope (v1.0)

| Area | Rationale |
|------|-----------|
| Web UI / Dashboard | CLI-only for simplicity |
| Cloud Sync / Remote State | Purely local operation |
| Multi-Project Management | One project at a time |
| Parallel Iterations | Sequential execution only |
| External Issue Tracker Integration | No Jira, Linear, GitHub Issues, etc. |

### 1.5 Assumptions and Dependencies

#### Assumptions

1. User has Claude Code CLI installed and authenticated
2. User has a git repository initialized in their project
3. User has Python 3.11+ installed
4. User's project has some form of test/lint commands (detected or manually configured)

#### Dependencies

| Dependency | Purpose |
|------------|---------|
| Claude Code CLI | Core AI agent execution |
| Git | Version control, branch management, memory via commits |
| Python 3.11+ | Runtime |
| uv | Package/project management |
| Typer | CLI framework |
| Rich | Terminal styling and output |
| Pydantic | Data validation and settings |
| ruff | Linting and formatting |
| pytest | Testing |

---

## 2. Functional Requirements

### 2.1 Command: `ralph init`

**Purpose:** Scaffold a project for Ralph-based autonomous development.

| ID | Requirement |
|----|-------------|
| FR-INIT-01 | Create `plans/` directory if it does not exist |
| FR-INIT-02 | Create `plans/SPEC.md` with placeholder content marked "to be overwritten" |
| FR-INIT-03 | Create `plans/TASKS.json` with placeholder content marked "to be overwritten" |
| FR-INIT-04 | Create `plans/PROGRESS.txt` with placeholder content marked "to be overwritten" |
| FR-INIT-05 | Create `CLAUDE.md` in project root with Ralph workflow instructions, marked "do not overwrite" |
| FR-INIT-06 | Create `AGENTS.md` in project root with Ralph workflow instructions, marked "do not overwrite" |
| FR-INIT-07 | Detect project type (e.g., Node.js, Python, Go) and populate `CLAUDE.md` with appropriate default test/lint commands |
| FR-INIT-08 | `CLAUDE.md` must contain a structured, parseable section for quality checks (see Section 4.3) |
| FR-INIT-09 | Invoke Claude Code's native `/init` command with instructions to enhance both `CLAUDE.md` and `AGENTS.md` with project-specific context |
| FR-INIT-10 | Display success message with next steps after scaffolding completes |

### 2.2 Command: `ralph prd`

**Purpose:** Launch an interactive PRD creation session with Claude Code.

| ID | Requirement |
|----|-------------|
| FR-PRD-01 | Launch Claude Code in interactive mode |
| FR-PRD-02 | Include prompt instructing Claude to "Use the ralph-prd skill" |
| FR-PRD-03 | The `ralph-prd` skill guides Claude through clarifying questions and PRD generation |
| FR-PRD-04 | Output file is `plans/SPEC.md` |
| FR-PRD-05 | Display informational message before launching Claude Code |

### 2.3 Command: `ralph tasks <spec-file>`

**Purpose:** Convert a specification document into executable tasks.

| ID | Requirement |
|----|-------------|
| FR-TASKS-01 | Accept a file path argument (e.g., `plans/SPEC.md`) |
| FR-TASKS-02 | Invoke Claude Code in non-interactive print mode (`-p`) |
| FR-TASKS-03 | Include prompt instructing Claude to "Use the ralph-tasks skill" |
| FR-TASKS-04 | Pass the spec file content to Claude Code |
| FR-TASKS-05 | Output file is `plans/TASKS.json` |
| FR-TASKS-06 | Validate output against TASKS.json schema (Pydantic) before writing |
| FR-TASKS-07 | Display success message with task count after completion |

### 2.4 Command: `ralph once`

**Purpose:** Execute a single iteration (one user story).

| ID | Requirement |
|----|-------------|
| FR-ONCE-01 | Read `plans/TASKS.json` to find highest-priority story where `passes: false` |
| FR-ONCE-02 | If no stories remain, display "All stories complete" and exit |
| FR-ONCE-03 | Invoke Claude Code in non-interactive print mode (`-p`) |
| FR-ONCE-04 | Include prompt instructing Claude to "Use the ralph-iteration skill" |
| FR-ONCE-05 | Stream Claude's text output to terminal in real-time (default) |
| FR-ONCE-06 | With `--verbose` / `-v`, stream full parsed JSON output instead |
| FR-ONCE-07 | Claude implements the story and runs quality checks defined in `CLAUDE.md` |
| FR-ONCE-08 | If quality checks fail, Claude attempts to fix and re-run (fix loop) |
| FR-ONCE-09 | Fix loop limited to `--max-fix-attempts` (default: 3) |
| FR-ONCE-10 | If checks pass, Claude commits with message format: `feat: [Story ID] - [Story Title]` |
| FR-ONCE-11 | Update `plans/TASKS.json` to set `passes: true` for completed story |
| FR-ONCE-12 | Append iteration summary to `plans/PROGRESS.txt` |
| FR-ONCE-13 | Update both `CLAUDE.md` and `AGENTS.md` with any discovered patterns (kept in sync) |
| FR-ONCE-14 | Display success/failure summary after iteration completes |

### 2.5 Command: `ralph loop [iterations]`

**Purpose:** Run multiple iterations until completion or limit reached.

| ID | Requirement |
|----|-------------|
| FR-LOOP-01 | Accept optional `iterations` argument (default: 10) |
| FR-LOOP-02 | Read `plans/TASKS.json` to get current state |
| FR-LOOP-03 | Check/create feature branch from `branchName` field in TASKS.json |
| FR-LOOP-04 | Execute iterations sequentially, each following `ralph once` logic |
| FR-LOOP-05 | Display iteration counter (e.g., "Iteration 3 of 10") |
| FR-LOOP-06 | Stream Claude's text output in real-time (default) |
| FR-LOOP-07 | With `--verbose` / `-v`, stream full parsed JSON output instead |
| FR-LOOP-08 | Support `--max-fix-attempts N` flag (default: 3) |
| FR-LOOP-09 | **Stop Condition - Success:** All stories have `passes: true` → exit cleanly with success message |
| FR-LOOP-10 | **Stop Condition - Max Iterations:** Reached limit → exit with warning |
| FR-LOOP-11 | **Stop Condition - Persistent Failure:** Quality checks fail after N fix attempts → exit with error |
| FR-LOOP-12 | **Stop Condition - Transient Failure:** Network/rate limit fails after 1 retry → exit with error |
| FR-LOOP-13 | **Stop Condition - Claude Cannot Complete:** Claude indicates it cannot finish → exit with error |
| FR-LOOP-14 | Archive previous run if `branchName` differs from last run (same behavior as original Ralph) |

### 2.6 Command: `ralph sync`

**Purpose:** Synchronize local skill definitions to global Claude Code skills directory.

| ID | Requirement |
|----|-------------|
| FR-SYNC-01 | Read skills from repo's `skills/` directory |
| FR-SYNC-02 | Copy skill folders to `~/.claude/skills/` |
| FR-SYNC-03 | Overwrite existing skills with same name |
| FR-SYNC-04 | Display list of synced skills with status (created/updated) |
| FR-SYNC-05 | Validate each SKILL.md has required frontmatter (`name`, `description`) before copying |

### 2.7 Branch Management

| ID | Requirement |
|----|-------------|
| FR-BRANCH-01 | On `ralph loop` start, check if on correct branch (from `branchName` in TASKS.json) |
| FR-BRANCH-02 | If not on correct branch, checkout or create from main/master |
| FR-BRANCH-03 | Commits happen automatically after each successful story |
| FR-BRANCH-04 | Commit message format: `feat: [Story ID] - [Story Title]` |
| FR-BRANCH-05 | Archive previous run files when starting a new feature (different `branchName`) |
| FR-BRANCH-06 | Archive location: `archive/YYYY-MM-DD-<feature-name>/` |

### 2.8 Memory System

| ID | Requirement |
|----|-------------|
| FR-MEM-01 | `plans/PROGRESS.txt` is append-only; each iteration adds a summary block |
| FR-MEM-02 | Progress block includes: timestamp, story ID, thread URL, changes made, learnings |
| FR-MEM-03 | A "Codebase Patterns" section at top of `PROGRESS.txt` consolidates key reusable learnings |
| FR-MEM-04 | `CLAUDE.md` and `AGENTS.md` are updated with discovered patterns after each iteration |
| FR-MEM-05 | Both files must be kept in sync (same patterns in both) |

---

## 3. Non-Functional Requirements

### 3.1 Performance

| ID | Requirement |
|----|-------------|
| NFR-PERF-01 | CLI commands (`init`, `sync`) complete in < 5 seconds (excluding Claude Code invocation) |
| NFR-PERF-02 | Streaming output has < 500ms latency from Claude Code output to terminal display |

### 3.2 Usability

| ID | Requirement |
|----|-------------|
| NFR-USE-01 | All commands support `--help` with clear descriptions and examples |
| NFR-USE-02 | Error messages are actionable (explain what went wrong and suggest fixes) |
| NFR-USE-03 | Terminal output uses Rich styling: colors, spinners, tables where appropriate |
| NFR-USE-04 | Minimal formatting by default; verbose output opt-in via `--verbose` |

### 3.3 Reliability

| ID | Requirement |
|----|-------------|
| NFR-REL-01 | Graceful handling of missing files (e.g., TASKS.json not found → clear error) |
| NFR-REL-02 | Partial state is preserved on failure (completed stories remain marked as `passes: true`) |
| NFR-REL-03 | Git operations fail safely (no partial commits) |

### 3.4 Maintainability

| ID | Requirement |
|----|-------------|
| NFR-MAINT-01 | Code formatted with ruff |
| NFR-MAINT-02 | Type hints on all public functions |
| NFR-MAINT-03 | Pydantic models for all data structures (TASKS.json, config) |
| NFR-MAINT-04 | Test coverage > 70% for core logic |

---

## 4. Technical Specifications

### 4.1 Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| CLI Framework | Typer |
| Terminal UI | Rich |
| Data Validation | Pydantic |
| Package Management | uv |
| Linting/Formatting | ruff |
| Testing | pytest |
| Claude Integration | Claude Code CLI (subprocess) |

### 4.2 Project Structure

```
ralph/
├── pyproject.toml
├── README.md
├── src/
│   └── ralph/
│       ├── __init__.py
│       ├── cli.py              # Typer app, command definitions
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── init.py         # ralph init
│       │   ├── prd.py          # ralph prd
│       │   ├── tasks.py        # ralph tasks
│       │   ├── once.py         # ralph once
│       │   ├── loop.py         # ralph loop
│       │   └── sync.py         # ralph sync
│       ├── models/
│       │   ├── __init__.py
│       │   ├── tasks.py        # TASKS.json Pydantic model
│       │   └── config.py       # Configuration models
│       ├── services/
│       │   ├── __init__.py
│       │   ├── claude.py       # Claude Code CLI wrapper
│       │   ├── git.py          # Git operations
│       │   ├── scaffold.py     # Project scaffolding
│       │   └── skills.py       # Skill sync logic
│       └── utils/
│           ├── __init__.py
│           ├── console.py      # Rich console utilities
│           └── files.py        # File operations
├── skills/
│   ├── ralph-prd/
│   │   └── SKILL.md
│   ├── ralph-tasks/
│   │   └── SKILL.md
│   └── ralph-iteration/
│       └── SKILL.md
└── tests/
    ├── __init__.py
    ├── test_cli.py
    ├── test_models.py
    └── test_services/
        ├── __init__.py
        ├── test_claude.py
        ├── test_git.py
        └── test_scaffold.py
```

### 4.3 CLAUDE.md Quality Check Format

`CLAUDE.md` contains a hybrid format: a structured block that Ralph parses, plus natural language context for Claude Code.

**Structured section (parseable by Ralph):**

```markdown
## Quality Checks

<!-- RALPH:CHECKS:START -->
```yaml
checks:
  - name: typecheck
    command: npm run typecheck
    required: true
  - name: lint
    command: npm run lint
    required: true
  - name: test
    command: npm test
    required: true
```
<!-- RALPH:CHECKS:END -->

Run all checks before committing. If any required check fails, fix the issue and re-run.
```

**Parsing rules:**
- Ralph extracts YAML between `<!-- RALPH:CHECKS:START -->` and `<!-- RALPH:CHECKS:END -->`
- Each check has: `name`, `command`, `required` (boolean)
- Checks run in order; all `required: true` must pass

### 4.4 TASKS.json Schema

```json
{
  "project": "string",
  "branchName": "string (e.g., ralph/feature-name)",
  "description": "string",
  "userStories": [
    {
      "id": "string (e.g., US-001)",
      "title": "string",
      "description": "string",
      "acceptanceCriteria": ["string"],
      "priority": "integer (1 = highest)",
      "passes": "boolean",
      "notes": "string"
    }
  ]
}
```

**Pydantic model:**

```python
from pydantic import BaseModel

class UserStory(BaseModel):
    id: str
    title: str
    description: str
    acceptanceCriteria: list[str]
    priority: int
    passes: bool = False
    notes: str = ""

class TasksFile(BaseModel):
    project: str
    branchName: str
    description: str
    userStories: list[UserStory]
```

### 4.5 Claude Code Integration

**Invocation patterns:**

| Command | Claude Code Invocation |
|---------|------------------------|
| `ralph prd` | `claude` (interactive) with stdin prompt |
| `ralph tasks` | `claude -p "..."` (print mode) |
| `ralph once` | `claude -p "..."` (print mode) |
| `ralph loop` | Repeated `claude -p "..."` calls |

**Prompt structure:**

```
Use the {skill-name} skill to {task description}.

{Additional context as needed}
```

**Output handling:**

- Default: Parse Claude Code's streaming output, display text portions
- Verbose: Display full JSON stream, pretty-printed with Rich

### 4.6 Skill Definitions

Skills are stored in `skills/` directory and synced to `~/.claude/skills/`.

**ralph-prd/SKILL.md:**

```markdown
---
name: ralph-prd
description: "Create a detailed Product Requirements Document (PRD). Use when the user wants to define a new feature, write requirements, or create a specification. Outputs to plans/SPEC.md."
---

# PRD Generator

[Detailed instructions for PRD creation, based on original skill]
```

**ralph-tasks/SKILL.md:**

```markdown
---
name: ralph-tasks
description: "Convert a PRD/specification document into TASKS.json format for Ralph autonomous execution. Use when converting specs to executable tasks."
---

# Task Converter

[Detailed instructions for spec-to-tasks conversion, based on original skill]
```

**ralph-iteration/SKILL.md:**

```markdown
---
name: ralph-iteration
description: "Execute a single user story from TASKS.json. Implements the story, runs quality checks, fixes failures, commits on success, and updates progress files."
---

# Ralph Iteration

[Detailed instructions for single iteration execution, based on original prompt.md]
```

### 4.7 Development Standards

| Standard | Specification |
|----------|---------------|
| Python version | 3.11+ |
| Formatting | ruff format |
| Linting | ruff check |
| Type checking | pyright or mypy (optional, recommended) |
| Testing | pytest with pytest-cov |
| Commit style | Conventional commits |

---

## 5. Open Questions

| ID | Question | Impact | Owner |
|----|----------|--------|-------|
| OQ-01 | Should `ralph init` prompt interactively for project type, or always auto-detect? | UX for edge cases | TBD |
| OQ-02 | What happens if user runs `ralph loop` without running `ralph init` first? | Error handling | TBD |
| OQ-03 | Should there be a `ralph status` command to show current progress? | Feature scope | TBD |
| OQ-04 | How should `ralph sync` handle skill version conflicts? | Sync behavior | TBD |
| OQ-05 | Should skills include bundled scripts (e.g., for validation), or be pure markdown? | Skill complexity | TBD |

---

## Appendix A: Command Reference

```
ralph init                      Scaffold project for Ralph workflow
ralph prd                       Interactive PRD creation session
ralph tasks <spec-file>         Convert spec to TASKS.json
ralph once                      Execute single iteration
ralph loop [iterations]         Run loop (default: 10 iterations)
ralph sync                      Sync skills to ~/.claude/skills/

Global flags:
  --help, -h                    Show help message
  --version                     Show version

Loop/Once flags:
  --verbose, -v                 Show full JSON stream output
  --max-fix-attempts N          Max quality check fix attempts (default: 3)
```

---

## Appendix B: File Templates

### plans/SPEC.md (placeholder)

```markdown
# Specification

> **This file will be overwritten.** Run `ralph prd` to generate your specification.

## Instructions

1. Run `ralph prd` to start an interactive PRD session
2. Answer Claude's clarifying questions
3. Review the generated specification
4. Run `ralph tasks plans/SPEC.md` to convert to tasks
```

### plans/TASKS.json (placeholder)

```json
{
  "_comment": "This file will be overwritten. Run 'ralph tasks plans/SPEC.md' to generate tasks.",
  "project": "",
  "branchName": "",
  "description": "",
  "userStories": []
}
```

### plans/PROGRESS.txt (placeholder)

```
# Ralph Progress Log

> **This file will be overwritten.** Progress entries are appended automatically during iterations.

## Codebase Patterns

(Patterns discovered during iterations will be consolidated here)

---
```

---

## Appendix C: Success Criteria Checklist

| # | Criterion | Verified |
|---|-----------|----------|
| 1 | `ralph init` scaffolds project with all expected files | ☐ |
| 2 | `ralph prd` launches Claude Code, user creates spec, outputs to `plans/SPEC.md` | ☐ |
| 3 | `ralph tasks plans/SPEC.md` converts spec to valid `plans/TASKS.json` | ☐ |
| 4 | `ralph once` completes one story (or fails gracefully with clear error) | ☐ |
| 5 | `ralph loop` runs to completion on a small test PRD (3-4 stories) | ☐ |
| 6 | `ralph sync` copies skills to `~/.claude/skills/` successfully | ☐ |
| 7 | All commands have `--help` with clear documentation | ☐ |
| 8 | Test suite passes with reasonable coverage (>70%) | ☐ |

---

## 6. Version 1.1: Bug Fixes & Automation Improvements

**Status:** Draft
**Date:** 2026-01-17

### 6.1 Overview

Testing revealed three issues preventing reliable autonomous operation and automation workflows. This section addresses bugs that block the core autonomous iteration loop from functioning properly.

**Problem Statement:**
1. The `ralph prd` command requires interactive terminal input, preventing automation
2. The `ralph prd` command reports success even when no changes were made
3. The `ralph loop` and `ralph once` commands fail because the Claude subprocess lacks write permissions

### 6.2 Goals

1. **Enable autonomous iteration** - The `ralph loop` and `ralph once` commands must run Claude with appropriate permissions without human intervention
2. **Support PRD automation** - Allow `ralph prd` to accept input programmatically for CI/CD and scripting
3. **Improve feedback accuracy** - Ensure command output reflects what actually happened

### 6.3 Non-Goals

- Changing the default interactive behavior of `ralph prd`
- Adding a global configuration system
- Modifying the TASKS.json schema or iteration logic

### 6.4 Functional Requirements

#### FR-FIX-01: Add `--dangerously-skip-permissions` Support for Autonomous Commands

**Priority: Critical**

| ID | Requirement |
|----|-------------|
| FR-FIX-01.1 | Add `skip_permissions: bool = False` parameter to `ClaudeService.run_print_mode()` |
| FR-FIX-01.2 | When `skip_permissions=True`, include `--dangerously-skip-permissions` in Claude CLI args |
| FR-FIX-01.3 | `ralph once` calls `run_print_mode()` with `skip_permissions=True` by default |
| FR-FIX-01.4 | `ralph loop` calls `run_print_mode()` with `skip_permissions=True` by default |
| FR-FIX-01.5 | Display one-time info message: "Running Claude with auto-approved permissions for autonomous iteration" |
| FR-FIX-01.6 | The flag is NOT applied to other commands (`prd`, `tasks`, etc.) |

**File:** `src/ralph/services/claude.py` (line ~186, `run_print_mode` method)

#### FR-FIX-02: Add Non-Interactive Input Options to `ralph prd`

**Priority: High**

| ID | Requirement |
|----|-------------|
| FR-FIX-02.1 | Add `--input` / `-i` option accepting a feature description string |
| FR-FIX-02.2 | Add `--file` / `-f` option accepting a path to a file with the description |
| FR-FIX-02.3 | `--input` and `--file` are mutually exclusive; error if both provided |
| FR-FIX-02.4 | When either flag is provided, run in non-interactive mode (single prompt) |
| FR-FIX-02.5 | When neither flag is provided, maintain current interactive behavior |

**Examples:**
```bash
ralph prd --input "A pomodoro timer CLI with Rich output"
ralph prd --file ./feature-idea.txt
```

#### FR-FIX-03: Accurate Success/Failure Reporting for `ralph prd`

**Priority: Medium**

| ID | Requirement |
|----|-------------|
| FR-FIX-03.1 | Before running Claude, record the mtime of `plans/SPEC.md` (if it exists) |
| FR-FIX-03.2 | After Claude completes, compare the new mtime or check if file now exists |
| FR-FIX-03.3 | If file was created/modified: display "PRD saved to plans/SPEC.md" |
| FR-FIX-03.4 | If file was NOT modified: display warning "Warning: PRD file was not modified. The session may have ended before completion." |
| FR-FIX-03.5 | Exit with code 0 in both cases (warning only, not error) |
| FR-FIX-03.6 | Warning message uses Rich warning styling (yellow) |

### 6.5 Technical Considerations

#### Files to Modify

| Requirement | File(s) |
|-------------|---------|
| FR-FIX-01 | `src/ralph/services/claude.py`, `src/ralph/commands/once.py`, `src/ralph/commands/loop.py` |
| FR-FIX-02 | `src/ralph/commands/prd.py`, `src/ralph/cli.py` |
| FR-FIX-03 | `src/ralph/commands/prd.py` |

#### Testing Strategy

- Unit tests for `ClaudeService.run_print_mode()` with `skip_permissions=True`
- Integration tests for `ralph prd --input` and `ralph prd --file`
- Tests for file modification detection logic
- Manual testing of full autonomous loop

### 6.6 Success Criteria

| # | Criterion | Verified |
|---|-----------|----------|
| 1 | `ralph once` completes an iteration without permission prompts | ☐ |
| 2 | `ralph loop 3` completes 3 iterations without human intervention | ☐ |
| 3 | `ralph prd --input "description"` generates a complete PRD | ☐ |
| 4 | `ralph prd --file path.txt` reads file and generates PRD | ☐ |
| 5 | Failed/incomplete PRD session shows warning message | ☐ |
| 6 | Existing interactive `ralph prd` workflow unchanged | ☐ |

### 6.7 Reference

- Original bug reports: `/Users/jack/Projects/ralph_cli/TESTING.txt`