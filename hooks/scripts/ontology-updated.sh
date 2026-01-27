#!/bin/bash
# Hook: Runs after build_ontology.py completes
# Provides helpful follow-up suggestions

CATALOG_DIR="${DENG_CATALOG_DIR:-$HOME/.ds_catalog}"

if [ -f "$CATALOG_DIR/ontology.jsonld" ]; then
    echo ""
    echo "Ontology built successfully!"
    echo ""
    echo "Files updated:"
    echo "  - $CATALOG_DIR/ontology.jsonld"
    echo "  - $CATALOG_DIR/ONTOLOGY_SUMMARY.md"
    echo ""
    echo "Use the MCP tools or /deng-find-data for semantic queries."
fi

exit 0
