#!/usr/bin/env python3
"""
Stored Procedure Analysis - Extract usage patterns from SQL Server programmable objects.

Usage:
    python analyze_procedures.py [--target NAME] [--deep-analysis N] [--skip-ssrs]

Examples:
    python analyze_procedures.py --target oms
    python analyze_procedures.py --target oms --deep-analysis 50
    python analyze_procedures.py --skip-ssrs

Analyzes stored procedures, views, functions to enrich the data catalog with:
- Execution statistics and importance rankings
- Column/table reference counts
- Join patterns and aggregation usage
- Discovered metric formulas
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import polars as pl

# Load environment variables
try:
    from dotenv import load_dotenv

    env_locations = [
        Path.cwd() / ".env",
        Path.home() / ".env",
        Path.home() / ".ds_catalog" / ".env",
        Path.home()
        / "Library/CloudStorage/OneDrive-RealPage/Documents/predictiveanalyticsexploration/.env",
    ]
    for env_path in env_locations:
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

# Import SQL parser (optional - degrades gracefully if sqlglot not available)
try:
    from adapters.procedure_parser import ProcedureParser

    PARSER_AVAILABLE = True
except ImportError:
    PARSER_AVAILABLE = False

from config import get_catalog_dir

CATALOG_DIR = get_catalog_dir()
METADATA_PATH = CATALOG_DIR / "metadata.parquet"
PROCEDURES_PATH = CATALOG_DIR / "procedures.parquet"
EXECUTION_STATS_PATH = CATALOG_DIR / "execution_stats.parquet"
PROCEDURE_ANALYSIS_PATH = CATALOG_DIR / "procedure_analysis.jsonld"
ONTOLOGY_PATH = CATALOG_DIR / "ontology.jsonld"
TARGETS_PATH = CATALOG_DIR / "targets.toml"


def load_targets_config() -> dict:
    """Load targets configuration from TOML file."""
    if not TARGETS_PATH.exists():
        raise FileNotFoundError(f"Targets config not found: {TARGETS_PATH}")
    with open(TARGETS_PATH, "rb") as f:
        return tomllib.load(f)


def get_connection(target_config: dict) -> Any:
    """Create database connection from target config."""
    import pymssql

    host = os.environ.get(target_config["host_env"])
    user = os.environ.get(target_config["user_env"])
    password = os.environ.get(target_config["password_env"])

    if not all([host, user, password]):
        missing = []
        if not host:
            missing.append(target_config["host_env"])
        if not user:
            missing.append(target_config["user_env"])
        if not password:
            missing.append(target_config["password_env"])
        raise EnvironmentError(f"Missing environment variables: {', '.join(missing)}")

    return pymssql.connect(server=host, user=user, password=password)


@dataclass
class ProcedureAnalyzer:
    """Analyzes SQL Server programmable objects."""

    conn: Any
    target_name: str
    server_name: str

    def get_programmable_objects(self, database: str) -> pl.DataFrame:
        """Extract all programmable objects from a database."""
        query = f"""
        USE [{database}];

        SELECT
            '{database}' AS [database],
            s.name AS [schema],
            o.name AS object_name,
            CASE o.type
                WHEN 'P' THEN 'PROCEDURE'
                WHEN 'V' THEN 'VIEW'
                WHEN 'FN' THEN 'SCALAR_FUNCTION'
                WHEN 'IF' THEN 'INLINE_FUNCTION'
                WHEN 'TF' THEN 'TABLE_FUNCTION'
                WHEN 'TR' THEN 'TRIGGER'
            END AS object_type,
            m.definition AS definition,
            o.create_date AS created_date,
            o.modify_date AS modified_date
        FROM sys.objects o
        INNER JOIN sys.schemas s ON o.schema_id = s.schema_id
        LEFT JOIN sys.sql_modules m ON o.object_id = m.object_id
        WHERE o.type IN ('P', 'V', 'FN', 'IF', 'TF', 'TR')
          AND s.name NOT IN ('sys', 'INFORMATION_SCHEMA')
        ORDER BY o.type, s.name, o.name;
        """
        return self._execute_query(query)

    def get_procedure_stats(self, database: str) -> pl.DataFrame:
        """Get execution statistics from dm_exec_procedure_stats."""
        query = f"""
        USE [{database}];

        SELECT
            '{database}' AS [database],
            OBJECT_SCHEMA_NAME(ps.object_id) AS [schema],
            OBJECT_NAME(ps.object_id) AS object_name,
            ps.execution_count,
            ps.last_execution_time,
            ps.total_worker_time / 1000 AS total_cpu_ms,
            ps.total_elapsed_time / 1000 AS total_elapsed_ms,
            ps.total_logical_reads,
            ps.total_logical_writes,
            CASE WHEN ps.execution_count > 0
                 THEN ps.total_elapsed_time / ps.execution_count / 1000
                 ELSE 0 END AS avg_duration_ms
        FROM sys.dm_exec_procedure_stats ps
        WHERE ps.database_id = DB_ID()
          AND OBJECT_SCHEMA_NAME(ps.object_id) IS NOT NULL;
        """
        return self._execute_query(query)

    def get_query_store_stats(self, database: str) -> pl.DataFrame:
        """Get execution statistics from Query Store if enabled."""
        # First check if Query Store is enabled
        check_query = f"""
        USE [{database}];
        SELECT is_query_store_on FROM sys.databases WHERE name = '{database}';
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(check_query)
            row = cursor.fetchone()
            if not row or not row[0]:
                return pl.DataFrame()
        except Exception:
            return pl.DataFrame()
        finally:
            cursor.close()

        # Query Store is enabled, get stats
        query = f"""
        USE [{database}];

        SELECT
            '{database}' AS [database],
            OBJECT_SCHEMA_NAME(q.object_id) AS [schema],
            OBJECT_NAME(q.object_id) AS object_name,
            SUM(rs.count_executions) AS execution_count,
            MAX(rs.last_execution_time) AS last_execution_time,
            AVG(rs.avg_duration) / 1000 AS avg_duration_ms,
            SUM(rs.avg_cpu_time * rs.count_executions) / 1000 AS total_cpu_ms
        FROM sys.query_store_query q
        INNER JOIN sys.query_store_plan p ON q.query_id = p.query_id
        INNER JOIN sys.query_store_runtime_stats rs ON p.plan_id = rs.plan_id
        WHERE q.object_id IS NOT NULL
          AND q.object_id > 0
        GROUP BY q.object_id
        HAVING OBJECT_SCHEMA_NAME(q.object_id) IS NOT NULL;
        """
        return self._execute_query(query)

    def get_ssrs_execution_logs(self) -> pl.DataFrame:
        """Get SSRS report execution logs from ReportServer database."""
        query = """
        USE [ReportServer];

        SELECT
            'ReportServer' AS [database],
            '' AS [schema],
            c.Name AS object_name,
            COUNT(*) AS execution_count,
            MAX(el.TimeStart) AS last_execution_time,
            AVG(el.TimeDataRetrieval + el.TimeProcessing + el.TimeRendering) AS avg_duration_ms,
            COUNT(DISTINCT el.UserName) AS unique_users
        FROM ExecutionLogStorage el
        INNER JOIN Catalog c ON el.ReportID = c.ItemID
        WHERE el.TimeStart > DATEADD(day, -90, GETDATE())
        GROUP BY c.Name
        ORDER BY COUNT(*) DESC;
        """
        try:
            return self._execute_query(query)
        except Exception as e:
            print(f"    WARNING: Could not read SSRS logs: {e}")
            return pl.DataFrame()

    def get_dependencies(self, database: str) -> pl.DataFrame:
        """Get column/table dependencies from sys.sql_expression_dependencies."""
        # Try modern query first (SQL Server 2008 R2 SP1+)
        query = f"""
        USE [{database}];

        SELECT
            '{database}' AS [database],
            OBJECT_SCHEMA_NAME(sed.referencing_id) AS referencing_schema,
            OBJECT_NAME(sed.referencing_id) AS referencing_object,
            sed.referenced_schema_name AS referenced_schema,
            sed.referenced_entity_name AS referenced_table,
            CAST(NULL AS NVARCHAR(128)) AS referenced_column,
            o.type_desc AS referencing_type
        FROM sys.sql_expression_dependencies sed
        INNER JOIN sys.objects o ON sed.referencing_id = o.object_id
        WHERE sed.referenced_entity_name IS NOT NULL
          AND OBJECT_SCHEMA_NAME(sed.referencing_id) NOT IN ('sys', 'INFORMATION_SCHEMA')
        ORDER BY referenced_table;
        """
        try:
            return self._execute_query(query)
        except Exception:
            # Fallback to sys.sql_dependencies for older versions
            fallback_query = f"""
            USE [{database}];

            SELECT
                '{database}' AS [database],
                OBJECT_SCHEMA_NAME(d.object_id) AS referencing_schema,
                OBJECT_NAME(d.object_id) AS referencing_object,
                OBJECT_SCHEMA_NAME(d.referenced_major_id) AS referenced_schema,
                OBJECT_NAME(d.referenced_major_id) AS referenced_table,
                COL_NAME(d.referenced_major_id, d.referenced_minor_id) AS referenced_column,
                o.type_desc AS referencing_type
            FROM sys.sql_dependencies d
            INNER JOIN sys.objects o ON d.object_id = o.object_id
            WHERE OBJECT_NAME(d.referenced_major_id) IS NOT NULL
              AND OBJECT_SCHEMA_NAME(d.object_id) NOT IN ('sys', 'INFORMATION_SCHEMA')
            ORDER BY OBJECT_NAME(d.referenced_major_id);
            """
            return self._execute_query(fallback_query)

    def _execute_query(self, query: str) -> pl.DataFrame:
        """Execute SQL query and return results as Polars DataFrame."""
        cursor = self.conn.cursor(as_dict=True)
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            if not rows:
                return pl.DataFrame()
            return pl.DataFrame(rows, infer_schema_length=None)
        finally:
            cursor.close()


