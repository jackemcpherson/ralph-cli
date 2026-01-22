# Release v2.0.4 - Product Requirements Document

## Overview

Minor release addressing three issues: fixing non-interactive initialization (#31), optimizing prompt construction to use file references (#34), and adding rich formatting to the review loop (#35).

## Goals

- Enable fully non-interactive `ralph init` workflow for scripted/automated usage
- Reduce token usage by using `@` file references instead of loading full prompt text
- Provide consistent, informative terminal output across all loop commands

## Non-Goals

- New features or commands
- Breaking changes to existing APIs
- Changes to the review pipeline logic itself (only formatting)

## User Stories Overview

Developers using Ralph CLI need reliable non-interactive modes for CI/automation, efficient token usage when invoking Claude, and clear visual feedback during review loops.

## Requirements

### Functional Requirements

#### Issue #31: Non-Interactive Init
- FR-001: `ralph init --skip-claude` must skip the PRD creation prompt
- FR-002: The command must complete without waiting for user input when `--skip-claude` is passed
- FR-003: All files should still be created successfully (current behavior preserved)

#### Issue #34: Prompt File References
- FR-004: Audit all commands that construct prompts for Claude
- FR-005: Replace inline text loading with `@` symbol file references where applicable
- FR-006: Document the preferred pattern for prompt construction in CLAUDE.md or AGENTS.md

#### Issue #35: Review Loop Formatting
- FR-007: Display review counter (e.g., "Review 1/5") matching ralph loop style
- FR-008: Display current reviewer name being executed
- FR-009: Use Rich formatting consistent with ralph loop implementation

### Non-Functional Requirements

- NFR-001: No increase in token usage from these changes
- NFR-002: Maintain backward compatibility with existing CLI flags
- NFR-003: All existing tests must continue to pass

## Technical Considerations

### Architecture

- **#31**: Modify the init command to check `skip_claude` flag before prompting for PRD creation
- **#34**: Update prompt construction in services/commands to use `@file` notation in the prompt string passed to Claude CLI
- **#35**: Reference existing `ralph loop` formatting patterns in the loop command and apply to review execution

### Dependencies

No new dependencies required.

### Integration Points

- Claude CLI subprocess invocation (prompt construction changes)
- Rich console output (review loop formatting)

## Success Criteria

- [ ] `ralph init --skip-claude` completes without any interactive prompts
- [ ] Prompts sent to Claude use `@` notation for file references
- [ ] Review loop displays "Review X/Y" counter and reviewer name
- [ ] All quality checks pass (typecheck, lint, format, test)
- [ ] Version bumped to 2.0.4

## Open Questions

None - requirements are well-defined by the issues.

## References

- Issue #31: https://github.com/jackmcpherson/ralph-cli/issues/31
- Issue #34: https://github.com/jackmcpherson/ralph-cli/issues/34
- Issue #35: https://github.com/jackmcpherson/ralph-cli/issues/35
