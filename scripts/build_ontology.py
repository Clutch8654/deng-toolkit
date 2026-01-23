#!/usr/bin/env python3
"""
Build Ontology - Transform database metadata catalog into JSON-LD knowledge graph.

Usage:
    python build_ontology.py [--config PATH] [--output PATH]

Examples:
    python build_ontology.py
    python build_ontology.py --output ./my_ontology.jsonld

Reads metadata from ~/.ds_catalog/metadata.parquet and produces:
- ontology.jsonld: JSON-LD knowledge graph
- ONTOLOGY_SUMMARY.md: Human-readable documentation
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import polars as pl


# Default paths - configurable via DENG_CATALOG_DIR env var
CATALOG_DIR = Path(os.environ.get("DENG_CATALOG_DIR", str(Path.home() / ".ds_catalog")))
METADATA_PATH = CATALOG_DIR / "metadata.parquet"
CONFIG_PATH = CATALOG_DIR / "ontology_config.toml"
OUTPUT_JSONLD_PATH = CATALOG_DIR / "ontology.jsonld"
OUTPUT_SUMMARY_PATH = CATALOG_DIR / "ONTOLOGY_SUMMARY.md"


def load_config(config_path: Path) -> dict:
    """Load ontology configuration from TOML file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(config_path, "rb") as f:
        return tomllib.load(f)


def load_catalog(metadata_path: Path) -> pl.DataFrame:
    """Load metadata catalog from parquet file."""
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"Catalog not found: {metadata_path}\n"
            "Run /ds-catalog-refresh first to create the catalog."
        )

    return pl.read_parquet(metadata_path)


