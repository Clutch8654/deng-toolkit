---
title: Refactor Catalog and Toolkit Separation
type: refactor
date: 2026-01-28
---

# Refactor: Catalog and Toolkit Separation

## Overview

Implement the two-repository architecture from the brainstorm: separate **data-catalog** repo from **deng-toolkit** plugin, with the toolkit referencing the catalog via `config.yaml`.

## Problem Statement

Currently:
- Catalog files are embedded in `~/.deng-toolkit/catalog/` and `~/.deng-toolkit/data_catalog/`
- Path defaults are inconsistent (Python: `~/.ds_catalog`, Shell: `~/.deng-toolkit/catalog`)
- `config.yaml` template exists but no scripts read it
- No way to configure catalog remote URL
- setup.sh hardcodes catalog location

## Proposed Solution

1. Create `~/.deng-toolkit/config.yaml` with catalog_dir and catalog_remote
2. Add shared config loading function for Python scripts
3. Update all scripts to read catalog path from config
4. Update setup.sh to prompt for catalog location/remote
5. Update catalog_sync.sh to use config
6. Migrate existing catalog files to new location

## Technical Approach

### Phase 1: Config Infrastructure

**Create config loading module:**

```python
# scripts/config.py
import yaml
from pathlib import Path

def load_config() -> dict:
    """Load config from ~/.deng-toolkit/config.yaml with defaults."""
    config_path = Path.home() / ".deng-toolkit" / "config.yaml"
    defaults = {
        "catalog_dir": str(Path.home() / "data-catalog"),
        "catalog_remote": "",
    }

    if config_path.exists():
        with open(config_path) as f:
            user_config = yaml.safe_load(f) or {}
        defaults.update(user_config)

    # Expand ~ in paths
    defaults["catalog_dir"] = str(Path(defaults["catalog_dir"]).expanduser())
    return defaults

def get_catalog_dir() -> Path:
    """Get catalog directory from config."""
    config = load_config()
    return Path(config["catalog_dir"])
```

**Files to create:**
- [x] `~/.deng-toolkit/scripts/config.py`

### Phase 2: Update Python Scripts

Replace hardcoded paths with config loading.

**Before:**
```python
CATALOG_DIR = Path(os.environ.get("DENG_CATALOG_DIR", str(Path.home() / ".ds_catalog")))
```

**After:**
```python
from config import get_catalog_dir
CATALOG_DIR = Path(os.environ.get("DENG_CATALOG_DIR")) if os.environ.get("DENG_CATALOG_DIR") else get_catalog_dir()
```

**Files to update:**
- [x] `scripts/catalog_refresh.py`
- [x] `scripts/catalog_query.py`
- [x] `scripts/build_ontology.py`
- [x] `scripts/analyze_procedures.py`
- [x] `scripts/catalog_snapshot.py`
- [x] `scripts/generate_review_excel.py`
- [x] `scripts/apply_review_feedback.py`
- [x] `servers/catalog_mcp/server.py`

### Phase 3: Update Shell Scripts

**catalog_sync.sh:**

```bash
#!/bin/bash
# Read config.yaml for catalog_dir and catalog_remote

CONFIG_FILE="$HOME/.deng-toolkit/config.yaml"

if [[ -f "$CONFIG_FILE" ]]; then
    CATALOG_DIR=$(grep "^catalog_dir:" "$CONFIG_FILE" | sed 's/catalog_dir: *//' | sed "s|~|$HOME|")
    CATALOG_REMOTE=$(grep "^catalog_remote:" "$CONFIG_FILE" | sed 's/catalog_remote: *//')
fi

CATALOG_DIR="${CATALOG_DIR:-$HOME/data-catalog}"
```

**Files to update:**
- [x] `scripts/catalog_sync.sh`
- [x] `ds-workflow-plugin/project/hooks/sync_catalog.sh`
- [x] `hooks/scripts/catalog-updated.sh`

### Phase 4: Update setup.sh

Add interactive prompts for catalog configuration:

