# Data Catalog Refresh

Rebuilds the global data catalog by scanning database metadata. This is an **expensive operation** that connects to databases and queries system tables.

**When to use:**
- Catalog doesn't exist (`~/.ds_catalog/metadata.parquet` missing)
- Catalog is stale (>7 days old)
- User explicitly requests a refresh
- New databases or tables have been added

**When NOT to use:**
- Just searching for data (use `/deng-find-data` instead)
- Catalog exists and is recent
- Quick lookups during analysis

## Process

### Step 1: Check Catalog Status

```bash
uv run --with polars python ${CLAUDE_PLUGIN_ROOT}/scripts/catalog_query.py --status
```

If catalog exists and is <7 days old, ask user to confirm they want to refresh anyway.

### Step 2: Verify Environment Variables

Check that required credentials are available:

```bash
# For OMS target, these must be set:
echo "OMS_HOST: ${OMS_HOST:-(not set)}"
echo "OMS_USER: ${OMS_USER:-(not set)}"
echo "OMS_PASSWORD: ${OMS_PASSWORD:+(set)}"
```

If credentials are missing, inform the user:
> Database credentials not found in environment. Ensure OMS_HOST, OMS_USER, and OMS_PASSWORD are set before running the catalog refresh.

### Step 3: Run the Scan

```bash
uv run --with pymssql --with polars --with python-dotenv \
    python ${CLAUDE_PLUGIN_ROOT}/scripts/catalog_refresh.py --target oms
```

For all targets:
```bash
uv run --with pymssql --with polars --with python-dotenv \
    python ${CLAUDE_PLUGIN_ROOT}/scripts/catalog_refresh.py
```

### Step 4: Create Project Snapshot (if in DS project)

If running from a DS project directory (has `configs/project.toml`):

```bash
uv run --with polars \
    python ${CLAUDE_PLUGIN_ROOT}/scripts/catalog_snapshot.py
```

### Step 5: Report Results

Show the user:
1. Number of databases/tables/columns scanned
2. Location of catalog files
3. Any errors encountered
4. Suggest using `/deng-find-data` for searches

## Output Files

| File | Location | Purpose |
|------|----------|---------|
| `metadata.parquet` | `~/.ds_catalog/` | Global catalog (machine-readable) |
| `last_scan.json` | `~/.ds_catalog/` | Scan timestamps |
| `DATA_CATALOG_SUMMARY.md` | `~/.ds_catalog/` | Human-readable summary |
| `snapshot_YYYYMMDD/` | `<project>/artifacts/catalog/` | Project snapshot (if applicable) |

## Available Targets

Targets are configured in `~/.ds_catalog/targets.toml`:

| Target | Description | Databases |
|--------|-------------|-----------|
| `oms` | OMS Server | Orders, Quotes, Customers, Invoices, Products |
| `warehouse` | Data Warehouse | All accessible |

## Error Handling

**Connection failures:**
- Verify environment variables are set
- Check network connectivity to database server
- Confirm credentials are valid

**Permission errors:**
- User may not have access to all databases
- Some system views require elevated permissions
- Script will skip inaccessible databases and continue

## Security Notes

- Credentials are read from environment variables, never stored in config files
- The catalog contains only metadata (schema, types, row counts), no actual data
- Catalog files should not be committed to version control if they contain sensitive schema info