class DomainClassifier:
    """Classify tables into business domains based on configuration rules."""

    def __init__(self, config: dict):
        self.domains = config.get("domains", [])
        self._compile_patterns()
        self._sort_by_priority()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for efficiency."""
        for domain in self.domains:
            patterns = domain.get("table_patterns", [])
            compiled = []
            for pattern in patterns:
                # Convert glob-style to regex
                if pattern.startswith("*"):
                    regex = ".*" + re.escape(pattern[1:]) + "$"
                elif pattern.endswith("*"):
                    regex = "^" + re.escape(pattern[:-1]) + ".*"
                elif "*" in pattern:
                    regex = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
                else:
                    regex = ".*" + re.escape(pattern) + ".*"
                compiled.append(re.compile(regex, re.IGNORECASE))
            domain["_compiled_patterns"] = compiled

    def _sort_by_priority(self) -> None:
        """Sort domains by priority (lower = checked first)."""
        self.domains = sorted(
            self.domains,
            key=lambda d: (d.get("priority", 50), d.get("is_fallback", False)),
        )

    def classify(self, database: str, table_name: str) -> str:
        """
        Classify a table into a domain.

        Evaluation order:
        1. Pattern-only domains (no database_affinity) checked first by priority
        2. Database-affinity domains checked second
        3. Fallback domain last
        """
        fallback_domain = None

        for domain in self.domains:
            if domain.get("is_fallback"):
                fallback_domain = domain["id"]
                continue

            db_affinity = domain.get("database_affinity", [])
            patterns = domain.get("_compiled_patterns", [])

            # Pattern-only domain (no database affinity)
            if not db_affinity:
                for pattern in patterns:
                    if pattern.search(table_name):
                        return domain["id"]
            # Database-affinity domain
            elif database in db_affinity:
                # If patterns specified, check them; otherwise match on DB alone
                if patterns:
                    for pattern in patterns:
                        if pattern.search(table_name):
                            return domain["id"]
                    # Database matches but no pattern match - still assign
                    # (this allows catching all tables in a database)
                return domain["id"]

        return fallback_domain or "UncategorizedDomain"


class SemanticRoleClassifier:
    """Assign semantic roles to columns based on patterns and data types."""

    def __init__(self, config: dict):
        self.roles = config.get("semantic_roles", [])
        self._compile_patterns()
        self._sort_by_priority()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for efficiency."""
        for role in self.roles:
            patterns = role.get("patterns", [])
            compiled = []
            for pattern in patterns:
                # Convert glob-style to regex
                if pattern.startswith("*"):
                    regex = ".*" + re.escape(pattern[1:])
                elif pattern.endswith("*"):
                    regex = re.escape(pattern[:-1]) + ".*"
                elif "*" in pattern:
                    regex = re.escape(pattern).replace(r"\*", ".*")
                elif pattern.startswith("^") or pattern.endswith("$"):
                    regex = pattern
                else:
                    regex = ".*" + re.escape(pattern) + ".*"
                compiled.append(re.compile(regex, re.IGNORECASE))
            role["_compiled_patterns"] = compiled

    def _sort_by_priority(self) -> None:
        """Sort roles by priority (lower = checked first)."""
        self.roles = sorted(
            self.roles,
            key=lambda r: (r.get("priority", 50), r.get("is_fallback", False)),
        )

    def classify(
        self, column_name: str, data_type: str, is_pk: bool = False, is_fk: bool = False
    ) -> str:
        """
        Classify a column's semantic role.

        Considers column name patterns, data types, and key constraints.
        Priority order is respected.
        """
        fallback_role = None

        for role in self.roles:
            if role.get("is_fallback"):
                fallback_role = role["id"]
                continue

            # Check conditions (PK/FK)
            conditions = role.get("conditions", {})
            if conditions:
                if conditions.get("is_primary_key") and not is_pk:
                    continue
                if conditions.get("is_foreign_key") and not is_fk:
                    continue

            # Check name patterns
            patterns = role.get("_compiled_patterns", [])
            pattern_matched = False
            for pattern in patterns:
                if pattern.search(column_name):
                    pattern_matched = True
                    break

            if not pattern_matched:
                continue

            # Pattern matches - check data type if specified
            allowed_types = role.get("data_types", [])
            if allowed_types:
                if data_type.lower() in [t.lower() for t in allowed_types]:
                    return role["id"]
                # Data type specified but doesn't match - continue to next role
            else:
                # No data type constraint - pattern match is enough
                return role["id"]

        return fallback_role or "Unclassified"


class RelationshipBuilder:
    """Build relationship edges from FK references."""

    def __init__(self, config: dict):
        self.relationship_types = config.get("relationship_types", [])

    def infer_relationship_type(self, column_name: str, fk_ref: str) -> dict:
        """
        Infer relationship type from FK column name pattern.

        Returns dict with type and inverse relationship names.
        """
        for rel_type in self.relationship_types:
            pattern = rel_type.get("pattern", "")
            if fnmatch.fnmatch(column_name, pattern):
                return {
                    "type": rel_type.get("type", "references"),
                    "inverse": rel_type.get("inverse", "referencedBy"),
                }

        # Default relationship
        return {"type": "references", "inverse": "referencedBy"}


