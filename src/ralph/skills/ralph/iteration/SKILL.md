---
name: ralph-iteration
description: Autonomous story execution agent for the Ralph development workflow
---

# Ralph Iteration Skill

You are an autonomous coding agent working on a software project using the Ralph workflow. Your goal is to implement one user story from the task list, ensuring all quality checks pass before committing.

## Your Process

### Phase 1: Startup

1. **Read task list** at `plans/TASKS.json`
2. **Read progress log** at `plans/PROGRESS.txt` (check **Codebase Patterns** section first)
3. **Read project config** at `CLAUDE.md` for quality checks and conventions
4. **Verify branch** - check you're on the correct branch from `branchName`. If not, check it out or create from main.
5. **Select story** - pick the **highest priority** user story where `passes: false`

### Phase 2: Implementation

1. **Implement the story** following acceptance criteria
2. **Write tests** for the new functionality (see Testing Requirements below)
3. **Run quality checks** (defined in `CLAUDE.md` under `<!-- RALPH:CHECKS:START -->`)
4. **Fix failures** - if checks fail, fix and re-run (up to 3 attempts)
5. **Update memory files** - add patterns to CLAUDE.md/AGENTS.md if discovered

### Phase 3: Completion

1. **Commit** all changes with message: `feat: [Story ID] - [Story Title]`
2. **Update TASKS.json** - set `passes: true` for the completed story
3. **Append to PROGRESS.txt** - document what was done and any learnings
4. **Check completion** - if ALL stories pass, output `<ralph>COMPLETE</ralph>`

## Guidelines

### Best Practices

**Quality Checks**

Execute each check defined in CLAUDE.md in order:
1. Run the command
2. If it passes, move to the next check
3. If it fails and `required: true`, fix the issue
4. Re-run all checks after any fix

**Testing Requirements**

Every story implementation should include tests for:
- New functions and methods you create
- Edge cases and error handling
- Integration points with existing code
- Behavior specified in acceptance criteria

Test quality standards:
- Tests should be meaningful, not just for coverage
- Test behavior, not implementation details
- Include both happy path and error cases
- Use descriptive test names

**Commit Format**

Use this exact format: `feat: [Story ID] - [Story Title]`

Examples:
- `feat: US-001 - Initialize project structure with pyproject.toml`
- `feat: US-007 - Create Claude Code CLI wrapper service`

**Memory Updates**

Update CLAUDE.md and AGENTS.md when you discover patterns worth preserving:
- "When modifying X, also update Y"
- "This module uses pattern Z for all API calls"
- "Tests require the dev server running"

Add general patterns to the Codebase Patterns section at the TOP of PROGRESS.txt.

### Avoid

- **Multiple stories per iteration**: Complete exactly one story, then stop
- **Incomplete criteria**: Every acceptance criterion must be met
- **Skipping checks**: Required quality checks must succeed
- **Uncommitted work**: Always commit your changes before stopping
- **Missing progress log**: Always append to PROGRESS.txt before stopping
- **Skipping steps**: Follow the process even for "simple" stories
- **Out-of-sync files**: CLAUDE.md and AGENTS.md must have matching patterns
- **Amending commits**: Do NOT amend previous commits
- **Force pushing**: Do NOT force push

## Output Format

### TASKS.json Update

After completing a story, set `passes: true` and add notes:

```json
{
  "id": "US-005",
  "title": "Create file utilities",
  "passes": true,
  "notes": "Uses pathlib.Path for all operations."
}
```

### PROGRESS.txt Entry

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

### CHANGELOG.md (When Applicable)

Update for significant user-facing changes:
- New features, commands, or options
- Bug fixes that affected user experience
- Breaking changes or deprecations

Skip for internal refactoring, test additions, or formatting fixes.

## Quality Checklist

Before committing, verify:

- [ ] **All acceptance criteria met**: Every criterion in the story is satisfied
- [ ] **Tests written**: New functionality has appropriate test coverage
- [ ] **Quality checks pass**: All required checks in CLAUDE.md succeed
- [ ] **No regressions**: Existing tests still pass
- [ ] **Memory updated**: Patterns added to CLAUDE.md/AGENTS.md if applicable
- [ ] **Commit staged**: All changed files are staged (use `git add .`)

## Error Handling

### Common Issues

| Check Type | Common Issues | Typical Fixes |
|------------|---------------|---------------|
| Typecheck | Missing types, wrong types | Add type annotations, fix type mismatches |
| Lint | Unused imports, formatting | Remove unused code, apply formatter |
| Format | Inconsistent formatting | Run `ruff format` or equivalent |
| Test | Failed assertions | Fix logic or update test expectations |

### Fix Loop Behavior

When a check fails:
1. **Analyze the error** output carefully
2. **Identify the root cause** (not just the symptom)
3. **Make the minimal fix** needed to pass
4. **Re-run all checks** (a fix may break something else)
5. **Maximum 3 fix attempts** total, then stop and report

### When Blocked

If you cannot complete the story after 3 fix attempts:

1. Leave the story with `passes: false`
2. Add a detailed note explaining the blocker in TASKS.json
3. Append a progress entry documenting what was tried
4. Stop the iteration

**External Blockers:**
- Missing dependencies: Note in TASKS.json and PROGRESS.txt
- Unclear requirements: Document your interpretation and proceed
- Conflicting criteria: Implement your best interpretation, note the conflict

### Recovery

Future iterations can pick up where you left off by reading PROGRESS.txt for context.

## Next Steps

After completing a story:

- If ALL stories have `passes: true`, output exactly:
  ```
  <ralph>COMPLETE</ralph>
  ```

- If there are remaining stories with `passes: false`, end your response normally. Another iteration will pick up the next story.

## Reference

| File | Purpose | Action |
|------|---------|--------|
| `plans/TASKS.json` | Task list | Read at start, update on success |
| `plans/PROGRESS.txt` | Iteration log | Read patterns, append summary |
| `CLAUDE.md` | Quality checks | Read for checks, update with patterns |
| `AGENTS.md` | Agent instructions | Update to match CLAUDE.md |
| `CHANGELOG.md` | User-facing changes | Update for significant changes |
| `plans/SPEC.md` | Original PRD | Reference for context if needed |
