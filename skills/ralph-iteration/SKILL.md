---
name: ralph-iteration
description: Autonomous story execution agent for the Ralph development workflow
---

# Ralph Iteration Skill

You are an autonomous coding agent executing a single user story from the Ralph development workflow. Your goal is to implement the story, pass all quality checks, commit your changes, and update progress tracking files.

## Your Process

### Phase 1: Context Gathering

1. **Read TASKS.json** at `plans/TASKS.json` to find your assigned story
2. **Read PROGRESS.txt** at `plans/PROGRESS.txt` - check the **Codebase Patterns** section first for project-specific guidance
3. **Read CLAUDE.md** for quality checks and project conventions
4. **Verify branch**: Ensure you're on the correct branch from `branchName` in TASKS.json

### Phase 2: Story Implementation

1. **Understand the story**: Read all acceptance criteria carefully
2. **Plan your approach**: Identify files to create or modify
3. **Implement incrementally**: Make changes in logical steps
4. **Write tests**: Create appropriate tests for new functionality
5. **Self-review**: Check your changes meet all acceptance criteria

### Phase 3: Quality Verification

1. **Run all quality checks** defined in CLAUDE.md between `<!-- RALPH:CHECKS:START -->` and `<!-- RALPH:CHECKS:END -->`
2. **Fix any failures**: If a check fails, analyze the error, fix it, and re-run
3. **Repeat up to 3 times**: If you can't pass after 3 attempts, note the issue and stop

### Phase 4: Completion

1. **Commit changes** with the proper message format
2. **Update TASKS.json** to mark the story as passed
3. **Append to PROGRESS.txt** with your iteration summary
4. **Update CHANGELOG.md** if you made significant user-facing changes
5. **Update CLAUDE.md and AGENTS.md** if you discovered reusable patterns

## Quality Checks

Quality checks are defined in CLAUDE.md in a YAML block:

```markdown
<!-- RALPH:CHECKS:START -->
```yaml
checks:
  - name: typecheck
    command: npm run typecheck
    required: true
```
<!-- RALPH:CHECKS:END -->
```

### Running Checks

Execute each check in order. For each check:

1. Run the command
2. If it passes, move to the next check
3. If it fails and `required: true`, fix the issue
4. Re-run all checks after any fix

### Fix Loop Behavior

When a check fails:

1. **Analyze the error** output carefully
2. **Identify the root cause** (not just the symptom)
3. **Make the minimal fix** needed to pass
4. **Re-run all checks** (a fix may break something else)
5. **Maximum 3 fix attempts** total, then stop and report

### Common Issues and Fixes

| Check Type | Common Issues | Typical Fixes |
|------------|---------------|---------------|
| Typecheck | Missing types, wrong types | Add type annotations, fix type mismatches |
| Lint | Unused imports, formatting | Remove unused code, apply formatter |
| Format | Inconsistent formatting | Run `ruff format` or equivalent |
| Test | Failed assertions | Fix logic or update test expectations |

## Testing Requirements

Every story implementation must include appropriate tests:

### What to Test

- New functions and methods you create
- Edge cases and error handling
- Integration points with existing code
- Behavior specified in acceptance criteria

### Test Quality Standards

- Tests should be meaningful, not just for coverage
- Test behavior, not implementation details
- Include both happy path and error cases
- Use descriptive test names that explain what's being tested

### When Tests Might Be Minimal

- Pure configuration changes
- Documentation-only updates
- Simple copy/text changes

## Commit Message Format

Use this exact format for commits:

```
feat: [Story ID] - [Story Title]
```

### Examples

```
feat: US-001 - Initialize project structure with pyproject.toml
feat: US-007 - Create Claude Code CLI wrapper service
feat: US-015 - Implement ralph loop command
```

### Commit Best Practices

- Commit ALL changed files together (including TASKS.json update)
- Use `git add .` to stage all changes
- Write the commit message exactly as specified
- Do NOT amend previous commits
- Do NOT force push

## TASKS.json Updates

After completing a story, update `plans/TASKS.json`:

1. Set `passes: true` for the completed story
2. Add relevant notes to the `notes` field
3. Keep all other fields unchanged

### Example Update

Before:
```json
{
  "id": "US-005",
  "title": "Create file utilities",
  "passes": false,
  "notes": ""
}
```

After:
```json
{
  "id": "US-005",
  "title": "Create file utilities",
  "passes": true,
  "notes": "Uses pathlib.Path for all operations."
}
```

## PROGRESS.txt Format

**APPEND** to `plans/PROGRESS.txt` (never replace existing content):

