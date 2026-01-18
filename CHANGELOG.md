# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
