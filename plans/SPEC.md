# Review Auto-Fix Loop - Product Requirements Document

## Overview

Extend the Ralph review loop to automatically fix issues identified by reviewers. When a reviewer returns a `NEEDS_WORK` verdict, the system will parse the structured findings, attempt to fix each one (with retries), commit successful fixes, and log progress to PROGRESS.txt before continuing to the next reviewer.

## Goals

- Automate resolution of review findings without human intervention
- Reduce iteration cycles by fixing issues as they're discovered
- Maintain clear audit trail of fixes in PROGRESS.txt
- Preserve granular git history with one commit per fix

## Non-Goals

- Interactive approval mode (defeats the purpose of automation)
- Rollback/undo capability for fixes
- `--no-fix` flag (deferred to future enhancement - log as GitHub issue)

## User Stories Overview

**Primary user**: Developer running `ralph loop` who wants the review pipeline to automatically fix issues rather than just report them.

**Workflow**: After all user stories complete, the review loop runs. When a reviewer identifies issues, instead of just logging "failed", the system attempts to fix each finding, commits successful fixes, and continues.

## Requirements

### Functional Requirements

#### Reviewer Output Format

- FR-001: Reviewers MUST output findings in a structured markdown format to PROGRESS.txt
- FR-002: Each finding MUST include: ID, category, file path with line number, issue description, and fix suggestion
- FR-003: Reviewers MUST log a summary to PROGRESS.txt regardless of verdict (PASSED or NEEDS_WORK)
- FR-004: The verdict and findings format MUST be parseable by the fix loop

#### Fix Loop Behavior

- FR-005: When a reviewer returns NEEDS_WORK, the fix loop MUST attempt to resolve each finding
- FR-006: Similar findings MAY be batched into a single fix attempt (at Claude's discretion)
- FR-007: Each fix attempt MUST be retried up to 3 times before moving on
- FR-008: After exhausting retries, the fix loop MUST log the failure and continue to the next finding
- FR-009: The fix loop MUST read findings from PROGRESS.txt to determine what needs fixing

#### Commit Behavior

- FR-010: Each successful fix MUST be committed individually
- FR-011: Fix commits MUST use format: `fix(review): [reviewer-name] - [finding-id] - [brief description]`

#### Reviewer Level Handling

- FR-012: By default, auto-fix MUST only run for `blocking` level reviewers
- FR-013: When `--strict` is passed, auto-fix MUST run for all levels (blocking, warning, suggestion)
- FR-014: Skipped reviewers (language filter) MUST NOT trigger the fix loop

#### Progress Logging

- FR-015: Fix attempts MUST be logged to PROGRESS.txt following the iteration entry format
- FR-016: Fix entries MUST include: what was fixed, files changed, and attempt count if retried
- FR-017: Failed fixes MUST be logged with the error/reason for failure

### Non-Functional Requirements

- NFR-001: Fix attempts should complete within the same timeout as regular Claude operations
- NFR-002: The fix loop should not significantly increase total review time for passing reviews
- NFR-003: Progress output should clearly indicate fix attempts vs reviewer execution

## Technical Considerations

### Architecture

```
Review Loop Flow (Updated):

For each reviewer:
  ├─ Run reviewer → Claude returns structured output
  ├─ Parse output for verdict and findings
  ├─ Log summary to PROGRESS.txt (always)
  │
  ├─ If PASSED → continue to next reviewer
  │
  ├─ If NEEDS_WORK and should_fix(level, strict):
  │   ├─ For each finding (or batch of similar findings):
  │   │   ├─ Attempt fix (up to 3 retries)
  │   │   ├─ If success:
  │   │   │   ├─ Commit with fix message
  │   │   │   └─ Log fix to PROGRESS.txt
  │   │   └─ If failure after retries:
  │   │       └─ Log failure and continue
  │   └─ Continue to next reviewer
  │
  └─ Next reviewer
```

### Structured Output Format

Reviewers will output findings in this format:

```markdown
[Review] YYYY-MM-DD HH:MM UTC - {reviewer-name} ({level})

### Verdict: {PASSED|NEEDS_WORK}

### Findings

1. **{FINDING-ID}**: {Category} - {Brief description}
   - File: {path/to/file.py}:{line_number}
   - Issue: {Detailed description of the problem}
   - Suggestion: {How to fix it}

2. **{FINDING-ID}**: {Category} - {Brief description}
   - File: {path/to/file.py}:{line_number}
   - Issue: {Detailed description of the problem}
   - Suggestion: {How to fix it}

---
```

Fix entries will follow this format:

```markdown
[Review Fix] YYYY-MM-DD HH:MM UTC - {reviewer-name}/{finding-id}

### What was fixed
- {Description of the fix applied}

### Files changed
- {path/to/file.py}

### Attempts
{N} of 3

---
```

Failed fix entries:

```markdown
[Review Fix Failed] YYYY-MM-DD HH:MM UTC - {reviewer-name}/{finding-id}

### Issue
- {Description of what couldn't be fixed}

### Attempts
3 of 3 (exhausted)

### Reason
{Error message or explanation of why fix failed}

---
```

### Dependencies

- Existing `ReviewLoopService` in `src/ralph/services/review_loop.py`
- Existing reviewer skills in `src/ralph/skills/reviewers/`
- `ClaudeService.run_print_mode()` for fix attempts
- PROGRESS.txt append utilities

### Integration Points

- All 6 reviewer skills must be updated to output structured findings format
- `ReviewLoopService.run_reviewer()` must parse structured output
- New `FixLoopService` (or extension to ReviewLoopService) for fix logic
- Git service for fix commits

### Files to Modify

| File | Changes |
|------|---------|
| `src/ralph/services/review_loop.py` | Add fix loop logic, parse structured output |
| `src/ralph/skills/reviewers/*/SKILL.md` | Update all 6 skills with structured output format |
| `src/ralph/commands/loop.py` | Pass strict flag through to fix logic |
| `src/ralph/utils/console.py` | Add `print_fix_step()` for fix progress display |

### New Files

| File | Purpose |
|------|---------|
| `src/ralph/services/fix_loop.py` | Fix attempt logic, retry handling, commit creation |
| `src/ralph/models/finding.py` | Pydantic models for parsing structured findings |

## Success Criteria

- [ ] All 6 reviewer skills output structured findings format
- [ ] Fix loop attempts to resolve NEEDS_WORK findings automatically
- [ ] Each successful fix is committed individually with proper message format
- [ ] Failed fixes are logged and don't block subsequent fixes or reviewers
- [ ] `--strict` flag enables fix loop for warning/suggestion level reviewers
- [ ] PROGRESS.txt contains clear audit trail of all fix attempts
- [ ] Existing tests pass; new tests cover fix loop behavior

## Open Questions

- None - all requirements clarified during discovery

## References

- Current review loop: `src/ralph/services/review_loop.py`
- Iteration skill format: `src/ralph/skills/ralph/iteration/SKILL.md`
- Existing PROGRESS.txt examples: `plans/PROGRESS.txt`
