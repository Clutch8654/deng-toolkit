---
title: "feat: Collaborative Catalog Annotations"
type: feat
date: 2026-01-27
status: ready
brainstorm: docs/brainstorms/2026-01-27-centralized-catalog-sync-brainstorm.md
---

# Collaborative Catalog Annotations

## Overview

Add **per-user annotation files** to the data catalog, enabling team collaboration without merge conflicts. Each user writes to their own JSON file; the MCP server merges all files at query time.

**Key changes:**
- Per-user annotation files (`annotations/{username}.json`)
- New MCP tools: `get_annotations()`, `add_annotation()`
- Query-time merge (no infrastructure required)

## Problem Statement

Current git-based catalog sync has two pain points:
1. **Sync friction** - Constant push/pull cycle is tedious, people forget
2. **Stale data** - Team members work with outdated catalogs without realizing

This impacts a **medium team (5-15 people)** who want **collaborative enrichment** (notes, quality flags, deprecation warnings) without merge conflicts.

## Proposed Solution

### Architecture

```
┌─────────────────────────────────────────────────────┐
│  Git Repository (~/.ds_catalog/)                    │
│  ├── metadata.parquet          (R/O, maintainers)  │
│  └── annotations/                                   │
│      ├── jensen.json           (user writes)       │
│      ├── alice.json            (user writes)       │
│      └── bob.json              (user writes)       │
└─────────────────────────────────────────────────────┘
              ▲
              │ git pull/push (user-initiated)
              │
    ┌─────────┴─────────────────────────────────────┐
    │ User's Machine                                 │
    │ ┌───────────────────────────────────────────┐ │
    │ │ MCP Server (servers/catalog_mcp/)         │ │
    │ │  - search_catalog()                       │ │
    │ │  - get_annotations()  reads ALL *.json    │ │
    │ │  - add_annotation()   writes user.json    │ │
    │ └───────────────────────────────────────────┘ │
    └───────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **File format** | Plain JSON | Simple, debuggable, no library dependencies |
| **Merge strategy** | Query-time | No infrastructure needed; merge N files on read |
| **Username detection** | `DENG_USERNAME` → `git config` → `$USER` | Explicit override, sensible defaults |
| **Target identifier** | `{database}.{schema}.{table}` | Matches parquet schema |

### Annotation Schema

```json
{
  "tables": {
    "Orders.dbo.Order": {
      "annotations": [
        {
          "id": "550e8400-e29b-41d4-a716-446655440000",
          "type": "note",
          "content": "Primary order table for churn analysis",
          "author": "jensen",
          "created_at": "2026-01-27T10:00:00Z"
        }
      ]
    }
  }
}
```

**Annotation types:**
- `note` - Freeform text (business context, usage tips)
- `quality_flag` - Enum: `TRUSTED`, `STALE`, `INCOMPLETE`, `EXPERIMENTAL`
- `deprecation` - Marks table as deprecated

## Acceptance Criteria

- [x] `get_annotations()` MCP tool returns merged annotation data from all user files
- [x] `add_annotation()` MCP tool writes to user-specific JSON file
- [x] Username resolved via `DENG_USERNAME` → `git config` → `$USER`
- [x] Input validation: target format, annotation type, content length
- [x] Atomic file writes (temp file + rename)
- [x] Tests covering CRUD, edge cases, error handling (30 tests)

## Implementation Tasks

### Task 1: Create annotation module

Create `servers/catalog_mcp/annotations.py` with core functions.

**Files:**
- `servers/catalog_mcp/annotations.py` (new)

```python
"""Annotation storage and retrieval for data catalog."""
import json
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Constants
VALID_ANNOTATION_TYPES = {"note", "quality_flag", "deprecation"}
QUALITY_FLAG_VALUES = {"TRUSTED", "STALE", "INCOMPLETE", "EXPERIMENTAL"}
MAX_CONTENT_LENGTH = 10_000


def get_catalog_dir() -> Path:
    """Get catalog directory from environment or default."""
    return Path(os.environ.get("DENG_CATALOG_DIR", Path.home() / ".ds_catalog"))


def get_username() -> str:
    """Get current username for annotation authorship.

    Priority: DENG_USERNAME env > git config user.name > USER env
    """
    # Check explicit override first
    if username := os.environ.get("DENG_USERNAME"):
        return _sanitize_username(username)

    # Try git config
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return _sanitize_username(result.stdout.strip())
    except (subprocess.SubprocessError, OSError):
        pass

    # Fall back to USER env
    return _sanitize_username(os.environ.get("USER", "anonymous"))


