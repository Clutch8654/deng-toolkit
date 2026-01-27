#!/bin/bash
# deng-toolkit setup script
# Installs as a Claude Code plugin

set -e

TOOLKIT_DIR="$HOME/.deng-toolkit"

echo "=========================================="
echo "  deng-toolkit plugin installer"
echo "=========================================="
echo ""

# Verify we're in the right place
if [ ! -f "$TOOLKIT_DIR/.claude-plugin/plugin.json" ]; then
    echo "ERROR: plugin.json not found at $TOOLKIT_DIR/.claude-plugin/"
    echo "Make sure you've cloned the repo to ~/.deng-toolkit/"
    exit 1
fi

# Check if claude CLI is available
if ! command -v claude &> /dev/null; then
    echo "ERROR: claude CLI not found in PATH"
    echo "Install Claude Code first: https://docs.anthropic.com/en/docs/claude-code"
    exit 1
fi

echo "Installing deng-toolkit plugin..."
echo ""

# Add the plugin globally (user scope)
claude plugins add "$TOOLKIT_DIR" --scope user 2>/dev/null || {
    echo "Note: Plugin may already be installed or claude plugins command syntax differs."
    echo "To manually install, add this to your Claude Code settings:"
    echo ""
    echo '  "plugins": ['
    echo "    \"$TOOLKIT_DIR\""
    echo '  ]'
    echo ""
}

# Initialize catalog directory if it doesn't exist
CATALOG_DIR="$HOME/.ds_catalog"
if [ ! -d "$CATALOG_DIR" ]; then
    echo "Creating catalog directory at $CATALOG_DIR"
    mkdir -p "$CATALOG_DIR"
fi

# Initialize git if not already a repo
if [ ! -d "$CATALOG_DIR/.git" ]; then
    echo "Initializing git repository in $CATALOG_DIR"
    cd "$CATALOG_DIR"
    git init -q

    # Create .gitignore for credentials
    cat > .gitignore << 'EOF'
# Credentials and connection info
.env
targets.toml

# Temporary files
*.tmp
*.bak

# OS files
.DS_Store
Thumbs.db
EOF

    echo "Created .gitignore (excludes credentials)"
fi

echo ""
echo "=========================================="
echo "  Installation complete!"
echo "=========================================="
echo ""
echo "Available commands:"
echo "  /deng-catalog-refresh    - Rebuild database metadata catalog"
echo "  /deng-find-data          - Search catalog for tables/columns"
echo "  /deng-build-ontology     - Build JSON-LD knowledge graph"
echo "  /deng-analyze-procedures - Extract SQL patterns from stored procs"
echo "  /deng-catalog-status     - Check catalog freshness"
echo "  /deng-catalog-sync       - Sync catalog with team repository"
echo ""
echo "MCP Tools (available as tools):"
echo "  search_catalog           - Search by keywords"
echo "  get_table_details        - Get table/column details"
echo "  find_join_paths          - Find FK relationships"
echo "  get_catalog_status       - Check catalog status"
echo ""
echo "Catalog location: $CATALOG_DIR"
echo ""
echo "To uninstall:"
echo "  claude plugins remove deng-toolkit"
echo ""
