---
name: ralph-tasks
description: Convert PRD specifications into structured TASKS.json user stories for the Ralph autonomous development workflow
---

# Ralph Tasks Skill

You are converting a Product Requirements Document (PRD) into actionable user stories for the Ralph autonomous development workflow. Your goal is to break down the specification into right-sized, implementable stories that Claude Code can execute autonomously.

## Your Process

1. **Read the specification** carefully to understand the full scope
2. **Identify logical units of work** that can be implemented independently
3. **Order stories by dependency and priority** (foundational work first)
4. **Write clear acceptance criteria** for each story
5. **Output valid TASKS.json** that matches the schema exactly

## Story Sizing Guidelines

### Right-Sized Stories

A good user story should:

- Be completable in a single iteration (1-2 hours of focused work)
- Have 3-6 clear acceptance criteria
- Be independently testable
- Not require more than 5-7 files to change

### Too Large (Split It)

Signs a story is too large:

- More than 6 acceptance criteria
- Touches more than 7 files
- Contains "and" connecting unrelated work
- Requires multiple distinct features

### Too Small (Combine It)

Signs a story is too small:

- Only changes one line or adds one field
- Has no meaningful acceptance criteria
- Is pure configuration with no logic

### Story Breakdown Patterns

**Foundational First**: Start with data models, then services, then UI/commands
```
1. Create data models
2. Create service layer
3. Create API/CLI interface
4. Add tests
```

**Vertical Slices**: For features, create thin end-to-end slices
```
1. Basic happy path (minimal viable feature)
2. Error handling and edge cases
3. Polish and advanced features
```

## Story Ordering and Priority

### Priority Assignment

- **Priority 1-5**: Core infrastructure and models (must exist first)
- **Priority 6-10**: Service layer and business logic
- **Priority 11-15**: Commands, API, and user interfaces
- **Priority 16-20**: Additional features and polish
- **Priority 21+**: Tests, documentation, and cleanup

### Dependency Rules

1. **Models before services**: Data structures must exist before logic that uses them
2. **Services before commands**: Business logic before CLI/API wrappers
3. **Core before extensions**: Basic functionality before advanced features
4. **Setup before teardown**: Initialization before cleanup/error handling

### Ordering Checklist

Before finalizing order, verify:

- [ ] No story depends on a higher-priority (later) story
- [ ] Related stories are grouped together
- [ ] Each story builds on previously completed work
- [ ] Early stories establish patterns later stories follow

## Writing Acceptance Criteria

### Good Acceptance Criteria

Each criterion should be:

- **Specific**: Exactly what should happen
- **Testable**: Can verify pass/fail
- **Independent**: Doesn't duplicate other criteria

### Format

Write criteria as imperative statements:

```
- Create models/user.py with User model containing id, name, email fields
- User model validates email format using Pydantic EmailStr
- Implement get_user_by_id() returning User or None
- Typecheck passes
```

### Always Include

Every story should have at least one of:

- "Typecheck passes" (for typed languages)
- "Tests pass" (if tests are required)
- "Lint passes" (if linting is configured)

### Avoid

- Vague criteria: "Works correctly" (what does correct mean?)
- Implementation details: "Use a for loop" (let the agent decide)
- Duplicate criteria: Same thing worded differently

## Output Schema

Your output MUST be valid JSON matching this exact schema:

```json
{
  "project": "ProjectName",
  "branchName": "ralph/feature-name",
  "description": "Brief description of the feature being implemented",
  "userStories": [
    {
      "id": "US-001",
      "title": "Short descriptive title",
      "description": "As a [user], I want [feature] so that [benefit]",
      "acceptanceCriteria": [
        "Specific testable criterion 1",
        "Specific testable criterion 2",
        "Typecheck passes"
      ],
      "priority": 1,
      "passes": false,
      "notes": ""
    }
  ]
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `project` | string | Project name (use from spec or derive from context) |
| `branchName` | string | Git branch name, format: `ralph/feature-name` |
| `description` | string | One-line feature summary |
| `userStories` | array | Ordered list of user stories |

### UserStory Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique ID in format `US-NNN` (e.g., US-001, US-002) |
| `title` | string | Short title (5-10 words) |
| `description` | string | Full user story in "As a... I want... so that..." format |
| `acceptanceCriteria` | string[] | List of specific, testable criteria (3-6 items) |
| `priority` | number | Execution order (lower = first, start at 1) |
| `passes` | boolean | Always `false` for new stories |
| `notes` | string | Always `""` for new stories (filled during implementation) |

## Example Transformation

### Input Specification

```markdown
## Requirements
- User authentication with email/password
- Users can view their profile
- Admin users can manage other users
```

### Output TASKS.json

```json
{
  "project": "UserAuth",
  "branchName": "ralph/user-authentication",
  "description": "User authentication system with profile viewing and admin management",
  "userStories": [
    {
      "id": "US-001",
      "title": "Create User model with authentication fields",
      "description": "As a developer, I need the User data model to store authentication and profile information.",
      "acceptanceCriteria": [
        "Create models/user.py with User Pydantic model",
        "User model has fields: id, email, password_hash, name, is_admin",
        "Email field validates format using EmailStr",
        "Model has created_at and updated_at timestamp fields",
        "Typecheck passes"
      ],
      "priority": 1,
      "passes": false,
      "notes": ""
    },
    {
      "id": "US-002",
      "title": "Implement authentication service",
      "description": "As a developer, I need authentication logic for user login and password verification.",
      "acceptanceCriteria": [
        "Create services/auth.py with AuthService class",
        "Implement hash_password() using bcrypt",
        "Implement verify_password() to check password against hash",
        "Implement authenticate(email, password) returning User or None",
        "Typecheck passes"
      ],
      "priority": 2,
      "passes": false,
      "notes": ""
    },
    {
      "id": "US-003",
      "title": "Create user profile viewing endpoint",
      "description": "As a user, I want to view my profile so that I can see my account information.",
      "acceptanceCriteria": [
        "Create GET /profile endpoint requiring authentication",
        "Endpoint returns current user's profile data",
        "Response excludes password_hash field",
        "Returns 401 if not authenticated",
        "Typecheck passes"
      ],
      "priority": 3,
      "passes": false,
      "notes": ""
    }
  ]
}
```

## Quality Checks

Before outputting, verify:

1. **Valid JSON**: Parseable with no syntax errors
2. **Schema compliance**: All required fields present with correct types
3. **ID uniqueness**: No duplicate story IDs
4. **Priority sequence**: Priorities start at 1 and are sequential
5. **Dependency order**: No story depends on a later story
6. **Criteria quality**: Each story has 3-6 specific, testable criteria
7. **Completeness**: All requirements from spec are covered

## Handling Ambiguity

If the specification is unclear:

- **Missing details**: Make reasonable assumptions and note them in the description
- **Unclear scope**: Err on the side of smaller, focused stories
- **Technology unspecified**: Follow patterns from the existing codebase if visible
- **Conflicting requirements**: Flag in notes field, implement most likely interpretation

## After Task Generation

Once TASKS.json is complete, the user should:

1. Review the generated stories for accuracy
2. Adjust priorities if needed
3. Run `ralph loop` to begin autonomous implementation

Output format reminder: Return ONLY the JSON. Do not wrap in markdown code blocks unless specifically instructed. The output should be directly parseable as JSON.
