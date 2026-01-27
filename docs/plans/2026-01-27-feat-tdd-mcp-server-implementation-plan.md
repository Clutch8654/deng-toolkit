---
title: "feat: TDD MCP Server Implementation"
type: feat
date: 2026-01-27
status: ready
revised: 2026-01-27
---

# TDD MCP Server Implementation Plan

Augments the deng-toolkit plugin conversion with Test-Driven Development for the MCP server implementation.

**Revision Notes (2026-01-27):** Simplified based on DHH, Kieran, and Simplicity reviewer feedback:
- Single `server.py` instead of 5 tool modules
- Single `test_catalog_tools.py` instead of 5 test files
- Removed `query_ontology` (YAGNI - no consumer exists)
- Removed integration tests phase (unit tests sufficient)
- Fixed module naming: `catalog_mcp` (underscore, not hyphen)
- Added `schema` column to output (matches original `catalog_query.py`)
- Fixed late binding for `CATALOG_DIR` (testable with monkeypatch)

## Overview

Complete the plugin conversion using TDD to implement 4 MCP catalog tools. Tests are written **before** implementation, ensuring the MCP server is thoroughly tested and reuses the existing `catalog_query.py` logic.

## Current State

**Completed (Phase 1):**
- ✅ `.claude-plugin/plugin.json` - Plugin manifest
- ✅ `commands/` - 6 command files
- ✅ `hooks/` - PostToolUse hooks

**Remaining (Phase 2 - This Plan):**
- ⬜ `.mcp.json` - MCP server configuration
- ⬜ `servers/catalog_mcp/` - MCP server with 4 tools
- ⬜ `pyproject.toml` - Dependencies and pytest config
- ⬜ Tests collocated with server

## Technical Approach

### Test-Driven Development Cycle

1. **RED**: Write failing tests for all tools
2. **GREEN**: Implement minimal code to pass tests
3. **REFACTOR**: Clean up while tests stay green
4. **COMMIT**: Single atomic commit

### Directory Structure (Simplified)

```
~/.deng-toolkit/
├── servers/
│   └── catalog_mcp/              # underscore (Python importable)
│       ├── __init__.py
│       ├── server.py             # ALL tools in one file
│       ├── conftest.py           # test fixtures
│       ├── test_catalog_tools.py # ALL tests in one file
│       └── pyproject.toml
├── pyproject.toml                # Root project config
└── .mcp.json
```

**Why this structure:**
- 3 files instead of 12 (~136 LOC saved)
- Tests collocated with code (easier to maintain)
- Single import path (`from servers.catalog_mcp.server import ...`)
- No tools/ subdirectory (tools are simple functions)

### MCP Tool Schemas

| Tool | Input | Output |
|------|-------|--------|
| `search_catalog` | `{keywords: string[], top_n?: int}` | `{matches: [], count: int}` |
| `get_table_details` | `{database: string, schema: string, table_name: string}` | `{table: {}, columns: []}` |
| `find_join_paths` | `{table_name: string}` | `{outbound: [], inbound: []}` |
| `get_catalog_status` | `{}` | `{status: string, age_days: int, stats: {}}` |

**Note:** `query_ontology` removed (YAGNI - no consumer exists yet).

---

## Implementation Phases

### Phase 1: Configuration & Test Setup

**Files to create:**

#### .mcp.json (Critical - P1 todo)

```json
{
  "mcpServers": {
    "deng-catalog": {
      "command": "uv",
      "args": ["run", "--directory", "${CLAUDE_PLUGIN_ROOT}/servers/catalog_mcp", "python", "-m", "server"]
    }
  }
}
```

#### servers/catalog_mcp/pyproject.toml

```toml
[project]
name = "catalog-mcp"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.2.0",
    "polars>=1.0.0",
]

[project.optional-dependencies]
test = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["."]
python_files = ["test_*.py"]
```

#### servers/catalog_mcp/conftest.py

