# Ralph CLI v2.1 Specification: Review Loop

## Metadata

- **Status:** Draft
- **Version:** 2.1.0
- **Last Updated:** 2026-01-22
- **Owner:** To be assigned

---

## 1. Overview

### 1.1 Problem Statement

The Ralph workflow currently completes user stories but lacks a quality assurance phase. After all stories pass, the code may still have:

1. **Code quality issues** - Overly complex code, missed simplification opportunities, inconsistent patterns
2. **Test gaps** - Weak assertions, missing edge cases, low-value tests
3. **Infrastructure problems** - Misconfigured CI/CD workflows, non-standard repository structure
4. **Release readiness issues** - Missing changelog entries, version mismatches, stale progress logs

Currently, users must manually invoke reviewer skills or skip quality review entirely.

### 1.2 Goals

1. **Automated review loop** - After `ralph loop` completes all stories, automatically spawn fresh Claude instances to run configured reviewers
2. **Configurable reviewer pipeline** - Define which reviewers run, their order, and severity levels via CLAUDE.md (consistent with existing checks pattern)
3. **Language-aware reviews** - Auto-detect project languages and run appropriate language-specific reviewers
4. **Flexible strictness** - Support `--strict` mode for enforcing warnings, and `--skip-review` for bypassing reviews entirely
5. **Organized skills directory** - Restructure skills into logical categories for better maintainability

### 1.3 Non-Goals

- Adding review capability to `ralph once` (single iteration)
- Creating new reviewer skills from scratch (they exist or are separate work items)
- Cross-language code review (each language has its own reviewer)
- Interactive review mode (reviews are fully autonomous)
- Caching or incremental reviews (each run reviews everything)

---

## 2. Architecture

### 2.1 Current State

```
ralph loop
    ↓
Execute stories until all pass
    ↓
Done (no quality review)
```

### 2.2 Target State

```
ralph loop [--skip-review] [--strict]
    ↓
Execute stories until all pass
    ↓
(unless --skip-review)
    ↓
Load reviewer config from CLAUDE.md
    ↓
Auto-detect project languages
    ↓
For each reviewer (in order):
    ├── Skip if language filter doesn't match
    ├── Spawn fresh Claude instance with reviewer skill
    ├── Implement suggested changes
    ├── Append summary to PROGRESS.txt
    └── Continue to next reviewer
    ↓
Done
```

### 2.3 Skills Directory Restructure

**Current structure (flat):**
```
skills/
├── code-simplifier/
├── github-actions-reviewer/
├── python-code-reviewer/
├── ralph-iteration/
├── ralph-prd/
├── ralph-tasks/
├── repo-structure-reviewer/
└── test-quality-reviewer/
```

**Target structure (nested):**
```
skills/
├── ralph/                      # Core workflow skills
│   ├── prd/
│   │   └── SKILL.md
│   ├── tasks/
│   │   └── SKILL.md
│   └── iteration/
│       └── SKILL.md
└── reviewers/                  # All reviewer skills
    ├── code-simplifier/
    │   └── SKILL.md
    ├── test-quality/
    │   └── SKILL.md
    ├── repo-structure/
    │   └── SKILL.md
    ├── github-actions/
    │   └── SKILL.md
    ├── release/                # New skill
    │   └── SKILL.md
    └── language/               # Language-specific reviewers
        └── python/
            └── SKILL.md
```

**Skill reference format:** `ralph/prd`, `reviewers/code-simplifier`, `reviewers/language/python`

---

## 3. Requirements

### 3.1 Reviewer Configuration

| ID | Requirement |
|----|-------------|
| FR-REV-01 | Reviewers are configured in CLAUDE.md between `<!-- RALPH:REVIEWERS:START -->` and `<!-- RALPH:REVIEWERS:END -->` markers |
| FR-REV-02 | Configuration uses YAML format consistent with existing checks |
| FR-REV-03 | Each reviewer entry has: `name`, `skill`, `level` (blocking/warning/suggestion) |
| FR-REV-04 | Reviewers can optionally specify `languages: [python, typescript, ...]` filter |
| FR-REV-05 | Reviewers execute in the order defined in configuration |
| FR-REV-06 | Default configuration is provided when markers are not present |

**Configuration format:**
```yaml
<!-- RALPH:REVIEWERS:START -->
reviewers:
  - name: test-quality
    skill: reviewers/test-quality
    level: blocking
  - name: code-simplifier
    skill: reviewers/code-simplifier
    level: blocking
  - name: python-code
    skill: reviewers/language/python
    languages: [python]
    level: blocking
  - name: github-actions
    skill: reviewers/github-actions
    level: warning
  - name: repo-structure
    skill: reviewers/repo-structure
    level: warning
  - name: release
    skill: reviewers/release
    level: blocking
<!-- RALPH:REVIEWERS:END -->
```