def _sanitize_username(name: str) -> str:
    """Sanitize username for safe file paths."""
    sanitized = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    return sanitized[:64] or "anonymous"


def get_user_annotation_path(username: str) -> Path:
    """Get path to user's annotation file."""
    return get_catalog_dir() / "annotations" / f"{username}.json"


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically using temp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(fd, content.encode())
        os.close(fd)
        os.replace(tmp_path, path)
    except Exception:
        os.close(fd)
        os.unlink(tmp_path)
        raise


def _load_json_file(path: Path) -> dict:
    """Load JSON file, returning empty structure if missing or corrupt."""
    if not path.exists():
        return {"tables": {}}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"tables": {}}


def get_annotations(target: str | None = None) -> dict:
    """Get all annotations, merging all user files at query time.

    Args:
        target: Optional filter by table (e.g., "Orders.dbo.Order")

    Returns:
        Dict with merged annotations from all users
    """
    annotations_dir = get_catalog_dir() / "annotations"
    if not annotations_dir.exists():
        return {"tables": {}}

    # Find all user JSON files
    user_files = list(annotations_dir.glob("*.json"))

    # Merge all files
    merged = {"tables": {}}
    seen_ids = set()

    for user_file in user_files:
        user_data = _load_json_file(user_file)
        for table_target, table_data in user_data.get("tables", {}).items():
            if table_target not in merged["tables"]:
                merged["tables"][table_target] = {"annotations": []}

            # Dedupe by annotation ID
            for annotation in table_data.get("annotations", []):
                if annotation.get("id") not in seen_ids:
                    merged["tables"][table_target]["annotations"].append(annotation)
                    seen_ids.add(annotation.get("id"))

    # Filter by target if specified
    if target:
        table_data = merged.get("tables", {}).get(target, {})
        return {
            "target": target,
            "annotations": table_data.get("annotations", []),
        }

    return merged


def add_annotation(target: str, annotation_type: str, content: str) -> dict:
    """Add annotation to user's file.

    Args:
        target: Table identifier (Database.Schema.Table)
        annotation_type: One of: note, quality_flag, deprecation
        content: Annotation content

    Returns:
        Dict with created annotation and file path

    Raises:
        ValueError: If inputs are invalid
    """
    # Validate target format
    if not target or target.count(".") != 2:
        raise ValueError(
            f"Invalid target format: {target}. Expected 'Database.Schema.Table'"
        )

    # Validate annotation type
    if annotation_type not in VALID_ANNOTATION_TYPES:
        raise ValueError(
            f"Invalid annotation type: {annotation_type}. "
            f"Valid types: {VALID_ANNOTATION_TYPES}"
        )

    # Validate quality flag content
    if annotation_type == "quality_flag" and content not in QUALITY_FLAG_VALUES:
        raise ValueError(
            f"Invalid quality flag: {content}. Valid values: {QUALITY_FLAG_VALUES}"
        )

    # Validate content length
    if len(content) > MAX_CONTENT_LENGTH:
        raise ValueError(f"Content exceeds {MAX_CONTENT_LENGTH} characters")

    username = get_username()
    user_path = get_user_annotation_path(username)

    # Load existing or create new
    data = _load_json_file(user_path)

    # Initialize table if needed
    if target not in data["tables"]:
        data["tables"][target] = {"annotations": []}

    # Create annotation
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    annotation = {
        "id": str(uuid.uuid4()),
        "type": annotation_type,
        "content": content,
        "author": username,
        "created_at": now,
    }

    data["tables"][target]["annotations"].append(annotation)

    # Atomic write
    _atomic_write(user_path, json.dumps(data, indent=2))

    return {"annotation": annotation, "file": str(user_path)}
```

### Task 2: Add MCP tool definitions

Register annotation tools in the MCP server.

**Files:**
- `servers/catalog_mcp/server.py` (modify)

Add to `list_tools()`:

```python
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
```

Add to `call_tool()` handlers:

```python
from .annotations import get_annotations, add_annotation

