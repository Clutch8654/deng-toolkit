#!/bin/bash
# catalog_sync.sh - Sync data catalog to git repository
#
# Usage: catalog_sync.sh [--push|--pull|--init|--full|--status]
#
# Configuration:
#   Reads from ~/.deng-toolkit/config.yaml:
#     catalog_dir: ~/data-catalog     # Where the catalog lives
#     catalog_remote: git@...         # Git remote URL
#
#   Override with DENG_CATALOG_DIR environment variable.

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err() { echo -e "${RED}[✗]${NC} $1"; }

# Configuration - read from config.yaml with env var override
CONFIG_FILE="$HOME/.deng-toolkit/config.yaml"

if [[ -f "$CONFIG_FILE" ]]; then
    CATALOG_DIR_CONFIG=$(grep "^catalog_dir:" "$CONFIG_FILE" 2>/dev/null | sed 's/catalog_dir: *//' | sed "s|~|$HOME|" | tr -d '"' | tr -d "'")
    CATALOG_REMOTE_CONFIG=$(grep "^catalog_remote:" "$CONFIG_FILE" 2>/dev/null | sed 's/catalog_remote: *//' | tr -d '"' | tr -d "'")
fi

# Environment variable takes precedence, then config, then default
CATALOG_DIR="${DENG_CATALOG_DIR:-${CATALOG_DIR_CONFIG:-$HOME/data-catalog}}"
CATALOG_REMOTE="${CATALOG_REMOTE_CONFIG:-}"

# Validate path is within expected location (security check)
validate_path() {
    local path="$1"
    local resolved
    resolved=$(cd "$path" 2>/dev/null && pwd) || return 1

    # Allow paths under HOME or /tmp (for testing)
    if [[ "$resolved" == "$HOME"* ]] || [[ "$resolved" == "/tmp"* ]]; then
        return 0
    fi

    err "Catalog path must be under \$HOME or /tmp: $resolved"
    return 1
}

# Functions
check_repo() {
    if [[ ! -d "$CATALOG_DIR/.git" ]]; then
        err "Catalog repo not found at $CATALOG_DIR"
        echo ""
        echo "Initialize with: catalog_sync.sh --init"
        echo "Or clone existing: git clone <repo-url> $CATALOG_DIR"
        exit 1
    fi
}

do_status() {
    echo ""
    echo "Catalog configuration:"
    echo "  Config file: $CONFIG_FILE"
    echo "  Catalog dir: $CATALOG_DIR"
    if [[ -n "$CATALOG_REMOTE" ]]; then
        echo "  Remote:      $CATALOG_REMOTE"
    else
        echo "  Remote:      (not configured)"
    fi
    echo ""

    if [[ ! -d "$CATALOG_DIR" ]]; then
        warn "Catalog directory does not exist"
        echo ""
        echo "Run 'catalog_sync.sh --init' to initialize"
        exit 0
    fi

    if [[ ! -d "$CATALOG_DIR/.git" ]]; then
        warn "Catalog is not a git repository"
        echo ""
        echo "Run 'catalog_sync.sh --init' to initialize"
        exit 0
    fi

    cd "$CATALOG_DIR"

    if git diff --quiet && git diff --staged --quiet; then
        log "No uncommitted changes"
    else
        warn "Uncommitted changes:"
        git status --short
        echo ""
        echo "Run 'catalog_sync.sh --push' to commit and push"
    fi

    # Show remote status
    if git remote get-url origin &>/dev/null; then
        echo ""
        git fetch origin --quiet 2>/dev/null || true
        local behind ahead
        behind=$(git rev-list --count HEAD..origin/main 2>/dev/null || git rev-list --count HEAD..origin/master 2>/dev/null || echo "0")
        ahead=$(git rev-list --count origin/main..HEAD 2>/dev/null || git rev-list --count origin/master..HEAD 2>/dev/null || echo "0")

        if [[ "$behind" -gt 0 ]]; then
            warn "Behind remote by $behind commit(s) - run --pull"
        fi
        if [[ "$ahead" -gt 0 ]]; then
            warn "Ahead of remote by $ahead commit(s) - run --push"
        fi
        if [[ "$behind" -eq 0 ]] && [[ "$ahead" -eq 0 ]]; then
            log "Up to date with remote"
        fi
    fi
}

