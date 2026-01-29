#!/usr/bin/env python3
"""
Data Catalog Query - Fast keyword search for database metadata.

Usage:
    python catalog_query.py <keywords> [--top N] [--format table|json|csv]

Examples:
    python catalog_query.py "order cancel"
    python catalog_query.py "customer churn" --top 30
    python catalog_query.py "invoice" --format json

Searches the global catalog by keywords and returns ranked matches.
No database access required - uses cached metadata only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import polars as pl

from config import get_catalog_dir

CATALOG_DIR = get_catalog_dir()
METADATA_PATH = CATALOG_DIR / "metadata.parquet"
LAST_SCAN_PATH = CATALOG_DIR / "last_scan.json"


def load_catalog() -> pl.DataFrame:
    """Load the global catalog from parquet file."""
    if not METADATA_PATH.exists():
        raise FileNotFoundError(
            f"Catalog not found at {METADATA_PATH}\n"
            "Run 'python catalog_refresh.py' to build the catalog first."
        )
    return pl.read_parquet(METADATA_PATH)


def get_catalog_age() -> tuple[int, str]:
    """
    Get catalog age in days and last scan timestamp.

    Returns:
        Tuple of (age_days, timestamp_str)
    """
    if not LAST_SCAN_PATH.exists():
        return -1, "unknown"

    with open(LAST_SCAN_PATH) as f:
        scan_info = json.load(f)

    last_updated = scan_info.get("last_updated")
    if not last_updated:
        return -1, "unknown"

    last_dt = datetime.fromisoformat(last_updated)
    age_days = (datetime.now() - last_dt).days
    return age_days, last_updated


def search_catalog(
    keywords: list[str],
    df: pl.DataFrame,
    top_n: int = 20,
) -> pl.DataFrame:
    """
    Search catalog by keywords and return ranked matches.

    Ranking factors:
    - Keyword matches in table_name (weight: 3)
    - Keyword matches in column_name (weight: 2)
    - Keyword matches in database name (weight: 1)
    - Is primary key (bonus: 2)
    - Is foreign key (bonus: 1)
    - Row count (tiebreaker, larger = more important)

    Args:
        keywords: List of search keywords
        df: Catalog DataFrame
        top_n: Maximum results to return

    Returns:
        DataFrame with search results, ranked by relevance
    """
    # Normalize keywords
    keywords = [k.lower().strip() for k in keywords]

    # Build match expressions
    table_match = pl.lit(0)
    column_match = pl.lit(0)
    db_match = pl.lit(0)

    for kw in keywords:
        table_match = (
            table_match
            + pl.col("table_name").str.to_lowercase().str.contains(kw).cast(pl.Int32)
            * 3
        )
        column_match = (
            column_match
            + pl.col("column_name").str.to_lowercase().str.contains(kw).cast(pl.Int32)
            * 2
        )
        db_match = (
            db_match
            + pl.col("database").str.to_lowercase().str.contains(kw).cast(pl.Int32) * 1
        )

    # Compute relevance score
    df_scored = df.with_columns(
        [
            (table_match + column_match + db_match).alias("keyword_score"),
            (pl.col("is_primary_key").cast(pl.Int32) * 2).alias("pk_bonus"),
            (pl.col("is_foreign_key").cast(pl.Int32) * 1).alias("fk_bonus"),
        ]
    ).with_columns(
        [
            (pl.col("keyword_score") + pl.col("pk_bonus") + pl.col("fk_bonus")).alias(
                "relevance"
            ),
        ]
    )

    # Filter to matches only
    results = (
        df_scored.filter(pl.col("keyword_score") > 0)
        .sort(
            ["relevance", "row_count_estimate"],
            descending=[True, True],
        )
        .head(top_n)
        .select(
            [
                "database",
                "schema",
                "table_name",
                "column_name",
                "data_type",
                "is_primary_key",
                "is_foreign_key",
                "fk_references",
                "row_count_estimate",
                "relevance",
            ]
        )
    )

    return results


def format_table(df: pl.DataFrame) -> str:
    """Format results as ASCII table."""
    if df.is_empty():
        return "No matches found."

    lines = []

    # Header
    lines.append("| Table | Column | Type | Keys | FK References | Rows | Score |")
    lines.append("|-------|--------|------|------|---------------|------|-------|")

    for row in df.iter_rows(named=True):
        full_table = f"{row['database']}.{row['table_name']}"

        # Key indicators
        keys = []
        if row["is_primary_key"]:
            keys.append("PK")
        if row["is_foreign_key"]:
            keys.append("FK")
        keys_str = ",".join(keys) if keys else "-"

        # FK reference
        fk_ref = row["fk_references"] if row["fk_references"] else "-"
        if len(fk_ref) > 30:
            fk_ref = fk_ref[:27] + "..."

        # Row count
        rows = f"{row['row_count_estimate']:,}" if row["row_count_estimate"] else "-"

        lines.append(
            f"| {full_table[:30]} | {row['column_name'][:20]} | {row['data_type'][:10]} | "
            f"{keys_str} | {fk_ref} | {rows} | {row['relevance']} |"
        )

    return "\n".join(lines)


def format_json(df: pl.DataFrame) -> str:
    """Format results as JSON."""
    return df.write_json()


def format_csv(df: pl.DataFrame) -> str:
    """Format results as CSV."""
    return df.write_csv()


def get_table_summary(df: pl.DataFrame, database: str, table_name: str) -> str:
    """Get detailed summary for a specific table."""
    table_df = df.filter(
        (pl.col("database") == database) & (pl.col("table_name") == table_name)
    )

    if table_df.is_empty():
        return f"Table not found: {database}.{table_name}"

    first_row = table_df.row(0, named=True)
    lines = [
        f"# {database}.{first_row['schema']}.{table_name}",
        "",
        f"**Rows:** {first_row['row_count_estimate']:,}"
        if first_row["row_count_estimate"]
        else "**Rows:** Unknown",
        "",
        "## Columns",
        "",
        "| Column | Type | PK | FK | References |",
        "|--------|------|----|----|------------|",
    ]

    for row in table_df.iter_rows(named=True):
        pk = "✓" if row["is_primary_key"] else ""
        fk = "✓" if row["is_foreign_key"] else ""
        ref = row["fk_references"] if row["fk_references"] else ""
        lines.append(
            f"| {row['column_name']} | {row['data_type']} | {pk} | {fk} | {ref} |"
        )

    return "\n".join(lines)


def suggest_joins(df: pl.DataFrame, table_name: str) -> str:
    """Suggest join paths for a table based on FK relationships."""
    # Find tables that reference this table
    inbound = (
        df.filter(pl.col("fk_references").str.contains(table_name))
        .select(["database", "table_name", "column_name", "fk_references"])
        .unique()
    )

    # Find tables this table references
    table_fks = (
        df.filter(
            (pl.col("table_name") == table_name) & (pl.col("is_foreign_key") == True)  # noqa: E712
        )
        .select(["database", "table_name", "column_name", "fk_references"])
        .unique()
    )

    lines = [f"# Join Paths for {table_name}", ""]

    if not table_fks.is_empty():
        lines.extend(["## Outbound (this table references)", ""])
        for row in table_fks.iter_rows(named=True):
            lines.append(f"- {row['column_name']} → {row['fk_references']}")

    if not inbound.is_empty():
        lines.extend(["", "## Inbound (referenced by)", ""])
        for row in inbound.iter_rows(named=True):
            lines.append(
                f"- {row['database']}.{row['table_name']}.{row['column_name']}"
            )

    if table_fks.is_empty() and inbound.is_empty():
        lines.append("*No foreign key relationships found*")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Search data catalog by keywords",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python catalog_query.py "order cancel"       Search for order cancellation data
  python catalog_query.py "churn" --top 30     Get more results
  python catalog_query.py --table Orders.Order Show table details
  python catalog_query.py --joins OrderItem    Show join paths
  python catalog_query.py --status             Show catalog status
        """,
    )
    parser.add_argument(
        "keywords",
        nargs="*",
        help="Search keywords (space-separated)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Maximum results to return (default: 20)",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json", "csv"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--table",
        metavar="DB.TABLE",
        help="Show details for a specific table",
    )
    parser.add_argument(
        "--joins",
        metavar="TABLE",
        help="Show join paths for a table",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show catalog status and exit",
    )

    args = parser.parse_args()

    # Check catalog status
    if args.status:
        age_days, last_updated = get_catalog_age()
        if age_days < 0:
            print("Catalog status: NOT BUILT")
            print("Run 'python catalog_refresh.py' to build the catalog.")
        else:
            print(f"Catalog status: OK")
            print(f"Last updated: {last_updated}")
            print(f"Age: {age_days} days")
            if age_days > 7:
                print("WARNING: Catalog is stale (>7 days). Consider refreshing.")

            # Show quick stats
            try:
                df = load_catalog()
                print(f"\nCatalog contains:")
                print(f"  - {df.n_unique('target')} targets")
                print(f"  - {df.n_unique('database')} databases")
                print(
                    f"  - {df.select(['database', 'table_name']).unique().height} tables"
                )
                print(f"  - {len(df)} columns")
            except FileNotFoundError:
                pass
        return

    # Load catalog
    try:
        df = load_catalog()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Check age and warn if stale
    age_days, _ = get_catalog_age()
    if age_days > 7:
        print(
            f"WARNING: Catalog is {age_days} days old. Consider running catalog_refresh.py",
            file=sys.stderr,
        )
        print("", file=sys.stderr)

    # Table details mode
    if args.table:
        parts = args.table.split(".")
        if len(parts) != 2:
            print("ERROR: Use format 'Database.TableName'")
            sys.exit(1)
        print(get_table_summary(df, parts[0], parts[1]))
        return

    # Join paths mode
    if args.joins:
        print(suggest_joins(df, args.joins))
        return

    # Search mode
    if not args.keywords:
        parser.print_help()
        sys.exit(1)

    # Parse keywords (handle both "word1 word2" and word1 word2)
    keywords = []
    for kw in args.keywords:
        keywords.extend(kw.split())

    results = search_catalog(keywords, df, args.top)

    # Format output
    if args.format == "table":
        print(format_table(results))
    elif args.format == "json":
        print(format_json(results))
    elif args.format == "csv":
        print(format_csv(results))

    # Show result count
    if args.format == "table":
        print(f"\n{len(results)} results (searched {len(df):,} columns)")


if __name__ == "__main__":
    main()