handlers = {
    # ... existing handlers ...
    "get_annotations": lambda args: get_annotations(args.get("target")),
    "add_annotation": lambda args: add_annotation(
        args["target"], args["type"], args["content"]
    ),
}
```

### Task 3: Add annotation tests

Comprehensive tests for annotation module.

**Files:**
- `servers/catalog_mcp/test_annotations.py` (new)

```python
"""Tests for annotation module."""
import json
import pytest
from pathlib import Path


class TestGetUsername:
    """Tests for username detection."""

    def test_uses_env_var_first(self, monkeypatch):
        monkeypatch.setenv("DENG_USERNAME", "testuser")
        from .annotations import get_username
        assert get_username() == "testuser"

    def test_sanitizes_path_traversal(self, monkeypatch):
        monkeypatch.setenv("DENG_USERNAME", "../etc/passwd")
        from .annotations import get_username
        result = get_username()
        assert ".." not in result
        assert "/" not in result

    def test_sanitizes_special_chars(self, monkeypatch):
        monkeypatch.setenv("DENG_USERNAME", "user@domain.com")
        from .annotations import get_username
        assert "@" not in get_username()
        assert "." not in get_username()

    def test_truncates_long_names(self, monkeypatch):
        monkeypatch.setenv("DENG_USERNAME", "a" * 100)
        from .annotations import get_username
        assert len(get_username()) <= 64

    def test_falls_back_to_user_env(self, monkeypatch):
        monkeypatch.delenv("DENG_USERNAME", raising=False)
        monkeypatch.setenv("USER", "fallback_user")
        # Mock git to fail
        monkeypatch.setattr("subprocess.run", lambda *a, **k: type("R", (), {"returncode": 1, "stdout": ""})())
        from .annotations import get_username
        assert get_username() == "fallback_user"


