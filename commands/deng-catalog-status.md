# Catalog Status

Shows the current status, age, and statistics of the data catalog.

## Usage

```
/deng-catalog-status
```

## Process

### Step 1: Check Status

```bash
uv run --with polars python ${CLAUDE_PLUGIN_ROOT}/scripts/catalog_query.py --status
```

### Step 2: Report

Display:
- **Status**: OK, STALE, or NOT BUILT
- **Last updated**: ISO timestamp
- **Age**: Days since last refresh
- **Statistics**:
  - Number of targets
  - Number of databases
  - Number of tables
  - Number of columns

### Step 3: Recommendations

Based on status:

| Status | Message |
|--------|---------|
| OK (< 7 days) | Catalog is current. Use `/deng-find-data` to search. |
| STALE (> 7 days) | Catalog may be outdated. Consider running `/deng-catalog-refresh`. |
| NOT BUILT | No catalog found. Run `/deng-catalog-refresh` to build it. |

## Example Output

```
Catalog Status: OK
Last updated: 2026-01-25T14:32:00
Age: 2 days

Statistics:
  - 1 target
  - 5 databases
  - 237 tables
  - 3,839 columns

Ontology: Built (157 relationships)
Procedures: Analyzed (342 objects)

Use /deng-find-data to search the catalog.
```

## Related Commands

| Command | Purpose |
|---------|---------|
| `/deng-catalog-refresh` | Rebuild the catalog |
| `/deng-find-data` | Search the catalog |
| `/deng-catalog-sync` | Sync with team |
