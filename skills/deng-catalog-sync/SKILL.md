---
name: deng-catalog-sync
description: Sync the data catalog to a git repository for version control and team sharing
---

# Data Catalog Sync

Syncs the local data catalog (`~/.deng-toolkit/catalog/`) to a git repository for version control, backup, and team sharing.

## Usage

```
/deng-catalog-sync              # Show status (what would be synced)
/deng-catalog-sync --push       # Commit and push changes to remote
/deng-catalog-sync --pull       # Pull latest from remote
/deng-catalog-sync --init       # Initialize the catalog git repo
```

## Configuration

The sync target is `~/.ds-catalog/` which should be a git repository.

**First-time setup:**
```bash
# Create the catalog repo
mkdir -p ~/.ds-catalog
cd ~/.ds-catalog
git init
git remote add origin <your-catalog-repo-url>

# Or clone an existing catalog
git clone <your-catalog-repo-url> ~/.ds-catalog
```

## Execution Steps

### Status (default)

Show what files have changed and would be synced:

```bash
CATALOG_SRC="$HOME/.deng-toolkit/catalog"
CATALOG_DEST="$HOME/.ds-catalog"

# Check if dest repo exists
if [[ ! -d "$CATALOG_DEST/.git" ]]; then
    echo "Catalog repo not initialized. Run /deng-catalog-sync --init"
    exit 1
fi

# Copy catalog files to git repo
rsync -av --delete \
    --exclude='.git' \
    --exclude='*.tmp' \
    "$CATALOG_SRC/" "$CATALOG_DEST/"

# Show git status
cd "$CATALOG_DEST"
git status
```

### Push (--push)

Commit local changes and push to remote:

```bash
CATALOG_SRC="$HOME/.deng-toolkit/catalog"
CATALOG_DEST="$HOME/.ds-catalog"

# Sync files
rsync -av --delete \
    --exclude='.git' \
    --exclude='*.tmp' \
    "$CATALOG_SRC/" "$CATALOG_DEST/"

cd "$CATALOG_DEST"

# Check for changes
if git diff --quiet && git diff --staged --quiet; then
    echo "No changes to sync"
    exit 0
fi

# Stage all changes
git add -A

# Create commit with timestamp
TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
git commit -m "Catalog update: $TIMESTAMP"

# Push to remote
git push origin main
echo "Catalog synced successfully"
```

### Pull (--pull)

Pull latest catalog from remote:

```bash
CATALOG_SRC="$HOME/.deng-toolkit/catalog"
CATALOG_DEST="$HOME/.ds-catalog"

cd "$CATALOG_DEST"
git pull origin main

# Sync back to local catalog
rsync -av --delete \
    --exclude='.git' \
    "$CATALOG_DEST/" "$CATALOG_SRC/"

echo "Catalog pulled and updated"
```

### Init (--init)

Initialize the catalog git repository:

```bash
CATALOG_DEST="$HOME/.ds-catalog"

if [[ -d "$CATALOG_DEST/.git" ]]; then
    echo "Catalog repo already exists at $CATALOG_DEST"
    exit 0
fi

mkdir -p "$CATALOG_DEST"
cd "$CATALOG_DEST"
git init

echo "# Data Catalog" > README.md
echo "" >> README.md
echo "Shared data catalog for the team." >> README.md
echo "" >> README.md
echo "Files:" >> README.md
echo "- tables.yaml - Table metadata" >> README.md
echo "- columns.yaml - Column definitions" >> README.md
echo "- joins.yaml - Join patterns" >> README.md
echo "- quality_rules.yaml - Data quality rules" >> README.md
echo "- semantic.yaml - Business terms" >> README.md

cat > .gitignore << 'EOF'
*.tmp
*.bak
.DS_Store
EOF

git add -A
git commit -m "Initialize data catalog"

echo ""
echo "Catalog repo initialized at $CATALOG_DEST"
echo ""
echo "Next: Add a remote origin:"
echo "  cd $CATALOG_DEST"
echo "  git remote add origin <your-repo-url>"
echo "  git push -u origin main"
```

## File Mapping

| Source | Destination |
|--------|-------------|
| `~/.deng-toolkit/catalog/tables.yaml` | `~/.ds-catalog/tables.yaml` |
| `~/.deng-toolkit/catalog/columns.yaml` | `~/.ds-catalog/columns.yaml` |
| `~/.deng-toolkit/catalog/joins.yaml` | `~/.ds-catalog/joins.yaml` |
| `~/.deng-toolkit/catalog/quality_rules.yaml` | `~/.ds-catalog/quality_rules.yaml` |
| `~/.deng-toolkit/catalog/semantic.yaml` | `~/.ds-catalog/semantic.yaml` |

## Integration

This skill is typically called:
- After `/deng-catalog-refresh` completes
- After manual catalog edits
- Before starting a new project (to get latest team catalog)

The `catalog-updated.sh` hook suggests running this after catalog refreshes.