### 3.2 Language Detection

| ID | Requirement |
|----|-------------|
| FR-LANG-01 | Auto-detect project languages from marker files |
| FR-LANG-02 | `pyproject.toml` or `setup.py` → Python |
| FR-LANG-03 | `package.json` → JavaScript/TypeScript |
| FR-LANG-04 | `go.mod` → Go |
| FR-LANG-05 | `Cargo.toml` → Rust |
| FR-LANG-06 | Multiple languages can be detected simultaneously |
| FR-LANG-07 | Language detection runs once at start of review loop |

### 3.3 Review Loop Execution

| ID | Requirement |
|----|-------------|
| FR-EXEC-01 | Review loop runs only after all stories in `ralph loop` pass |
| FR-EXEC-02 | Each reviewer spawns a fresh Claude instance (clean context) |
| FR-EXEC-03 | Reviewer receives the skill content and implements changes |
| FR-EXEC-04 | After each reviewer completes, append summary to PROGRESS.txt |
| FR-EXEC-05 | If reviewer finds blocking issues and fix fails, retry up to 3 times |
| FR-EXEC-06 | After 3 failed attempts, log the issue and continue to next reviewer |
| FR-EXEC-07 | Reviewers without `languages` filter always run |
| FR-EXEC-08 | Reviewers with `languages` filter only run if language is detected |

### 3.4 CLI Flags

| ID | Requirement |
|----|-------------|
| FR-FLAG-01 | `--skip-review` bypasses the entire review loop |
| FR-FLAG-02 | `--strict` treats `warning` level reviewers as blocking |
| FR-FLAG-03 | Default behavior (no flags): review enabled, only `blocking` level enforced |
| FR-FLAG-04 | `suggestion` level reviewers are always informational (logged but not enforced) |

**Behavior matrix:**

| Flag | Blocking | Warning | Suggestion |
|------|----------|---------|------------|
| (default) | Enforced | Logged | Logged |
| `--strict` | Enforced | Enforced | Logged |
| `--skip-review` | Skipped | Skipped | Skipped |

### 3.5 Release Reviewer Skill

| ID | Requirement |
|----|-------------|
| FR-RELEASE-01 | Create new `reviewers/release` skill |
| FR-RELEASE-02 | Check for changelog entries corresponding to changes |
| FR-RELEASE-03 | Verify version consistency between pyproject.toml and __init__.py |
| FR-RELEASE-04 | Verify nothing is missing from CHANGELOG.md, AGENTS.md, CLAUDE.md, and README.md |
| FR-RELEASE-05 | Clean up PROGRESS.txt archives in plans/ after verification |
| FR-RELEASE-06 | Verify git tag readiness (version not already tagged) |
| FR-RELEASE-07 | Check for any TODOs or FIXMEs that should be addressed |

### 3.6 Skills Directory Restructure

| ID | Requirement |
|----|-------------|
| FR-STRUCT-01 | Move `ralph-prd/` to `ralph/prd/` |
| FR-STRUCT-02 | Move `ralph-tasks/` to `ralph/tasks/` |
| FR-STRUCT-03 | Move `ralph-iteration/` to `ralph/iteration/` |
| FR-STRUCT-04 | Move `code-simplifier/` to `reviewers/code-simplifier/` |
| FR-STRUCT-05 | Move `test-quality-reviewer/` to `reviewers/test-quality/` |
| FR-STRUCT-06 | Move `repo-structure-reviewer/` to `reviewers/repo-structure/` |
| FR-STRUCT-07 | Move `github-actions-reviewer/` to `reviewers/github-actions/` |
| FR-STRUCT-08 | Move `python-code-reviewer/` to `reviewers/language/python/` |
| FR-STRUCT-09 | Create `reviewers/release/` with new skill |

### 3.7 Sync Command Updates

| ID | Requirement |
|----|-------------|
| FR-SYNC-01 | `ralph sync` mirrors nested structure to `~/.claude/skills/` |
| FR-SYNC-02 | Manifest stores full paths: `["ralph/prd", "reviewers/code-simplifier", ...]` |
| FR-SYNC-03 | `ralph sync --remove` removes nested directories correctly |
| FR-SYNC-04 | Clean up any old flat-structure skills during sync |

### 3.8 Skill Loader Updates