```bash
# Prompt for catalog location
echo ""
echo "Configure data catalog location:"
read -p "Catalog directory [~/data-catalog]: " CATALOG_DIR
CATALOG_DIR="${CATALOG_DIR:-$HOME/data-catalog}"

read -p "Catalog git remote URL (leave blank for local-only): " CATALOG_REMOTE

# Write config.yaml
cat > "$TOOLKIT_DIR/config.yaml" << EOF
# deng-toolkit configuration
catalog_dir: $CATALOG_DIR
catalog_remote: $CATALOG_REMOTE
EOF

# Clone or create catalog directory
if [[ -n "$CATALOG_REMOTE" ]] && [[ ! -d "$CATALOG_DIR" ]]; then
    echo "Cloning catalog from $CATALOG_REMOTE..."
    git clone "$CATALOG_REMOTE" "$CATALOG_DIR"
elif [[ ! -d "$CATALOG_DIR" ]]; then
    echo "Creating catalog directory at $CATALOG_DIR..."
    mkdir -p "$CATALOG_DIR"
    cd "$CATALOG_DIR"
    git init
fi
```

**Files to update:**
- [x] `setup.sh`

### Phase 5: Update Tests

Update test_catalog_sync.sh to work with new config-based paths:

```bash
# Create temporary config for testing
cat > "$TEST_DIR/.deng-toolkit/config.yaml" << EOF
catalog_dir: $TEST_DIR/data-catalog
catalog_remote: ""
EOF
```

**Files to update:**
- [x] `scripts/test_config.py` - New tests for config module
- [x] MCP tests pass (use env var override)

### Phase 6: Migration Script

Create script to migrate existing catalogs:

```bash
#!/bin/bash
# migrate_catalog.sh - Move catalog files to new location

OLD_LOCATIONS=(
    "$HOME/.deng-toolkit/catalog"
    "$HOME/.deng-toolkit/data_catalog"
    "$HOME/.ds_catalog"
)

NEW_LOCATION="$HOME/data-catalog"

# ... migration logic
```

**Files to create:**
- [x] `scripts/migrate_catalog.sh`

## Acceptance Criteria

### Functional Requirements

- [x] `config.yaml` created during setup with catalog_dir and catalog_remote
- [x] All Python scripts read catalog path from config (with env var override)
- [x] catalog_sync.sh reads catalog path from config
- [x] setup.sh prompts for catalog location and remote URL
- [x] Existing env var `DENG_CATALOG_DIR` still works as override

### Non-Functional Requirements

- [x] Backward compatible - existing setups continue to work
- [x] No secrets in config.yaml (env vars for credentials)
- [x] Config loading is testable (late binding pattern)

### Quality Gates

- [x] All existing tests pass (13 MCP tests + 7 config tests)
- [x] New tests for config loading
- [x] Documentation updated

## Success Metrics

- Team members can clone catalog separately from toolkit
- Catalog syncs to different GitHub than toolkit
- Config is readable by AI tooling

## Dependencies & Prerequisites

- PyYAML available (already in deps via `uv run --with pyyaml`)

## Risk Analysis & Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking existing setups | Env var override takes precedence |
| Missing config.yaml | Sensible defaults in code |
| Partial migration | Migration script validates state |

## Implementation Order

1. **scripts/config.py** - Config loading module
2. **setup.sh** - Add prompts (can test interactively)
3. **catalog_sync.sh** - Update to use config
4. **Python scripts** - Update all 8 files
5. **Tests** - Update test suite
6. **Migration script** - For existing users
7. **Documentation** - Update README

## Verification

1. Fresh install: `setup.sh` prompts for config, creates catalog
2. Existing install: `migrate_catalog.sh` moves files, updates config
3. `catalog_sync.sh --status` reads from config
4. `catalog_refresh.py` writes to configured location
5. All tests pass: `test_catalog_sync.sh`

## References

- Brainstorm: `docs/brainstorms/2026-01-28-catalog-toolkit-separation-brainstorm.md`
- Current config template: `config.yaml.template`
- Test suite: `scripts/test_catalog_sync.sh`
