#!/usr/bin/env python3
"""
Data Catalog Refresh - Heavy database metadata scan.

Usage:
    python catalog_refresh.py [--target NAME] [--depth metadata|profile] [--project PATH]

Examples:
    python catalog_refresh.py --target oms
    python catalog_refresh.py --target oms --depth profile
    python catalog_refresh.py --target oms --project /path/to/ds-project

Scans database metadata and writes to global catalog at ~/.ds_catalog/metadata.parquet.
If --project is specified or run from a DS project directory, also creates a project snapshot.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import polars as pl

# Load environment variables from .env files
try:
    from dotenv import load_dotenv

    # Try multiple locations
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
    pass  # dotenv not available, rely on shell environment

# Add scripts directory to path for imports
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from adapters.sqlserver import SQLServerAdapter, get_accessible_databases

CATALOG_DIR = Path(os.environ.get("DENG_CATALOG_DIR", str(Path.home() / ".ds_catalog")))
METADATA_PATH = CATALOG_DIR / "metadata.parquet"
LAST_SCAN_PATH = CATALOG_DIR / "last_scan.json"
TARGETS_PATH = CATALOG_DIR / "targets.toml"


def load_targets_config() -> dict:
    """Load targets configuration from TOML file."""
    if not TARGETS_PATH.exists():
        raise FileNotFoundError(f"Targets config not found: {TARGETS_PATH}")

    with open(TARGETS_PATH, "rb") as f:
        return tomllib.load(f)


def get_connection(target_config: dict) -> Any:
    """
    Create database connection from target config.

    Reads credentials from environment variables specified in config.
    """
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


def scan_target(
    target_name: str, target_config: dict, depth: str = "metadata"
) -> pl.DataFrame:
    """
    Scan a single target and return metadata DataFrame.

    Args:
        target_name: Name of the target (for logging)
        target_config: Target configuration dict
        depth: Scan depth - "metadata" (schema only) or "profile" (with stats)

    Returns:
        Polars DataFrame with catalog schema
    """
    print(f"Connecting to {target_config['name']}...")
    conn = get_connection(target_config)

    try:
        adapter = SQLServerAdapter(conn)

        # Get list of databases to scan
        include_dbs = target_config.get("include_databases", ["*"])
        databases = get_accessible_databases(conn, include_dbs)

        print(f"Found {len(databases)} databases to scan: {', '.join(databases)}")

        # Determine if we should run profiling
        include_profile = depth == "profile"
        if include_profile:
            print("  Data profiling enabled (this may take longer)")

        all_metadata = []
        for db in databases:
            print(f"  Scanning {db}...")
            try:
                df = adapter.get_all_metadata(
                    db,
                    include_profile=include_profile,
                    profile_sample_size=1000,  # Sample 1000 rows per table
                )
                if not df.is_empty():
                    # Add server/target info
                    df = df.with_columns(
                        [
                            pl.lit(target_name).alias("target"),
                            pl.lit(target_config["name"]).alias("server"),
                        ]
                    )
                    all_metadata.append(df)
                    profile_info = ""
                    if include_profile and "null_rate" in df.columns:
                        avg_null_rate = df["null_rate"].mean()
                        profile_info = f", avg null rate: {avg_null_rate:.1%}"
                    print(
                        f"    Found {df.n_unique('table_name')} tables, {len(df)} columns{profile_info}"
                    )
            except Exception as e:
                print(f"    WARNING: Failed to scan {db}: {e}")

        if not all_metadata:
            return pl.DataFrame()

        # Normalize schema across all dataframes to handle type mismatches
        # (e.g., is_nullable may be Boolean in some DBs, Int64 in others)
        normalized = []
        for df in all_metadata:
            casts = [
                pl.col("is_nullable").cast(pl.Boolean),
                pl.col("is_primary_key").cast(pl.Boolean),
                pl.col("is_foreign_key").cast(pl.Boolean),
                pl.col("row_count_estimate").cast(pl.Int64),
            ]
            # Add profile column casts if present
            if "null_count" in df.columns:
                casts.extend(
                    [
                        pl.col("null_count").cast(pl.Int64),
                        pl.col("null_rate").cast(pl.Float64),
                        pl.col("distinct_count").cast(pl.Int64),
                        pl.col("profiled_rows").cast(pl.Int64),
                    ]
                )
            df = df.with_columns(casts)
            normalized.append(df)

        return pl.concat(
            normalized, how="diagonal"
        )  # diagonal allows different columns

    finally:
        conn.close()


def write_global_catalog(df: pl.DataFrame, target_name: str) -> None:
    """
    Write or update global catalog with new scan data.

    Merges new data with existing catalog, replacing data for the scanned target.
    """
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)

    if METADATA_PATH.exists():
        existing = pl.read_parquet(METADATA_PATH)
        # Normalize schema for compatibility
        existing = existing.with_columns(
            [
                pl.col("is_nullable").cast(pl.Boolean),
                pl.col("is_primary_key").cast(pl.Boolean),
                pl.col("is_foreign_key").cast(pl.Boolean),
                pl.col("row_count_estimate").cast(pl.Int64),
            ]
        )
        # Remove old data for this target
        existing = existing.filter(pl.col("target") != target_name)
        # Normalize new data too
        if not df.is_empty():
            df = df.with_columns(
                [
                    pl.col("is_nullable").cast(pl.Boolean),
                    pl.col("is_primary_key").cast(pl.Boolean),
                    pl.col("is_foreign_key").cast(pl.Boolean),
                    pl.col("row_count_estimate").cast(pl.Int64),
                ]
            )
            result = pl.concat([existing, df])
        else:
            result = existing
    else:
        result = df

    # Write catalog
    result.write_parquet(METADATA_PATH)
    print(f"Wrote catalog to {METADATA_PATH}")

    # Update scan metadata
    update_scan_metadata(target_name, len(df))


def update_scan_metadata(target_name: str, row_count: int) -> None:
    """Update last_scan.json with scan info."""
    if LAST_SCAN_PATH.exists():
        with open(LAST_SCAN_PATH) as f:
            scan_info = json.load(f)
    else:
        scan_info = {"scans": {}}

    scan_info["scans"][target_name] = {
        "timestamp": datetime.now().isoformat(),
        "row_count": row_count,
    }
    scan_info["last_updated"] = datetime.now().isoformat()

    with open(LAST_SCAN_PATH, "w") as f:
        json.dump(scan_info, f, indent=2)


def generate_summary_markdown(df: pl.DataFrame) -> str:
    """Generate human-readable summary of the catalog."""
    if df.is_empty():
        return "# Data Catalog Summary\n\nNo data in catalog."

    lines = [
        "# Data Catalog Summary",
        "",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "## Overview",
        "",
    ]

    # Summary stats
    n_targets = df.n_unique("target")
    n_databases = df.n_unique("database")
    n_tables = df.select(["database", "schema", "table_name"]).unique().height
    n_columns = len(df)

    lines.extend(
        [
            f"- **Targets:** {n_targets}",
            f"- **Databases:** {n_databases}",
            f"- **Tables:** {n_tables}",
            f"- **Columns:** {n_columns}",
            "",
            "## Databases",
            "",
        ]
    )

    # Per-database summary
    db_summary = (
        df.group_by(["target", "database"])
        .agg(
            [
                pl.col("table_name").n_unique().alias("tables"),
                pl.len().alias("columns"),
                pl.col("row_count_estimate").max().alias("max_rows"),
            ]
        )
        .sort(["target", "database"])
    )

    lines.append("| Target | Database | Tables | Columns | Max Rows |")
    lines.append("|--------|----------|--------|---------|----------|")

    for row in db_summary.iter_rows(named=True):
        max_rows = f"{row['max_rows']:,}" if row["max_rows"] else "N/A"
        lines.append(
            f"| {row['target']} | {row['database']} | {row['tables']} | {row['columns']} | {max_rows} |"
        )

    lines.extend(["", "## Large Tables (>1M rows)", ""])

    # Large tables
    large_tables = (
        df.select(["target", "database", "schema", "table_name", "row_count_estimate"])
        .unique()
        .filter(pl.col("row_count_estimate") > 1_000_000)
        .sort("row_count_estimate", descending=True)
        .head(20)
    )

    if large_tables.height > 0:
        lines.append("| Table | Rows |")
        lines.append("|-------|------|")
        for row in large_tables.iter_rows(named=True):
            full_name = f"{row['database']}.{row['schema']}.{row['table_name']}"
            lines.append(f"| {full_name} | {row['row_count_estimate']:,} |")
    else:
        lines.append("*No tables with >1M rows*")

    lines.extend(["", "## Key Relationships", ""])

    # Foreign key summary
    fk_cols = df.filter(pl.col("is_foreign_key") == True)  # noqa: E712
    if fk_cols.height > 0:
        lines.append("| From | To |")
        lines.append("|------|-----|")

        fk_summary = (
            fk_cols.select(
                [
                    "database",
                    "schema",
                    "table_name",
                    "column_name",
                    "fk_references",
                ]
            )
            .unique()
            .head(30)
        )

        for row in fk_summary.iter_rows(named=True):
            from_col = f"{row['database']}.{row['table_name']}.{row['column_name']}"
            lines.append(f"| {from_col} | {row['fk_references']} |")
    else:
        lines.append("*No foreign keys found*")

    return "\n".join(lines)


def create_project_snapshot(project_root: Path, df: pl.DataFrame) -> None:
    """Create a snapshot of the catalog in a DS project."""
    catalog_dir = project_root / "artifacts" / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamped snapshot directory
    snapshot_name = f"snapshot_{datetime.now().strftime('%Y%m%d')}"
    snapshot_dir = catalog_dir / snapshot_name
    snapshot_dir.mkdir(exist_ok=True)

    # Copy metadata
    snapshot_path = snapshot_dir / "metadata.parquet"
    df.write_parquet(snapshot_path)
    print(f"Created snapshot at {snapshot_path}")

    # Generate summary
    summary = generate_summary_markdown(df)
    summary_path = catalog_dir / "DATA_CATALOG_SUMMARY.md"
    with open(summary_path, "w") as f:
        f.write(summary)
    print(f"Generated summary at {summary_path}")


def detect_project_root() -> Path | None:
    """
    Detect if we're in a DS project directory.

    Looks for configs/project.toml or .claude/settings.json.
    """
    cwd = Path.cwd()

    # Check current directory and parents
    for path in [cwd] + list(cwd.parents)[:3]:
        if (path / "configs" / "project.toml").exists():
            return path
        if (path / ".claude" / "settings.json").exists() and (path / "src").exists():
            return path

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Refresh data catalog from database metadata"
    )
    parser.add_argument(
        "--target",
        help="Target name from targets.toml (default: scan all targets)",
    )
    parser.add_argument(
        "--depth",
        choices=["metadata", "profile"],
        default="metadata",
        help="Scan depth (default: metadata)",
    )
    parser.add_argument(
        "--project",
        type=Path,
        help="DS project path for snapshot (auto-detected if not specified)",
    )
    parser.add_argument(
        "--list-targets",
        action="store_true",
        help="List available targets and exit",
    )

    args = parser.parse_args()

    # Load config
    try:
        config = load_targets_config()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Create targets.toml with database connection config.")
        sys.exit(1)

    # TOML parses [targets.oms] as nested dict: config["targets"]["oms"]
    targets = config.get("targets", {})

    if args.list_targets:
        print("Available targets:")
        for name, cfg in targets.items():
            print(f"  {name}: {cfg.get('name', 'Unknown')}")
        sys.exit(0)

    # Determine which targets to scan
    if args.target:
        if args.target not in targets:
            print(f"ERROR: Unknown target '{args.target}'")
            print(f"Available targets: {', '.join(targets.keys())}")
            sys.exit(1)
        targets_to_scan = {args.target: targets[args.target]}
    else:
        targets_to_scan = targets

    # Scan targets
    all_data = []
    for target_name, target_config in targets_to_scan.items():
        print(f"\n=== Scanning target: {target_name} ===")
        try:
            df = scan_target(target_name, target_config, args.depth)
            if not df.is_empty():
                all_data.append(df)
                write_global_catalog(df, target_name)
        except Exception as e:
            print(f"ERROR scanning {target_name}: {e}")

    if not all_data:
        print("\nNo data collected from any target.")
        sys.exit(1)

    combined = pl.concat(all_data)
    print(f"\n=== Scan Complete ===")
    print(f"Total: {combined.n_unique('table_name')} tables, {len(combined)} columns")

    # Create project snapshot if applicable
    project_root = args.project or detect_project_root()
    if project_root:
        print(f"\nCreating project snapshot in {project_root}...")
        create_project_snapshot(project_root, combined)

    # Generate global summary
    summary = generate_summary_markdown(combined)
    summary_path = CATALOG_DIR / "DATA_CATALOG_SUMMARY.md"
    with open(summary_path, "w") as f:
        f.write(summary)
    print(f"\nGenerated global summary at {summary_path}")


if __name__ == "__main__":
    main()
