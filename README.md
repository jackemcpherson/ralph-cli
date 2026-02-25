# Ralph CLI

A Python CLI tool that implements the Ralph autonomous iteration pattern for Claude Code. Ralph enables AI-driven development by breaking down specifications into user stories and executing them autonomously.

## Features

- **Project Scaffolding**: Initialize any project with Ralph workflow files
- **PRD Generation**: Create product requirements documents interactively with Claude
- **Task Breakdown**: Convert specifications into structured user stories
- **Autonomous Iteration**: Execute stories one at a time with quality checks
- **Loop Execution**: Run multiple iterations automatically with failure detection
- **Skills Management**: Sync custom Claude Code skills to your system
- **Code Review Skills**: Built-in reviewers for Python, repo structure, GitHub Actions, and tests

## How It Works

Ralph automates the full cycle from idea to implemented code using Claude Code:

1. **Define** — Write a PRD or spec describing what you want built (`ralph prd` helps you do this interactively with Claude)
2. **Plan** — Convert the spec into prioritised user stories with acceptance criteria (`ralph tasks plans/SPEC.md`)
3. **Build** — Ralph picks the next incomplete story, hands it to Claude Code, and runs your quality checks (typecheck, lint, tests). If checks fail, it retries automatically. On success, it commits and moves to the next story (`ralph loop`)
4. **Review** — Run automated code reviewers across the finished work (`ralph review`)

Each iteration appends to `plans/PROGRESS.txt` so you have a full log of what was done and why. Quality checks and reviewers are configured in `CLAUDE.md`, so Ralph enforces your project's standards on every story.

## Installation

### Homebrew (macOS)

```bash
brew tap jackemcpherson/tap
brew install ralph-cli
```

### PyPI

```bash
pip install ralph-cli
# or
uv pip install ralph-cli
```

### From Source

Requires Python 3.11+ and [uv](https://github.com/astral-sh/uv) package manager.

```bash
git clone https://github.com/jackemcpherson/ralph-cli.git
cd ralph-cli
uv pip install -e ".[dev]"
```

Verify installation:

```bash
ralph --version
```

## Quick Start

```bash
# 1. Initialize Ralph in your project
cd your-project
ralph init

# 2. Create a PRD interactively
ralph prd

# 3. Convert the PRD to tasks
ralph tasks plans/SPEC.md

# 4. Run autonomous iterations
ralph loop
```

## Commands

| Command | Description |
|---------|-------------|
| `ralph init` | Scaffold a project for Ralph workflow |
| `ralph prd` | Create a PRD interactively with Claude |
| `ralph tasks <spec>` | Convert spec to TASKS.json |
| `ralph once` | Execute single iteration |
| `ralph loop [n]` | Run n iterations (default: 10) |
| `ralph review` | Run the review pipeline with automatic configuration |
| `ralph sync` | Sync skills to ~/.claude/skills/ |

### ralph init

Scaffolds your project with Ralph workflow files:

```bash
ralph init                    # Auto-detect project type
ralph init --name MyProject   # Custom project name
ralph init --skip-claude      # Skip Claude Code enhancement
ralph init --force            # Overwrite existing files
```

If no PRD exists at `plans/SPEC.md`, you'll be prompted to create one interactively before proceeding.

Creates:
- `plans/SPEC.md` - Specification template
- `plans/TASKS.json` - Task list (empty)
- `plans/PROGRESS.txt` - Progress log
- `CLAUDE.md` - Project instructions with quality checks
- `AGENTS.md` - Agent workflow instructions

### ralph prd

Launches an interactive session with Claude to create a PRD:

```bash
ralph prd                     # Output to plans/SPEC.md
ralph prd --output custom.md  # Custom output path
ralph prd --verbose           # Verbose Claude output
```

### ralph tasks

Converts a specification file to structured tasks:

```bash
ralph tasks plans/SPEC.md              # Default output
ralph tasks spec.md --output tasks.json # Custom output
ralph tasks spec.md --branch feature/x  # Custom branch name
```

### ralph once

Executes a single iteration (one user story):

```bash
ralph once                      # Run one iteration
ralph once --verbose            # Show full Claude output
ralph once --max-fix-attempts 5 # Custom retry limit
```

### ralph loop

Runs multiple iterations automatically:

```bash
ralph loop                      # Run up to 10 iterations
ralph loop 5                    # Run up to 5 iterations
ralph loop --verbose            # Verbose output
ralph loop --max-fix-attempts 5 # Custom retry limit per story
```

Stop conditions:
- All stories complete
- Max iterations reached
- Persistent failure (same story fails twice)
- Transient failure (Claude error)

### ralph review

Runs the automated review pipeline:

```bash
ralph review                    # Auto-detect and configure reviewers
ralph review --force            # Re-detect and overwrite reviewer config
ralph review --strict           # Treat warnings as blocking
ralph review --verbose          # Verbose Claude output
```

On first run, detects project languages and configures reviewers in CLAUDE.md. On subsequent runs, uses the existing configuration and suggests any missing reviewers.

### ralph sync

Syncs skills to Claude Code:

```bash
ralph sync                           # Sync from ./skills
ralph sync --skills-dir /path/to/skills  # Custom source
ralph sync --remove                  # Remove synced skills
```

## Reviewer Skills

Ralph includes code review skills that can be invoked directly in Claude Code:

| Skill | Description |
|-------|-------------|
| `/python-code-reviewer` | Type hints, docstrings, logging, code quality |
| `/bicep-reviewer` | Azure Bicep template best practices and security |
| `/repo-structure-reviewer` | README, .gitignore, project organization |
| `/github-actions-reviewer` | CI/CD completeness, security, best practices |
| `/test-quality-reviewer` | Meaningful assertions, coverage, anti-patterns |
| `/code-simplifier` | Code clarity and maintainability improvements |
| `/release-reviewer` | Version consistency, changelog, release readiness |

Each reviewer outputs a structured report with severity levels (error/warning/suggestion) and a verdict tag:
- `<ralph-review>PASS</ralph-review>` - No blocking errors
- `<ralph-review>NEEDS_WORK</ralph-review>` - Has errors that must be fixed

## Project Structure

After running `ralph init`:

```
your-project/
├── CLAUDE.md           # Project instructions + quality checks
├── AGENTS.md           # Agent workflow instructions
└── plans/
    ├── SPEC.md         # Product specification
    ├── TASKS.json      # User stories with status
    └── PROGRESS.txt    # Iteration log
```

## TASKS.json Format

```json
{
  "project": "ProjectName",
  "branchName": "ralph/feature-name",
  "description": "Feature description",
  "userStories": [
    {
      "id": "US-001",
      "title": "Story title",
      "description": "As a user, I want...",
      "acceptanceCriteria": ["Criterion 1", "Criterion 2"],
      "priority": 1,
      "passes": false,
      "notes": ""
    }
  ]
}
```

## Quality Checks

Define quality checks in `CLAUDE.md`:

```yaml
<!-- RALPH:CHECKS:START -->
```yaml
checks:
  - name: typecheck
    command: uv run pyright
    required: true
  - name: lint
    command: uv run ruff check .
    required: true
  - name: test
    command: uv run pytest
    required: true
```
<!-- RALPH:CHECKS:END -->
```

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
uv run pytest

# Run type checking
uv run pyright

# Run linting
uv run ruff check .

# Format code
uv run ruff format .
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT - see [LICENSE](LICENSE) for details.
