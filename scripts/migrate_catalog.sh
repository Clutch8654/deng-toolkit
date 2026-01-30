#!/bin/bash
# migrate_catalog.sh - Migrate catalog files to new location
#
# Migrates existing catalog data from old locations to the new config-based location.
# Run this after updating to the new config-based deng-toolkit.
#
# Usage:
#   migrate_catalog.sh              # Interactive migration
#   migrate_catalog.sh --dry-run    # Show what would be done without changes
#   migrate_catalog.sh --force      # Overwrite existing files in destination
#
# Old locations checked:
#   ~/.deng-toolkit/catalog/         (shell scripts default)
#   ~/.deng-toolkit/data_catalog/    (alternative)
#   ~/.ds_catalog/                   (Python scripts default)
#
# New location:
#   Read from ~/.deng-toolkit/config.yaml, defaults to ~/data-catalog

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Configuration
CONFIG_FILE="$HOME/.deng-toolkit/config.yaml"
OLD_LOCATIONS=(
    "$HOME/.deng-toolkit/catalog"
    "$HOME/.deng-toolkit/data_catalog"
    "$HOME/.ds_catalog"
)

# Parse arguments
DRY_RUN=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --help|-h)
            echo "Usage: migrate_catalog.sh [OPTIONS]"
            echo ""
            echo "Migrate catalog files from old locations to config-based location."
            echo ""
            echo "Options:"
            echo "  --dry-run    Show what would be done without making changes"
            echo "  --force      Overwrite existing files in destination"
            echo "  --help       Show this help"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "  Catalog Migration Tool"
echo "=========================================="
echo ""

# Read destination from config
if [[ -f "$CONFIG_FILE" ]]; then
    NEW_LOCATION=$(grep "^catalog_dir:" "$CONFIG_FILE" 2>/dev/null | sed 's/catalog_dir: *//' | sed "s|~|$HOME|" | tr -d '"' | tr -d "'")
    CATALOG_REMOTE=$(grep "^catalog_remote:" "$CONFIG_FILE" 2>/dev/null | sed 's/catalog_remote: *//' | tr -d '"' | tr -d "'")
fi

NEW_LOCATION="${NEW_LOCATION:-$HOME/data-catalog}"
CATALOG_REMOTE="${CATALOG_REMOTE:-}"

log_info "Configuration:"
echo "  Config file: $CONFIG_FILE"
echo "  Destination: $NEW_LOCATION"
if [[ -n "$CATALOG_REMOTE" ]]; then
    echo "  Remote: $CATALOG_REMOTE"
fi
echo ""

# Find old catalog locations with data
FOUND_SOURCES=()
for old_loc in "${OLD_LOCATIONS[@]}"; do
    if [[ -d "$old_loc" ]]; then
        file_count=$(find "$old_loc" -maxdepth 1 \( -name "*.yaml" -o -name "*.parquet" -o -name "*.json" \) 2>/dev/null | wc -l | tr -d ' ')
        if [[ "$file_count" -gt 0 ]]; then
            FOUND_SOURCES+=("$old_loc")
            log_info "Found catalog at: $old_loc ($file_count files)"
        fi
    fi
done

if [[ ${#FOUND_SOURCES[@]} -eq 0 ]]; then
    log_info "No existing catalog data found in old locations."
    echo ""
    echo "Checked:"
    for old_loc in "${OLD_LOCATIONS[@]}"; do
        echo "  - $old_loc"
    done
    exit 0
fi

echo ""

# Check if destination already exists
if [[ -d "$NEW_LOCATION" ]]; then
    existing_count=$(find "$NEW_LOCATION" -maxdepth 1 \( -name "*.yaml" -o -name "*.parquet" \) 2>/dev/null | wc -l | tr -d ' ')
    if [[ "$existing_count" -gt 0 ]]; then
        log_warn "Destination already has $existing_count catalog files."
        if [[ "$FORCE" == false ]] && [[ "$DRY_RUN" == false ]]; then
            echo ""
            read -p "Overwrite existing files? (y/N): " confirm
            if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
                log_info "Migration cancelled."
                exit 0
            fi
        fi
    fi
fi

# Determine which source to use (prefer most recent)
if [[ ${#FOUND_SOURCES[@]} -gt 1 ]]; then
    log_warn "Multiple catalog locations found!"
    echo ""
    echo "Select which to migrate:"
    select source in "${FOUND_SOURCES[@]}"; do
        if [[ -n "$source" ]]; then
            SOURCE_DIR="$source"
            break
        fi
    done
else
    SOURCE_DIR="${FOUND_SOURCES[0]}"
fi

log_step "Migrating from: $SOURCE_DIR"
log_step "Migrating to:   $NEW_LOCATION"
echo ""

# List files to migrate
FILES_TO_MIGRATE=()
while IFS= read -r -d '' file; do
    FILES_TO_MIGRATE+=("$file")
done < <(find "$SOURCE_DIR" -maxdepth 1 \( -name "*.yaml" -o -name "*.parquet" -o -name "*.json" -o -name "*.md" \) -print0 2>/dev/null)

echo "Files to migrate:"
for file in "${FILES_TO_MIGRATE[@]}"; do
    basename=$(basename "$file")
    echo "  - $basename"
done
echo ""

if [[ "$DRY_RUN" == true ]]; then
    log_info "DRY RUN - No changes made"
    exit 0
fi

# Create destination
log_step "Creating destination directory..."
mkdir -p "$NEW_LOCATION"

# Copy files
log_step "Copying files..."
for file in "${FILES_TO_MIGRATE[@]}"; do
    basename=$(basename "$file")
    if [[ "$FORCE" == true ]] || [[ ! -f "$NEW_LOCATION/$basename" ]]; then
        cp "$file" "$NEW_LOCATION/"
        echo "  Copied: $basename"
    else
        log_warn "Skipped (exists): $basename"
    fi
done

# Initialize git if not already
if [[ ! -d "$NEW_LOCATION/.git" ]]; then
    log_step "Initializing git repository..."
    cd "$NEW_LOCATION"
    git init -q

    # Create .gitignore
    if [[ ! -f ".gitignore" ]]; then
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
    fi

    # Set up remote if configured
    if [[ -n "$CATALOG_REMOTE" ]]; then
        git remote add origin "$CATALOG_REMOTE" 2>/dev/null || true
        log_info "Added remote: $CATALOG_REMOTE"
    fi
fi

# Optionally remove old location
echo ""
read -p "Remove old catalog at $SOURCE_DIR? (y/N): " remove_old
if [[ "$remove_old" =~ ^[Yy]$ ]]; then
    rm -rf "$SOURCE_DIR"
    log_info "Removed: $SOURCE_DIR"
fi

echo ""
echo "=========================================="
echo "  Migration Complete!"
echo "=========================================="
echo ""
echo "Catalog location: $NEW_LOCATION"
echo ""
echo "Next steps:"
echo "  1. Verify: ls -la $NEW_LOCATION"
echo "  2. Test: /deng-catalog-sync --status"
if [[ -n "$CATALOG_REMOTE" ]]; then
    echo "  3. Push: /deng-catalog-sync --full"
fi
