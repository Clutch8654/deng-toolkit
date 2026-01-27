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

### Data Catalog Location

By default, catalog data is stored in `~/.ds_catalog/`. Override with:

```bash
export DENG_CATALOG_DIR=/path/to/custom/catalog
```

### Database Targets

Create `~/.ds_catalog/targets.toml`:

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
cp ~/.deng-toolkit/templates/ontology_config.toml.example ~/.ds_catalog/ontology_config.toml
```

## Directory Structure

```
~/.deng-toolkit/
├── .claude-plugin/
│   └── plugin.json         # Plugin manifest
├── .mcp.json               # MCP server configuration
├── commands/               # Slash command definitions
│   ├── deng-catalog-refresh.md
│   ├── deng-find-data.md
│   ├── deng-build-ontology.md
│   ├── deng-analyze-procedures.md
│   ├── deng-catalog-status.md
│   └── deng-catalog-sync.md
├── servers/
│   └── catalog_mcp/        # MCP server
│       ├── server.py       # 4 MCP tools
│       └── pyproject.toml
├── hooks/
│   ├── hooks.json          # PostToolUse hooks
│   └── scripts/            # Hook scripts
├── scripts/                # Python scripts for data operations
│   ├── catalog_refresh.py
│   ├── catalog_query.py
│   ├── build_ontology.py
│   └── analyze_procedures.py
├── templates/              # Configuration templates
├── setup.sh                # Installation script
└── README.md
```

## Team Sharing

The data catalog at `~/.ds_catalog/` is initialized as a git repository during setup. To share with your team:

### First-Time Setup (Team Lead)

```bash
cd ~/.ds_catalog
git remote add origin <your-repo-url>
git add -A
git commit -m "Initial catalog"
git push -u origin main
```

### Joining the Team

```bash
# Clone the shared catalog
git clone <your-repo-url> ~/.ds_catalog

# Install the toolkit
git clone https://github.com/Clutch8654/deng-toolkit.git ~/.deng-toolkit
~/.deng-toolkit/setup.sh
```

### Syncing Changes

Use the `/deng-catalog-sync` command or manually:

```bash
cd ~/.ds_catalog && git pull && git add -A && git commit -m "Update" && git push
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

The data catalog at `~/.ds_catalog/` is preserved.

## License

MIT
