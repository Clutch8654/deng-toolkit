# deng-toolkit

Data engineering toolkit for Claude Code - provides skills and scripts for database metadata management, ontology building, and SQL pattern analysis.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/<org>/deng-toolkit.git ~/.deng-toolkit

# Install skills (creates symlinks to ~/.claude/skills/)
~/.deng-toolkit/setup.sh

# Verify installation
ls -la ~/.claude/skills/deng-*
```

## Skills

| Skill | Description |
|-------|-------------|
| `/deng-catalog-refresh` | Rebuild database metadata catalog from SQL Server |
| `/deng-find-data` | Fast keyword search for tables/columns |
| `/deng-build-ontology` | Build JSON-LD knowledge graph from metadata |
| `/deng-analyze-procedures` | Extract SQL patterns from stored procedures |
| `/deng-new` | Scaffold a new data science project |

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency management
- Claude Code CLI

### Python Dependencies

Scripts are run via `uv run` with inline dependencies:

```bash
uv run --with pymssql --with polars --with python-dotenv python <script>
```

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

Edit to define:
- Business domain classifications
- Semantic column roles
- Business metric definitions
- Relationship type mappings

## Directory Structure

```
~/.deng-toolkit/
├── scripts/           # Python scripts for data operations
│   ├── catalog_refresh.py
│   ├── catalog_query.py
│   ├── catalog_snapshot.py
│   ├── build_ontology.py
│   ├── analyze_procedures.py
│   ├── generate_review_excel.py
│   ├── apply_review_feedback.py
│   └── adapters/      # Database-specific adapters
├── skills/            # Claude Code skill definitions
│   ├── deng-catalog-refresh/
│   ├── deng-find-data/
│   ├── deng-build-ontology/
│   ├── deng-analyze-procedures/
│   └── deng-new/
├── templates/         # Configuration templates
├── setup.sh           # Installation script
├── uninstall.sh       # Removal script
└── README.md
```

## Uninstall

```bash
# Remove skill symlinks
~/.deng-toolkit/uninstall.sh

# Optionally remove the toolkit entirely
rm -rf ~/.deng-toolkit
```

**Note:** Uninstalling only removes symlinks that point to this toolkit. Your data catalog at `~/.ds_catalog/` is preserved.

## Workflow

```
/deng-catalog-refresh  →  metadata.parquet (schema metadata)
        ↓
/deng-analyze-procedures  →  procedures.parquet (SQL patterns)
        ↓
/deng-build-ontology  →  ontology.jsonld (knowledge graph)
        ↓
/deng-find-data  →  Query the catalog
```

## Separating Toolkit from Data

This toolkit is designed to be separate from your data catalog:

| Component | Location | Git Repo |
|-----------|----------|----------|
| **Toolkit** (scripts, skills) | `~/.deng-toolkit/` | Public/shareable |
| **Data Catalog** (parquet, configs) | `~/.ds_catalog/` | Private/org-specific |

This separation allows you to:
- Share the toolkit without exposing schema metadata
- Version control the toolkit independently
- Use the same toolkit with multiple data catalogs

## License

MIT