| ID | Requirement |
|----|-------------|
| FR-LOADER-01 | SkillLoader accepts nested paths like `ralph/prd` |
| FR-LOADER-02 | Update all command skill references to use new paths |
| FR-LOADER-03 | Maintain backward compatibility during transition (optional) |

---

## 4. Technical Considerations

### 4.1 Reviewer Configuration Parsing

Reuse the existing YAML parsing pattern from checks:

```python
def parse_reviewers(claude_md_content: str) -> list[ReviewerConfig]:
    """Parse reviewers from CLAUDE.md YAML block."""
    match = re.search(
        r'<!-- RALPH:REVIEWERS:START -->\s*```yaml\s*(.*?)\s*```\s*<!-- RALPH:REVIEWERS:END -->',
        claude_md_content,
        re.DOTALL
    )
    if not match:
        return get_default_reviewers()

    data = yaml.safe_load(match.group(1))
    return [ReviewerConfig(**r) for r in data.get('reviewers', [])]
```

### 4.2 Language Detection

```python
LANGUAGE_MARKERS = {
    'python': ['pyproject.toml', 'setup.py', 'requirements.txt'],
    'javascript': ['package.json'],
    'typescript': ['package.json', 'tsconfig.json'],
    'go': ['go.mod'],
    'rust': ['Cargo.toml'],
}

def detect_languages(project_root: Path) -> set[str]:
    """Detect project languages from marker files."""
    detected = set()
    for language, markers in LANGUAGE_MARKERS.items():
        if any((project_root / marker).exists() for marker in markers):
            detected.add(language)
    return detected
```

### 4.3 Review Loop Flow

```python
async def run_review_loop(
    reviewers: list[ReviewerConfig],
    detected_languages: set[str],
    strict: bool,
    progress_file: Path,
) -> None:
    for reviewer in reviewers:
        # Skip if language filter doesn't match
        if reviewer.languages and not (set(reviewer.languages) & detected_languages):
            console.print(f"Skipping {reviewer.name} (language not detected)")
            continue

        # Determine if enforced
        enforced = reviewer.level == 'blocking' or (strict and reviewer.level == 'warning')

        # Spawn fresh Claude instance
        success = await run_reviewer_with_retries(
            reviewer,
            enforced=enforced,
            max_retries=3,
        )

        # Log to progress
        append_review_summary(progress_file, reviewer, success)
```

### 4.4 Manifest Format Update

```json
{
  "version": 2,
  "installed": [
    "ralph/prd",
    "ralph/tasks",
    "ralph/iteration",
    "reviewers/code-simplifier",
    "reviewers/test-quality",
    "reviewers/repo-structure",
    "reviewers/github-actions",
    "reviewers/release",
    "reviewers/language/python"
  ],
  "synced_at": "2026-01-22T12:00:00Z"
}
```

### 4.5 Migration Path

1. Run `ralph sync --remove` to clean old skills
2. Restructure skills directory
3. Update skill references in code
4. Run `ralph sync` to install new structure
5. Update CLAUDE.md with reviewer configuration

---

## 5. Success Criteria

| # | Criterion |
|---|-----------|
| 1 | `ralph loop` runs review loop after stories complete (default behavior) |
| 2 | `ralph loop --skip-review` bypasses review loop entirely |
| 3 | `ralph loop --strict` enforces warning-level reviewers |
| 4 | Reviewers execute in configured order |
| 5 | Language-specific reviewers only run when language detected |
| 6 | Each review iteration appends summary to PROGRESS.txt |
| 7 | Skills directory uses nested structure |
| 8 | `ralph sync` and `ralph sync --remove` work with new structure |
| 9 | All existing commands work with restructured skills |
| 10 | New release reviewer skill created and functional |
| 11 | All quality checks pass (typecheck, lint, format, test) |

---

## 6. Default Reviewer Configuration

When no `<!-- RALPH:REVIEWERS:START -->` block exists, use these defaults:

```yaml
reviewers:
  - name: test-quality
    skill: reviewers/test-quality
    level: blocking
  - name: code-simplifier
    skill: reviewers/code-simplifier
    level: blocking
  - name: python-code
    skill: reviewers/language/python
    languages: [python]
    level: blocking
  - name: github-actions
    skill: reviewers/github-actions
    level: warning
  - name: repo-structure
    skill: reviewers/repo-structure
    level: warning
  - name: release
    skill: reviewers/release
    level: blocking
```

---

## 7. Future Enhancements

The following are out of scope for v2.1 but tracked for future consideration:

1. **Partial review runs** - If `ralph loop` is interrupted mid-review, add capability to resume from where it left off. ([#26](https://github.com/jackemcpherson/ralph-cli/issues/26))