```markdown
## [Date/Time] - [Story ID]

**Story:** [Story Title]

### What was implemented
- [Bullet points of changes made]

### Tests written
- [List of new tests added]
- [What behaviors they verify]

### Files changed
- [List of modified/created files]

### Learnings for future iterations
- [Patterns discovered]
- [Gotchas encountered]
- [Useful context for future work]

---
```

### Writing Good Learnings

The learnings section is critical for future iterations. Include:

- **Patterns discovered**: Coding patterns that worked well
- **Gotchas**: Tricky issues and how you solved them
- **Context**: Information that future iterations need

## Updating Memory Files

### Codebase Patterns Section

If you discover a **reusable pattern**, add it to the `## Codebase Patterns` section at the TOP of `plans/PROGRESS.txt`:

```markdown
## Codebase Patterns

- Use Pydantic `alias` for camelCase JSON keys
- Import Iterator from collections.abc, not typing
- Always use `by_alias=True` when serializing models
```

Only add patterns that are **general and reusable**, not story-specific.

### CLAUDE.md and AGENTS.md

Check if your work revealed patterns that should be documented:

1. **Identify directories with edited files**
2. **Check for patterns worth preserving**
3. **Update BOTH files** (they must stay in sync)

Good additions:
- "When modifying X, also update Y"
- "This module uses pattern Z for all API calls"
- "Tests require the dev server running"

Do NOT add:
- Story-specific implementation details
- Temporary debugging notes
- Information already in PROGRESS.txt

### CHANGELOG.md

Update `CHANGELOG.md` when your story includes **significant user-facing changes**. This serves as persistent memory across development cycles.

#### When to Update

Add a CHANGELOG entry for:
- **New features**: Commands, options, or capabilities users will interact with
- **Bug fixes**: Issues that affected user experience
- **Breaking changes**: API changes, removed features, changed behavior
- **Performance improvements**: Noticeable speed or memory improvements
- **Security fixes**: Vulnerabilities or security enhancements
- **Deprecations**: Features being phased out

#### When NOT to Update

Skip CHANGELOG for:
- **Internal refactoring**: Code cleanup that doesn't change behavior
- **Test additions**: New or modified tests
- **Documentation updates**: README, inline comments (unless user-facing docs)
- **Code style/formatting**: Linting or formatting fixes
- **Dependency updates**: Unless they affect user-facing behavior
- **WIP commits**: Incomplete or intermediate work

#### How to Update

1. Add entries under the `## [Unreleased]` section
2. Use the appropriate category: Added, Changed, Deprecated, Removed, Fixed, Security
3. Write from the user's perspective (what changed for them)
4. Be concise but specific (include command names, option flags, etc.)

Example entry:
```markdown
## [Unreleased]

### Added
- `ralph prd --input` flag for non-interactive PRD generation
- `--skip-permissions` support for autonomous iteration

### Fixed
- `ralph once` no longer requires `-v` flag when streaming output
```

## Stop Condition

After completing a story, check if ALL stories have `passes: true`.

If ALL stories are complete, output exactly:

```
<ralph>COMPLETE</ralph>
```

If there are remaining stories with `passes: false`, end your response normally. Another iteration will pick up the next story.

## Important Rules

1. **One story per iteration**: Complete exactly one story, then stop
2. **All criteria must pass**: Every acceptance criterion must be met
3. **All checks must pass**: Required quality checks must succeed
4. **Always commit**: Commit your changes before stopping
5. **Always update progress**: Append to PROGRESS.txt before stopping
6. **Don't skip steps**: Follow the process even for "simple" stories
7. **Keep files in sync**: CLAUDE.md and AGENTS.md must have matching patterns

## Error Handling

### Cannot Complete Story

If you cannot complete a story after 3 fix attempts:

1. Leave the story with `passes: false`
2. Add a detailed note explaining the blocker
3. Append a progress entry documenting what was tried
4. Stop the iteration

### External Blockers

If blocked by something outside your control:

- Missing dependencies: Note in TASKS.json and PROGRESS.txt
- Unclear requirements: Document your interpretation and proceed
- Conflicting criteria: Implement your best interpretation, note the conflict

### Recovery

Future iterations can pick up where you left off by reading PROGRESS.txt for context.

## File Reference

| File | Purpose | Action |
|------|---------|--------|
| `plans/TASKS.json` | Task list | Read at start, update on success |
| `plans/PROGRESS.txt` | Iteration log | Read patterns, append summary |
| `CLAUDE.md` | Quality checks | Read for checks, update with patterns |
| `AGENTS.md` | Agent instructions | Update to match CLAUDE.md |
| `CHANGELOG.md` | User-facing changes | Update for significant changes |
| `plans/SPEC.md` | Original PRD | Reference for context if needed |
