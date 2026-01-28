---
name: deng-catalog-sync
description: Sync the data catalog to a git repository for version control and team sharing
---

# Data Catalog Sync

Git operations for the data catalog at `~/.deng-toolkit/catalog/`.

The catalog directory IS the git repository - no intermediate sync needed.

## Usage

```
/deng-catalog-sync              # Show status (git status)
/deng-catalog-sync --push       # Commit and push changes
/deng-catalog-sync --pull       # Pull latest from remote
/deng-catalog-sync --init       # Initialize as git repo
```

## First-Time Setup

```bash
# Initialize the catalog as a git repo
~/.deng-toolkit/scripts/catalog_sync.sh --init

# Add your remote
cd ~/.deng-toolkit/catalog
git remote add origin <your-catalog-repo-url>
git push -u origin main
```

Or clone an existing catalog:

```bash
rm -rf ~/.deng-toolkit/catalog
git clone <your-catalog-repo-url> ~/.deng-toolkit/catalog
```

## Execution

Run the script directly:

```bash
~/.deng-toolkit/scripts/catalog_sync.sh --status
~/.deng-toolkit/scripts/catalog_sync.sh --push
~/.deng-toolkit/scripts/catalog_sync.sh --pull
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
