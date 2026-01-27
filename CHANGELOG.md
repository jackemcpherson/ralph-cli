# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Release tagging:** After merging a release PR, create a git tag matching the version (e.g., `git tag v1.2.6 && git push origin v1.2.6`).

## [2.0.8] - 2026-01-27

### Added

- Bicep template reviewer skill for Azure infrastructure-as-code review (#41)
  - Reviews `.bicep` files for Azure best practices, security, and code quality
  - Checks parameter descriptions, secure decorators, naming conventions
  - Validates module structure, output security, and API version usage
  - Follows same review format as other language reviewers

## [2.0.7] - 2026-01-27

### Fixed

- PowerShell TUI crashes caused by non-compliant Unicode characters (#39)
  - Replaced Unicode checkmark (✓) with `[OK]` for success messages
  - Replaced Unicode ballot X (✗) with `[FAIL]` for error messages
  - Replaced Unicode warning sign (⚠) with `[!]` for warning messages
  - Replaced Unicode bullets (•, ◦) with ASCII hyphens (-) in list output
  - Changed spinner from `dots` (Unicode braille) to `line` (ASCII) for better compatibility
  - All TUI characters are now fully compatible with PowerShell's default character encoding (cp437/cp1252)

## [2.0.6] - 2026-01-22

### Added

- Structured output format for all reviewer skills with `<ralph-review>` verdict tags (US-008 through US-012)
- GitHub issue created for `--no-fix` flag enhancement to skip auto-fix attempts

### Changed

- All reviewer skills now output consistent structured format with verdicts (PASS/NEEDS_WORK), issues table, and fix instructions

## [2.0.5] - 2026-01-22

### Fixed

- Project structure in AGENTS.md updated to reflect bundled skills in `src/ralph/skills/`
- Cleaned up archived PROGRESS files before release

## [2.0.4] - 2026-01-22

### Fixed

- `ralph init --skip-claude` now completes without interactive prompts for automation use cases (US-001)
- Prompts now use `@filepath` references to bundled skill files, reducing token usage (US-002)
- Review loop now displays `[Review X/Y]` progress counters with rich formatting (US-003)

## [2.0.3] - 2026-01-22

### Changed

- Standardized review scope in all reviewer skills to focus on feature branch diff (files changed since branching from main)
- Added **Project Context** section to python-code-reviewer, test-quality-reviewer, and code-simplifier skills
- Added **Test Appropriateness** section to test-quality-reviewer for evaluating whether tests match implementation changes
- Updated REVIEWER_TEMPLATE.md with new review scope pattern for consistency

## [2.0.2] - 2026-01-22

### Fixed

- `ralph tasks` now correctly extracts JSON from Claude's stdout instead of reading stale file content
- CI tests for `--skip-review` and `--strict` flags now pass on Python 3.13 by setting terminal width

## [2.0.1] - 2026-01-22

### Changed

- Refactored `loop.py` with `IterationOutcome` enum and `_execute_story()` helper for clarity
- Simplified language list check in `review_loop.py`
- Leaned test suite further with behavior-focused tests

### Fixed

- Updated SPEC.md to v2.1 for review loop documentation

## [2.0.0] - 2026-01-21

### Added

- **Reviewer skills** - Four new code review skills with structured output format:
  - `python-code-reviewer` - Type hints, docstrings, logging practices
  - `repo-structure-reviewer` - README, .gitignore, project organization
  - `github-actions-reviewer` - CI/CD completeness, security, best practices
  - `test-quality-reviewer` - Meaningful assertions, coverage, anti-patterns
- `skills/REVIEWER_TEMPLATE.md` - Template for creating reviewer-type skills
- `skills/SKILL_TEMPLATE.md` - General skill authoring template
- `src/ralph/utils/prompt.py` with `build_skill_prompt()` function
- Structured review output format with `<ralph-review>PASS|NEEDS_WORK</ralph-review>` verdict tags

### Changed

- **Breaking:** `SkillLoader.load()` now returns `Path` instead of file content string
- Skill loading now uses Claude Code's native `@file` reference syntax instead of embedding skill content in prompts
- Reduced prompt size significantly by referencing skills instead of inlining them
- Refactored all commands (prd, tasks, once, loop) to use skill-based prompts
- Replaced 682 tests with focused 48-test suite covering behavior not implementation

### Removed

- Embedded prompt templates from command files (now in skill files)
- `PERMISSIONS_SYSTEM_PROMPT` constant (permissions now embedded in skills)

## [1.2.6] - 2026-01-21

### Added

- Windows runner (`windows-latest`) in CI matrix for cross-platform verification (#US-003)
- Test coverage for `ralph init` -> PRD invocation flow (#US-002)

### Fixed

- PRD command invocation in `ralph init` now works correctly when user confirms PRD creation (#US-001)
  - Typer Option defaults not applied when calling function directly
  - Now explicitly passes `input_text=None, file=None` to avoid mutual exclusivity error
- Console encoding tests fixed for Windows CI (#US-004)
  - Tests no longer incorrectly assert `legacy_windows=False` when Rich auto-detects Windows

## [1.2.5] - 2026-01-20

### Added

- Auto-PRD prompt in `ralph init` - prompts to create PRD if none exists (#11)
- Windows encoding detection for Rich console with `legacy_windows` support (#15)
- Path normalization test utility for cross-platform test compatibility (#14)
- Centralized Claude CLI flag handling with `SKIP_PERMISSIONS_FLAG` constant (#12)

### Fixed

- Rich unicode symbols now fall back gracefully on Windows cp1252 terminals (#15)
- Test suite now passes on Windows with proper path separator handling (#14)
- PROGRESS.txt archiving now skips template-only files without iteration content (#13)
- All Claude invocations now consistently use `--dangerously-skip-permissions` (#12)

### Changed

- `ClassVar` pattern added to codebase patterns for Pydantic class constants

## [1.2.4] - 2026-01-20

### Fixed

- Claude CLI not found on Windows when installed via npm
  - Windows `subprocess.run()` doesn't resolve `.cmd` files without `shell=True`
  - Now uses `shutil.which()` for cross-platform PATH resolution

## [1.2.3] - 2026-01-18

### Changed

- Version bump for release preparation

## [1.2.2] - 2026-01-18

### Fixed

- Output formatting between Claude's thoughts now displays correctly (#6)
  - v1.2.1 fix was based on Anthropic API format, not Claude CLI format
  - Corrected to add trailing newline to assistant event text content

## [1.2.1] - 2026-01-18

### Fixed

- Attempted fix for newlines between message blocks (#6) - incomplete
  - Added `content_block_stop` detection (incorrect approach)
  - Superseded by v1.2.2

## [1.2.0] - 2026-01-18

### Added

- CHANGELOG.md creation on `ralph init` with Keep a Changelog format (#9)
- CHANGELOG guidelines added to CLAUDE.md and AGENTS.md templates (#9)
- PROGRESS.txt archival when generating new TASKS.json (#8)
- Streaming output for `ralph tasks` command (#5)
- Skip permissions support for `ralph prd` command (#4)

### Fixed

- `ralph once` and `ralph loop` no longer crash when `-v` flag is not provided (#7)
- Output formatting now includes proper newlines between message blocks (#6)

## [1.1.0] - 2026-01-17

### Added

- Non-interactive PRD generation with `--input` and `--file` flags
- File modification detection for PRD creation
- Skip permissions for autonomous iteration (`ralph once` and `ralph loop`)

## [1.0.0] - 2026-01-17

### Added

- Initial release of Ralph CLI
- `ralph init` - Scaffold project for Ralph workflow
- `ralph prd` - Interactive PRD creation with Claude
- `ralph tasks` - Convert spec to TASKS.json
- `ralph once` - Execute single iteration
- `ralph loop` - Run multiple iterations
- `ralph sync` - Sync skills to ~/.claude/skills/
- Three skills: ralph-prd, ralph-tasks, ralph-iteration
