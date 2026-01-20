# Ralph CLI v1.2.5 Specification: Windows Compatibility & UX Improvements

## Metadata

- **Status:** Draft
- **Version:** 1.2.5
- **Last Updated:** 2026-01-20
- **Owner:** To be assigned
- **Related Issues:** #5, #11, #12, #13, #14, #15

---

## 1. Overview

### 1.1 Problem Statement

Ralph CLI v1.2 has several issues affecting Windows compatibility and user experience:

1. **Windows Encoding Bug (#15):** Rich unicode warning symbols fail on Windows systems using cp1252 encoding, causing encoding errors or corrupted output.

2. **Windows Path Bug (#14):** Tests fail on Windows due to path separator mismatches (forward vs backslashes), preventing CI from passing on Windows environments.

3. **Empty Archive Bug (#13):** The `ralph tasks` command archives PROGRESS.txt even when it only contains boilerplate template text with no actual iteration content, cluttering the plans directory.

4. **Inconsistent Permissions (#12):** Claude sessions invoked by different Ralph commands have inconsistent behavior regarding permission prompts and autonomous mode, causing unexpected interruptions.

5. **Missing Auto-PRD (#11):** Running `ralph init` without an existing PRD file causes `claude init` to fail or produce suboptimal results because there's no specification to work with.

6. **No Streaming (#5):** The `ralph tasks` command doesn't stream output, leaving users with no feedback during task generation.

### 1.2 Goals

1. **Full Windows compatibility** - Commands work correctly on Windows with cp1252/legacy encodings
2. **Cross-platform tests** - Test suite passes on both Unix and Windows
3. **Smart archiving** - Only archive PROGRESS.txt when it has meaningful content
4. **Consistent permissions** - All Claude invocations use the same flags
5. **Guided initialization** - Auto-generate PRD if missing during init
6. **Better feedback** - Stream output for all long-running commands

### 1.3 Non-Goals

- Changing the TASKS.json schema
- Adding new CLI commands (beyond enhancing existing ones)
- Modifying the core iteration logic
- Windows-specific installation procedures

---

## 2. Requirements

### 2.1 Bug Fix: Rich Unicode on Windows (#15)

**Priority: Critical**

Rich console attempts to render unicode symbols (warning triangles, checkmarks) that Windows cp1252 encoding cannot display.

| ID | Requirement |
|----|-------------|
| FR-WIN15-01 | Configure Rich console to handle Windows legacy encodings |
| FR-WIN15-02 | Use ASCII fallbacks for warning/error symbols on Windows |
| FR-WIN15-03 | Auto-detect terminal encoding capabilities |
| FR-WIN15-04 | No encoding errors on Windows terminals |

**Files to Modify:**
- `src/ralph/utils/console.py` - Rich console initialization

**Technical Solution:**
```python
import sys
from rich.console import Console

def create_console() -> Console:
    """Create Rich console with cross-platform encoding support."""
    # Check for Windows legacy encoding
    legacy_windows = (
        sys.platform == "win32"
        and sys.stdout.encoding.lower() in ("cp1252", "cp437", "ascii")
    )
    return Console(legacy_windows=legacy_windows)
```

**Alternative:** Use `console.is_terminal` and `console.encoding` to conditionally substitute unicode symbols with ASCII equivalents.

### 2.2 Bug Fix: Path Separators in Tests (#14)

**Priority: High**

Tests assert specific path strings like `plans/SPEC.md` but Windows outputs `plans\SPEC.md`.

| ID | Requirement |
|----|-------------|
| FR-WIN14-01 | Test assertions handle both Unix and Windows path separators |
| FR-WIN14-02 | Path comparisons use normalized paths or both separators |
| FR-WIN14-03 | All path-related tests pass on Windows |
| FR-WIN14-04 | No changes to actual command output (display native paths) |

**Affected Tests:**
- `tests/test_commands/test_prd.py::test_prd_includes_prd_prompt`
- `tests/test_commands/test_prd.py::test_prd_shows_output_path`
- `tests/test_commands/test_prd.py::test_prd_with_custom_output_path`
- `tests/test_commands/test_tasks.py::test_tasks_displays_informational_message`
- `tests/test_commands/test_tasks.py::test_tasks_with_custom_output_path`

**Technical Solution:**
```python
# Option 1: Normalize output for comparison
def normalize_paths(text: str) -> str:
    """Normalize path separators for cross-platform comparison."""
    return text.replace("\\", "/")

assert "plans/SPEC.md" in normalize_paths(result.output)

# Option 2: Check both separators
assert "plans/SPEC.md" in result.output or "plans\\SPEC.md" in result.output
```

### 2.3 Bug Fix: Skip Empty PROGRESS.txt Archiving (#13)

**Priority: High**

The archive logic triggers even when PROGRESS.txt contains only the boilerplate template with no actual iteration content.

| ID | Requirement |
|----|-------------|
| FR-ARCH13-01 | Detect if PROGRESS.txt contains only template boilerplate |
| FR-ARCH13-02 | Skip archiving if no meaningful content exists |
| FR-ARCH13-03 | Return `None` (no archive path) when file is template-only |
| FR-ARCH13-04 | Only archive files with actual iteration entries |

**Files to Modify:**
- `src/ralph/commands/tasks.py` - `_archive_progress_file()` function

**Technical Solution:**
```python
def _has_meaningful_content(progress_path: Path) -> bool:
    """Check if PROGRESS.txt has content beyond the template."""
    content = progress_path.read_text()

    # Check for iteration markers that indicate actual work
    iteration_markers = [
        "## Iteration",
        "### Story:",
        "**Status:**",
        "**Completed:**",
    ]
    return any(marker in content for marker in iteration_markers)

def _archive_progress_file(progress_path: Path) -> Path | None:
    """Archive PROGRESS.txt if it has meaningful content."""
    if not progress_path.exists():
        return None
    if not _has_meaningful_content(progress_path):
        return None  # Skip archiving template-only files
    # ... existing archival logic
```

### 2.4 Enhancement: Consistent Claude Flags (#12)

**Priority: High**

Different commands use different Claude flags, causing inconsistent behavior with permissions and autonomous mode.

| ID | Requirement |
|----|-------------|
| FR-FLAGS12-01 | All Claude invocations use `--dangerously-skip-permissions` |
| FR-FLAGS12-02 | All Claude invocations include autonomous mode configuration |
| FR-FLAGS12-03 | Create centralized function for building Claude CLI args |
| FR-FLAGS12-04 | No unexpected permission prompts during any Ralph operation |
| FR-FLAGS12-05 | Document consistent flag behavior |

**Commands to Audit:**
- `ralph init` - runs `claude init`
- `ralph prd` - PRD agent sessions
- `ralph tasks` - task generation sessions
- `ralph once` - single iteration
- `ralph loop` - multiple iterations

**Files to Modify:**
- `src/ralph/services/claude.py` - Centralize flag handling
- `src/ralph/commands/init_cmd.py`
- `src/ralph/commands/prd.py`
- `src/ralph/commands/tasks.py`

**Technical Solution:**
```python
class ClaudeService:
    # Centralized flags
    SKIP_PERMISSIONS_FLAG = "--dangerously-skip-permissions"

    def _build_base_args(self, skip_permissions: bool = True) -> list[str]:
        """Build base args with consistent flag handling."""
        args = ["claude"]
        if skip_permissions:
            args.append(self.SKIP_PERMISSIONS_FLAG)
        return args
```

### 2.5 Enhancement: Auto-PRD in Init (#11)

**Priority: Medium**

`ralph init` fails or produces poor results when no PRD exists because `claude init` has no specification.

| ID | Requirement |
|----|-------------|
| FR-INIT11-01 | Check for PRD file before running `claude init` |
| FR-INIT11-02 | If PRD missing, prompt user to create one via PRD agent |
| FR-INIT11-03 | Allow user to skip PRD creation and proceed anyway |
| FR-INIT11-04 | Display clear feedback about the PRD generation step |
| FR-INIT11-05 | Fail gracefully if PRD generation is cancelled |

**Files to Modify:**
- `src/ralph/commands/init_cmd.py`

**Technical Solution:**
```python
def init_command():
    # Check for PRD
    prd_path = project_root / "plans" / "SPEC.md"
    if not prd_path.exists():
        console.print("[yellow]No PRD found at plans/SPEC.md[/yellow]")
        if Confirm.ask("Would you like to create a PRD first?"):
            # Run PRD flow
            from ralph.commands.prd import prd_command
            prd_command(output=prd_path)
        else:
            console.print("[dim]Proceeding without PRD...[/dim]")

    # Continue with claude init
    ...
```

### 2.6 Enhancement: Stream Output for Tasks (#5)

**Priority: Low**

`ralph tasks` runs with `stream=False`, providing no feedback during generation.

| ID | Requirement |
|----|-------------|
| FR-STREAM5-01 | Change `stream=False` to `stream=True` in `ralph tasks` |
| FR-STREAM5-02 | Users see Claude's progress during task breakdown |
| FR-STREAM5-03 | JSON extraction continues to work from streamed output |

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

### 3.1 Windows Encoding Detection

Windows terminals can use various encodings:
- `cp1252` - Western European (common)
- `cp437` - Original IBM PC
- `utf-8` - Modern terminals (Windows Terminal, VS Code)

Rich provides `legacy_windows` parameter that forces ASCII-safe output. We should detect the encoding and apply this setting automatically.

### 3.2 Path Handling Strategy

The fix should be in tests only, not in the production code. Commands should continue displaying native paths (backslashes on Windows). Test assertions should normalize for comparison.

Create a test utility function for path normalization to avoid duplicating logic across test files.

### 3.3 Content Detection for Archiving

The PROGRESS.txt template contains:
```
# Ralph Progress Log

## Codebase Patterns
...
```

Actual iteration content contains markers like:
```
## Iteration 1
### Story: US-001
**Status:** Completed
```

Detecting any iteration marker is a reliable heuristic for meaningful content.

### 3.4 File Modification Summary

| File | Changes |
|------|---------|
| `src/ralph/utils/console.py` | Windows encoding detection |
| `src/ralph/services/claude.py` | Centralized flag handling |
| `src/ralph/commands/init_cmd.py` | Auto-PRD prompt |
| `src/ralph/commands/prd.py` | Use consistent flags |
| `src/ralph/commands/tasks.py` | Enable streaming, smart archiving |
| `tests/test_commands/test_prd.py` | Path normalization |
| `tests/test_commands/test_tasks.py` | Path normalization |
| `tests/conftest.py` | Add path normalization utility |

---

## 4. Success Criteria

| # | Criterion | Issue |
|---|-----------|-------|
| 1 | No encoding errors on Windows cp1252 terminals | #15 |
| 2 | All tests pass on Windows | #14 |
| 3 | Empty/template PROGRESS.txt is not archived | #13 |
| 4 | All Claude invocations skip permissions | #12 |
| 5 | `ralph init` prompts for PRD if missing | #11 |
| 6 | `ralph tasks` streams output in real-time | #5 |
| 7 | All existing tests continue to pass on Unix | - |
| 8 | Quality checks (typecheck, lint, format, test) pass | - |

---

## 5. Testing Strategy

### 5.1 Unit Tests

- Test `create_console()` returns console with correct `legacy_windows` setting
- Test `_has_meaningful_content()` with template-only and real content
- Test `_archive_progress_file()` returns `None` for template-only files
- Test path normalization utility function

### 5.2 Integration Tests

- Test `ralph init` prompts for PRD when missing
- Test `ralph tasks` archives only meaningful PROGRESS.txt
- Test `ralph tasks` streams output
- Run full test suite on Windows (CI)

### 5.3 Manual Testing

- Run `ralph` commands on Windows with cp1252 encoding
- Verify no unicode errors in terminal output
- Verify archived files only created for real progress

---

## Appendix A: Issue Reference

| Issue | Title | Type | Priority |
|-------|-------|------|----------|
| #15 | Rich unicode warning symbol fails on Windows cp1252 | Bug | Critical |
| #14 | Windows: Path separator mismatches in tests | Bug | High |
| #13 | PROGRESS.txt archiving should skip empty files | Bug | High |
| #12 | Consistent Claude session flags across all commands | Enhancement | High |
| #11 | ralph init: Auto-run PRD agent if no PRD file exists | Enhancement | Medium |
| #5 | ralph tasks does not stream output | Enhancement | Low |
