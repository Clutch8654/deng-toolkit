---
name: deng-catalog-sync
description: Sync the data catalog to a git repository for version control and team sharing
---

# Data Catalog Sync

Git operations for the data catalog. Location configured in `~/.deng-toolkit/config.yaml`.

## Usage

```
/deng-catalog-sync              # Show status and configuration
/deng-catalog-sync --push       # Commit and push changes
/deng-catalog-sync --pull       # Pull latest from remote
/deng-catalog-sync --full       # Pull, then commit and push
/deng-catalog-sync --init       # Initialize as git repo
```

## Configuration

Edit `~/.deng-toolkit/config.yaml`:

```yaml
catalog_dir: ~/data-catalog
catalog_remote: git@github.com:YourOrg/data-catalog.git
```

Or override with environment variable: `DENG_CATALOG_DIR=/path/to/catalog`

## First-Time Setup

**Option A: Initialize new catalog**

```bash
~/.deng-toolkit/scripts/catalog_sync.sh --init
# If catalog_remote is configured, remote is added automatically
git push -u origin main
```

**Option B: Clone existing team catalog**

```bash
git clone <your-catalog-repo-url> ~/data-catalog
# Update config.yaml if using different path
```

## Execution

Run the script directly:

```bash
~/.deng-toolkit/scripts/catalog_sync.sh --status
~/.deng-toolkit/scripts/catalog_sync.sh --push
~/.deng-toolkit/scripts/catalog_sync.sh --pull
~/.deng-toolkit/scripts/catalog_sync.sh --full
```

## Catalog Files

| File | Purpose |
|------|---------|
| `tables.yaml` | Table metadata (row counts, key columns) |
| `columns.yaml` | Column definitions and semantic roles |
| `joins.yaml` | Validated SQL join patterns |
| `quality_rules.yaml` | Data quality constraints |
| `semantic.yaml` | Business term definitions |

## Integration

Call after `/deng-catalog-refresh` to push new discoveries to the team.
