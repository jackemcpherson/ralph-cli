# Ralph CLI v2.0.3 - Product Requirements Document

## Overview

This patch release addresses three issues with the reviewer skills: fixing the code-simplifier's review scope to examine feature branch changes (not just uncommitted files), enhancing the test-quality-reviewer to assess test count appropriateness, and ensuring all reviewer skills consistently reference project context files (CLAUDE.md/AGENTS.md).

## Goals

- Fix code-simplifier to review all code changed on the feature branch, not just uncommitted changes
- Enhance test-quality-reviewer to flag over-testing patterns (framework testing, redundant tests)
- Ensure all reviewer skills check and respect project-specific context from CLAUDE.md/AGENTS.md

## Non-Goals

- Resume partial review runs (#26) - deferred to future release
- Detect already-implemented stories in `ralph tasks` (#17) - deferred to future release
- Adding new reviewer skills
- Changes to the core `ralph loop` command logic

## User Stories Overview

Developers using Ralph's review pipeline need reviewers that:
1. Actually examine the code written during `ralph loop` (currently missed due to commits)
2. Catch over-testing patterns that bloat test suites without adding value
3. Respect project-specific conventions defined in CLAUDE.md/AGENTS.md

## Requirements

### Functional Requirements

#### Standardize Review Scope Across Diff-Based Reviewers (#28)

Three reviewer skills use git diff to identify files to review: code-simplifier, test-quality-reviewer, and python-code-reviewer. All three currently only check uncommitted/staged changes, missing committed code from `ralph loop`.

**Consistent Git Diff Logic**
- FR-001: All diff-based reviewers MUST use `git diff main...HEAD` to find files changed on the feature branch
- FR-002: All diff-based reviewers MUST also include uncommitted changes via `git diff HEAD`
- FR-003: The git diff logic MUST be documented identically across all three skills

**Affected Skills**
- FR-004: code-simplifier MUST be updated with new review scope logic
- FR-005: test-quality-reviewer MUST be updated with new review scope logic
- FR-006: python-code-reviewer MUST be updated with new review scope logic

**Standard Review Scope Section**
All three skills should use this consistent documentation:

```markdown
## Review Scope

Review files modified on the current feature branch compared to main.

To identify changed files:
1. Run `git diff --name-only main...HEAD` for all changes on this branch
2. Run `git diff --name-only HEAD` for any uncommitted changes
3. Combine and deduplicate the results
4. Filter to relevant file types

> **Note**: If not on a feature branch (e.g., on main), falls back to uncommitted changes only.
```

**Reviewer Template**
- FR-007: Update `skills/REVIEWER_TEMPLATE.md` with the new review scope pattern
- FR-008: Template MUST include the standard review scope section above
- FR-009: Template MUST document when to use diff-based vs full-repository review scope

#### Enhance test-quality-reviewer with Test Count Assessment (#29)

- FR-010: test-quality-reviewer MUST assess test density relative to codebase complexity
- FR-011: test-quality-reviewer MUST flag tests that verify framework/stdlib behavior (enum values, Pydantic validation, NamedTuple fields)
- FR-012: test-quality-reviewer MUST identify redundant tests that verify the same behavior multiple ways
- FR-013: test-quality-reviewer MUST suggest consolidation opportunities for similar tests
- FR-014: Over-testing indicators MUST be classified as warnings (not errors)

#### Add Consistent Project Context References (#22)

- FR-015: All reviewer skills MUST check for CLAUDE.md at project root and read it if present
- FR-016: All reviewer skills MUST check for AGENTS.md at project root and read it if present
- FR-017: All reviewer skills MUST check for skill-specific override files in `.ralph/` directory
- FR-018: Project rules from context files MUST take precedence over built-in standards
- FR-019: Review feedback SHOULD reference relevant project patterns when applicable

### Non-Functional Requirements

- NFR-001: Skill file changes must follow existing markdown structure and formatting conventions
- NFR-002: Changes must be backward compatible (skills work with or without context files)
- NFR-003: All reviewer skills must use consistent language for context file instructions

## Technical Considerations

### Architecture

All changes are to skill definition files (markdown). No Python code changes required.

**Affected files (review scope standardization - #28):**
- `skills/reviewers/code-simplifier/SKILL.md` - update Review Scope section
- `skills/reviewers/test-quality/SKILL.md` - update Review Scope section
- `skills/reviewers/language/python/SKILL.md` - update Review Scope section
- `skills/REVIEWER_TEMPLATE.md` - update Review Scope section to new pattern

**Affected files (test appropriateness - #29):**
- `skills/reviewers/test-quality/SKILL.md` - add Test Appropriateness section

**Affected files (project context - #22):**
- `skills/reviewers/code-simplifier/SKILL.md`
- `skills/reviewers/test-quality/SKILL.md`
- `skills/reviewers/language/python/SKILL.md`
- `skills/reviewers/repo-structure/SKILL.md`
- `skills/reviewers/github-actions/SKILL.md`
- `skills/reviewers/release/SKILL.md`

### Dependencies

None - these are standalone skill definition updates.

### Integration Points

- Skills are invoked by Claude Code during `ralph loop` review phase
- Skills read git state to determine files to review
- Skills may read CLAUDE.md/AGENTS.md for project context

## Success Criteria

- [ ] code-simplifier, test-quality-reviewer, and python-code-reviewer all use `git diff main...HEAD`
- [ ] All three diff-based reviewers have identical Review Scope documentation
- [ ] `skills/REVIEWER_TEMPLATE.md` updated with new review scope pattern
- [ ] test-quality-reviewer includes "Test Appropriateness" section with over-testing indicators
- [ ] All 6 reviewer skills include consistent "Project Context" section
- [ ] Running `ralph loop` on a feature branch results in diff-based reviewers finding committed files
- [ ] test-quality-reviewer flags tests that verify enum literal values as warnings
- [ ] Reviewer skills respect patterns defined in CLAUDE.md when present

## Open Questions

None - requirements are well-defined in the GitHub issues.

## References

- GitHub Issue #28: https://github.com/jackemcpherson/ralph-cli/issues/28
- GitHub Issue #29: https://github.com/jackemcpherson/ralph-cli/issues/29
- GitHub Issue #22: https://github.com/jackemcpherson/ralph-cli/issues/22
