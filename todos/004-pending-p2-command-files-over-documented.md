---
status: pending
priority: p2
issue_id: "004"
tags: [code-review, simplicity, documentation]
dependencies: []
---

# Command Files Over-Documented

## Problem Statement

The command files contain ~320 lines of reference documentation that belongs elsewhere. This adds cognitive load and makes the actual execution instructions harder to find.

## Findings

- **Source**: code-simplicity-reviewer agent
- **Location**: `commands/*.md` (all 6 files)
- **Impact**: MEDIUM - Maintenance burden, harder to parse

**Estimated removable content:**
| File | Total Lines | Removable | Percentage |
|------|-------------|-----------|------------|
| deng-catalog-refresh.md | 105 | 35 | 33% |
| deng-find-data.md | 134 | 57 | 43% |
| deng-build-ontology.md | 189 | 103 | 55% |
| deng-analyze-procedures.md | 85 | 0 | 0% (good) |
| deng-catalog-status.md | 67 | 27 | 40% |
| deng-catalog-sync.md | 138 | 85 | 62% |

**Content types to remove:**
- JSON-LD schema examples (reference)
- Python usage examples (reference)
- Search ranking algorithm details (internal)
- Team onboarding instructions (belongs in README)
- Example output sections (Claude sees actual output)

## Proposed Solutions

### Option A: Trim to essentials (Recommended)
**Pros**: Cleaner commands, faster to parse
**Cons**: Loses some context
**Effort**: Medium
**Risk**: Low

Each command should follow minimal template:
```markdown
# Command Name
One sentence description.

## When to Use / When NOT to Use
- Bullets

## Process
### Step 1-N with code blocks

## Output
Brief description
```

### Option B: Move reference content to docs/
**Pros**: Preserves all content, better organization
**Cons**: More files, cross-references needed
**Effort**: Medium
**Risk**: Low

Create:
- `docs/JSON_LD_SCHEMA.md`
- `docs/PYTHON_EXAMPLES.md`
- `docs/TEAM_ONBOARDING.md`

### Option C: Keep as-is
**Pros**: No work required
**Cons**: Continued bloat
**Effort**: None
**Risk**: Low (just annoying)

## Recommended Action

Option A with selective Option B - Trim commands to essentials, move team onboarding to README.

## Technical Details

**Specific sections to remove:**
- `deng-find-data.md`: Lines 89-119 (Search Ranking, Common Patterns, MCP duplicate)
- `deng-build-ontology.md`: Lines 98-188 (JSON-LD examples, Python examples)
- `deng-catalog-sync.md`: Lines 46-130 (Team Onboarding, gitignore, OneDrive)

## Acceptance Criteria

- [ ] Each command file is under 100 lines
- [ ] Reference material moved to appropriate location
- [ ] Commands contain only execution instructions

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-27 | Identified in simplicity review | Commands should be instructions, not manuals |
