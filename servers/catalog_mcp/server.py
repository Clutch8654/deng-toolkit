"""MCP server exposing data catalog tools.

All tools in one file for simplicity. Reuses logic patterns from
scripts/catalog_query.py but optimized for MCP tool interface.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import polars as pl
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Add scripts directory to path for config import
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from config import get_catalog_dir


# --- Tool Implementations ---


def search_catalog(keywords: list[str], top_n: int = 20) -> dict:
    """Search catalog by keywords and return ranked matches."""
    metadata_path = get_catalog_dir() / "metadata.parquet"

    if not metadata_path.exists():
        raise FileNotFoundError(f"Catalog not found at {metadata_path}")

    df = pl.read_parquet(metadata_path)
    keywords = [k.lower().strip() for k in keywords if k.strip()]

    if not keywords:
        return {"matches": [], "count": 0}

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

    results = (
        df_scored.filter(pl.col("keyword_score") > 0)
        .sort(["relevance", "row_count_estimate"], descending=[True, True])
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

    matches = results.to_dicts()
    return {"matches": matches, "count": len(matches)}


def get_table_details(database: str, schema: str, table_name: str) -> dict:
    """Get full details for a specific table."""
    metadata_path = get_catalog_dir() / "metadata.parquet"

    if not metadata_path.exists():
        raise FileNotFoundError(f"Catalog not found at {metadata_path}")

    df = pl.read_parquet(metadata_path)
    table_df = df.filter(
        (pl.col("database") == database)
        & (pl.col("schema") == schema)
        & (pl.col("table_name") == table_name)
    )

    if table_df.is_empty():
        return {"error": f"Table {database}.{schema}.{table_name} not found"}

    columns = table_df.to_dicts()
    table_info = {
        "database": database,
        "schema": schema,
        "table_name": table_name,
        "row_count_estimate": columns[0].get("row_count_estimate"),
    }

    return {"table": table_info, "columns": columns}


def find_join_paths(table_name: str) -> dict:
    """Find FK relationships for a table."""
    metadata_path = get_catalog_dir() / "metadata.parquet"

    if not metadata_path.exists():
        raise FileNotFoundError(f"Catalog not found at {metadata_path}")

    df = pl.read_parquet(metadata_path)

    # Outbound: FKs from this table to others
    outbound = (
        df.filter(
            (pl.col("table_name") == table_name) & (pl.col("is_foreign_key") == True)
        )
        .select(["column_name", "fk_references"])
        .to_dicts()
    )

    # Inbound: FKs from other tables to this one
    inbound = (
        df.filter(pl.col("fk_references").str.contains(f"{table_name}\\."))
        .select(["table_name", "column_name", "fk_references"])
        .to_dicts()
    )

    return {"outbound": outbound, "inbound": inbound}


def get_catalog_status() -> dict:
    """Get catalog age and statistics."""
    catalog_dir = get_catalog_dir()
    metadata_path = catalog_dir / "metadata.parquet"
    scan_path = catalog_dir / "last_scan.json"

    if not metadata_path.exists():
        return {"status": "NOT_BUILT", "age_days": None, "stats": {}}

    df = pl.read_parquet(metadata_path)
    stats = {
        "tables": df.select("table_name").n_unique(),
        "columns": len(df),
        "databases": df.select("database").n_unique(),
    }

    if scan_path.exists():
        scan_info = json.loads(scan_path.read_text())
        last_updated = datetime.fromisoformat(scan_info["last_updated"])
        age_days = (datetime.now() - last_updated).days
        status = "OK" if age_days < 7 else "STALE"
    else:
        age_days = None
        status = "UNKNOWN"

    return {"status": status, "age_days": age_days, "stats": stats}


# --- MCP Server ---

app = Server("deng-catalog")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available catalog tools."""
    return [
        Tool(
            name="search_catalog",
            description="Search catalog by keywords",
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "top_n": {"type": "integer", "default": 20},
                },
                "required": ["keywords"],
            },
        ),
        Tool(
            name="get_table_details",
            description="Get full details for a specific table",
            inputSchema={
                "type": "object",
                "properties": {
                    "database": {"type": "string"},
                    "schema": {"type": "string"},
                    "table_name": {"type": "string"},
                },
                "required": ["database", "schema", "table_name"],
            },
        ),
        Tool(
            name="find_join_paths",
            description="Find FK relationships for a table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {"type": "string"},
                },
                "required": ["table_name"],
            },
        ),
        Tool(
            name="get_catalog_status",
            description="Get catalog age and statistics",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_annotations",
            description="Get catalog annotations (notes, quality flags) for tables. Merges all team members' annotations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Filter by table (Database.Schema.Table). Omit for all annotations.",
                    },
                },
            },
        ),
        Tool(
            name="add_annotation",
            description="Add annotation to a table (note, quality_flag, or deprecation)",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Table identifier (Database.Schema.Table)",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["note", "quality_flag", "deprecation"],
                        "description": "Annotation type",
                    },
                    "content": {
                        "type": "string",
                        "description": "Annotation content. For quality_flag: TRUSTED, STALE, INCOMPLETE, or EXPERIMENTAL",
                    },
                },
                "required": ["target", "type", "content"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch tool calls to handlers."""
    from .annotations import get_annotations, add_annotation

    handlers = {
        "search_catalog": search_catalog,
        "get_table_details": get_table_details,
        "find_join_paths": find_join_paths,
        "get_catalog_status": get_catalog_status,
        "get_annotations": lambda **args: get_annotations(args.get("target")),
        "add_annotation": lambda **args: add_annotation(
            args["target"], args["type"], args["content"]
        ),
    }

    handler = handlers.get(name)
    if not handler:
        raise ValueError(f"Unknown tool: {name}")

    result = handler(**arguments)
    return [TextContent(type="text", text=json.dumps(result, default=str))]


def main():
    """Run the MCP server."""
    asyncio.run(stdio_server(app))


if __name__ == "__main__":
    main()
