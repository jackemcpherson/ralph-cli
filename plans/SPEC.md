# Ralph CLI v1.2 Specification: Bug Fixes & Memory System Improvements

## Metadata

- **Status:** Draft
- **Version:** 1.2.0
- **Last Updated:** 2026-01-18
- **Owner:** To be assigned
- **Related Issues:** #4, #5, #6, #7, #8, #9

---

## 1. Overview

### 1.1 Problem Statement

Ralph CLI v1.1 has several issues affecting reliability and developer experience:

1. **Critical Bug:** The `ralph once` and `ralph loop` commands crash when the `-v` (verbose) flag is not provided. The error message indicates that `--output-format=stream-json` requires `--verbose` when using `--print` mode.

2. **Output Formatting Bug:** When streaming output works, text chunks are written without proper newlines, creating a wall of text that is difficult to read.

3. **Permissions Bug:** The `ralph prd` interactive command does not use `--dangerously-skip-permissions`, causing Claude to prompt for permissions during autonomous execution.

4. **Missing Feature:** No long-term memory persists across feature development cycles. PROGRESS.txt accumulates entries from previous features, causing confusion.

5. **UX Issue:** The `ralph tasks` command does not stream output, leaving users with no feedback during generation.

### 1.2 Goals

1. **Fix crash on non-verbose mode** - Commands must work correctly with or without the `-v` flag
2. **Improve output readability** - Add proper newlines between response blocks
3. **Enable autonomous PRD creation** - Apply skip permissions to interactive commands
4. **Implement persistent memory** - Add CHANGELOG.md for cross-feature learning
5. **Clean slate for new features** - Archive PROGRESS.txt when starting new task sets
6. **Better feedback** - Stream output for the `ralph tasks` command

### 1.3 Non-Goals

- Changing the TASKS.json schema
- Adding new CLI commands
- Modifying the iteration logic
- Automatic version bumping

---

## 2. Requirements

### 2.1 Bug Fix: Stream-JSON Without Verbose Flag (Issue #7)

**Priority: Critical**

The root cause is that Claude Code CLI requires `--verbose` when using `--output-format=stream-json` with `--print` mode. The current implementation always uses stream-json format but doesn't always pass verbose.

| ID | Requirement |
|----|-------------|
| FR-BUG7-01 | When `stream=True` in `run_print_mode()`, always include `--verbose` in CLI args |
| FR-BUG7-02 | The `--verbose` flag controls output *display*, not the underlying stream format |
| FR-BUG7-03 | In non-verbose mode, parse stream-json but only display text content |
| FR-BUG7-04 | In verbose mode, display the full JSON stream (current behavior) |
| FR-BUG7-05 | Commands `ralph once` and `ralph loop` must work without any flags |

**Files to Modify:**
- `src/ralph/services/claude.py` - `_build_base_args()` and `run_print_mode()`

**Technical Solution:**
```python
# Always use --verbose when streaming, as stream-json requires it
# The parse_json parameter controls what gets displayed, not the underlying format
if stream:
    args.extend(["--verbose", "--output-format", "stream-json"])
```

### 2.2 Bug Fix: Output Formatting with Newlines (Issue #6)

**Priority: High**

Text chunks from stream-json events are written directly without newlines, creating unreadable output.

| ID | Requirement |
|----|-------------|
| FR-BUG6-01 | Detect message boundaries in the JSON stream |
| FR-BUG6-02 | Add newline after each complete assistant message/turn |
| FR-BUG6-03 | Preserve inline text flow within a single message |
| FR-BUG6-04 | Output should be readable without requiring verbose mode |

**Files to Modify:**
- `src/ralph/services/claude.py` - `_stream_output()` and `_parse_stream_event()`

**Technical Solution:**
The stream-json format includes event types. Track when a message completes and add newlines:
```python
def _parse_stream_event(self, line: str) -> tuple[str | None, bool]:
    """Parse a stream event, return (text, is_message_complete)."""
    # Return is_message_complete=True when we see end-of-turn markers
```

### 2.3 Bug Fix: Skip Permissions for Interactive Commands (Issue #4)

**Priority: High**

