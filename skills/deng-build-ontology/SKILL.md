---
name: deng-build-ontology
description: Use when creating or updating the semantic knowledge graph from database metadata. Transforms catalog into JSON-LD ontology with domain classification, semantic roles, and business metrics. Run after catalog refresh or when ontology needs updating.
---

# Build Data Ontology

## Overview

Transforms the database metadata catalog (`~/.ds_catalog/metadata.parquet`) into a **JSON-LD knowledge graph** with semantic enrichment for AI agent consumption and human review.

**When to use:**
- After running `/deng-catalog-refresh` to update the ontology
- When you need semantic understanding of the database schema
- When building queries that span multiple domains
- When documenting data relationships for stakeholders

**When NOT to use:**
- Just searching for a table/column (use `/deng-find-data` instead)
- Catalog doesn't exist yet (run `/deng-catalog-refresh` first)
- Quick lookups during analysis

## Invocation

```
/deng-build-ontology
```

## Process

### Step 1: Check Prerequisites

Verify the catalog exists:

```bash
ls -la ~/.ds_catalog/metadata.parquet
```

If not found, tell the user:
> Metadata catalog not found. Run `/deng-catalog-refresh` first to create the catalog.

### Step 2: Run the Build

```bash
uv run --with polars python ~/.deng-toolkit/scripts/build_ontology.py
```

### Step 3: Verify Outputs

Check that outputs were created:

```bash
ls -la ~/.ds_catalog/ontology.jsonld ~/.ds_catalog/ONTOLOGY_SUMMARY.md
```

### Step 4: Report Results

Show the user:
1. Number of tables, columns, and relationships processed
2. Domain classification breakdown
3. Location of output files
4. Quick usage example

Example report:
```
Ontology built successfully!

**Statistics:**
- Tables: 237
- Columns: 3,839
- Relationships: 157
- Domains: 7
- Metrics: 8

**Output files:**
- JSON-LD: ~/.ds_catalog/ontology.jsonld
- Summary: ~/.ds_catalog/ONTOLOGY_SUMMARY.md

**Domain breakdown:**
| Domain | Tables |
|--------|--------|
| Customer | 45 |
| Order | 38 |
| Product | 22 |
| Quote | 15 |
| Invoice | 31 |
| Reference | 52 |
| Audit | 12 |
| Uncategorized | 22 |
```

## Output Files

| File | Location | Purpose |
|------|----------|---------|
| `ontology.jsonld` | `~/.ds_catalog/` | JSON-LD knowledge graph |
| `ONTOLOGY_SUMMARY.md` | `~/.ds_catalog/` | Human-readable documentation |

## Configuration

The ontology is built using rules defined in:
`~/.ds_catalog/ontology_config.toml`

This file contains:
- **Domain classification rules** - Map tables to business domains
- **Semantic role rules** - Classify columns by semantic meaning
- **Metric definitions** - Business metrics from CLAUDE.md
- **Relationship type mappings** - Infer relationship semantics from FK patterns
- **Core entity definitions** - Key business entities

## Integration with Other Skills

| Skill | Integration |
|-------|-------------|
| `/deng-catalog-refresh` | Run first to populate the source catalog |
| `/deng-find-data` | Uses catalog; ontology provides semantic context |
| Analysis scripts | Can load ontology.jsonld for schema understanding |

## JSON-LD Schema

### Entity Node Example
```json
{
  "@id": "oms:Orders.OrderItem",
  "@type": ["Table", "OrderEntity"],
  "rdfs:label": "OrderItem",
  "database": "Orders",
  "rowCount": 18154352,
  "belongsToDomain": "oms:OrderDomain",
  "hasColumn": [
    {
      "@id": "oms:Orders.OrderItem.StatusCode",
      "@type": "Column",
      "dataType": "varchar",
      "semanticRole": "StatusIndicator"
    }
  ]
}
```

### Metric Definition Example
```json
{
  "@id": "oms:metric:FullCustomerChurnRate",
  "@type": "Metric",
  "rdfs:label": "Full Customer Churn Rate",
  "formula": "COUNT(churned) / COUNT(total_customers)",
  "sourceColumns": [
    "Orders.dbo.OrderItem.StatusCode",
    "Orders.dbo.Order.CompanyIDSeq"
  ],
  "conditions": [
    {"field": "ItemsActive", "operator": "==", "value": "0"},
    {"field": "ItemsOpen", "operator": "==", "value": "0"}
  ]
}
```

## Troubleshooting

**"Config not found" error:**
- Ensure `~/.ds_catalog/ontology_config.toml` exists
- Copy from template: `cp ~/.deng-toolkit/templates/ontology_config.toml.example ~/.ds_catalog/ontology_config.toml`

**"Catalog not found" error:**
- Run `/deng-catalog-refresh` first
- Check that `~/.ds_catalog/metadata.parquet` exists

**Empty domains:**
- Review domain classification rules in `~/.ds_catalog/ontology_config.toml`
- Check that database names match the `database_affinity` settings

## Usage Examples

### Loading in Python
```python
import json
from pathlib import Path

ontology_path = Path.home() / '.ds_catalog' / 'ontology.jsonld'
with open(ontology_path) as f:
    ontology = json.load(f)

# Find all tables in the Order domain
order_tables = [
    e for e in ontology['entities']
    if 'OrderDomain' in e['belongsToDomain']
]

# Find columns with monetary semantic role
monetary_cols = []
for entity in ontology['entities']:
    for col in entity.get('hasColumn', []):
        if col.get('semanticRole') == 'Monetary':
            monetary_cols.append(col['@id'])
```

### Querying Relationships
```python
# Find all relationships from OrderItem
order_item_rels = [
    r for r in ontology['relationships']
    if 'OrderItem' in r['fromTable']
]
```
