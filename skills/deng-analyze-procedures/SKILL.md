---
name: deng-analyze-procedures
description: Use when enriching the data catalog with usage patterns from stored procedures, views, and execution statistics. Run after deng-catalog-refresh to add importance rankings and discover which tables/columns are most used.
---

# Analyze Stored Procedures

Extracts usage patterns from SQL Server programmable objects to enrich the data catalog.

## What It Does

1. **Extracts programmable objects** - Stored procedures, views, functions, triggers
2. **Captures execution statistics** - From dm_exec_procedure_stats, Query Store, SSRS logs
3. **Maps dependencies** - Which procedures reference which tables
4. **Calculates importance scores** - Based on execution count and recency
5. **Enriches the ontology** - Adds usageStats to tables/columns

## Quick Reference

| Output File | Contents |
|-------------|----------|
| `procedures.parquet` | All programmable objects with SQL definitions |
| `execution_stats.parquet` | Runtime statistics per procedure |
| `procedure_analysis.jsonld` | Top procedures by importance, usage patterns |
| `ontology.jsonld` | Enriched with usageStats per table |

## Commands

```bash
# Analyze specific target
uv run --with pymssql --with polars --with python-dotenv \
    python ~/.deng-toolkit/scripts/analyze_procedures.py --target oms

# Analyze all targets
uv run --with pymssql --with polars --with python-dotenv \
    python ~/.deng-toolkit/scripts/analyze_procedures.py

# Deep analysis on top 50 procedures only
uv run --with pymssql --with polars --with python-dotenv \
    python ~/.deng-toolkit/scripts/analyze_procedures.py --deep-analysis 50

# Skip SSRS log analysis
uv run --with pymssql --with polars --with python-dotenv \
    python ~/.deng-toolkit/scripts/analyze_procedures.py --skip-ssrs
```

## Workflow

Run after catalog refresh:

```
/deng-catalog-refresh  →  metadata.parquet
        ↓
/deng-analyze-procedures  →  procedures.parquet, execution_stats.parquet
        ↓
/deng-build-ontology  →  ontology.jsonld (enriched with usageStats)
```

## Importance Score

```
importance = log(execution_count + 1) × 0.6 + recency_score × 0.4
```

Higher score = more important. Used for:
- Prioritizing which tables to document first
- Identifying heavily-used columns for optimization
- Finding unused tables (candidates for deprecation)

## Querying Results

```python
import polars as pl
import json

# Find most-executed procedures
stats = pl.read_parquet("~/.ds_catalog/execution_stats.parquet")
top_procs = stats.sort("execution_count", descending=True).head(20)

# Find tables by usage
with open("~/.ds_catalog/procedure_analysis.jsonld") as f:
    analysis = json.load(f)

most_used = sorted(
    analysis["tableUsage"].items(),
    key=lambda x: x[1]["referenceCount"],
    reverse=True
)[:20]
```
