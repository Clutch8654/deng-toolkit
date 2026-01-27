# Data Catalog Search

Fast keyword search against the cached data catalog. **No database access required** - searches pre-built metadata only.

**When to use:**
- Looking for tables related to a concept (e.g., "churn", "order", "invoice")
- Finding columns by name pattern
- Discovering join paths between tables
- Before writing any SQL query

**When NOT to use:**
- Catalog doesn't exist (use `/deng-catalog-refresh` first)
- Need actual data values (requires SQL query)

## Usage

```
/deng-find-data <keywords>
```

Examples:
```
/deng-find-data order cancel
/deng-find-data customer churn
/deng-find-data invoice payment
/deng-find-data activation date
```

## Process

### Step 1: Check Catalog Exists

```bash
uv run --with polars python ${CLAUDE_PLUGIN_ROOT}/scripts/catalog_query.py --status
```

If catalog is missing or stale (>7 days), inform the user and suggest `/deng-catalog-refresh`.

### Step 2: Run Search

```bash
uv run --with polars python ${CLAUDE_PLUGIN_ROOT}/scripts/catalog_query.py "<keywords>" --top 20
```

### Step 3: Present Results

Format the results as a table showing:
- Table name (database.table)
- Column name
- Data type
- Key indicators (PK/FK)
- FK references (for join hints)
- Estimated row count
- Relevance score

### Step 4: Suggest Next Steps

Based on results, suggest:
1. **For table details:** `uv run --with polars python ${CLAUDE_PLUGIN_ROOT}/scripts/catalog_query.py --table Database.TableName`
2. **For join paths:** `uv run --with polars python ${CLAUDE_PLUGIN_ROOT}/scripts/catalog_query.py --joins TableName`
3. **For SQL exploration:** Provide example SELECT with discovered tables

## Advanced Usage

### Get Table Details

```bash
uv run --with polars python ${CLAUDE_PLUGIN_ROOT}/scripts/catalog_query.py --table Orders.OrderItem
```

Shows all columns, types, and relationships for a specific table.

### Find Join Paths

```bash
uv run --with polars python ${CLAUDE_PLUGIN_ROOT}/scripts/catalog_query.py --joins OrderItem
```

Shows:
- Tables this table references (outbound FKs)
- Tables that reference this table (inbound FKs)

### JSON Output (for programmatic use)

```bash
uv run --with polars python ${CLAUDE_PLUGIN_ROOT}/scripts/catalog_query.py "order cancel" --format json
```

## Search Ranking

Results are ranked by relevance:

| Match Type | Weight |
|------------|--------|
| Table name contains keyword | 3 |
| Column name contains keyword | 2 |
| Database name contains keyword | 1 |
| Is primary key | +2 bonus |
| Is foreign key | +1 bonus |

Ties broken by row count (larger tables ranked higher).

## Common Search Patterns

| Goal | Search Keywords |
|------|-----------------|
| Find churn/cancellation data | `order cancel`, `status cancel`, `churn` |
| Find customer info | `customer company account` |
| Find date/time columns | `date created`, `activation start` |
| Find pricing data | `charge amount price discount` |
| Find product info | `product family code` |
| Find invoice data | `invoice item payment` |

## MCP Tools Alternative

If the MCP server is running, you can also use these tools directly:
- `search_catalog` - Keyword search
- `get_table_details` - Full table info
- `find_join_paths` - FK relationships

## Troubleshooting

**"Catalog not found"**
- Run `/deng-catalog-refresh` to build the catalog

**"Catalog is stale"**
- Results may be outdated if schema changed
- Run `/deng-catalog-refresh` to update

**No results found**
- Try different keywords
- Use partial matches (e.g., "cancel" instead of "cancellation")
- Check `--status` to confirm catalog has data
