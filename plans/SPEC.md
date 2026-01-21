# Ralph CLI v2.0 Specification: Skills-First Architecture

## Metadata

- **Status:** Draft
- **Version:** 2.0.0
- **Last Updated:** 2026-01-21
- **Owner:** To be assigned

---

## 1. Overview

### 1.1 Problem Statement

Ralph CLI has accumulated architectural debt:

1. **Orphaned skills** - The `skills/` directory contains comprehensive instruction files (3,500-9,500 words each), but CLI commands build their own shorter prompts in Python code (300-1,200 words). The skills are never loaded or used at runtime.

2. **Duplicated prompt logic** - Every command has prompt-building logic embedded in Python, creating maintenance burden and drift between skills and actual behavior.

3. **Overly complex codebase** - The codebase has grown more complex than necessary for a CLI that primarily orchestrates Claude invocations.

4. **Bloated test suite** - ~700 tests for a CLI project is excessive, with heavy mocking that tests implementation details rather than behavior.

5. **Incomplete sync command** - `ralph sync` installs skills but provides no way to cleanly remove them.

### 1.2 Goals

1. **Skills-first architecture** - Commands become thin orchestration wrappers that load skills from disk and pass context to Claude. Skills are the source of truth for prompts and instructions.

2. **Simplify codebase** - Remove redundant prompt logic from Python. Commands should assemble context (file paths, story data, branch info) and delegate to skills.

3. **Lean test suite** - Replace ~700 tests with 30-50 focused tests covering happy paths and discrete logic units.

4. **Safe skill removal** - `ralph sync --remove` cleanly uninstalls ralph skills without affecting other user skills.

### 1.3 Non-Goals

- Backward compatibility with pre-2.0 usage patterns
- Adding new CLI commands
- Making `ralph init` skill-driven (it remains pure scaffolding)
- Composing multiple skills per command (keep 1:1 mapping)
- Build-time skill validation (use runtime discovery)

---

## 2. Architecture

### 2.1 Current State

```
Command → Build prompt in Python → ClaudeService.run()
                ↓
         Skills sit unused in skills/
```

Commands embed prompt logic directly. `ClaudeService` has `system_prompt` and `allowed_tools` parameters that are never used.

### 2.2 Target State

```
Command → Load skill from disk → Assemble context → ClaudeService.run(skill_content + context)
```

Skills become the source of truth. Python commands handle:
- Argument parsing (Typer)
- Context assembly (paths, story data, branch info)
- Skill loading
- Claude invocation

### 2.3 Command-to-Skill Mapping

| Command | Skill | Responsibility |
|---------|-------|----------------|
| `ralph prd` | `ralph-prd` | Interactive PRD creation |
| `ralph tasks` | `ralph-tasks` | Convert spec to TASKS.json |
| `ralph once` | `ralph-iteration` | Execute single iteration |
| `ralph loop` | `ralph-iteration` | Execute N iterations (reuses same skill) |
| `ralph init` | None | Pure scaffolding, no AI |
| `ralph sync` | None | Filesystem operations |

---

## 3. Requirements

### 3.1 Skill Loading System

| ID | Requirement |
|----|-------------|
| FR-SKILL-01 | Create `SkillLoader` service that reads skill content from `skills/{name}/SKILL.md` |
| FR-SKILL-02 | Skills are loaded at runtime when commands execute |
| FR-SKILL-03 | Fail fast with clear error if skill file is missing or malformed |
| FR-SKILL-04 | Skill content is passed to Claude as the primary prompt/instruction |

### 3.2 Command Simplification

| ID | Requirement |
|----|-------------|
| FR-CMD-01 | `ralph prd` loads `ralph-prd` skill, passes output path as context |
| FR-CMD-02 | `ralph tasks` loads `ralph-tasks` skill, passes spec file content as context |
| FR-CMD-03 | `ralph once` loads `ralph-iteration` skill, passes story data and project context |
| FR-CMD-04 | `ralph loop` reuses `ralph-iteration` skill for each iteration |
| FR-CMD-05 | Remove all embedded prompt constants and `_build_*_prompt()` functions |
| FR-CMD-06 | Commands assemble minimal context (paths, data) and delegate to skills |

### 3.3 Sync Enhancement

