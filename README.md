# Ralph CLI

A Python CLI tool that implements the Ralph autonomous iteration pattern for Claude Code.

## Installation

```bash
uv pip install -e ".[dev]"
```

## Usage

```bash
ralph --help
```

## Commands

- `ralph init` - Scaffold a project for Ralph workflow
- `ralph prd` - Interactive PRD creation with Claude
- `ralph tasks <spec>` - Convert spec to TASKS.json
- `ralph once` - Execute single iteration
- `ralph loop [n]` - Run n iterations (default: 10)
- `ralph sync` - Sync skills to ~/.claude/skills/
