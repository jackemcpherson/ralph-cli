# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