| ID | Requirement |
|----|-------------|
| FR-SYNC-01 | `ralph sync` writes manifest to `~/.claude/skills/.ralph-manifest.json` |
| FR-SYNC-02 | Manifest contains list of installed skill directory names |
| FR-SYNC-03 | `ralph sync --remove` reads manifest and deletes only listed directories |
| FR-SYNC-04 | `ralph sync --remove` deletes the manifest file after cleanup |
| FR-SYNC-05 | `ralph sync --remove` is idempotent (no error if already removed) |
| FR-SYNC-06 | Never delete skills not listed in manifest |

**Manifest format:**
```json
{
  "installed": ["ralph-prd", "ralph-tasks", "ralph-iteration"],
  "synced_at": "2026-01-21T12:00:00Z"
}
```

### 3.4 Test Suite Overhaul

| ID | Requirement |
|----|-------------|
| FR-TEST-01 | Replace existing test suite with focused tests |
| FR-TEST-02 | Integration tests for happy path of each command (5-10 tests) |
| FR-TEST-03 | Unit tests for discrete logic: skill loading, manifest handling, context assembly |
| FR-TEST-04 | Minimal mocking - prefer testing real integration where practical |
| FR-TEST-05 | Target 30-50 total tests |

---

## 4. Technical Considerations

### 4.1 Skill Loading Strategy

Skills are loaded from the project's `skills/` directory at runtime:

```python
class SkillLoader:
    def load(self, skill_name: str) -> str:
        """Load skill content from skills/{skill_name}/SKILL.md"""
        path = self.skills_dir / skill_name / "SKILL.md"
        if not path.exists():
            raise SkillNotFoundError(f"Skill '{skill_name}' not found at {path}")
        return path.read_text()
```

### 4.2 Context Assembly Pattern

Each command assembles context specific to its needs:

```python
# Example: ralph tasks
skill_content = skill_loader.load("ralph-tasks")
spec_content = spec_path.read_text()

prompt = f"{skill_content}\n\n## Spec to Convert\n\n{spec_content}"
claude.run_print_mode(prompt, ...)
```

### 4.3 ClaudeService Usage

Leverage existing but unused parameters:
- `system_prompt` - Could be used for skill content
- `allowed_tools` - Could restrict tools per command if needed

### 4.4 File Changes Summary

| Directory | Changes |
|-----------|---------|
| `src/ralph/services/` | Add `SkillLoader`, enhance `SkillsService` for manifest |
| `src/ralph/commands/` | Simplify all commands to use skill loading |
| `src/ralph/models/` | Add `Manifest` model if needed |
| `tests/` | Replace entire suite with focused tests |
| `skills/` | No changes (skills are already comprehensive) |

---

## 5. Success Criteria

| # | Criterion |
|---|-----------|
| 1 | All commands load instructions from skill files, not Python code |
| 2 | No `_build_*_prompt()` functions or prompt constants in command files |
| 3 | `ralph sync` creates manifest at `~/.claude/skills/.ralph-manifest.json` |
| 4 | `ralph sync --remove` cleanly removes only ralph skills |
| 5 | Test count reduced from ~700 to 30-50 |
| 6 | All quality checks pass (typecheck, lint, format, test) |
| 7 | Commands produce equivalent behavior to pre-refactor |

---

## 6. Migration Notes

This is a major version bump (2.0.0). No migration path is provided for pre-release users. The CLI interface remains the same; only internals change.

**Commands unchanged from user perspective:**
- `ralph init` - Same behavior
- `ralph prd` - Same behavior
- `ralph tasks <spec>` - Same behavior
- `ralph once` - Same behavior
- `ralph loop [n]` - Same behavior
- `ralph sync` - Same behavior, plus new `--remove` flag

---

## Appendix A: Current vs Target Line Counts (Estimated)

| File | Current | Target | Change |
|------|---------|--------|--------|
| `commands/prd.py` | ~80 | ~30 | -60% |
| `commands/tasks.py` | ~120 | ~40 | -65% |
| `commands/once.py` | ~150 | ~50 | -65% |
| `commands/loop.py` | ~80 | ~40 | -50% |
| `services/skills.py` | ~50 | ~100 | +100% (adds loader + manifest) |
| `tests/` | ~700 tests | ~40 tests | -94% |
