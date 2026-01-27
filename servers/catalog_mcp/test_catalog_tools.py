"""Tests for all catalog MCP tools."""
import pytest


class TestSearchCatalog:
    """Test search_catalog tool."""

    def test_search_returns_matching_tables(self, happy_catalog, monkeypatch):
        """Search for 'order' should return Order and OrderItem tables."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from .server import search_catalog

        result = search_catalog(keywords=["order"], top_n=10)

        assert result["count"] >= 2
        table_names = [m["table_name"] for m in result["matches"]]
        assert "Order" in table_names
        assert "OrderItem" in table_names

    def test_search_includes_schema_column(self, happy_catalog, monkeypatch):
        """Search results should include schema column."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from .server import search_catalog

        result = search_catalog(keywords=["order"], top_n=10)

        assert result["count"] > 0
        assert "schema" in result["matches"][0]

    def test_search_returns_empty_for_no_matches(self, empty_catalog, monkeypatch):
        """Search for non-existent term returns empty results."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(empty_catalog))
        from .server import search_catalog

        result = search_catalog(keywords=["xyz123nonexistent"], top_n=10)

        assert result["count"] == 0
        assert result["matches"] == []

    def test_search_respects_top_n_limit(self, happy_catalog, monkeypatch):
        """Search should not return more than top_n results."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from .server import search_catalog

        result = search_catalog(keywords=[""], top_n=2)

        assert len(result["matches"]) <= 2

    def test_search_raises_for_missing_catalog(self, missing_catalog, monkeypatch):
        """Search should raise FileNotFoundError if catalog missing."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(missing_catalog))
        from .server import search_catalog

        with pytest.raises(FileNotFoundError):
            search_catalog(keywords=["order"], top_n=10)


class TestGetTableDetails:
    """Test get_table_details tool."""

    def test_returns_table_info(self, happy_catalog, monkeypatch):
        """Should return table info and columns."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from .server import get_table_details

        result = get_table_details(database="Orders", schema="dbo", table_name="Order")

        assert result["table"]["table_name"] == "Order"
        assert len(result["columns"]) > 0

    def test_returns_error_for_missing_table(self, happy_catalog, monkeypatch):
        """Should return error for non-existent table."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from .server import get_table_details

        result = get_table_details(database="Orders", schema="dbo", table_name="NonExistent")

        assert "error" in result


class TestFindJoinPaths:
    """Test find_join_paths tool."""

    def test_finds_outbound_fks(self, happy_catalog, monkeypatch):
        """OrderItem has FK to Order."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from .server import find_join_paths

        result = find_join_paths(table_name="OrderItem")

        assert len(result["outbound"]) > 0
        assert any("Order" in str(fk) for fk in result["outbound"])

    def test_finds_inbound_fks(self, happy_catalog, monkeypatch):
        """Order has inbound FK from OrderItem."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from .server import find_join_paths

        result = find_join_paths(table_name="Order")

        assert len(result["inbound"]) > 0


class TestGetCatalogStatus:
    """Test get_catalog_status tool."""

    def test_status_ok_for_fresh_catalog(self, happy_catalog, monkeypatch):
        """Fresh catalog (<7 days) should return OK status."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from .server import get_catalog_status

        result = get_catalog_status()

        assert result["status"] == "OK"
        assert result["age_days"] < 7

    def test_status_stale_for_old_catalog(self, stale_catalog, monkeypatch):
        """Old catalog (>7 days) should return STALE status."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(stale_catalog))
        from .server import get_catalog_status

        result = get_catalog_status()

        assert result["status"] == "STALE"
        assert result["age_days"] > 7

    def test_status_not_built_for_missing_catalog(self, missing_catalog, monkeypatch):
        """Missing catalog should return NOT_BUILT status."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(missing_catalog))
        from .server import get_catalog_status

        result = get_catalog_status()

        assert result["status"] == "NOT_BUILT"

    def test_status_includes_statistics(self, happy_catalog, monkeypatch):
        """Status should include catalog statistics."""
        monkeypatch.setenv("DENG_CATALOG_DIR", str(happy_catalog))
        from .server import get_catalog_status

        result = get_catalog_status()

        assert "stats" in result
        assert "tables" in result["stats"]
        assert "columns" in result["stats"]
