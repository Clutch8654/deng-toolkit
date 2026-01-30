"""Tests for annotation module."""
import json
import subprocess

import pytest

from .annotations import (
    MAX_CONTENT_LENGTH,
    _load_json_file,
    _sanitize_username,
    add_annotation,
    get_annotations,
    get_user_annotation_path,
    get_username,
)


class TestSanitizeUsername:
    """Tests for username sanitization."""

    def test_allows_alphanumeric(self):
        assert _sanitize_username("alice123") == "alice123"

    def test_allows_dash_underscore(self):
        assert _sanitize_username("alice-bob_123") == "alice-bob_123"

    def test_replaces_special_chars(self):
        result = _sanitize_username("user@domain.com")
        assert "@" not in result
        assert "." not in result
        assert result == "user_domain_com"

    def test_replaces_path_traversal(self):
        result = _sanitize_username("../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_truncates_long_names(self):
        result = _sanitize_username("a" * 100)
        assert len(result) == 64

    def test_returns_anonymous_for_empty(self):
        assert _sanitize_username("") == "anonymous"

    def test_converts_spaces_to_underscores(self):
        # Spaces become underscores (valid path characters)
        assert _sanitize_username("   ") == "___"
        assert _sanitize_username("john doe") == "john_doe"


class TestGetUsername:
    """Tests for username detection priority."""

    def test_uses_env_var_first(self, monkeypatch):
        monkeypatch.setenv("DENG_USERNAME", "testuser")
        assert get_username() == "testuser"

    def test_sanitizes_env_var(self, monkeypatch):
        monkeypatch.setenv("DENG_USERNAME", "test@user.com")
        result = get_username()
        assert "@" not in result
        assert "." not in result

    def test_falls_back_to_user_env(self, monkeypatch):
        monkeypatch.delenv("DENG_USERNAME", raising=False)
        monkeypatch.setenv("USER", "fallback_user")
        # Mock git to fail
        def mock_run(*args, **kwargs):
            return type("Result", (), {"returncode": 1, "stdout": ""})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        assert get_username() == "fallback_user"

    def test_returns_anonymous_when_nothing_available(self, monkeypatch):
        monkeypatch.delenv("DENG_USERNAME", raising=False)
        monkeypatch.delenv("USER", raising=False)

        def mock_run(*args, **kwargs):
            return type("Result", (), {"returncode": 1, "stdout": ""})()

        monkeypatch.setattr(subprocess, "run", mock_run)
        assert get_username() == "anonymous"


class TestLoadJsonFile:
    """Tests for JSON file loading."""

    def test_returns_empty_when_missing(self, tmp_path):
        result = _load_json_file(tmp_path / "nonexistent.json")
        assert result == {"tables": {}}

    def test_loads_valid_json(self, tmp_path):
        json_file = tmp_path / "test.json"
        json_file.write_text('{"tables": {"foo": "bar"}}')
        result = _load_json_file(json_file)
        assert result == {"tables": {"foo": "bar"}}

    def test_returns_empty_for_corrupt_json(self, tmp_path):
        json_file = tmp_path / "corrupt.json"
        json_file.write_text("not valid json{{{")
        result = _load_json_file(json_file)
        assert result == {"tables": {}}


class TestGetAnnotations:
    """Tests for reading and merging annotations."""

    def test_returns_empty_when_no_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        result = get_annotations()
        assert result == {"tables": {}}

    def test_returns_empty_when_dir_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        (tmp_path / "annotations").mkdir()
        result = get_annotations()
        assert result == {"tables": {}}

    def test_merges_multiple_user_files(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        annotations_dir = tmp_path / "annotations"
        annotations_dir.mkdir()

        # Create two user files with different annotations
        (annotations_dir / "alice.json").write_text(
            json.dumps(
                {
                    "tables": {
                        "Orders.dbo.Order": {
                            "annotations": [
                                {"id": "1", "content": "Alice's note", "author": "alice"}
                            ]
                        }
                    }
                }
            )
        )
        (annotations_dir / "bob.json").write_text(
            json.dumps(
                {
                    "tables": {
                        "Orders.dbo.Order": {
                            "annotations": [
                                {"id": "2", "content": "Bob's note", "author": "bob"}
                            ]
                        }
                    }
                }
            )
        )

        result = get_annotations()

        annotations = result["tables"]["Orders.dbo.Order"]["annotations"]
        assert len(annotations) == 2
        authors = {a["author"] for a in annotations}
        assert authors == {"alice", "bob"}

    def test_deduplicates_by_id(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        annotations_dir = tmp_path / "annotations"
        annotations_dir.mkdir()

        # Same annotation ID in two files (edge case)
        for user in ["alice", "bob"]:
            (annotations_dir / f"{user}.json").write_text(
                json.dumps(
                    {
                        "tables": {
                            "Orders.dbo.Order": {
                                "annotations": [
                                    {"id": "same-id", "content": f"{user}'s note"}
                                ]
                            }
                        }
                    }
                )
            )

        result = get_annotations()
        assert len(result["tables"]["Orders.dbo.Order"]["annotations"]) == 1

    def test_filters_by_target(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        annotations_dir = tmp_path / "annotations"
        annotations_dir.mkdir()

        (annotations_dir / "alice.json").write_text(
            json.dumps(
                {
                    "tables": {
                        "Orders.dbo.Order": {
                            "annotations": [{"id": "1", "content": "Order note"}]
                        },
                        "Orders.dbo.Customer": {
                            "annotations": [{"id": "2", "content": "Customer note"}]
                        },
                    }
                }
            )
        )

        result = get_annotations(target="Orders.dbo.Order")

        assert result["target"] == "Orders.dbo.Order"
        assert len(result["annotations"]) == 1
        assert result["annotations"][0]["content"] == "Order note"

    def test_returns_empty_for_unknown_target(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        annotations_dir = tmp_path / "annotations"
        annotations_dir.mkdir()

        result = get_annotations(target="Unknown.dbo.Table")
        assert result["target"] == "Unknown.dbo.Table"
        assert result["annotations"] == []

    def test_handles_corrupt_files_gracefully(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        annotations_dir = tmp_path / "annotations"
        annotations_dir.mkdir()

        # One corrupt, one valid
        (annotations_dir / "corrupt.json").write_text("not valid json{{{")
        (annotations_dir / "valid.json").write_text(
            json.dumps(
                {
                    "tables": {
                        "Orders.dbo.Order": {
                            "annotations": [{"id": "1", "content": "Valid note"}]
                        }
                    }
                }
            )
        )

        result = get_annotations()
        assert len(result["tables"]["Orders.dbo.Order"]["annotations"]) == 1


class TestAddAnnotation:
    """Tests for adding annotations."""

    def test_creates_user_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        monkeypatch.setenv("DENG_USERNAME", "testuser")

        result = add_annotation("Orders.dbo.Order", "note", "Test annotation")

        assert result["annotation"]["content"] == "Test annotation"
        assert result["annotation"]["author"] == "testuser"
        assert result["annotation"]["type"] == "note"
        assert "id" in result["annotation"]
        assert "created_at" in result["annotation"]
        assert (tmp_path / "annotations" / "testuser.json").exists()

    def test_appends_to_existing_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        monkeypatch.setenv("DENG_USERNAME", "testuser")

        add_annotation("Orders.dbo.Order", "note", "First")
        add_annotation("Orders.dbo.Order", "note", "Second")

        data = _load_json_file(get_user_annotation_path("testuser"))
        assert len(data["tables"]["Orders.dbo.Order"]["annotations"]) == 2

    def test_creates_annotations_directory(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        monkeypatch.setenv("DENG_USERNAME", "testuser")

        # Directory doesn't exist yet
        assert not (tmp_path / "annotations").exists()

        add_annotation("Orders.dbo.Order", "note", "Test")

        assert (tmp_path / "annotations").exists()
        assert (tmp_path / "annotations" / "testuser.json").exists()

    def test_rejects_invalid_target_format(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        monkeypatch.setenv("DENG_USERNAME", "testuser")

        with pytest.raises(ValueError, match="Invalid target format"):
            add_annotation("InvalidTarget", "note", "Test")

        with pytest.raises(ValueError, match="Invalid target format"):
            add_annotation("Only.OneDot", "note", "Test")

        with pytest.raises(ValueError, match="Invalid target format"):
            add_annotation("Too.Many.Dots.Here", "note", "Test")

    def test_rejects_invalid_annotation_type(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        monkeypatch.setenv("DENG_USERNAME", "testuser")

        with pytest.raises(ValueError, match="Invalid annotation type"):
            add_annotation("Orders.dbo.Order", "invalid_type", "Test")

    def test_validates_quality_flag_values(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        monkeypatch.setenv("DENG_USERNAME", "testuser")

        # Valid quality flags
        for flag in ["TRUSTED", "STALE", "INCOMPLETE", "EXPERIMENTAL"]:
            result = add_annotation(f"Orders.dbo.Table{flag}", "quality_flag", flag)
            assert result["annotation"]["content"] == flag

        # Invalid quality flag
        with pytest.raises(ValueError, match="Invalid quality flag"):
            add_annotation("Orders.dbo.Order", "quality_flag", "INVALID")

    def test_rejects_oversized_content(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        monkeypatch.setenv("DENG_USERNAME", "testuser")

        with pytest.raises(ValueError, match="exceeds"):
            add_annotation("Orders.dbo.Order", "note", "x" * (MAX_CONTENT_LENGTH + 1))

    def test_generates_unique_ids(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        monkeypatch.setenv("DENG_USERNAME", "testuser")

        result1 = add_annotation("Orders.dbo.Order", "note", "First")
        result2 = add_annotation("Orders.dbo.Order", "note", "Second")

        assert result1["annotation"]["id"] != result2["annotation"]["id"]

    def test_supports_deprecation_type(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        monkeypatch.setenv("DENG_USERNAME", "testuser")

        result = add_annotation(
            "Orders.dbo.OldTable", "deprecation", "Use NewTable instead"
        )
        assert result["annotation"]["type"] == "deprecation"
        assert result["annotation"]["content"] == "Use NewTable instead"