def calculate_importance_score(
    execution_count: int,
    last_execution: datetime | None,
    reference_date: datetime | None = None,
) -> float:
    """
    Calculate importance score based on execution count and recency.

    Formula: log(exec_count + 1) * 0.6 + recency_score * 0.4
    """
    if reference_date is None:
        reference_date = datetime.now()

    # Execution count component (log scale)
    count_score = math.log(execution_count + 1)

    # Recency component (decays over 30 days)
    if last_execution:
        days_ago = (reference_date - last_execution).days
        recency_score = max(0.1, 1.0 - (days_ago / 30) * 0.9)
    else:
        recency_score = 0.1

    # Combined score
    importance = count_score * 0.6 + recency_score * 0.4

    return round(importance, 2)


def analyze_target(
    target_name: str,
    target_config: dict,
    include_ssrs: bool = True,
    deep_analysis_count: int = 100,
) -> tuple[pl.DataFrame, pl.DataFrame, dict]:
    """
    Analyze a single target and return procedures, stats, and analysis.

    Returns:
        Tuple of (procedures_df, execution_stats_df, analysis_dict)
    """
    print(f"Connecting to {target_config['name']}...")
    conn = get_connection(target_config)

    try:
        analyzer = ProcedureAnalyzer(conn, target_name, target_config["name"])

        # Get list of databases
        include_dbs = target_config.get("include_databases", ["*"])
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sys.databases
            WHERE state = 0 AND name NOT IN ('master', 'tempdb', 'model', 'msdb')
            ORDER BY name;
        """)
        all_dbs = [row[0] for row in cursor.fetchall()]
        cursor.close()

        if "*" not in include_dbs:
            all_dbs = [db for db in all_dbs if db in include_dbs]

        print(f"Found {len(all_dbs)} databases to analyze")

        all_procedures = []
        all_stats = []
        all_dependencies = []

        for db in all_dbs:
            print(f"  Analyzing {db}...")
            try:
                # Get programmable objects
                procs = analyzer.get_programmable_objects(db)
                if not procs.is_empty():
                    procs = procs.with_columns(
                        [
                            pl.lit(target_name).alias("target"),
                            pl.lit(target_config["name"]).alias("server"),
                            pl.lit(datetime.now()).alias("scanned_at"),
                        ]
                    )
                    all_procedures.append(procs)
                    print(f"    Found {len(procs)} programmable objects")

                # Get execution stats
                stats = analyzer.get_procedure_stats(db)
                if not stats.is_empty():
                    stats = stats.with_columns(
                        [
                            pl.lit(target_name).alias("target"),
                            pl.lit("dm_exec_procedure_stats").alias("source"),
                        ]
                    )
                    all_stats.append(stats)

                # Get Query Store stats
                qs_stats = analyzer.get_query_store_stats(db)
                if not qs_stats.is_empty():
                    qs_stats = qs_stats.with_columns(
                        [
                            pl.lit(target_name).alias("target"),
                            pl.lit("query_store").alias("source"),
                        ]
                    )
                    all_stats.append(qs_stats)

                # Get dependencies
                deps = analyzer.get_dependencies(db)
                if not deps.is_empty():
                    all_dependencies.append(deps)

            except Exception as e:
                print(f"    WARNING: Failed to analyze {db}: {e}")

        # Get SSRS logs if available and requested
        if include_ssrs and target_name == "warehouse":
            print("  Checking SSRS execution logs...")
            ssrs_stats = analyzer.get_ssrs_execution_logs()
            if not ssrs_stats.is_empty():
                ssrs_stats = ssrs_stats.with_columns(
                    [
                        pl.lit(target_name).alias("target"),
                        pl.lit("ssrs").alias("source"),
                    ]
                )
                all_stats.append(ssrs_stats)
                print(f"    Found {len(ssrs_stats)} report execution records")

        # Combine results
        procedures_df = pl.concat(all_procedures) if all_procedures else pl.DataFrame()
        stats_df = pl.concat(all_stats, how="diagonal") if all_stats else pl.DataFrame()
        deps_df = pl.concat(all_dependencies) if all_dependencies else pl.DataFrame()

        # Build analysis dict
        analysis = build_analysis(procedures_df, stats_df, deps_df, deep_analysis_count)

        return procedures_df, stats_df, analysis

    finally:
        conn.close()


def _compute_global_patterns(
    joins: list[dict],
    aggregations: list[dict],
    filters: list[dict],
    metrics: list[dict],
) -> dict:
    """Compute aggregate patterns across all parsed procedures."""
    from collections import Counter

    # Most joined tables
    join_tables = Counter()
    for j in joins:
        join_tables[j.get("rightTable", "UNKNOWN")] += 1
        if j.get("leftTable") and j["leftTable"] != "UNKNOWN":
            join_tables[j["leftTable"]] += 1

    # Most aggregated columns
    agg_columns = Counter()
    for a in aggregations:
        col = a.get("column", "*")
        if col != "*":
            agg_columns[col] += 1

    # Most filtered columns
    filter_columns = Counter()
    for f in filters:
        col = f.get("column", "")
        if col:
            # Strip table prefix for aggregation
            col_name = col.split(".")[-1] if "." in col else col
            filter_columns[col_name] += 1

    # Most common filter patterns
    filter_patterns = Counter()
    for f in filters:
        pattern = f"{f.get('column', '')} {f.get('operator', '')}"
        filter_patterns[pattern] += 1

    return {
        "mostJoinedTables": [
            {"table": t, "count": c} for t, c in join_tables.most_common(20)
        ],
        "mostAggregatedColumns": [
            {"column": c, "count": n} for c, n in agg_columns.most_common(20)
        ],
        "mostFilteredColumns": [
            {"column": c, "count": n} for c, n in filter_columns.most_common(20)
        ],
        "commonFilterPatterns": [
            {"pattern": p, "count": c} for p, c in filter_patterns.most_common(20)
        ],
        "discoveredMetrics": metrics[:50],  # Top 50 metrics
        "totals": {
            "joins": len(joins),
            "aggregations": len(aggregations),
            "filters": len(filters),
            "metrics": len(metrics),
        },
    }


def build_analysis(
    procedures_df: pl.DataFrame,
    stats_df: pl.DataFrame,
    deps_df: pl.DataFrame,
    deep_analysis_count: int,
) -> dict:
    """Build the procedure analysis dictionary."""
    analysis = {
        "@context": {
            "oms": "http://realpage.com/oms/",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        },
        "generatedAt": datetime.now().isoformat(),
        "summary": {
            "totalProcedures": 0,
            "totalViews": 0,
            "totalFunctions": 0,
            "totalTriggers": 0,
            "totalWithStats": 0,
        },
        "procedures": [],
        "columnUsage": {},
        "tableUsage": {},
        "unusedObjects": {"tables": [], "columns": []},
    }

    if procedures_df.is_empty():
        return analysis

    # Summary counts
    type_counts = procedures_df.group_by("object_type").len()
    for row in type_counts.iter_rows(named=True):
        obj_type = row["object_type"]
        count = row["len"]
        if obj_type == "PROCEDURE":
            analysis["summary"]["totalProcedures"] = count
        elif obj_type == "VIEW":
            analysis["summary"]["totalViews"] = count
        elif obj_type in ("SCALAR_FUNCTION", "INLINE_FUNCTION", "TABLE_FUNCTION"):
            analysis["summary"]["totalFunctions"] += count
        elif obj_type == "TRIGGER":
            analysis["summary"]["totalTriggers"] = count

    # Build stats lookup for procedures with execution data
    stats_lookup = {}
    if not stats_df.is_empty():
        agg_stats = stats_df.group_by(["database", "object_name"]).agg(
            [
                pl.col("execution_count").sum(),
                pl.col("last_execution_time").max(),
                pl.col("avg_duration_ms").mean(),
                pl.col("total_cpu_ms").sum()
                if "total_cpu_ms" in stats_df.columns
                else pl.lit(0),
            ]
        )
        for row in agg_stats.iter_rows(named=True):
            key = f"{row['database']}.{row['object_name']}"
            stats_lookup[key] = row
        analysis["summary"]["totalWithStats"] = len(stats_lookup)

    # Build proc_list from ALL procedures (not just those with stats)
    now = datetime.now()
    proc_list = []
    for row in procedures_df.iter_rows(named=True):
        key = f"{row['database']}.{row['object_name']}"
        stats = stats_lookup.get(key, {})

        last_exec = stats.get("last_execution_time")
        if isinstance(last_exec, str):
            try:
                last_exec = datetime.fromisoformat(last_exec)
            except:
                last_exec = None

        exec_count = stats.get("execution_count") or 0
        importance = calculate_importance_score(exec_count, last_exec, now)

        proc_list.append(
            {
                "@id": f"oms:{row['database']}.dbo.{row['object_name']}",
                "database": row["database"],
                "objectName": row["object_name"],
                "objectType": row.get("object_type", "UNKNOWN"),
                "executionCount": exec_count,
                "lastExecuted": last_exec.isoformat() if last_exec else None,
                "avgDurationMs": round(stats.get("avg_duration_ms") or 0, 2),
                "importanceScore": importance,
                "hasDefinition": bool(row.get("definition")),
            }
        )

    # Sort: procedures with stats first (by importance), then others alphabetically
    proc_list.sort(key=lambda x: (-x["importanceScore"], x["objectName"]))
    top_procs = proc_list[:deep_analysis_count]
    print(f"  Processing {len(top_procs)} procedures (of {len(proc_list)} total)")

    # Deep parse procedures if parser available
    if PARSER_AVAILABLE and not procedures_df.is_empty():
        print(f"  Deep parsing {len(top_procs)} procedures...")
        parser = ProcedureParser()

        # Build lookup for procedure definitions
        proc_defs = {}
        for row in procedures_df.iter_rows(named=True):
            key = f"{row['database']}.{row['object_name']}"
            if row.get("definition"):
                proc_defs[key] = row["definition"]

        # Parse each procedure
        all_joins = []
        all_aggregations = []
        all_filters = []
        all_metrics = []

        for i, proc in enumerate(top_procs):
            key = f"{proc['database']}.{proc['objectName']}"
            definition = proc_defs.get(key)

            if definition:
                parsed = parser.parse(definition)

                # Add parsed patterns to procedure entry
                proc["parsedPatterns"] = {
                    "joins": [j.to_dict() for j in parsed.joins],
                    "aggregations": [a.to_dict() for a in parsed.aggregations],
                    "filters": [f.to_dict() for f in parsed.filters],
                    "metrics": [m.to_dict() for m in parsed.metrics],
                    "tablesReferenced": list(parsed.tables_referenced),
                    "complexity": {
                        "tables": len(parsed.tables_referenced),
                        "joins": len(parsed.joins),
                        "aggregations": len(parsed.aggregations),
                    },
                }

                # Collect for global aggregation
                for j in parsed.joins:
                    all_joins.append({"proc": proc["objectName"], **j.to_dict()})
                for a in parsed.aggregations:
                    all_aggregations.append({"proc": proc["objectName"], **a.to_dict()})
                for f in parsed.filters:
                    all_filters.append({"proc": proc["objectName"], **f.to_dict()})
                for m in parsed.metrics:
                    all_metrics.append({"proc": proc["objectName"], **m.to_dict()})

            if (i + 1) % 50 == 0:
                print(f"    Parsed {i + 1}/{len(top_procs)}")

        # Add global patterns summary (outside the loop)
        analysis["globalPatterns"] = _compute_global_patterns(
            all_joins, all_aggregations, all_filters, all_metrics
        )
        print(
            f"    Found {len(all_joins)} joins, {len(all_aggregations)} aggregations, "
            f"{len(all_filters)} filters, {len(all_metrics)} metrics"
        )

    analysis["procedures"] = top_procs

    # Build column/table usage from dependencies
    if not deps_df.is_empty():
        # Column usage
        col_usage = (
            deps_df.filter(pl.col("referenced_column").is_not_null())
            .group_by(["referenced_table", "referenced_column"])
            .agg(
                [
                    pl.len().alias("reference_count"),
                    pl.col("referencing_object").n_unique().alias("unique_referrers"),
                ]
            )
        )
        for row in col_usage.iter_rows(named=True):
            key = f"{row['referenced_table']}.{row['referenced_column']}"
            analysis["columnUsage"][key] = {
                "referenceCount": row["reference_count"],
                "uniqueReferrers": row["unique_referrers"],
            }

        # Table usage
        table_usage = deps_df.group_by("referenced_table").agg(
            [
                pl.len().alias("reference_count"),
                pl.col("referencing_object").n_unique().alias("unique_referrers"),
            ]
        )
        for row in table_usage.iter_rows(named=True):
            analysis["tableUsage"][row["referenced_table"]] = {
                "referenceCount": row["reference_count"],
                "uniqueReferrers": row["unique_referrers"],
            }

    return analysis


def enrich_ontology(analysis: dict) -> None:
    """Add usage stats to the existing ontology."""
    if not ONTOLOGY_PATH.exists():
        print("WARNING: ontology.jsonld not found, skipping enrichment")
        return

    with open(ONTOLOGY_PATH) as f:
        ontology = json.load(f)

    # Add usage stats to entities
    column_usage = analysis.get("columnUsage", {})
    table_usage = analysis.get("tableUsage", {})

    for entity in ontology.get("entities", []):
        table_name = entity.get("rdfs:label", "")

        # Add table-level usage
        if table_name in table_usage:
            entity["usageStats"] = {
                "referenceCount": table_usage[table_name]["referenceCount"],
                "uniqueReferrers": table_usage[table_name]["uniqueReferrers"],
            }

        # Add column-level usage
        for col in entity.get("hasColumn", []):
            col_name = col.get("rdfs:label", "")
            key = f"{table_name}.{col_name}"
            if key in column_usage:
                col["usageStats"] = {
                    "referenceCount": column_usage[key]["referenceCount"],
                    "uniqueReferrers": column_usage[key]["uniqueReferrers"],
                }

    # Write enriched ontology
    with open(ONTOLOGY_PATH, "w") as f:
        json.dump(ontology, f, indent=2, default=str)

    print(f"Enriched ontology at {ONTOLOGY_PATH}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze stored procedures and enrich data catalog"
    )
    parser.add_argument(
        "--target",
        help="Target name from targets.toml (default: analyze all targets)",
    )
    parser.add_argument(
        "--deep-analysis",
        type=int,
        default=100,
        help="Number of top procedures to analyze deeply (default: 100)",
    )
    parser.add_argument(
        "--skip-ssrs",
        action="store_true",
        help="Skip SSRS execution log analysis",
    )

    args = parser.parse_args()

    # Load config
    try:
        config = load_targets_config()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    targets = config.get("targets", {})

    # Determine targets to analyze
    if args.target:
        if args.target not in targets:
            print(f"ERROR: Unknown target '{args.target}'")
            sys.exit(1)
        targets_to_analyze = {args.target: targets[args.target]}
    else:
        targets_to_analyze = targets

    # Analyze targets
    all_procedures = []
    all_stats = []
    combined_analysis = {
        "@context": {"oms": "http://realpage.com/oms/"},
        "generatedAt": datetime.now().isoformat(),
        "summary": {},
        "procedures": [],
        "columnUsage": {},
        "tableUsage": {},
    }

    for target_name, target_config in targets_to_analyze.items():
        print(f"\n=== Analyzing target: {target_name} ===")
        try:
            procs, stats, analysis = analyze_target(
                target_name,
                target_config,
                include_ssrs=not args.skip_ssrs,
                deep_analysis_count=args.deep_analysis,
            )

            if not procs.is_empty():
                all_procedures.append(procs)
            if not stats.is_empty():
                all_stats.append(stats)

            # Merge analysis
            combined_analysis["procedures"].extend(analysis.get("procedures", []))
            combined_analysis["columnUsage"].update(analysis.get("columnUsage", {}))
            combined_analysis["tableUsage"].update(analysis.get("tableUsage", {}))

        except Exception as e:
            print(f"ERROR analyzing {target_name}: {e}")

    # Write procedures.parquet
    if all_procedures:
        procedures_df = pl.concat(all_procedures, how="diagonal")
        procedures_df.write_parquet(PROCEDURES_PATH)
        print(f"\nWrote {len(procedures_df)} procedures to {PROCEDURES_PATH}")

    # Write execution_stats.parquet
    if all_stats:
        stats_df = pl.concat(all_stats, how="diagonal")
        stats_df.write_parquet(EXECUTION_STATS_PATH)
        print(f"Wrote {len(stats_df)} execution stats to {EXECUTION_STATS_PATH}")

    # Write procedure_analysis.jsonld
    with open(PROCEDURE_ANALYSIS_PATH, "w") as f:
        json.dump(combined_analysis, f, indent=2, default=str)
    print(f"Wrote analysis to {PROCEDURE_ANALYSIS_PATH}")

    # Enrich ontology
    enrich_ontology(combined_analysis)

    # Summary
    print(f"\n=== Analysis Complete ===")
    if all_procedures:
        print(f"  Procedures/Views/Functions: {len(procedures_df)}")
    if all_stats:
        print(f"  Execution statistics: {len(stats_df)}")
    print(f"  Columns with usage data: {len(combined_analysis['columnUsage'])}")
    print(f"  Tables with usage data: {len(combined_analysis['tableUsage'])}")


if __name__ == "__main__":
    main()
