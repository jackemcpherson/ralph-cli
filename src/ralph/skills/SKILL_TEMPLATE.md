---
# REQUIRED: Lowercase, hyphens only, max 64 chars. Uses directory name if omitted.
name: skill-name

# RECOMMENDED: One-line description. Claude uses this for auto-invocation decisions.
description: What this skill does and when to use it

# OPTIONAL: Hint for autocomplete (e.g., "[issue-number]", "<file-path>")
# argument-hint: [argument]

# OPTIONAL: Set to true to disable Claude's automatic invocation (user-only)
# disable-model-invocation: false

# OPTIONAL: Set to false to hide from user's "/" menu (Claude-only invocation)
# user-invocable: true

# OPTIONAL: Tools Claude can use without asking permission
# allowed-tools: ["Read", "Glob", "Grep"]

# OPTIONAL: Set to "fork" to run in a subagent
# context: fork

# OPTIONAL: Subagent type when context is "fork"
# agent: Explore
---

# Skill Title

<!--
  ROLE DEFINITION: 2-3 sentences explaining:
  - What role Claude plays when using this skill
  - What the primary goal/outcome is
  - Any key context about the workflow
-->

You are [role description]. Your goal is [primary objective] so that [benefit/outcome].

## Your Process

<!--
  PROCESS: Break into 3-5 numbered phases/steps
  - Keep each phase focused on a single concern
  - Use sub-bullets for details within a phase
  - Phases should flow logically (read -> analyze -> implement -> verify)
-->

### Phase 1: [Discovery/Setup/Input]

1. [First action in this phase]
2. [Second action in this phase]

### Phase 2: [Main Work/Implementation]

1. [First action in this phase]
2. [Second action in this phase]

### Phase 3: [Finalization/Output]

1. [First action in this phase]
2. [Second action in this phase]

## Guidelines

<!--
  GUIDELINES: Split into what TO do and what NOT to do
  - Best Practices: Positive patterns to follow
  - Avoid: Anti-patterns and common mistakes
-->

### Best Practices

- [Pattern or practice to follow]
- [Another good practice]
- [Quality standard to maintain]

### Avoid

- [Anti-pattern or common mistake]
- [Thing that seems right but causes problems]
- [Behavior that leads to poor outcomes]

## Output Format

<!--
  OUTPUT: Define the deliverable structure
  - Use code blocks for schemas/templates
  - Include field descriptions for complex formats
  - Show a concrete example
-->

[Description of what the output should look like]

```[format]
[Schema or template structure]
```

### Example

```[format]
[Concrete example of correct output]
```

## Quality Checklist

<!--
  QUALITY: Verification before completion
  - Use checkboxes for items to verify
  - Cover completeness, correctness, and consistency
  - Include any automated checks to run
-->

Before completing, verify:

- [ ] [Completeness check - all required elements present]
- [ ] [Correctness check - output is valid/accurate]
- [ ] [Consistency check - follows established patterns]
- [ ] [Quality check - meets standards]

## Error Handling

<!--
  ERRORS: How to handle edge cases and blockers
  - Common issues and their resolutions
  - What to do when blocked
  - How to communicate issues to the user
-->

### Common Issues

| Issue | Resolution |
|-------|------------|
| [Problem that may occur] | [How to handle it] |
| [Another common issue] | [Resolution approach] |

### When Blocked

If you cannot complete the task:

1. [First recovery action]
2. [Second recovery action]
3. [How to communicate the blocker]

## Next Steps

<!--
  HANDOFF: What happens after this skill completes
  - Suggest next commands or actions
  - Explain what the user should do with the output
-->

After completion:

> [Suggested next action or command]
>
> ```
> [Example command to run next]
> ```

<!--
  ============================================================
  SKILL AUTHORING TIPS
  ============================================================

  1. KEEP UNDER 500 LINES
     - Move detailed reference material to supporting files
     - Link to external docs rather than duplicating

  2. USE DYNAMIC CONTEXT
     - $ARGUMENTS for passed arguments
     - !`command` for dynamic context injection

  3. SECTION ORDER
     Always use this order for consistency:
     1. Frontmatter (YAML)
     2. Title + Role Definition
     3. Your Process
     4. Guidelines (Best Practices + Avoid)
     5. Output Format + Example
     6. Quality Checklist
     7. Error Handling
     8. Next Steps

  4. REFERENCE vs TASK CONTENT
     - Reference: Knowledge/conventions Claude applies inline
     - Task: Step-by-step instructions for actions
     - Most skills are task-focused

  5. TESTING YOUR SKILL
     - Run `ralph sync` to install
     - Test invocation: `/skill-name` or `ralph once --skill skill-name`
     - Verify Claude understands the process
-->
