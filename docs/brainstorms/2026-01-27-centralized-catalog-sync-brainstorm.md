---
date: 2026-01-27
topic: centralized-catalog-sync
---

# Centralized Catalog with Scheduled Git Sync

## What We're Building

A **scheduled Git-based sync system** that replaces manual push/pull workflows with automated hourly merges. The system uses **per-user annotation files** (Automerge CRDTs) to eliminate merge conflicts, with a **GitHub Action** that periodically merges all annotations into a unified view.

**Key components:**
1. Per-user annotation files (`annotations/{username}.automerge`)
2. Scheduled GitHub Action (hourly merge into `annotations/merged.automerge`)
3. MCP server reads merged view, writes to user's file
4. Standard git pull/push for sync (no daemon required)

## Why This Approach

### Approaches Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| **A: REST API + Auto-Sync** | Real-time, central authority | Requires hosting, network dependency | Rejected (infrastructure overhead) |
| **B: Full Catalog Database** | Web UI, GraphQL | Heavy infrastructure, migration effort | Rejected (too much maintenance) |
| **C: Git + Local Daemon** | Simple, offline-first | Daemon permissions, management | Rejected (permission concerns) |
| **C': Git + Scheduled Runner** | No daemon, server-side merge | Hourly latency (acceptable) | **Selected** |

### Why Scheduled Git Runner Wins

1. **No local daemon** - No background process to manage, no SSH key permissions on user machines
2. **No new infrastructure** - Uses existing Git repo + free GitHub Actions
3. **No merge conflicts** - Per-user files mean push never fails
4. **Full git history** - Backtrack, cherry-pick, audit trail built-in
5. **Works with existing MCP** - Minimal changes to current `server.py`

## Key Decisions

- **Per-user annotation files**: Each user writes to `annotations/{username}.automerge`. GitHub Action merges into `merged.automerge`. Eliminates push conflicts entirely.

- **Automerge CRDT format**: Conflict-free by design. Two users annotating same table = both annotations preserved. No manual merge resolution needed.

- **Hourly sync schedule**: GitHub Action runs `0 * * * *` (every hour). Balances freshness with Action minutes. Can adjust to 15-min or daily.

- **MCP reads merged view**: `get_annotations()` reads `merged.automerge`. `add_annotation()` writes to user's file. User runs `git push` when ready.

- **Parquet unchanged**: `metadata.parquet` still refreshed by maintainers, pushed directly. Branch protection optional for review workflow.

- **Changelog auto-generated**: Each merge appends to `CHANGELOG.md` with timestamp and changes summary.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  GitHub Repository                                  │
│  ├── metadata.parquet          (R/O, maintainers)  │
│  ├── annotations/                                   │
│  │   ├── jensen.automerge      (user writes)       │
│  │   ├── alice.automerge       (user writes)       │
│  │   └── merged.automerge      (Action merges)     │
│  ├── CHANGELOG.md              (auto-appended)     │
│  └── .github/workflows/                             │
│      └── scheduled-merge.yml   (hourly trigger)    │
└─────────────────────────────────────────────────────┘
              ▲
              │ git pull/push (manual, when user chooses)
              │
    ┌─────────┴─────────────────────────────────────┐
    │ User's Machine                                 │
    │ ┌───────────────────────────────────────────┐ │
    │ │ MCP Server (servers/catalog_mcp/)         │ │
    │ │  - search_catalog()     reads parquet     │ │
    │ │  - get_annotations()    reads merged.am   │ │
    │ │  - add_annotation()     writes user.am    │ │
    │ └───────────────────────────────────────────┘ │
    │ ┌───────────────────────────────────────────┐ │
    │ │ /deng-catalog-sync command                │ │
    │ │  - git pull (default)                     │ │
    │ │  - git push (with --push flag)            │ │
    │ └───────────────────────────────────────────┘ │
    └───────────────────────────────────────────────┘
```

## User Workflow

```bash
# 1. Get latest (includes everyone's merged annotations)
/deng-catalog-sync   # or: git pull

# 2. Search and annotate
/deng-find-data "order churn"
# MCP tool: add_annotation("Orders.Order", "Primary order table", "jensen")

# 3. Push when ready
/deng-catalog-sync --push   # or: git push

# 4. Within 1 hour, GitHub Action merges into merged.automerge
# 5. Others get your annotations on their next pull
```

## Open Questions

- **Username detection**: How does MCP server know current user? Options: environment variable, git config, explicit parameter.
- **Annotation schema**: What fields? `{notes: [], quality_flags: [], deprecated: bool, trust_score: int?}`
- **Large team scaling**: At 50+ users, 50 Automerge files to merge. May need batching or hierarchical merge.
- **Offline conflict**: If user never pulls, their local merged view diverges. Acceptable? Or warn if >24h stale?

## Implementation Scope

### Phase 1: Foundation
- Create `annotations/` directory structure
- Implement `merge_all_annotations.py` script
- Create GitHub Action workflow
- Update MCP server with annotation read/write

### Phase 2: MCP Integration
- Add `get_annotations()` tool
- Add `add_annotation()` tool
- Update `search_catalog()` to include annotations in results
- Update `/deng-catalog-sync` command

### Phase 3: Polish
- Add `generate_changelog.py` for human-readable history
- Add MCP tool `get_recent_changes()` for team activity
- Branch protection rules for parquet changes

## Next Steps

→ `/workflows:plan` for detailed implementation plan