do_push() {
    check_repo
    validate_path "$CATALOG_DIR" || exit 1

    cd "$CATALOG_DIR"

    # Check for changes
    if git diff --quiet && git diff --staged --quiet; then
        log "No changes to commit"
        exit 0
    fi

    # Stage all changes
    git add -A

    # Show what changed
    echo ""
    echo "Changes to commit:"
    git diff --staged --stat
    echo ""

    # Create commit
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
    git commit -m "Catalog update: $TIMESTAMP"

    # Push to remote
    if git remote get-url origin &>/dev/null; then
        git push origin main 2>/dev/null || git push origin master 2>/dev/null || {
            warn "Could not push to remote. Push manually if needed."
        }
        log "Catalog synced and pushed"
    else
        warn "No remote configured. Changes committed locally."
        echo "Add remote: git remote add origin <repo-url>"
    fi
}

do_pull() {
    check_repo
    validate_path "$CATALOG_DIR" || exit 1

    cd "$CATALOG_DIR"

    # Pull from remote
    if git remote get-url origin &>/dev/null; then
        git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || {
            err "Could not pull from remote"
            exit 1
        }
        log "Catalog pulled and updated"
    else
        warn "No remote configured. Nothing to pull."
        exit 0
    fi
}

do_init() {
    if [[ -d "$CATALOG_DIR/.git" ]]; then
        warn "Catalog repo already exists at $CATALOG_DIR"
        exit 0
    fi

    mkdir -p "$CATALOG_DIR"
    validate_path "$CATALOG_DIR" || exit 1

    cd "$CATALOG_DIR"
    git init

    # Create README
    cat > README.md << 'EOF'
# Data Catalog

Shared data catalog for the team.

## Files

- `tables.yaml` - Table metadata (row counts, key columns)
- `columns.yaml` - Column definitions and semantic roles
- `joins.yaml` - Validated SQL join patterns
- `quality_rules.yaml` - Data quality constraints
- `semantic.yaml` - Business term definitions

## Usage

This catalog is managed by deng-toolkit.

```bash
# Check status
/deng-catalog-sync --status

# Pull latest catalog
/deng-catalog-sync --pull

# Push local changes
/deng-catalog-sync --push
```

## Configuration

Catalog location is configured in `~/.deng-toolkit/config.yaml`:

```yaml
catalog_dir: ~/data-catalog
catalog_remote: git@github.com:YourOrg/data-catalog.git
```
EOF

    # Create .gitignore
    cat > .gitignore << 'EOF'
# Credentials
.env
targets.toml

# Temp files
*.tmp
*.bak

# OS
.DS_Store
EOF

    git add -A
    git commit -m "Initialize data catalog"

    # Set up remote if configured
    if [[ -n "$CATALOG_REMOTE" ]]; then
        git remote add origin "$CATALOG_REMOTE" 2>/dev/null || true
        log "Added remote: $CATALOG_REMOTE"
    fi

    log "Catalog repo initialized at $CATALOG_DIR"
    echo ""
    echo "Next steps:"
    if [[ -z "$CATALOG_REMOTE" ]]; then
        echo "  1. Add remote: git remote add origin <your-repo-url>"
        echo "  2. Push: git push -u origin main"
    else
        echo "  Push: git push -u origin main"
    fi
}

do_full() {
    check_repo
    validate_path "$CATALOG_DIR" || exit 1

    # Pull first
    do_pull

    # Then push any local changes
    do_push
}

# Main
case "${1:-}" in
    --push|--git)
        do_push
        ;;
    --pull)
        do_pull
        ;;
    --init)
        do_init
        ;;
    --full)
        do_full
        ;;
    --status|"")
        do_status
        ;;
    *)
        echo "Usage: catalog_sync.sh [--push|--pull|--init|--full|--status]"
        echo ""
        echo "Commands:"
        echo "  --status  Show configuration and sync status (default)"
        echo "  --push    Commit and push changes to remote"
        echo "  --pull    Pull latest from remote"
        echo "  --full    Full sync: pull, then commit and push"
        echo "  --init    Initialize the catalog git repo"
        echo ""
        echo "Configuration:"
        echo "  Edit ~/.deng-toolkit/config.yaml to set catalog_dir and catalog_remote"
        echo "  Or set DENG_CATALOG_DIR environment variable"
        exit 1
        ;;
esac
