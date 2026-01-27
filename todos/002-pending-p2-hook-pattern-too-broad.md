---
status: pending
priority: p2
issue_id: "002"
tags: [code-review, security, hooks]
dependencies: []
---

# Hook Command Patterns Too Broad

## Problem Statement

The hook patterns in `hooks/hooks.json` use substring matching that could trigger on unintended commands. The pattern `catalog_refresh\\.py` matches any Bash command containing that substring.

## Findings

- **Source**: security-sentinel, architecture-strategist agents
- **Location**: `hooks/hooks.json` lines 7-8, 18-19
- **Impact**: MEDIUM - Hooks could fire on unintended commands

**Current pattern:**
```json
"command_pattern": "catalog_refresh\\.py"
```

**Unintended matches:**
- `cat catalog_refresh.py` (reading the file)
- `git add catalog_refresh.py` (staging)
- `ls catalog_refresh.py` (listing)

## Proposed Solutions

### Option A: Anchor to script execution (Recommended)
**Pros**: More specific, still flexible
**Cons**: Slight complexity increase
**Effort**: Small
**Risk**: Low

```json
"command_pattern": "python.*catalog_refresh\\.py"
```

### Option B: Anchor to full plugin path
**Pros**: Most specific, prevents all false positives
**Cons**: May break if paths change
**Effort**: Small
**Risk**: Low

```json
"command_pattern": "\\$\\{CLAUDE_PLUGIN_ROOT\\}/scripts/catalog_refresh\\.py"
```

### Option C: Use uv run pattern
**Pros**: Matches actual usage in commands
**Cons**: Breaks if execution method changes
**Effort**: Small
**Risk**: Low

```json
"command_pattern": "uv run.*catalog_refresh\\.py"
```

## Recommended Action

Option A - Balance between specificity and flexibility.

## Technical Details

**Affected files:**
- `hooks/hooks.json`

**Pattern updates needed:**
- `catalog_refresh\\.py` → `python.*catalog_refresh\\.py`
- `build_ontology\\.py` → `python.*build_ontology\\.py`

## Acceptance Criteria

- [ ] Hook patterns only match actual script execution
- [ ] `git add catalog_refresh.py` does not trigger hook
- [ ] `uv run python .../catalog_refresh.py` still triggers hook

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-27 | Identified in security review | Regex patterns need careful anchoring |
