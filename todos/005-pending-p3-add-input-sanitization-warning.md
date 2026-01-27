---
status: pending
priority: p3
issue_id: "005"
tags: [code-review, security, documentation]
dependencies: []
---

# Add Input Sanitization Warning to deng-find-data.md

## Problem Statement

The `deng-find-data.md` command shows user input being passed to a bash command without explicit sanitization warning:

```bash
uv run --with polars python ${CLAUDE_PLUGIN_ROOT}/scripts/catalog_query.py "<keywords>" --top 20
```

While the underlying Python script uses argparse (safe), the documentation doesn't emphasize proper quoting.

## Findings

- **Source**: security-sentinel agent
- **Location**: `commands/deng-find-data.md` line 42
- **Impact**: LOW - Documentation improvement

## Proposed Solutions

### Option A: Add security note (Recommended)
**Pros**: Explicit warning, best practice
**Cons**: Adds a few lines
**Effort**: Small
**Risk**: None

Add after line 42:
```markdown
**Note:** Always properly quote the keywords parameter. The underlying script uses argparse for safe argument parsing.
```

### Option B: Show explicit quoting in examples
**Pros**: Demonstrates correct usage
**Cons**: Might be overlooked
**Effort**: Small
**Risk**: None

Update examples to always show proper quoting.

## Recommended Action

Option A - Add explicit security note.

## Technical Details

**Affected files:**
- `commands/deng-find-data.md`

## Acceptance Criteria

- [ ] Security note added about input handling
- [ ] Examples show proper quoting

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-27 | Identified in security review | Documentation should reinforce safe practices |
