# Ralph CLI v2.1.0 — Point Release Enhancements - Product Requirements Document

## Overview

Point release adding three enhancements to the Ralph CLI: a `--no-fix` flag for review-only mode, resumable review runs, and heuristic detection of already-implemented stories during task generation. These improvements address usability gaps identified during v2.0.x usage (#37, #26, #17).

## Goals

- Allow users to run the review pipeline without automated fixes (#37)
- Enable resuming interrupted review runs from the last completed reviewer (#26)
- Reduce wasted iteration time by detecting already-implemented stories before generating tasks (#17)

## Non-Goals

- No changes to the core iteration loop (`ralph once` / `ralph loop` story execution)
- No changes to the reviewer skill format or review verdict schema
- No deterministic/AST-level detection for already-implemented stories — heuristic only
- No new CLI commands — all changes extend existing commands

## User Stories Overview

Three personas benefit from these changes:

- **Developer running reviews for audit**: Wants to see findings without automated changes (`--no-fix`)
- **Developer with interrupted sessions**: Wants to resume a long review pipeline without re-running completed reviewers (`--resume-review`)
- **Developer generating tasks**: Wants to avoid stories for work that's already shipped (heuristic detection)

## Requirements

### Functional Requirements

#### Review-Only Mode (#37)

- FR-001: Add a `--no-fix` boolean flag to the `ralph loop` command (default: `false`)
- FR-002: When `--no-fix` is set, skip the call to `FixLoopService.run_fix_loop()` after a NEEDS_WORK verdict
- FR-003: Log `[Fix] Skipped (--no-fix)` when a fix is skipped due to the flag
- FR-004: Continue to the next reviewer after logging (do not abort the pipeline)
- FR-005: Final summary must indicate which reviewers had findings that were not auto-fixed

#### Resumable Review Runs (#26)

- FR-006: Track review progress in a state file (`.ralph-review-state.json`) in the project root
- FR-007: State file records: list of reviewers, pass/fail status for each completed reviewer, and timestamp
- FR-008: Add a `--resume-review` flag to `ralph loop` that resumes from the last completed reviewer
- FR-009: When `--resume-review` is set and no state file exists, run the full review pipeline from the beginning
- FR-010: Clean up the state file when the review loop completes successfully
- FR-011: If the reviewer configuration has changed since the state file was written (e.g., reviewers added/removed), discard state and restart

#### Already-Implemented Story Detection (#17)

- FR-012: During `ralph tasks` generation, pass codebase context to Claude alongside the SPEC.md
- FR-013: Prompt Claude to identify requirements that appear to already be implemented in the codebase
- FR-014: Stories detected as already-implemented must be included in TASKS.json with `"passes": true` and a note explaining the detection
- FR-015: Log a summary of detected already-implemented stories to the console (e.g., `[Tasks] 2 stories detected as already implemented`)

### Non-Functional Requirements

- NFR-001: All new flags must include help text visible via `ralph loop --help` and `ralph tasks --help`
- NFR-002: State file (`.ralph-review-state.json`) must be added to the default `.gitignore` scaffold in `ralph init`
- NFR-003: Heuristic detection must not add more than one additional Claude API call to `ralph tasks`
- NFR-004: All new functionality must have unit tests

## Technical Considerations

### Architecture

- **`--no-fix` flag**: Minimal change — thread the flag through `run_review_loop()` and gate the `FixLoopService.run_fix_loop()` call
- **Resume state**: New `ReviewState` Pydantic model in `src/ralph/models/`. `ReviewLoopService` writes state after each reviewer completes, reads it on `--resume-review`
- **Heuristic detection**: Extend the Claude prompt in `ralph tasks` to include a codebase summary and ask Claude to flag already-implemented items. Parse Claude's response to set `passes: true` and add notes

### Dependencies

- No new external dependencies required
- All features use existing Claude subprocess integration

### Integration Points

- `--no-fix` integrates with `FixLoopService` and `ReviewLoopService` in `src/ralph/services/`
- Resume state integrates with `ReviewLoopService` and the reviewer configuration parser
- Heuristic detection integrates with the `ralph tasks` command and `SkillLoader`

## Success Criteria

- [ ] `ralph loop --no-fix` runs all reviewers and reports findings without modifying code
- [ ] `ralph loop --resume-review` skips previously-completed reviewers and picks up where it left off
- [ ] Changing reviewer config between runs correctly invalidates stale resume state
- [ ] `ralph tasks` flags at least one obviously-implemented story when run against a spec with already-shipped features
- [ ] All quality checks pass (pyright, ruff, pytest)
- [ ] Version bumped to 2.1.0 in `pyproject.toml` and `src/ralph/__init__.py`

## Open Questions

- None — all three issues are well-defined and the user has confirmed the approaches.

## References

- [#37 — Add --no-fix flag to disable auto-fix in review loop](https://github.com/jackmcpherson/ralph-cli/issues/37)
- [#26 — Enhancement: Resume partial review runs](https://github.com/jackmcpherson/ralph-cli/issues/26)
- [#17 — ralph tasks: Detect already-implemented stories before generating tasks](https://github.com/jackmcpherson/ralph-cli/issues/17)
