#!/bin/bash
# catalog_sync.sh - Sync data catalog with git remote
#
# Wrapper script that provides catalog sync functionality.
# The main implementation is in ds-workflow-plugin/project/hooks/sync_catalog.sh
#
# Usage:
#   catalog_sync.sh --status    # Show current configuration
#   catalog_sync.sh --pull      # Pull latest from remote
#   catalog_sync.sh --git       # Commit local changes
#   catalog_sync.sh --full      # Full sync: pull + commit + push
#
# Configuration:
#   Reads from ~/.deng-toolkit/config.yaml:
#     catalog_dir: ~/data-catalog     # Where the catalog lives
#     catalog_remote: git@...         # Git remote URL
#
#   Override with DENG_CATALOG_DIR environment variable.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLKIT_DIR="$(dirname "$SCRIPT_DIR")"

# Use the ds-workflow-plugin implementation if available
DS_WORKFLOW_SYNC="$TOOLKIT_DIR/ds-workflow-plugin/project/hooks/sync_catalog.sh"

if [[ -f "$DS_WORKFLOW_SYNC" ]]; then
    exec "$DS_WORKFLOW_SYNC" "$@"
else
    echo "Error: sync_catalog.sh not found at $DS_WORKFLOW_SYNC"
    echo "Make sure ds-workflow-plugin is installed."
    exit 1
fi
