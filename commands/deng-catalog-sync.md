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
- All team members' annotation files (`annotations/*.json`)

### Step 2: Push (if --push flag)

```bash
cd ~/.ds_catalog && git add annotations/*.json && git commit -m "Annotation update" && git push
```

## What Gets Synced

| File | Direction | Notes |
|------|-----------|-------|
| `metadata.parquet` | Pull only | Maintainers push, users pull |
| `annotations/*.json` | Both | Per-user files, no conflicts |
| `ontology.jsonld` | Pull only | Knowledge graph |
| `targets.toml` | **Never** | Contains connection info |
| `.env` | **Never** | Credentials |

## User Workflow

```bash
# 1. Get team's latest annotations
/deng-catalog-sync

# 2. Add your annotations via MCP tools
# (automatically writes to annotations/{your-username}.json)

# 3. Share your annotations with the team
/deng-catalog-sync --push
```

## Annotation Files

Each team member has their own annotation file:
- `annotations/jensen.json` - Jensen's notes and flags
- `annotations/alice.json` - Alice's notes and flags
- etc.

**No merge conflicts!** Each user writes only to their own file. The MCP server merges all files at query time.

## Team Onboarding

### First-Time Setup (Team Lead)

1. Create a shared git repository (e.g., GitHub, GitLab, Azure DevOps)
2. Initialize the catalog:
   ```bash
   cd ~/.ds_catalog
   git init
   mkdir -p annotations
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

## Recommended .gitignore

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

## Alternative: OneDrive Snapshot

For teams without git access, create a shareable snapshot:

```bash
# Create timestamped snapshot
mkdir -p ~/OneDrive/DataCatalog/$(date +%Y%m%d)
cp ~/.ds_catalog/metadata.parquet ~/OneDrive/DataCatalog/$(date +%Y%m%d)/
cp -r ~/.ds_catalog/annotations ~/OneDrive/DataCatalog/$(date +%Y%m%d)/
cp ~/.ds_catalog/ontology.jsonld ~/OneDrive/DataCatalog/$(date +%Y%m%d)/
```

## Related Commands

| Command | Purpose |
|---------|---------|
| `/deng-catalog-refresh` | Update the catalog from databases |
| `/deng-catalog-status` | Check catalog health |
| `/deng-find-data` | Search the catalog |
