# deng-toolkit

Data engineering toolkit for Claude Code - a plugin providing commands and MCP tools for database metadata management, ontology building, and SQL pattern analysis.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/Clutch8654/deng-toolkit.git ~/.deng-toolkit

# Install the plugin
~/.deng-toolkit/setup.sh
```

## Commands

| Command | Description |
|---------|-------------|
| `/deng-catalog-refresh` | Rebuild database metadata catalog from SQL Server |
| `/deng-find-data` | Fast keyword search for tables/columns |
| `/deng-build-ontology` | Build JSON-LD knowledge graph from metadata |
| `/deng-analyze-procedures` | Extract SQL patterns from stored procedures |
| `/deng-catalog-status` | Check catalog freshness and statistics |
| `/deng-catalog-sync` | Sync catalog with team git repository |

## MCP Tools

The plugin exposes an MCP server with these tools:

| Tool | Description |
|------|-------------|
| `search_catalog` | Search catalog by keywords |
| `get_table_details` | Get full details for a specific table |
| `find_join_paths` | Find FK relationships for a table |
| `get_catalog_status` | Get catalog age and statistics |

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency management
- Claude Code CLI

## Configuration

### Setup Configuration

During installation, `setup.sh` prompts for catalog location and creates `~/.deng-toolkit/config.yaml`:

```yaml
# deng-toolkit configuration
catalog_dir: ~/data-catalog          # Where the catalog lives
catalog_remote: git@github.com:...   # Git remote for team sharing (optional)
```

### Data Catalog Location

By default, catalog data is stored in `~/data-catalog/`. Configure via:

1. **config.yaml** (recommended): Edit `~/.deng-toolkit/config.yaml`
2. **Environment variable** (override): `export DENG_CATALOG_DIR=/path/to/catalog`

### Database Targets

Create `~/data-catalog/targets.toml`:

```toml
# Example: SQL Server target
[targets.oms]
name = "RCOOMSSQL001"
host_env = "OMS_HOST"
user_env = "OMS_USER"
password_env = "OMS_PASSWORD"
databases = ["Orders", "Quotes", "Customers", "Invoices", "Products"]
```

Set credentials in environment:

```bash
export OMS_HOST=your-server.database.windows.net
export OMS_USER=readonly_user
export OMS_PASSWORD=your_password
```

### Ontology Configuration

Copy the template and customize:

```bash
cp ~/.deng-toolkit/templates/ontology_config.toml.example ~/data-catalog/ontology_config.toml
```

## Directory Structure

```
~/.deng-toolkit/                    # Plugin (tooling)
├── .claude-plugin/
│   └── plugin.json                 # Plugin manifest
├── .mcp.json                       # MCP server configuration
├── config.yaml                     # Catalog location config
├── commands/                       # Slash command definitions
├── servers/catalog_mcp/            # MCP server (4 tools)
├── hooks/                          # PostToolUse hooks
├── scripts/                        # Python scripts
│   ├── config.py                   # Config loading module
│   ├── catalog_refresh.py
│   ├── catalog_query.py
│   ├── catalog_sync.sh
│   ├── migrate_catalog.sh
│   └── ...
├── templates/                      # Configuration templates
├── setup.sh                        # Installation script
└── README.md

~/data-catalog/                     # Data catalog (separate git repo)
├── metadata.parquet                # Schema metadata
├── ontology.jsonld                 # Knowledge graph
├── procedures.parquet              # SQL patterns
├── targets.toml                    # Database connection config
└── .git/                           # Team-shared via git
```

## Team Sharing

The toolkit and catalog are separate git repositories:
- **Toolkit** (`~/.deng-toolkit/`): Shared via GitHub, same for everyone
- **Catalog** (`~/data-catalog/`): Team-specific, configured during setup

### First-Time Setup (Team Lead)

```bash
# Create team catalog repo on GitHub, then:
cd ~/data-catalog
git remote add origin <your-catalog-repo-url>
git add -A
git commit -m "Initial catalog"
git push -u origin main
```

### Joining the Team

```bash
# Install the toolkit
git clone https://github.com/Clutch8654/deng-toolkit.git ~/.deng-toolkit
~/.deng-toolkit/setup.sh

# During setup, enter the team's catalog remote URL
# Or clone manually first:
git clone <your-catalog-repo-url> ~/data-catalog
```

### Syncing Changes

```bash
# Check current configuration
/deng-catalog-sync --status

# Pull latest from team
/deng-catalog-sync --pull

# Full sync: pull, commit local changes, push
/deng-catalog-sync --full
```

### Migrating Existing Catalogs

If you have an existing catalog in an old location:

```bash
~/.deng-toolkit/scripts/migrate_catalog.sh
```

## Workflow

```
/deng-catalog-refresh  →  metadata.parquet (schema metadata)
        ↓
/deng-analyze-procedures  →  procedures.parquet (SQL patterns)
        ↓
/deng-build-ontology  →  ontology.jsonld (knowledge graph)
        ↓
/deng-find-data  →  Query the catalog (or use MCP tools)
```

## Uninstall

```bash
claude plugins remove deng-toolkit
```

The data catalog (default: `~/data-catalog/`) is preserved.

## License

MIT