```python
"""Test fixtures for catalog MCP server."""
import json
from pathlib import Path
import pytest
import polars as pl


def get_catalog_dir() -> Path:
    """Get catalog directory with late binding for testability."""
    import os
    return Path(os.environ.get("DENG_CATALOG_DIR", str(Path.home() / ".ds_catalog")))


@pytest.fixture
def happy_catalog(tmp_path) -> Path:
    """Catalog with searchable test data."""
    catalog_dir = tmp_path / ".ds_catalog"
    catalog_dir.mkdir()

    df = pl.DataFrame({
        "target": ["test"] * 5,
        "server": ["test-server"] * 5,
        "database": ["Orders", "Orders", "Customers", "Products", "Products"],
        "schema": ["dbo"] * 5,
        "table_name": ["Order", "OrderItem", "Customer", "Product", "Category"],
        "column_name": ["OrderId", "OrderId", "CustomerId", "ProductId", "CategoryId"],
        "data_type": ["int"] * 5,
        "is_nullable": [False] * 5,
        "is_primary_key": [True, False, True, True, True],
        "is_foreign_key": [False, True, False, False, False],
        "fk_references": [None, "Order.OrderId", None, None, None],
        "row_count_estimate": [100000, 500000, 10000, 5000, 100],
    })
    df.write_parquet(catalog_dir / "metadata.parquet")

    scan_info = {"last_updated": "2026-01-26T10:00:00"}
    (catalog_dir / "last_scan.json").write_text(json.dumps(scan_info))

    return catalog_dir


@pytest.fixture
def empty_catalog(tmp_path) -> Path:
    """Catalog with no searchable matches."""
    catalog_dir = tmp_path / ".ds_catalog"
    catalog_dir.mkdir()

    df = pl.DataFrame({
        "target": ["test"],
        "server": ["test-server"],
        "database": ["Internal"],
        "schema": ["sys"],
        "table_name": ["Configuration"],
        "column_name": ["SettingId"],
        "data_type": ["int"],
        "is_nullable": [False],
        "is_primary_key": [True],
        "is_foreign_key": [False],
        "fk_references": [None],
        "row_count_estimate": [10],
    })
    df.write_parquet(catalog_dir / "metadata.parquet")

    return catalog_dir


@pytest.fixture
def stale_catalog(tmp_path) -> Path:
    """Catalog older than 7 days."""
    catalog_dir = tmp_path / ".ds_catalog"
    catalog_dir.mkdir()

    df = pl.DataFrame({
        "target": ["test"],
        "server": ["test-server"],
        "database": ["DB"],
        "schema": ["dbo"],
        "table_name": ["T"],
        "column_name": ["c"],
        "data_type": ["int"],
        "is_nullable": [False],
        "is_primary_key": [False],
        "is_foreign_key": [False],
        "fk_references": [None],
        "row_count_estimate": [100],
    })
    df.write_parquet(catalog_dir / "metadata.parquet")

    scan_info = {"last_updated": "2026-01-01T10:00:00"}  # 26 days ago
    (catalog_dir / "last_scan.json").write_text(json.dumps(scan_info))

    return catalog_dir


@pytest.fixture
def missing_catalog(tmp_path) -> Path:
    """Empty directory with no catalog."""
    catalog_dir = tmp_path / ".ds_catalog"
    catalog_dir.mkdir()
    return catalog_dir
```

**Acceptance Criteria:**
- [ ] `.mcp.json` exists and is valid JSON
- [ ] `uv run pytest --collect-only` finds test files
- [ ] Fixtures create valid parquet files with consistent columns

---

### Phase 2: Tests (RED) + Implementation (GREEN)

Write tests and implementation together in single file.

#### servers/catalog_mcp/test_catalog_tools.py

