"""Test fixtures for catalog MCP server."""
import json
from pathlib import Path

import polars as pl
import pytest


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
