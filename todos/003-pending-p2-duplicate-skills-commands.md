---
status: pending
priority: p2
issue_id: "003"
tags: [code-review, architecture, cleanup]
dependencies: []
---

# Duplicate skills/ and commands/ Directories

## Problem Statement

The plugin has two parallel directory structures with overlapping content:
- `skills/` - Original skill format (5 skills)
- `commands/` - New command format (6 commands)

This creates:
1. Maintenance burden (two places to update)
2. Confusion about which is canonical
3. Potential for drift between versions

## Findings

- **Source**: architecture-strategist, pattern-recognition-specialist agents
- **Location**: `skills/` and `commands/` directories
- **Impact**: MEDIUM - Technical debt and confusion

**Overlap:**
| Skill | Command | Status |
|-------|---------|--------|
| deng-catalog-refresh | deng-catalog-refresh | Duplicated |
| deng-find-data | deng-find-data | Duplicated |
| deng-build-ontology | deng-build-ontology | Duplicated |
| deng-analyze-procedures | deng-analyze-procedures | Duplicated |
| deng-new | (none) | Missing in commands |
| (none) | deng-catalog-status | New in commands |
| (none) | deng-catalog-sync | New in commands |

## Proposed Solutions

### Option A: Delete skills/ directory (Recommended)
**Pros**: Clean slate, single source of truth
**Cons**: Loses deng-new skill content
**Effort**: Small
**Risk**: Low (can recover from git)

1. Create `commands/deng-new.md` from `skills/deng-new/SKILL.md`
2. Delete `skills/` directory
3. Update any references

### Option B: Add DEPRECATED notice to skills/
**Pros**: Preserves history, gradual transition
**Cons**: Still two directories, continued confusion
**Effort**: Small
**Risk**: Low

Add `skills/DEPRECATED.md`:
```markdown
# DEPRECATED

These skills are deprecated. Use commands/ instead.
See commands/ directory for the new format.
```

### Option C: Keep both with clear documentation
**Pros**: Backwards compatibility
**Cons**: Perpetuates the problem
**Effort**: Small
**Risk**: Medium (ongoing confusion)

## Recommended Action

Option A - Complete the migration by converting deng-new and removing skills/.

## Technical Details

**Affected files:**
- `skills/` directory (delete)
- `commands/deng-new.md` (create)
- `.gitignore` (optionally ignore skills/)

## Acceptance Criteria

- [ ] `commands/deng-new.md` exists with full functionality
- [ ] `skills/` directory is removed or deprecated
- [ ] No broken references to skills/

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-27 | Identified in architecture review | Plugin conversion should be complete, not partial |