class OntologyBuilder:
    """Main orchestrator that assembles the JSON-LD document."""

    def __init__(self, config: dict, catalog: pl.DataFrame):
        self.config = config
        self.catalog = catalog
        self.domain_classifier = DomainClassifier(config)
        self.role_classifier = SemanticRoleClassifier(config)
        self.relationship_builder = RelationshipBuilder(config)

        # Extract config sections
        self.ontology_config = config.get("ontology", {})
        self.namespace = self.ontology_config.get("namespace", "oms")
        self.base_uri = self.ontology_config.get(
            "base_uri", "https://example.com/ontology#"
        )

    def build(self) -> dict:
        """Build the complete JSON-LD document."""
        # Build entities first to collect review items
        entities = self._build_entities()

        doc = {
            "@context": self._build_context(),
            "@id": f"{self.namespace}:OntologyRoot",
            "@type": "Ontology",
            "rdfs:label": "OMS Data Ontology",
            "rdfs:comment": "Knowledge graph of RealPage OMS database schema",
            "generatedAt": datetime.now().isoformat(),
            "sourceStats": self._get_source_stats(),
            "domains": self._build_domains(),
            "entities": entities,
            "relationships": self._build_relationships(),
            "metrics": self._build_metrics(),
            "coreEntities": self._build_core_entities(),
            "reviewQueue": self._build_review_queue(entities),
        }
        return doc

    def _build_review_queue(self, entities: list[dict]) -> dict:
        """Build a queue of items requiring human review."""
        review_items = {
            "summary": {"totalItemsNeedingReview": 0, "byCategory": {}},
            "domainReview": [],
            "semanticRoleReview": [],
            "unclassifiedColumns": [],
            "highNullRateColumns": [],
            "lowCardinalityColumns": [],
        }

        for entity in entities:
            # Check for uncategorized domain
            if "UncategorizedDomain" in entity.get("belongsToDomain", ""):
                review_items["domainReview"].append(
                    {
                        "@id": entity["@id"],
                        "table": f"{entity['database']}.{entity['rdfs:label']}",
                        "rowCount": entity.get("rowCount", 0),
                        "reason": "Table not classified into any business domain",
                        "suggestedAction": "Review table purpose and assign to appropriate domain",
                    }
                )

            # Check columns
            for col in entity.get("hasColumn", []):
                col_id = col["@id"]
                col_name = col["rdfs:label"]
                role = col.get("semanticRole", "")

                # Unclassified columns
                if role == "Unclassified":
                    review_items["unclassifiedColumns"].append(
                        {
                            "@id": col_id,
                            "column": col_name,
                            "table": entity["rdfs:label"],
                            "dataType": col.get("dataType", ""),
                            "reason": "No semantic role pattern matched",
                            "suggestedAction": "Add pattern to ontology_config.toml or manually classify",
                        }
                    )

                # High null rate columns (if profiled)
                null_rate = col.get("nullRate", 0)
                if null_rate and null_rate > 0.5:
                    review_items["highNullRateColumns"].append(
                        {
                            "@id": col_id,
                            "column": col_name,
                            "table": entity["rdfs:label"],
                            "nullRate": null_rate,
                            "reason": f"Column is {null_rate:.0%} null",
                            "suggestedAction": "Verify if column is deprecated or has data quality issues",
                        }
                    )

                # Low cardinality columns (potential reference data)
                distinct = col.get("distinctCount", 0)
                profiled = col.get("profiledRows", 0)
                if (
                    profiled > 100
                    and distinct > 0
                    and distinct < 20
                    and role not in ["BooleanFlag", "StatusIndicator", "Code"]
                ):
                    review_items["lowCardinalityColumns"].append(
                        {
                            "@id": col_id,
                            "column": col_name,
                            "table": entity["rdfs:label"],
                            "distinctCount": distinct,
                            "currentRole": role,
                            "reason": f"Only {distinct} distinct values - may be a code/status field",
                            "suggestedAction": "Consider reclassifying as Code or StatusIndicator",
                        }
                    )

        # Compute summary
        total = (
            len(review_items["domainReview"])
            + len(review_items["unclassifiedColumns"])
            + len(review_items["highNullRateColumns"])
            + len(review_items["lowCardinalityColumns"])
        )
        review_items["summary"]["totalItemsNeedingReview"] = total
        review_items["summary"]["byCategory"] = {
            "domainReview": len(review_items["domainReview"]),
            "unclassifiedColumns": len(review_items["unclassifiedColumns"]),
            "highNullRateColumns": len(review_items["highNullRateColumns"]),
            "lowCardinalityColumns": len(review_items["lowCardinalityColumns"]),
        }

        return review_items

    def _build_context(self) -> dict:
        """Build the @context section with prefixes."""
        context = self.ontology_config.get("context", {}).copy()

        # Add standard context entries
        context.update(
            {
                "@vocab": self.base_uri,
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                "xsd": "http://www.w3.org/2001/XMLSchema#",
                self.namespace: self.base_uri,
                "generatedAt": {"@type": "xsd:dateTime"},
                "rowCount": {"@type": "xsd:integer"},
                "belongsToDomain": {"@type": "@id"},
                "hasColumn": {"@container": "@set"},
                "sourceColumns": {"@container": "@list"},
                "conditions": {"@container": "@list"},
            }
        )

        return context

    def _get_source_stats(self) -> dict:
        """Get statistics about the source catalog."""
        return {
            "totalColumns": len(self.catalog),
            "totalTables": self.catalog.select(["database", "schema", "table_name"])
            .unique()
            .height,
            "totalDatabases": self.catalog.n_unique("database"),
            "totalForeignKeys": self.catalog.filter(
                pl.col("is_foreign_key") == True  # noqa: E712
            ).height,
        }

    def _build_domains(self) -> list[dict]:
        """Build domain nodes from configuration."""
        domains = []

        for domain_config in self.config.get("domains", []):
            domain_id = domain_config["id"]

            # Count tables in this domain
            table_count = 0
            for row in (
                self.catalog.select(["database", "table_name"])
                .unique()
                .iter_rows(named=True)
            ):
                if (
                    self.domain_classifier.classify(row["database"], row["table_name"])
                    == domain_id
                ):
                    table_count += 1

            domains.append(
                {
                    "@id": f"{self.namespace}:{domain_id}",
                    "@type": "Domain",
                    "rdfs:label": domain_config.get("label", domain_id),
                    "rdfs:comment": domain_config.get("description", ""),
                    "tableCount": table_count,
                    "databaseAffinity": domain_config.get("database_affinity", []),
                }
            )

        return domains

    def _build_entities(self) -> list[dict]:
        """Build entity (table) nodes with their columns."""
        entities = []

        # Group by table
        tables = self.catalog.select(
            ["database", "schema", "table_name", "row_count_estimate"]
        ).unique()

        for table_row in tables.iter_rows(named=True):
            db = table_row["database"]
            schema = table_row["schema"]
            table = table_row["table_name"]
            row_count = table_row["row_count_estimate"]

            # Get domain classification
            domain_id = self.domain_classifier.classify(db, table)

            # Build entity ID
            entity_id = f"{self.namespace}:{db}.{table}"

            # Get columns for this table
            table_cols = self.catalog.filter(
                (pl.col("database") == db)
                & (pl.col("schema") == schema)
                & (pl.col("table_name") == table)
            )

            columns = []
            for col_row in table_cols.iter_rows(named=True):
                col_name = col_row["column_name"]
                data_type = col_row["data_type"]
                is_pk = col_row.get("is_primary_key", False)
                is_fk = col_row.get("is_foreign_key", False)
                fk_ref = col_row.get("fk_references", "")

                semantic_role = self.role_classifier.classify(
                    col_name, data_type, is_pk, is_fk
                )

                col_node = {
                    "@id": f"{entity_id}.{col_name}",
                    "@type": "Column",
                    "rdfs:label": col_name,
                    "dataType": data_type,
                    "semanticRole": semantic_role,
                    "isNullable": col_row.get("is_nullable", True),
                }

                if is_pk:
                    col_node["isPrimaryKey"] = True
                if is_fk:
                    col_node["isForeignKey"] = True
                    if fk_ref:
                        col_node["references"] = fk_ref

                # Add profiling data if available
                if "null_rate" in col_row and col_row.get("profiled_rows", 0) > 0:
                    col_node["nullRate"] = col_row.get("null_rate", 0)
                    col_node["nullCount"] = col_row.get("null_count", 0)
                    col_node["distinctCount"] = col_row.get("distinct_count", 0)
                    col_node["profiledRows"] = col_row.get("profiled_rows", 0)

                # Determine review status
                needs_review = []
                if semantic_role == "Unclassified":
                    needs_review.append("unclassified_role")
                if col_row.get("null_rate", 0) > 0.5:
                    needs_review.append("high_null_rate")

                if needs_review:
                    col_node["reviewStatus"] = "needs_review"
                    col_node["reviewReasons"] = needs_review
                else:
                    col_node["reviewStatus"] = "auto_classified"

                columns.append(col_node)

            # Determine table-level review status
            table_needs_review = []
            if domain_id == "UncategorizedDomain":
                table_needs_review.append("unclassified_domain")
            cols_needing_review = sum(
                1 for c in columns if c.get("reviewStatus") == "needs_review"
            )
            if cols_needing_review > len(columns) * 0.3:  # >30% columns need review
                table_needs_review.append("many_unclassified_columns")

            entity = {
                "@id": entity_id,
                "@type": ["Table", f"{domain_id.replace('Domain', '')}Entity"],
                "rdfs:label": table,
                "database": db,
                "schema": schema,
                "belongsToDomain": f"{self.namespace}:{domain_id}",
                "rowCount": row_count or 0,
                "columnCount": len(columns),
                "columnsNeedingReview": cols_needing_review,
                "hasColumn": columns,
                "reviewStatus": "needs_review"
                if table_needs_review
                else "auto_classified",
                "reviewReasons": table_needs_review if table_needs_review else [],
            }

            entities.append(entity)

        return entities

    def _build_relationships(self) -> list[dict]:
        """Build relationship edges from FK references."""
        relationships = []

        fk_cols = self.catalog.filter(
            (pl.col("is_foreign_key") == True)  # noqa: E712
            & (pl.col("fk_references").is_not_null())
            & (pl.col("fk_references") != "")
        )

        for row in fk_cols.iter_rows(named=True):
            db = row["database"]
            table = row["table_name"]
            col = row["column_name"]
            fk_ref = row["fk_references"]

            from_id = f"{self.namespace}:{db}.{table}.{col}"

            # Parse FK reference (format: "dbo.Table.Column")
            to_id = (
                f"{self.namespace}:{db}.{fk_ref}"
                if "." not in fk_ref
                else f"{self.namespace}:{fk_ref}"
            )

            # Infer relationship type
            rel_info = self.relationship_builder.infer_relationship_type(col, fk_ref)

            relationships.append(
                {
                    "@id": f"{self.namespace}:rel_{db}_{table}_{col}",
                    "@type": "Relationship",
                    "relationshipType": rel_info["type"],
                    "inverseType": rel_info["inverse"],
                    "from": from_id,
                    "to": to_id,
                    "fromTable": f"{self.namespace}:{db}.{table}",
                    "toReference": fk_ref,
                }
            )

        return relationships

    def _build_metrics(self) -> list[dict]:
        """Build metric definition nodes from configuration."""
        metrics = []

        for metric_config in self.config.get("metrics", []):
            metric = {
                "@id": f"{self.namespace}:metric:{metric_config['id']}",
                "@type": "Metric",
                "rdfs:label": metric_config.get("label", metric_config["id"]),
                "rdfs:comment": metric_config.get("description", ""),
                "formula": metric_config.get("formula", ""),
                "sourceColumns": metric_config.get("source_columns", []),
                "conditions": metric_config.get("conditions", []),
            }

            if "observation_window_days" in metric_config:
                metric["observationWindowDays"] = metric_config[
                    "observation_window_days"
                ]

            if "notes" in metric_config:
                metric["notes"] = metric_config["notes"]

            metrics.append(metric)

        return metrics

    def _build_core_entities(self) -> list[dict]:
        """Build core entity definitions from configuration."""
        core_entities = []

        for entity_config in self.config.get("core_entities", []):
            entity = {
                "@id": f"{self.namespace}:core:{entity_config['table']}",
                "@type": "CoreEntity",
                "rdfs:label": entity_config.get("label", entity_config["table"]),
                "rdfs:comment": entity_config.get("description", ""),
                "table": entity_config["table"],
                "keyColumn": entity_config.get("key_column", ""),
                "isAggregateRoot": entity_config.get("is_aggregate_root", False),
            }

            if "belongs_to" in entity_config:
                entity["belongsTo"] = (
                    f"{self.namespace}:core:{entity_config['belongs_to']}"
                )

            core_entities.append(entity)

        return core_entities


