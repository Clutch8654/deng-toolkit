#!/bin/bash
# Hook: Runs after catalog_refresh.py completes
# Provides helpful follow-up suggestions

CATALOG_DIR="${DENG_CATALOG_DIR:-$HOME/.ds_catalog}"

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
