"""Configuration loading for deng-toolkit.

Reads config from ~/.deng-toolkit/config.yaml with sensible defaults.
Environment variables take precedence over config file values.
"""

import os
from pathlib import Path
from typing import Optional

# Lazy import to avoid dependency issues if PyYAML not installed
_yaml = None


def _get_yaml():
    """Lazy load PyYAML."""
    global _yaml
    if _yaml is None:
        import yaml

        _yaml = yaml
    return _yaml


def load_config() -> dict:
    """Load config from ~/.deng-toolkit/config.yaml with defaults.

    Returns:
        dict with keys: catalog_dir, catalog_remote
    """
    config_path = Path.home() / ".deng-toolkit" / "config.yaml"

    defaults = {
        "catalog_dir": str(Path.home() / "data-catalog"),
        "catalog_remote": "",
    }

    if config_path.exists():
        try:
            yaml = _get_yaml()
            with open(config_path) as f:
                user_config = yaml.safe_load(f) or {}
            defaults.update(user_config)
        except Exception:
            # If YAML loading fails, use defaults
            pass

    # Expand ~ in paths
    if "catalog_dir" in defaults:
        defaults["catalog_dir"] = str(Path(defaults["catalog_dir"]).expanduser())

    return defaults


def get_catalog_dir() -> Path:
    """Get catalog directory from config.

    Environment variable DENG_CATALOG_DIR takes precedence.

    Returns:
        Path to catalog directory
    """
    # Environment variable takes precedence
    env_val = os.environ.get("DENG_CATALOG_DIR")
    if env_val:
        return Path(env_val).expanduser()

    config = load_config()
    return Path(config["catalog_dir"])


def get_catalog_remote() -> Optional[str]:
    """Get catalog git remote URL from config.

    Returns:
        Remote URL string or None if not configured
    """
    config = load_config()
    remote = config.get("catalog_remote", "")
    return remote if remote else None
