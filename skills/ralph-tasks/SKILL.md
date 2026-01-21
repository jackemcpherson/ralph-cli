---
name: ralph-tasks
description: Convert PRD specifications into structured TASKS.json user stories for the Ralph autonomous development workflow
---

# Ralph Tasks Skill

You are converting a Product Requirements Document (PRD) into actionable user stories for the Ralph autonomous development workflow. Your goal is to break down the specification into right-sized, implementable stories that Claude Code can execute autonomously.

## Your Process

### Phase 1: Analysis

1. **Read the specification** carefully to understand the full scope
2. **Identify logical units of work** that can be implemented independently
3. **Map dependencies** between different pieces of functionality

### Phase 2: Story Creation

1. **Order stories by dependency and priority** (foundational work first)
2. **Write clear acceptance criteria** for each story
3. **Assign priorities** following the priority guidelines below

### Phase 3: Output

1. **Generate valid TASKS.json** that matches the schema exactly
2. **Verify** all quality checks pass
3. **Present** for user review

## Guidelines

### Best Practices

**Story Sizing**

A good user story should:
- Be completable in a single iteration (1-2 hours of focused work)
- Have 3-6 clear acceptance criteria
- Be independently testable
- Not require more than 5-7 files to change

**Story Ordering**

- **Foundational first**: Data models → Services → UI/Commands
- **Vertical slices**: For features, create thin end-to-end slices
- **Models before services**: Data structures must exist before logic
- **Services before commands**: Business logic before CLI/API wrappers
- **Core before extensions**: Basic functionality before advanced features

**Priority Assignment**

| Priority Range | Content |
|----------------|---------|
| 1-5 | Core infrastructure and models |
| 6-10 | Service layer and business logic |
| 11-15 | Commands, API, and user interfaces |
| 16-20 | Additional features and polish |
| 21+ | Tests, documentation, and cleanup |

**Acceptance Criteria**

Write criteria as imperative statements:
```
- Create models/user.py with User model containing id, name, email fields
- User model validates email format using Pydantic EmailStr
- Implement get_user_by_id() returning User or None
- Typecheck passes
```

Every story should include at least one of:
- "Typecheck passes" (for typed languages)
- "Tests pass" (if tests are required)
- "Lint passes" (if linting is configured)

### Avoid

**Too Large Stories** (split them):
- More than 6 acceptance criteria
- Touches more than 7 files
- Contains "and" connecting unrelated work
- Requires multiple distinct features

**Too Small Stories** (combine them):
- Only changes one line or adds one field
- Has no meaningful acceptance criteria
- Is pure configuration with no logic

**Poor Criteria**:
- Vague: "Works correctly" (what does correct mean?)
- Implementation details: "Use a for loop" (let the agent decide)
- Duplicates: Same thing worded differently

## Output Format

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

### Example

**Input Specification:**
```markdown
## Requirements
- User authentication with email/password
- Users can view their profile
- Admin users can manage other users
```

**Output TASKS.json:**
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

## Quality Checklist

Before outputting, verify:

- [ ] **Valid JSON**: Parseable with no syntax errors
- [ ] **Schema compliance**: All required fields present with correct types
- [ ] **ID uniqueness**: No duplicate story IDs
- [ ] **Priority sequence**: Priorities start at 1 and are sequential
- [ ] **Dependency order**: No story depends on a later story
- [ ] **Criteria quality**: Each story has 3-6 specific, testable criteria
- [ ] **Completeness**: All requirements from spec are covered

## Error Handling

### Common Issues

| Issue | Resolution |
|-------|------------|
| Missing details in spec | Make reasonable assumptions and note them in the description |
| Unclear scope | Err on the side of smaller, focused stories |
| Technology unspecified | Follow patterns from the existing codebase if visible |
| Conflicting requirements | Flag in notes field, implement most likely interpretation |
| Spec too large | Suggest splitting into multiple task files or phases |

### When Blocked

If you cannot create valid TASKS.json:

1. Document what information is missing
2. Note any assumptions you would make
3. Produce a partial task list if possible
4. Explain what the user needs to clarify

## Next Steps

Once TASKS.json is complete:

> Review the generated stories for accuracy, then run:
>
> ```
> ralph loop
> ```
>
> This will begin autonomous implementation of the user stories.