```python
"""Tests for all catalog MCP tools."""
import pytest


class TestSearchCatalog:
    """Test search_catalog tool."""

    def test_search_returns_matching_tables(self, happy_catalog, monkeypatch):
        """Search for 'order' should return Order and OrderItem tables."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from server import search_catalog

        result = search_catalog(keywords=["order"], top_n=10)

        assert result["count"] >= 2
        table_names = [m["table_name"] for m in result["matches"]]
        assert "Order" in table_names
        assert "OrderItem" in table_names

    def test_search_includes_schema_column(self, happy_catalog, monkeypatch):
        """Search results should include schema column."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from server import search_catalog

        result = search_catalog(keywords=["order"], top_n=10)

        assert result["count"] > 0
        assert "schema" in result["matches"][0]

    def test_search_returns_empty_for_no_matches(self, empty_catalog, monkeypatch):
        """Search for non-existent term returns empty results."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(empty_catalog))
        from server import search_catalog

        result = search_catalog(keywords=["xyz123nonexistent"], top_n=10)

        assert result["count"] == 0
        assert result["matches"] == []

    def test_search_respects_top_n_limit(self, happy_catalog, monkeypatch):
        """Search should not return more than top_n results."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from server import search_catalog

        result = search_catalog(keywords=[""], top_n=2)

        assert len(result["matches"]) <= 2

    def test_search_raises_for_missing_catalog(self, missing_catalog, monkeypatch):
        """Search should raise FileNotFoundError if catalog missing."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(missing_catalog))
        from server import search_catalog

        with pytest.raises(FileNotFoundError):
            search_catalog(keywords=["order"], top_n=10)


class TestGetTableDetails:
    """Test get_table_details tool."""

    def test_returns_table_info(self, happy_catalog, monkeypatch):
        """Should return table info and columns."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from server import get_table_details

        result = get_table_details(database="Orders", schema="dbo", table_name="Order")

        assert result["table"]["table_name"] == "Order"
        assert len(result["columns"]) > 0

    def test_returns_error_for_missing_table(self, happy_catalog, monkeypatch):
        """Should return error for non-existent table."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from server import get_table_details

        result = get_table_details(database="Orders", schema="dbo", table_name="NonExistent")

        assert "error" in result


class TestFindJoinPaths:
    """Test find_join_paths tool."""

    def test_finds_outbound_fks(self, happy_catalog, monkeypatch):
        """OrderItem has FK to Order."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from server import find_join_paths

        result = find_join_paths(table_name="OrderItem")

        assert len(result["outbound"]) > 0
        assert any("Order" in str(fk) for fk in result["outbound"])

    def test_finds_inbound_fks(self, happy_catalog, monkeypatch):
        """Order has inbound FK from OrderItem."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from server import find_join_paths

        result = find_join_paths(table_name="Order")

        assert len(result["inbound"]) > 0


class TestGetCatalogStatus:
    """Test get_catalog_status tool."""

    def test_status_ok_for_fresh_catalog(self, happy_catalog, monkeypatch):
        """Fresh catalog (<7 days) should return OK status."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from server import get_catalog_status

        result = get_catalog_status()

        assert result["status"] == "OK"
        assert result["age_days"] < 7

    def test_status_stale_for_old_catalog(self, stale_catalog, monkeypatch):
        """Old catalog (>7 days) should return STALE status."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(stale_catalog))
        from server import get_catalog_status

        result = get_catalog_status()

        assert result["status"] == "STALE"
        assert result["age_days"] > 7

    def test_status_not_built_for_missing_catalog(self, missing_catalog, monkeypatch):
        """Missing catalog should return NOT_BUILT status."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(missing_catalog))
        from server import get_catalog_status

        result = get_catalog_status()

        assert result["status"] == "NOT_BUILT"

    def test_status_includes_statistics(self, happy_catalog, monkeypatch):
        """Status should include catalog statistics."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from server import get_catalog_status

        result = get_catalog_status()

        assert "stats" in result
        assert "tables" in result["stats"]
        assert "columns" in result["stats"]
```

**Acceptance Criteria:**
- [ ] All tests fail initially (RED)
- [ ] Tests cover all 4 tools
- [ ] Tests include `schema` column validation

---

### Phase 3: MCP Server Implementation (GREEN)

#### servers/catalog_mcp/server.py