class TestGetAnnotations:
    """Tests for reading annotations."""

    def test_returns_empty_when_no_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        from .annotations import get_annotations
        result = get_annotations()
        assert result == {"tables": {}}

    def test_merges_multiple_user_files(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        annotations_dir = tmp_path / "annotations"
        annotations_dir.mkdir()

        # Create two user files
        (annotations_dir / "alice.json").write_text(json.dumps({
            "tables": {"Orders.dbo.Order": {"annotations": [
                {"id": "1", "content": "Alice's note", "author": "alice"}
            ]}}
        }))
        (annotations_dir / "bob.json").write_text(json.dumps({
            "tables": {"Orders.dbo.Order": {"annotations": [
                {"id": "2", "content": "Bob's note", "author": "bob"}
            ]}}
        }))

        from .annotations import get_annotations
        result = get_annotations()

        annotations = result["tables"]["Orders.dbo.Order"]["annotations"]
        assert len(annotations) == 2
        authors = {a["author"] for a in annotations}
        assert authors == {"alice", "bob"}

    def test_deduplicates_by_id(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        annotations_dir = tmp_path / "annotations"
        annotations_dir.mkdir()

        # Same annotation ID in two files (shouldn't happen, but handle it)
        for user in ["alice", "bob"]:
            (annotations_dir / f"{user}.json").write_text(json.dumps({
                "tables": {"Orders.dbo.Order": {"annotations": [
                    {"id": "same-id", "content": f"{user}'s note"}
                ]}}
            }))

        from .annotations import get_annotations
        result = get_annotations()
        assert len(result["tables"]["Orders.dbo.Order"]["annotations"]) == 1

    def test_filters_by_target(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        annotations_dir = tmp_path / "annotations"
        annotations_dir.mkdir()

        (annotations_dir / "alice.json").write_text(json.dumps({
            "tables": {
                "Orders.dbo.Order": {"annotations": [{"id": "1", "content": "Order note"}]},
                "Orders.dbo.Customer": {"annotations": [{"id": "2", "content": "Customer note"}]},
            }
        }))

        from .annotations import get_annotations
        result = get_annotations(target="Orders.dbo.Order")

        assert result["target"] == "Orders.dbo.Order"
        assert len(result["annotations"]) == 1
        assert result["annotations"][0]["content"] == "Order note"

    def test_handles_corrupt_json(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        annotations_dir = tmp_path / "annotations"
        annotations_dir.mkdir()
        (annotations_dir / "corrupt.json").write_text("not valid json{{{")

        from .annotations import get_annotations
        result = get_annotations()  # Should not raise
        assert result == {"tables": {}}


class TestAddAnnotation:
    """Tests for adding annotations."""

    def test_creates_user_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        monkeypatch.setenv("DENG_USERNAME", "testuser")

        from .annotations import add_annotation
        result = add_annotation("Orders.dbo.Order", "note", "Test annotation")

        assert result["annotation"]["content"] == "Test annotation"
        assert result["annotation"]["author"] == "testuser"
        assert result["annotation"]["type"] == "note"
        assert "id" in result["annotation"]
        assert (tmp_path / "annotations" / "testuser.json").exists()

    def test_appends_to_existing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        monkeypatch.setenv("DENG_USERNAME", "testuser")

        from .annotations import add_annotation, get_user_annotation_path, _load_json_file
        add_annotation("Orders.dbo.Order", "note", "First")
        add_annotation("Orders.dbo.Order", "note", "Second")

        data = _load_json_file(get_user_annotation_path("testuser"))
        assert len(data["tables"]["Orders.dbo.Order"]["annotations"]) == 2

    def test_rejects_invalid_target_format(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        monkeypatch.setenv("DENG_USERNAME", "testuser")

        from .annotations import add_annotation
        with pytest.raises(ValueError, match="Invalid target format"):
            add_annotation("InvalidTarget", "note", "Test")

    def test_rejects_invalid_type(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        monkeypatch.setenv("DENG_USERNAME", "testuser")

        from .annotations import add_annotation
        with pytest.raises(ValueError, match="Invalid annotation type"):
            add_annotation("Orders.dbo.Order", "invalid_type", "Test")

    def test_validates_quality_flag_values(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        monkeypatch.setenv("DENG_USERNAME", "testuser")

        from .annotations import add_annotation

        # Valid quality flag
        result = add_annotation("Orders.dbo.Order", "quality_flag", "TRUSTED")
        assert result["annotation"]["content"] == "TRUSTED"

        # Invalid quality flag
        with pytest.raises(ValueError, match="Invalid quality flag"):
            add_annotation("Orders.dbo.Order", "quality_flag", "INVALID")

    def test_rejects_oversized_content(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DENG_CATALOG_DIR", str(tmp_path))
        monkeypatch.setenv("DENG_USERNAME", "testuser")

        from .annotations import add_annotation, MAX_CONTENT_LENGTH
        with pytest.raises(ValueError, match="exceeds"):
            add_annotation("Orders.dbo.Order", "note", "x" * (MAX_CONTENT_LENGTH + 1))
```

### Task 4: Update sync command

Update the sync command to include annotation files.

**Files:**
- `commands/deng-catalog-sync.md` (modify)

```markdown
---
name: deng-catalog-sync
description: Sync catalog and annotations with team git repository
arguments: "[--push]"
---

# Catalog Sync

Synchronizes catalog and annotations with your team via git.

## Usage

```
/deng-catalog-sync [--push]
```

**Options:**
- `--push` - Push your annotation changes after pulling

## Process

### Step 1: Pull Latest

```bash
cd ~/.ds_catalog && git pull --rebase
```

This gets:
- Latest `metadata.parquet` from maintainers
- All team members' annotation files

### Step 2: Push (if --push flag)

```bash
cd ~/.ds_catalog && git add annotations/*.json && git commit -m "Annotation update" && git push
```

## What Gets Synced

| File | Direction | Notes |
|------|-----------|-------|
| `metadata.parquet` | Pull only | Maintainers push, users pull |
| `annotations/*.json` | Both | Per-user files, no conflicts |

## User Workflow

```bash
# 1. Get team's latest annotations
/deng-catalog-sync

# 2. Add your annotations via MCP tools
# (automatically writes to annotations/{your-username}.json)

# 3. Share your annotations with the team
/deng-catalog-sync --push
```
```

## Success Metrics

| Metric | Target |
|--------|--------|
| Sync friction | Reduced to single command |
| Merge conflicts | Zero (per-user files) |
| New dependencies | Zero |
| Test coverage | >90% on annotation module |

## Future Enhancements (Deferred)

These features can be added later if needed:

- **Search integration** - Show annotations in `/deng-find-data` results
- **Staleness detection** - Warn when annotations are old
- **GitHub Action merge** - Pre-merge for faster reads (if query-time becomes slow)
- **CHANGELOG generation** - Auto-generate activity log

## References

- Brainstorm: `docs/brainstorms/2026-01-27-centralized-catalog-sync-brainstorm.md`
- Existing MCP server: `servers/catalog_mcp/server.py`