The `ralph prd` command should use `--dangerously-skip-permissions` like `ralph once` and `ralph loop`.

| ID | Requirement |
|----|-------------|
| FR-BUG4-01 | Add `skip_permissions: bool = False` parameter to `run_interactive()` |
| FR-BUG4-02 | When `skip_permissions=True`, include `--dangerously-skip-permissions` in args |
| FR-BUG4-03 | `ralph prd` calls `run_interactive()` with `skip_permissions=True` |
| FR-BUG4-04 | Display info message about auto-approved permissions |

**Files to Modify:**
- `src/ralph/services/claude.py` - `run_interactive()`
- `src/ralph/commands/prd.py`

### 2.4 Enhancement: Implement CHANGELOG.md (Issue #9)

**Priority: Medium**

Add a CHANGELOG.md file that persists across feature development cycles, following the Keep a Changelog format.

| ID | Requirement |
|----|-------------|
| FR-ENH9-01 | `ralph init` creates `CHANGELOG.md` in project root if it doesn't exist |
| FR-ENH9-02 | Use [Keep a Changelog](https://keepachangelog.com/) format |
| FR-ENH9-03 | Template includes: Unreleased section, category headers (Added, Changed, etc.) |
| FR-ENH9-04 | Add CHANGELOG guidelines section to `CLAUDE.md` |
| FR-ENH9-05 | Add same CHANGELOG guidelines section to `AGENTS.md` (keep in sync) |
| FR-ENH9-06 | Update iteration prompt to mention CHANGELOG for significant changes |

**CHANGELOG.md Template:**
```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project setup

```

**CLAUDE.md/AGENTS.md Section to Add:**
```markdown
## CHANGELOG.md

This project maintains a CHANGELOG.md following Keep a Changelog format.

**When to update:**
- After implementing significant features
- When fixing important bugs
- When making breaking changes
- When deprecating functionality

**How to update:**
1. Add entries under the `[Unreleased]` section
2. Use appropriate category: Added, Changed, Deprecated, Removed, Fixed, Security
3. Write user-facing descriptions (not implementation details)
4. Reference story IDs when applicable

**Do NOT update CHANGELOG.md for:**
- Minor refactorings
- Internal code reorganization
- Test additions (unless significant new test infrastructure)
```

**Files to Modify:**
- `src/ralph/commands/init_cmd.py` - Add CHANGELOG.md creation
- `src/ralph/services/scaffold.py` - Add template
- `skills/ralph-iteration/SKILL.md` - Update iteration instructions

### 2.5 Enhancement: Clear PROGRESS.txt on New Tasks (Issue #8)

**Priority: Medium**

When `ralph tasks` generates a new TASKS.json, archive the existing PROGRESS.txt to prevent stale context from confusing Claude.

| ID | Requirement |
|----|-------------|
| FR-ENH8-01 | After writing new TASKS.json, check if PROGRESS.txt exists |
| FR-ENH8-02 | If exists, archive to `plans/PROGRESS.{timestamp}.txt` |
| FR-ENH8-03 | Timestamp format: `YYYYMMDD_HHMMSS` |
| FR-ENH8-04 | Create fresh empty PROGRESS.txt with header template |
| FR-ENH8-05 | Display message: "Archived previous progress to PROGRESS.{timestamp}.txt" |

**Files to Modify:**
- `src/ralph/commands/tasks.py` - Add archival logic after `save_tasks()`

**Implementation:**
```python
# After save_tasks(tasks_model, output_path)
progress_path = project_root / "plans" / "PROGRESS.txt"
if progress_path.exists() and progress_path.stat().st_size > 0:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = project_root / "plans" / f"PROGRESS.{timestamp}.txt"
    progress_path.rename(archive_path)
    console.print(f"[dim]Archived previous progress to {archive_path.name}[/dim]")
    # Create fresh PROGRESS.txt
    progress_path.write_text(PROGRESS_TEMPLATE)
```

### 2.6 Enhancement: Stream Output for `ralph tasks` (Issue #5)

**Priority: Low**

Enable streaming output for the `ralph tasks` command to provide feedback during generation.

| ID | Requirement |
|----|-------------|
| FR-ENH5-01 | Change `stream=False` to `stream=True` in `ralph tasks` |
| FR-ENH5-02 | Users see Claude's progress as it generates the task breakdown |
| FR-ENH5-03 | JSON extraction still works correctly from streamed output |

**Files to Modify:**
- `src/ralph/commands/tasks.py` - Line ~86

**Change:**
```python
# Before
output_text, exit_code = claude.run_print_mode(prompt, stream=False)

# After
output_text, exit_code = claude.run_print_mode(prompt, stream=True)
```

---

## 3. Technical Considerations

### 3.1 Claude Code CLI Behavior

The key insight from Issue #7 is that Claude Code's `--output-format=stream-json` flag requires `--verbose` when used with `--print` mode. This is a Claude Code requirement, not a bug in ralph-cli. The fix is to always pass `--verbose` internally when streaming, then control what gets *displayed* based on the user's verbose preference.

### 3.2 Stream Event Types

Claude Code stream-json outputs different event types:
- `assistant` - Contains text content from Claude
- `tool_use` - Tool invocation
- `tool_result` - Tool execution result
- `error` - Error messages

For newline insertion, we should add newlines when transitioning between major message blocks, particularly after a complete assistant response before a new tool use or vice versa.

### 3.3 File Modification Summary

| File | Changes |
|------|---------|
| `src/ralph/services/claude.py` | Fix stream args, improve output parsing |
| `src/ralph/commands/tasks.py` | Enable streaming, add PROGRESS.txt archival |
| `src/ralph/commands/prd.py` | Add skip_permissions to interactive mode |
| `src/ralph/commands/init_cmd.py` | Create CHANGELOG.md |
| `src/ralph/services/scaffold.py` | Add CHANGELOG template |
| `skills/ralph-iteration/SKILL.md` | Update iteration instructions |
| `CLAUDE.md` | Add CHANGELOG guidelines |
| `AGENTS.md` | Add CHANGELOG guidelines (keep in sync) |

---

## 4. Success Criteria

| # | Criterion | Issue |
|---|-----------|-------|
| 1 | `ralph once` works without `-v` flag | #7 |
| 2 | `ralph loop 3` completes without `-v` flag | #7 |
| 3 | Output shows proper newlines between message blocks | #6 |
| 4 | Output is readable without verbose mode | #6 |
| 5 | `ralph prd` runs without permission prompts | #4 |
| 6 | `ralph init` creates CHANGELOG.md with proper template | #9 |
| 7 | CLAUDE.md and AGENTS.md contain CHANGELOG guidelines | #9 |
| 8 | `ralph tasks` archives existing PROGRESS.txt | #8 |
| 9 | `ralph tasks` streams output in real-time | #5 |
| 10 | All existing tests continue to pass | - |

---

## 5. Testing Strategy

### 5.1 Unit Tests

- Test `_build_base_args()` always includes `--verbose` when streaming
- Test `_parse_stream_event()` returns newline markers correctly
- Test `run_interactive()` with `skip_permissions=True`
- Test PROGRESS.txt archival with timestamp format

### 5.2 Integration Tests

- Run `ralph once` without flags, verify no crash
- Run `ralph loop 2` without flags, verify completion
- Run `ralph tasks` and verify streaming output
- Run `ralph init` and verify CHANGELOG.md created

### 5.3 Manual Testing

- Visual inspection of output formatting
- Verify CHANGELOG.md template follows Keep a Changelog format
- Verify archived PROGRESS.txt files are created correctly

---

## Appendix A: Issue Reference

| Issue | Title | Type | Priority |
|-------|-------|------|----------|
| #7 | ralph once/loop crash when -v flag is not passed | Bug | Critical |
| #6 | ralph once/loop output formatting: need newlines | Bug | High |
| #4 | Enable skip permissions for interactive commands | Bug | High |
| #9 | Implement CHANGELOG.md for long-term memory | Enhancement | Medium |
| #8 | ralph tasks should clear PROGRESS.txt | Enhancement | Medium |
| #5 | ralph tasks does not stream output | Enhancement | Low |
