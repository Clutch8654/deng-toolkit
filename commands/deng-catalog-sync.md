# Catalog Sync

Synchronizes catalog changes with your team via git. The catalog at `~/.ds_catalog/` is a git repository that can be shared.

## Usage

```
/deng-catalog-sync [--push]
```

**Options:**
- `--push` - Push changes to remote after committing

## Process

### Step 1: Check Git Status

```bash
cd ~/.ds_catalog && git status
```

If `~/.ds_catalog/` is not a git repository, initialize it:

```bash
cd ~/.ds_catalog && git init
```

### Step 2: Stage Changes

```bash
cd ~/.ds_catalog && git add -A
```

### Step 3: Commit

```bash
cd ~/.ds_catalog && git commit -m "Catalog update $(date +%Y-%m-%d)"
```

### Step 4: Push (if --push)

```bash
cd ~/.ds_catalog && git push origin main
```

## Team Onboarding

### First-Time Setup (Team Lead)

1. Create a shared git repository (e.g., GitHub, GitLab, Azure DevOps)
2. Initialize the catalog:
   ```bash
   cd ~/.ds_catalog
   git init
   git remote add origin <your-repo-url>
   git add -A
   git commit -m "Initial catalog"
   git push -u origin main
   ```

### Joining the Team

1. Clone the catalog repository:
   ```bash
   git clone <your-repo-url> ~/.ds_catalog
   ```

2. Verify:
   ```bash
   /deng-catalog-status
   ```

### Updating Your Catalog

```bash
cd ~/.ds_catalog && git pull origin main
```

Or use the MCP tool if available:
```
# Pull latest from remote
cd ~/.ds_catalog && git pull
```

## What Gets Synced

| File | Synced | Notes |
|------|--------|-------|
| `metadata.parquet` | Yes | Core catalog data |
| `ontology.jsonld` | Yes | Knowledge graph |
| `ontology_config.toml` | Yes | Team-shared config |
| `targets.toml` | **No** | Contains connection info |
| `procedures.parquet` | Yes | Procedure metadata |
| `.env` | **No** | Credentials |

### Recommended .gitignore

Create `~/.ds_catalog/.gitignore`:
```
# Credentials and connection info
.env
targets.toml

# Temporary files
*.tmp
*.bak

# OS files
.DS_Store
```

## Conflict Resolution

If you get merge conflicts:

1. For `.parquet` files: Accept the newer version (by date)
2. For `.toml` config: Merge manually
3. For `.jsonld`: Rebuild with `/deng-build-ontology`

## Alternative: OneDrive Snapshot

For teams without git access, create a shareable snapshot:

```bash
# Create timestamped snapshot
mkdir -p ~/OneDrive/DataCatalog/$(date +%Y%m%d)
cp ~/.ds_catalog/metadata.parquet ~/OneDrive/DataCatalog/$(date +%Y%m%d)/
cp ~/.ds_catalog/ontology.jsonld ~/OneDrive/DataCatalog/$(date +%Y%m%d)/
cp ~/.ds_catalog/ONTOLOGY_SUMMARY.md ~/OneDrive/DataCatalog/$(date +%Y%m%d)/
```

## Related Commands

| Command | Purpose |
|---------|---------|
| `/deng-catalog-refresh` | Update the catalog from databases |
| `/deng-catalog-status` | Check catalog health |
