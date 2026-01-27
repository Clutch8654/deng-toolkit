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
    finally:
        os.close(fd)
    try:
        os.replace(tmp_path, path)
    except Exception:
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
