#!/bin/bash
# Hook: Runs after catalog_refresh.py completes
# Provides helpful follow-up suggestions

# Read catalog_dir from config.yaml if it exists
CONFIG_FILE="$HOME/.deng-toolkit/config.yaml"
if [[ -f "$CONFIG_FILE" ]]; then
    CATALOG_DIR_CONFIG=$(grep "^catalog_dir:" "$CONFIG_FILE" 2>/dev/null | sed 's/catalog_dir: *//' | sed "s|~|$HOME|" | tr -d '"' | tr -d "'")
fi

# Environment variable overrides config, config overrides default
CATALOG_DIR="${DENG_CATALOG_DIR:-${CATALOG_DIR_CONFIG:-$HOME/data-catalog}}"

if [ -f "$CATALOG_DIR/metadata.parquet" ]; then
    echo ""
    echo "Catalog updated successfully!"
    echo ""
    echo "Next steps:"
    echo "  - Run /deng-build-ontology to update the knowledge graph"
    echo "  - Run /deng-find-data to search the catalog"
    echo "  - Run /deng-catalog-sync --push to share with team"
fi

exit 0
