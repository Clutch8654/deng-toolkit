#!/usr/bin/env python3
"""
Data Catalog Snapshot - Copy global catalog to a DS project.

Usage:
    python catalog_snapshot.py [--project PATH] [--filter TARGET]

Examples:
    python catalog_snapshot.py                          # Auto-detect project
    python catalog_snapshot.py --project ./my-project   # Specify project
    python catalog_snapshot.py --filter oms             # Only include OMS data

Creates a timestamped snapshot of the global catalog in the project's
artifacts/catalog/ directory for reproducibility and version control.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import polars as pl

CATALOG_DIR = Path(os.environ.get("DENG_CATALOG_DIR", str(Path.home() / ".ds_catalog")))
METADATA_PATH = CATALOG_DIR / "metadata.parquet"
LAST_SCAN_PATH = CATALOG_DIR / "last_scan.json"


def load_global_catalog() -> pl.DataFrame:
    """Load the global catalog."""
    if not METADATA_PATH.exists():
        raise FileNotFoundError(
            f"Global catalog not found at {METADATA_PATH}\n"
            "Run 'python catalog_refresh.py' to build the catalog first."
        )
    return pl.read_parquet(METADATA_PATH)


def detect_project_root() -> Path | None:
    """
    Detect if we're in a DS project directory.

    Looks for configs/project.toml or artifacts/ directory.
    """
    cwd = Path.cwd()

    for path in [cwd] + list(cwd.parents)[:3]:
        if (path / "configs" / "project.toml").exists():
            return path
        if (path / "artifacts").exists() and (path / "src").exists():
            return path

    return None


def generate_summary_markdown(df: pl.DataFrame, scan_info: dict | None = None) -> str:
    """Generate human-readable summary of the catalog snapshot."""
    if df.is_empty():
        return "# Data Catalog Summary\n\nNo data in catalog."

    lines = [
        "# Data Catalog Summary",
        "",
        f"*Snapshot created: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
    ]

    # Add scan info if available
    if scan_info:
        lines.extend(
            [
                "## Scan Information",
                "",
            ]
        )
        for target, info in scan_info.get("scans", {}).items():
            lines.append(f"- **{target}**: scanned {info.get('timestamp', 'unknown')}")
        lines.append("")

    lines.extend(
        [
            "## Overview",
            "",
        ]
    )

    # Summary stats
    n_targets = df.n_unique("target")
    n_databases = df.n_unique("database")
    n_tables = df.select(["database", "schema", "table_name"]).unique().height
    n_columns = len(df)

    lines.extend(
        [
            f"| Metric | Count |",
            f"|--------|-------|",
            f"| Targets | {n_targets} |",
            f"| Databases | {n_databases} |",
            f"| Tables | {n_tables} |",
            f"| Columns | {n_columns:,} |",
            "",
            "## Databases by Target",
            "",
        ]
    )

    # Per-target/database summary
    db_summary = (
        df.group_by(["target", "database"])
        .agg(
            [
                pl.col("table_name").n_unique().alias("tables"),
                pl.len().alias("columns"),
                pl.col("row_count_estimate").sum().alias("total_rows"),
            ]
        )
        .sort(["target", "database"])
    )

    lines.append("| Target | Database | Tables | Columns | Est. Rows |")
    lines.append("|--------|----------|--------|---------|-----------|")

    for row in db_summary.iter_rows(named=True):
        total_rows = f"{row['total_rows']:,}" if row["total_rows"] else "N/A"
        lines.append(
            f"| {row['target']} | {row['database']} | {row['tables']} | {row['columns']} | {total_rows} |"
        )

    lines.extend(["", "## Key Tables (by row count)", ""])

    # Top tables by row count
    top_tables = (
        df.select(["target", "database", "schema", "table_name", "row_count_estimate"])
        .unique()
        .sort("row_count_estimate", descending=True)
        .head(20)
    )

    lines.append("| Table | Est. Rows |")
    lines.append("|-------|-----------|")

    for row in top_tables.iter_rows(named=True):
        full_name = f"{row['database']}.{row['schema']}.{row['table_name']}"
        rows = f"{row['row_count_estimate']:,}" if row["row_count_estimate"] else "N/A"
        lines.append(f"| {full_name} | {rows} |")

    lines.extend(["", "## Foreign Key Relationships", ""])

    # FK relationships
    fk_cols = df.filter(pl.col("is_foreign_key") == True)  # noqa: E712
    if fk_cols.height > 0:
        # Group by source table
        fk_by_table = (
            fk_cols.group_by(["database", "table_name"])
            .agg(pl.col("fk_references").alias("references"))
            .sort(["database", "table_name"])
            .head(30)
        )

        lines.append("| Table | References |")
        lines.append("|-------|------------|")

        for row in fk_by_table.iter_rows(named=True):
            refs = ", ".join(row["references"][:3])
            if len(row["references"]) > 3:
                refs += f" (+{len(row['references']) - 3} more)"
            lines.append(f"| {row['database']}.{row['table_name']} | {refs} |")
    else:
        lines.append("*No foreign keys found in catalog*")

    lines.extend(
        [
            "",
            "---",
            "",
            "## Usage",
            "",
            "Search the catalog:",
            "```bash",
            'python ~/.ds_catalog/scripts/catalog_query.py "order cancel"',
            "```",
            "",
            "Refresh the catalog:",
            "```bash",
            "python ~/.ds_catalog/scripts/catalog_refresh.py --target oms",
            "```",
        ]
    )

    return "\n".join(lines)


def create_snapshot(
    project_root: Path,
    df: pl.DataFrame,
    scan_info: dict | None = None,
) -> Path:
    """
    Create a snapshot in the project's artifacts/catalog/ directory.

    Returns the path to the snapshot directory.
    """
    catalog_dir = project_root / "artifacts" / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamped snapshot
    timestamp = datetime.now().strftime("%Y%m%d")
    snapshot_dir = catalog_dir / f"snapshot_{timestamp}"

    # If snapshot for today already exists, add time
    if snapshot_dir.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_dir = catalog_dir / f"snapshot_{timestamp}"

    snapshot_dir.mkdir(exist_ok=True)

    # Write metadata parquet
    metadata_path = snapshot_dir / "metadata.parquet"
    df.write_parquet(metadata_path)
    print(f"Created: {metadata_path}")

    # Write scan info
    if scan_info:
        scan_info_path = snapshot_dir / "scan_info.json"
        with open(scan_info_path, "w") as f:
            json.dump(scan_info, f, indent=2)
        print(f"Created: {scan_info_path}")

    # Generate and write summary
    summary = generate_summary_markdown(df, scan_info)
    summary_path = catalog_dir / "DATA_CATALOG_SUMMARY.md"
    with open(summary_path, "w") as f:
        f.write(summary)
    print(f"Created: {summary_path}")

    # Create/update symlink to latest snapshot
    latest_link = catalog_dir / "latest"
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    latest_link.symlink_to(snapshot_dir.name)
    print(f"Updated: {latest_link} -> {snapshot_dir.name}")

    return snapshot_dir


def main():
    parser = argparse.ArgumentParser(
        description="Create a project snapshot of the global data catalog",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--project",
        type=Path,
        help="Project root directory (auto-detected if not specified)",
    )
    parser.add_argument(
        "--filter",
        dest="target_filter",
        help="Only include data from specified target",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List existing snapshots in project",
    )

    args = parser.parse_args()

    # Find project root
    project_root = args.project or detect_project_root()

    if project_root is None:
        print("ERROR: Could not detect project root.")
        print("Run from a DS project directory or specify --project PATH")
        sys.exit(1)

    project_root = project_root.resolve()
    print(f"Project: {project_root}")

    catalog_dir = project_root / "artifacts" / "catalog"

    # List mode
    if args.list:
        if not catalog_dir.exists():
            print("No catalog snapshots found.")
            sys.exit(0)

        snapshots = sorted(catalog_dir.glob("snapshot_*"))
        if not snapshots:
            print("No catalog snapshots found.")
            sys.exit(0)

        print(f"\nSnapshots in {catalog_dir}:")
        for snap in snapshots:
            metadata = snap / "metadata.parquet"
            if metadata.exists():
                df = pl.read_parquet(metadata)
                tables = df.select(["database", "table_name"]).unique().height
                cols = len(df)
                print(f"  {snap.name}: {tables} tables, {cols} columns")
            else:
                print(f"  {snap.name}: (no metadata)")
        sys.exit(0)

    # Load global catalog
    try:
        df = load_global_catalog()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Filter by target if specified
    if args.target_filter:
        df = df.filter(pl.col("target") == args.target_filter)
        if df.is_empty():
            print(f"ERROR: No data found for target '{args.target_filter}'")
            sys.exit(1)
        print(f"Filtered to target: {args.target_filter}")

    # Load scan info
    scan_info = None
    if LAST_SCAN_PATH.exists():
        with open(LAST_SCAN_PATH) as f:
            scan_info = json.load(f)

    # Create snapshot
    print(f"\nCreating snapshot...")
    snapshot_dir = create_snapshot(project_root, df, scan_info)

    print(f"\nSnapshot created: {snapshot_dir}")
    print(f"  Tables: {df.select(['database', 'table_name']).unique().height}")
    print(f"  Columns: {len(df):,}")


if __name__ == "__main__":
    main()
