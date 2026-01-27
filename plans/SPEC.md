# Ralph Review Command - Product Requirements Document

## Overview

Implement a standalone `ralph review` command that automatically configures project-appropriate reviewers and executes the review loop independently of `ralph loop`. This makes reviewers discoverable, simplifies configuration, and allows reviews to run at any point in the development workflow.

## Goals

- Make reviewer configuration automatic and discoverable
- Allow reviews to run independently of the iteration loop
- Detect project characteristics and configure appropriate reviewers
- Keep reviewer configuration in sync with project evolution

## Non-Goals

- Changing the existing `ralph loop` auto-review behavior
- Adding reviewer skills for languages not yet supported
- Interactive/TUI reviewer selection (defer to future)
- Removing or deprecating manual CLAUDE.md configuration

## User Stories Overview

**Primary persona**: A developer using Ralph CLI who wants code quality reviews without manually configuring reviewers or running the full iteration loop.

**Secondary persona**: A developer whose project has evolved (added Bicep files, GitHub workflows) and needs to update their reviewer configuration.

## Requirements

### Functional Requirements

#### Command Structure
- FR-001: Add `ralph review` command to the CLI
- FR-002: Support `--force` flag to re-run detection and overwrite existing reviewer configuration
- FR-003: Support `--verbose` flag consistent with other commands
- FR-004: Support `--strict` flag to treat warning-level reviewers as blocking (pass through to review loop)

#### First-Run Behavior (No Existing Config)
- FR-005: Detect project characteristics to determine applicable reviewers
- FR-006: Write `<!-- RALPH:REVIEWERS:START -->` section to CLAUDE.md with detected reviewers
- FR-007: Display which reviewers were configured and why (e.g., "Added python-code reviewer (found .py files)")
- FR-008: Execute the review loop after configuration

#### Subsequent-Run Behavior (Config Exists)
- FR-009: Execute the review loop using existing CLAUDE.md configuration
- FR-010: Detect if there are suggested reviewers not in current config
- FR-011: Display warning listing suggested reviewers that could be added
- FR-012: Suggest running `ralph review --force` to update configuration

#### Force Flag Behavior
- FR-013: Re-run full project detection when `--force` is provided
- FR-014: Overwrite existing `RALPH:REVIEWERS` section with newly detected config
- FR-015: Display what changed (added/removed reviewers) before executing review loop

#### Project Detection
- FR-016: Detect Python projects (presence of `.py` files) → python-code reviewer
- FR-017: Detect Bicep projects (presence of `.bicep` files) → bicep reviewer
- FR-018: Detect GitHub Actions (presence of `.github/workflows/*.yml`) → github-actions reviewer
- FR-019: Detect test files (presence of `test_*.py`, `*_test.go`, etc.) → test-quality reviewer
- FR-020: Always include universal reviewers: code-simplifier, repo-structure
- FR-021: Include release reviewer if CHANGELOG.md exists

#### Language Detection Enhancement
- FR-022: Add Bicep to `detect_languages()` service function
- FR-023: Detect Bicep by presence of `.bicep` files in project

### Non-Functional Requirements

- NFR-001: Detection should complete in under 2 seconds for typical projects
- NFR-002: Command should work without network access (all detection is local)
- NFR-003: CLAUDE.md modifications should preserve existing content outside the RALPH:REVIEWERS markers
- NFR-004: Output should follow existing CLI formatting conventions (Rich, [OK]/[FAIL] markers)

## Technical Considerations

### Architecture

The command should follow the existing pattern:
- `src/ralph/commands/review.py` - Command implementation
- Reuse `ReviewLoopService` from `src/ralph/services/review_loop.py`
- Add `ReviewerConfigService` for detection and CLAUDE.md manipulation
- Extend `detect_languages()` in `src/ralph/services/language.py`

### Detection Strategy

```
Project Detection Matrix:
+------------------+------------------------+------------------+
| Detector         | File Pattern           | Reviewer         |
+------------------+------------------------+------------------+
| Python           | **/*.py                | python-code      |
| Bicep            | **/*.bicep             | bicep            |
| GitHub Actions   | .github/workflows/*.yml| github-actions   |
| Tests            | test_*.py, *_test.py   | test-quality     |
| Changelog        | CHANGELOG.md           | release          |
| Universal        | (always)               | code-simplifier  |
| Universal        | (always)               | repo-structure   |
+------------------+------------------------+------------------+
```

### CLAUDE.md Manipulation

- Parse existing content to find `<!-- RALPH:REVIEWERS:START -->` markers
- If markers exist: replace content between markers
- If markers don't exist: append section before `## Project-Specific Instructions` or at end
- Preserve all content outside the markers

### Dependencies

- No new external dependencies required
- Reuses existing: `rich`, `pydantic`, `pyyaml`

### Integration Points

- Integrates with existing `ReviewLoopService`
- Integrates with existing `load_reviewer_configs()`
- Extends existing `detect_languages()` function

## Success Criteria

- [ ] `ralph review` auto-configures reviewers on first run in a Python project
- [ ] `ralph review` auto-configures reviewers on first run in a project with Bicep files
- [ ] Subsequent runs show warning when new file types are detected
- [ ] `ralph review --force` updates configuration when project evolves
- [ ] Reviews execute successfully after configuration
- [ ] Existing manual CLAUDE.md configurations continue to work
- [ ] `ralph loop` auto-review behavior is unchanged

## Open Questions

None - all requirements have been clarified.

## References

- Existing reviewer configuration: `src/ralph/models/reviewer.py`
- Review loop implementation: `src/ralph/services/review_loop.py`
- Language detection: `src/ralph/services/language.py`
- GitHub Issue #41: Bicep reviewer skill (completed)
