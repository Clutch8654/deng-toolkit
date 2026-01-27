---
status: pending
priority: p3
issue_id: "006"
tags: [code-review, simplicity, plugin-structure]
dependencies: []
---

# Unnecessary Metadata in plugin.json

## Problem Statement

The `plugin.json` contains metadata fields that are not consumed by Claude Code's plugin loader:

```json
"author": "Jensen Carlsen",
"homepage": "https://github.com/Clutch8654/deng-toolkit",
"installation": { ... },
"requirements": { ... }
```

These add 12 lines without functional benefit - the requirements are never validated.

## Findings

- **Source**: code-simplicity-reviewer agent
- **Location**: `.claude-plugin/plugin.json` lines 5-6, 47-54
- **Impact**: LOW - YAGNI violation

## Proposed Solutions

### Option A: Remove unnecessary fields (Recommended)
**Pros**: Cleaner manifest, YAGNI compliance
**Cons**: Loses some human-readable info
**Effort**: Small
**Risk**: None

### Option B: Keep as documentation
**Pros**: Self-documenting manifest
**Cons**: Misleading (suggests validation)
**Effort**: None
**Risk**: Low

## Recommended Action

Option A - Remove or move to README.

## Technical Details

**Minimal plugin.json:**
```json
{
  "name": "deng-toolkit",
  "version": "1.0.0",
  "description": "Data engineering toolkit for database metadata management",
  "components": {
    "commands": [...],
    "hooks": { "file": "hooks/hooks.json" },
    "mcpServers": { "file": ".mcp.json" }
  }
}
```

## Acceptance Criteria

- [ ] plugin.json contains only functional fields
- [ ] Installation/requirements info moved to README

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-27 | Identified in simplicity review | Manifests should be minimal |
