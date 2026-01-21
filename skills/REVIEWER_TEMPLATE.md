---
# REQUIRED: Lowercase, hyphens only, max 64 chars
name: reviewer-name

# REQUIRED: One-line description for auto-invocation decisions
description: Reviews [aspect] against [standards]. Use after [trigger].

# OPTIONAL: Uncomment to disable automatic invocation (user-only)
# disable-model-invocation: false

# OPTIONAL: Tools Claude can use without asking permission
# allowed-tools: ["Read", "Glob", "Grep"]
---

# [Reviewer Title]

<!--
  ROLE DEFINITION: Define the reviewer role and scope.
  - What expertise Claude brings to this review
  - What the primary goal is
  - When this reviewer should be invoked
-->

You are a [role] responsible for reviewing [scope] against [standard]. Your goal is to identify issues that violate standards and provide actionable feedback.

## Review Scope

<!--
  SCOPE: Define what gets reviewed.
  - Changed files since last commit? Staged files? Entire codebase?
  - Specific file patterns to include/exclude?
  - Note any future expansion (e.g., --full flag)
-->

Review files modified since the last commit or currently staged.

To identify changed files:
1. Run `git diff --name-only HEAD` for uncommitted changes
2. Run `git diff --name-only --cached` for staged changes
3. Filter to relevant file patterns (e.g., `*.py` for Python)

> **Future**: A `--full` flag will review the entire codebase.

## Standards

### Core Rules

<!--
  CORE RULES: Embed the mandatory standards (blocking - errors).
  These are adapted from authoritative sources (e.g., OLD.md).
  Violations here produce errors that must be fixed.
-->

**[Category 1]**
- Rule 1: [Specific requirement]
- Rule 2: [Specific requirement]

**[Category 2]**
- Rule 3: [Specific requirement]
- Rule 4: [Specific requirement]

### Project Overrides

Projects can customize standards by creating override files:
- `CLAUDE.md` - Project-wide coding standards section
- `.ralph/[skill-name]-standards.md` - Skill-specific overrides

When overrides exist, merge them with core rules (project rules take precedence).

## Your Process

### Phase 1: Gather

1. Identify changed files using git commands
2. Filter to relevant file patterns
3. Check for project override files
4. Read each file to be reviewed

### Phase 2: Analyze

1. Apply core rules to each file
2. Apply project overrides if present
3. Classify each issue by severity:
   - **error**: Violates blocking requirement (must fix)
   - **warning**: Non-blocking recommendation (should fix)
   - **suggestion**: Could be improved (consider)
4. Document specific location and remediation for each issue

### Phase 3: Report

1. Generate the structured output format (below)
2. Include all issues found with locations
3. Summarize issue counts by severity
4. Emit the verdict tag

## Severity Levels

| Level | Meaning | Action |
|-------|---------|--------|
| error | Violates blocking requirement | Must fix before approval |
| warning | Non-blocking recommendation | Should fix |
| suggestion | Could be improved | Consider fixing |

## Output Format

```markdown
## Review: [skill-name] - [scope description]

### Issues Found

| Severity | Location | Issue | Suggestion |
|----------|----------|-------|------------|
| error | file.py:42 | [What's wrong] | [How to fix] |
| warning | file.py:55 | [What's wrong] | [How to fix] |
| suggestion | file.py:70 | [What could improve] | [Recommendation] |

### Summary
- X errors (must fix)
- Y warnings (should fix)
- Z suggestions (consider)

<ralph-review>VERDICT</ralph-review>
```

### Verdict Values

- **PASS**: No errors found. Warnings are acceptable but noted.
- **NEEDS_WORK**: Has errors that must be fixed before approval.

## Quality Checklist

Before completing, verify:

- [ ] All changed files were reviewed
- [ ] Each issue has a specific location (file:line)
- [ ] Each issue has an actionable suggestion
- [ ] Severity levels are correctly assigned
- [ ] Summary counts match the issues table
- [ ] Verdict tag is present and correct

## Error Handling

### Common Issues

| Issue | Resolution |
|-------|------------|
| No changed files found | Report "No files to review" with PASS verdict |
| Cannot read a file | Note the file as skipped, continue with others |
| Project override has conflicts | Project rules take precedence over core rules |
| Ambiguous severity | Default to warning unless clearly blocking |

### When Blocked

If you cannot complete the review:

1. Report which files could not be reviewed and why
2. Complete the review for files that could be processed
3. Note limitations in the summary
4. Use NEEDS_WORK verdict if any files were skipped

## Next Steps

After the review:

> If **PASS**: The reviewed files meet standards. Proceed with your workflow.
>
> If **NEEDS_WORK**: Fix the listed errors and re-run the review:
> ```
> /[skill-name]
> ```

<!--
  ============================================================
  REVIEWER SKILL AUTHORING TIPS
  ============================================================

  1. SEVERITY DISCIPLINE
     - errors: Only for clear standard violations
     - warnings: For best practices and recommendations
     - suggestions: For style preferences and optimizations

  2. LOCATION PRECISION
     - Always include file:line format
     - For multi-line issues, use file:start-end

  3. ACTIONABLE FEEDBACK
     - Every issue needs a "how to fix" suggestion
     - Be specific, not "improve this"

  4. VERDICT CONSISTENCY
     - PASS: Zero errors (warnings OK)
     - NEEDS_WORK: One or more errors

  5. ADAPT STANDARDS FROM OLD.md
     - Lines 474-550: Repo structure standards
     - Lines 554-703: Python code standards
     - Lines 707-808: CI/CD workflow standards
     - Lines 814-948: Test quality standards
-->