```python
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


def get_catalog_dir() -> Path:
    """Get catalog directory with late binding for testability."""
    return Path(os.environ.get("DENG_CATALOG_DIR", str(Path.home() / ".ds_catalog")))


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
        table_match = table_match + pl.col("table_name").str.to_lowercase().str.contains(kw).cast(pl.Int32) * 3
        column_match = column_match + pl.col("column_name").str.to_lowercase().str.contains(kw).cast(pl.Int32) * 2
        db_match = db_match + pl.col("database").str.to_lowercase().str.contains(kw).cast(pl.Int32) * 1

    df_scored = df.with_columns([
        (table_match + column_match + db_match).alias("keyword_score"),
        (pl.col("is_primary_key").cast(pl.Int32) * 2).alias("pk_bonus"),
        (pl.col("is_foreign_key").cast(pl.Int32) * 1).alias("fk_bonus"),
    ]).with_columns([
        (pl.col("keyword_score") + pl.col("pk_bonus") + pl.col("fk_bonus")).alias("relevance"),
    ])

    results = (
        df_scored.filter(pl.col("keyword_score") > 0)
        .sort(["relevance", "row_count_estimate"], descending=[True, True])
        .head(top_n)
        .select(["database", "schema", "table_name", "column_name", "data_type",
                 "is_primary_key", "is_foreign_key", "fk_references",
                 "row_count_estimate", "relevance"])
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
        (pl.col("database") == database) &
        (pl.col("schema") == schema) &
        (pl.col("table_name") == table_name)
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
            (pl.col("table_name") == table_name) &
            (pl.col("is_foreign_key") == True)
        )
        .select(["column_name", "fk_references"])
        .to_dicts()
    )

    # Inbound: FKs from other tables to this one
    inbound = (
        df.filter(
            pl.col("fk_references").str.contains(f"{table_name}\\.")
        )
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
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch tool calls to handlers."""
    handlers = {
        "search_catalog": search_catalog,
        "get_table_details": get_table_details,
        "find_join_paths": find_join_paths,
        "get_catalog_status": get_catalog_status,
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
```

**Acceptance Criteria:**
- [ ] All unit tests pass (GREEN)
- [ ] 4 tools implemented in single file
- [ ] Late binding for `CATALOG_DIR` (testable)
- [ ] `schema` column included in search results

---

## Acceptance Criteria Summary

### Configuration
- [ ] `.mcp.json` exists and is valid JSON
- [ ] Claude Code discovers the MCP server
- [ ] MCP tools appear in tool list

### Tests
- [ ] `conftest.py` with fixtures collocated in `servers/catalog_mcp/`
- [ ] `test_catalog_tools.py` covers all 4 tools
- [ ] Tests cover: happy path, empty results, errors
- [ ] `uv run pytest` passes

### MCP Server
- [ ] `servers/catalog_mcp/server.py` implements all 4 tools
- [ ] Late binding for `CATALOG_DIR` (testable with monkeypatch)
- [ ] `schema` column included in search results
- [ ] Server starts with `python -m server`

---

## Task Checklist

### Phase 1: Configuration & Test Setup
- [ ] Create `.mcp.json` (P1 - critical)
- [ ] Create `servers/catalog_mcp/` directory
- [ ] Create `servers/catalog_mcp/__init__.py`
- [ ] Create `servers/catalog_mcp/pyproject.toml`
- [ ] Create `servers/catalog_mcp/conftest.py`
- [ ] Verify `uv run pytest --collect-only` works

### Phase 2: Tests (RED)
- [ ] Create `servers/catalog_mcp/test_catalog_tools.py`
- [ ] Verify all tests fail (imports not found)

### Phase 3: Implementation (GREEN)
- [ ] Create `servers/catalog_mcp/server.py` with all 4 tools
- [ ] Verify all tests pass

### Phase 4: Verification
- [ ] Run `uv run pytest` - all tests green
- [ ] Test MCP server manually: `python -m server`
- [ ] Verify plugin loads in Claude Code

---

## References

- Existing logic: `scripts/catalog_query.py`
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Code review findings: `todos/001-pending-p1-missing-mcp-json.md`