def generate_summary_markdown(ontology: dict, config: dict) -> str:
    """Generate human-readable summary of the ontology."""
    lines = [
        "# OMS Data Ontology Summary",
        "",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "## Overview",
        "",
        "This document summarizes the JSON-LD knowledge graph generated from the OMS database metadata catalog.",
        "",
        "### Statistics",
        "",
    ]

    stats = ontology.get("sourceStats", {})
    lines.extend(
        [
            f"- **Total Columns:** {stats.get('totalColumns', 0):,}",
            f"- **Total Tables:** {stats.get('totalTables', 0):,}",
            f"- **Total Databases:** {stats.get('totalDatabases', 0):,}",
            f"- **Foreign Key Relationships:** {stats.get('totalForeignKeys', 0):,}",
            "",
            "## Business Domains",
            "",
            "Tables are classified into the following business domains:",
            "",
            "| Domain | Description | Tables |",
            "|--------|-------------|--------|",
        ]
    )

    for domain in ontology.get("domains", []):
        label = domain.get("rdfs:label", "Unknown")
        desc = domain.get("rdfs:comment", "")[:50]
        count = domain.get("tableCount", 0)
        lines.append(f"| {label} | {desc} | {count} |")

    lines.extend(
        [
            "",
            "## Core Entities",
            "",
            "Key business entities that form the domain model:",
            "",
            "| Entity | Table | Aggregate Root | Key Column |",
            "|--------|-------|----------------|------------|",
        ]
    )

    for entity in ontology.get("coreEntities", []):
        label = entity.get("rdfs:label", "Unknown")
        table = entity.get("table", "")
        is_root = "Yes" if entity.get("isAggregateRoot") else "No"
        key = entity.get("keyColumn", "")
        lines.append(f"| {label} | {table} | {is_root} | {key} |")

    lines.extend(
        [
            "",
            "## Semantic Roles",
            "",
            "Columns are assigned semantic roles based on naming patterns:",
            "",
            "| Role | Description |",
            "|------|-------------|",
        ]
    )

    for role in config.get("semantic_roles", []):
        if role.get("is_fallback"):
            continue
        role_id = role.get("id", "")
        label = role.get("label", role_id)
        patterns = ", ".join(role.get("patterns", [])[:3])
        lines.append(f"| {label} | Patterns: `{patterns}` |")

    lines.extend(
        [
            "",
            "## Business Metrics",
            "",
            "Metrics derived from base entities (from CLAUDE.md business rules):",
            "",
        ]
    )

    for metric in ontology.get("metrics", []):
        metric_id = metric.get("@id", "").split(":")[-1]
        label = metric.get("rdfs:label", metric_id)
        desc = metric.get("rdfs:comment", "")
        formula = metric.get("formula", "")
        notes = metric.get("notes", "")

        lines.extend(
            [
                f"### {label}",
                "",
                f"**Description:** {desc}",
                "",
                f"**Formula:** `{formula}`",
                "",
            ]
        )

        if metric.get("sourceColumns"):
            lines.append("**Source Columns:**")
            for col in metric.get("sourceColumns", []):
                lines.append(f"- `{col}`")
            lines.append("")

        if metric.get("conditions"):
            lines.append("**Conditions:**")
            for cond in metric.get("conditions", []):
                field = cond.get("field", "")
                op = cond.get("operator", "")
                val = cond.get("value", "")
                lines.append(f"- `{field} {op} {val}`")
            lines.append("")

        if notes:
            lines.append(f"**Notes:** {notes}")
            lines.append("")

    lines.extend(
        [
            "## Relationships",
            "",
            f"The ontology contains **{len(ontology.get('relationships', []))}** foreign key relationships.",
            "",
            "### Relationship Types",
            "",
            "| Pattern | Type | Inverse |",
            "|---------|------|---------|",
        ]
    )

    for rel_type in config.get("relationship_types", []):
        pattern = rel_type.get("pattern", "")
        rel = rel_type.get("type", "")
        inv = rel_type.get("inverse", "")
        lines.append(f"| `{pattern}` | {rel} | {inv} |")

    lines.extend(
        [
            "",
            "## Large Tables (>1M rows)",
            "",
            "| Table | Domain | Rows | Columns |",
            "|-------|--------|------|---------|",
        ]
    )

    large_tables = sorted(
        [e for e in ontology.get("entities", []) if e.get("rowCount", 0) > 1_000_000],
        key=lambda x: x.get("rowCount", 0),
        reverse=True,
    )[:15]

    for entity in large_tables:
        label = entity.get("rdfs:label", "")
        db = entity.get("database", "")
        domain = entity.get("belongsToDomain", "").split(":")[-1]
        rows = entity.get("rowCount", 0)
        cols = entity.get("columnCount", 0)
        lines.append(f"| {db}.{label} | {domain} | {rows:,} | {cols} |")

    # Add review queue section
    review_queue = ontology.get("reviewQueue", {})
    review_summary = review_queue.get("summary", {})
    total_review = review_summary.get("totalItemsNeedingReview", 0)
    by_category = review_summary.get("byCategory", {})

    lines.extend(
        [
            "",
            "## Items Requiring Human Review",
            "",
            f"**Total items needing review: {total_review}**",
            "",
            "| Category | Count | Description |",
            "|----------|-------|-------------|",
            f"| Domain Classification | {by_category.get('domainReview', 0)} | Tables not assigned to a business domain |",
            f"| Unclassified Columns | {by_category.get('unclassifiedColumns', 0)} | Columns with no semantic role |",
            f"| High Null Rate | {by_category.get('highNullRateColumns', 0)} | Columns >50% null |",
            f"| Low Cardinality | {by_category.get('lowCardinalityColumns', 0)} | Potential reference/code columns |",
            "",
        ]
    )

    # Show top items needing review
    if review_queue.get("domainReview"):
        lines.extend(
            [
                "### Tables Needing Domain Classification",
                "",
                "| Table | Rows | Suggested Action |",
                "|-------|------|------------------|",
            ]
        )
        for item in review_queue.get("domainReview", [])[:10]:
            lines.append(
                f"| {item.get('table', '')} | {item.get('rowCount', 0):,} | {item.get('suggestedAction', '')} |"
            )
        if len(review_queue.get("domainReview", [])) > 10:
            lines.append(
                f"| ... | ... | *({len(review_queue.get('domainReview', [])) - 10} more)* |"
            )
        lines.append("")

    if review_queue.get("unclassifiedColumns"):
        lines.extend(
            [
                "### Sample Unclassified Columns",
                "",
                "| Column | Table | Data Type |",
                "|--------|-------|-----------|",
            ]
        )
        for item in review_queue.get("unclassifiedColumns", [])[:15]:
            lines.append(
                f"| {item.get('column', '')} | {item.get('table', '')} | {item.get('dataType', '')} |"
            )
        if len(review_queue.get("unclassifiedColumns", [])) > 15:
            lines.append(
                f"| ... | ... | *({len(review_queue.get('unclassifiedColumns', [])) - 15} more)* |"
            )
        lines.append("")

    if review_queue.get("highNullRateColumns"):
        lines.extend(
            [
                "### High Null Rate Columns (>50%)",
                "",
                "| Column | Table | Null Rate |",
                "|--------|-------|-----------|",
            ]
        )
        for item in review_queue.get("highNullRateColumns", [])[:10]:
            null_rate = item.get("nullRate", 0)
            lines.append(
                f"| {item.get('column', '')} | {item.get('table', '')} | {null_rate:.0%} |"
            )
        lines.append("")

    lines.extend(
        [
            "",
            "## Usage",
            "",
            "### Loading the Ontology",
            "",
            "```python",
            "import json",
            "from pathlib import Path",
            "",
            "ontology_path = Path.home() / '.ds_catalog' / 'ontology.jsonld'",
            "with open(ontology_path) as f:",
            "    ontology = json.load(f)",
            "",
            "# Access domains",
            "for domain in ontology['domains']:",
            "    print(domain['rdfs:label'], domain['tableCount'])",
            "",
            "# Find entities in a domain",
            "order_entities = [",
            "    e for e in ontology['entities']",
            "    if 'OrderDomain' in e['belongsToDomain']",
            "]",
            "",
            "# Get items needing review",
            "review_queue = ontology['reviewQueue']",
            "print(f\"Items to review: {review_queue['summary']['totalItemsNeedingReview']}\")",
            "```",
            "",
            "### Querying Columns by Semantic Role",
            "",
            "```python",
            "# Find all monetary columns",
            "monetary_cols = []",
            "for entity in ontology['entities']:",
            "    for col in entity.get('hasColumn', []):",
            "        if col.get('semanticRole') == 'Monetary':",
            "            monetary_cols.append(col['@id'])",
            "```",
            "",
            "---",
            "",
            "*This ontology was generated by the `/ds-build-ontology` skill.*",
        ]
    )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Build JSON-LD ontology from database metadata catalog"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG_PATH,
        help=f"Path to ontology config (default: {CONFIG_PATH})",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=METADATA_PATH,
        help=f"Path to metadata catalog (default: {METADATA_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_JSONLD_PATH,
        help=f"Path for JSON-LD output (default: {OUTPUT_JSONLD_PATH})",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=OUTPUT_SUMMARY_PATH,
        help=f"Path for markdown summary (default: {OUTPUT_SUMMARY_PATH})",
    )

    args = parser.parse_args()

    # Load configuration
    print(f"Loading config from {args.config}...")
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Load catalog
    print(f"Loading catalog from {args.catalog}...")
    try:
        catalog = load_catalog(args.catalog)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(
        f"Catalog contains {len(catalog)} columns from {catalog.n_unique('table_name')} tables"
    )

    # Build ontology
    print("Building ontology...")
    builder = OntologyBuilder(config, catalog)
    ontology = builder.build()

    # Write JSON-LD
    print(f"Writing JSON-LD to {args.output}...")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(ontology, f, indent=2, default=str)

    # Generate and write summary
    print(f"Generating summary at {args.summary}...")
    summary = generate_summary_markdown(ontology, config)
    with open(args.summary, "w") as f:
        f.write(summary)

    # Print summary stats
    print("\n=== Ontology Build Complete ===")
    stats = ontology.get("sourceStats", {})
    print(f"  Tables: {stats.get('totalTables', 0)}")
    print(f"  Columns: {stats.get('totalColumns', 0)}")
    print(f"  Relationships: {len(ontology.get('relationships', []))}")
    print(f"  Domains: {len(ontology.get('domains', []))}")
    print(f"  Metrics: {len(ontology.get('metrics', []))}")
    print(f"  Core Entities: {len(ontology.get('coreEntities', []))}")
    print(f"\nOutput files:")
    print(f"  JSON-LD: {args.output}")
    print(f"  Summary: {args.summary}")


if __name__ == "__main__":
    main()
