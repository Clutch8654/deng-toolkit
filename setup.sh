#!/bin/bash
# deng-toolkit setup script
# Creates symlinks from toolkit skills to ~/.claude/skills/

set -e

TOOLKIT_DIR="$HOME/.deng-toolkit"
SKILLS_DIR="$HOME/.claude/skills"

echo "=========================================="
echo "  deng-toolkit installer"
echo "=========================================="
echo ""

# Verify we're in the right place
if [ ! -d "$TOOLKIT_DIR/skills" ]; then
    echo "ERROR: Skills directory not found at $TOOLKIT_DIR/skills"
    echo "Make sure you've cloned the repo to ~/.deng-toolkit/"
    exit 1
fi

# Ensure skills directory exists
mkdir -p "$SKILLS_DIR"

echo "Installing skills from $TOOLKIT_DIR/skills/ to $SKILLS_DIR/"
echo ""

# Create symlinks for each skill
for skill in "$TOOLKIT_DIR/skills/deng-"*; do
    if [ -d "$skill" ]; then
        skill_name=$(basename "$skill")
        target="$SKILLS_DIR/$skill_name"

        if [ -L "$target" ]; then
            # Existing symlink - update it
            echo "  Updating: $skill_name"
            rm "$target"
            ln -s "$skill" "$target"
        elif [ -e "$target" ]; then
            # Existing directory/file (not symlink) - skip
            echo "  WARNING: $target exists and is not a symlink. Skipping."
            echo "           Remove it manually if you want to use the toolkit version."
            continue
        else
            # New installation
            echo "  Linking: $skill_name"
            ln -s "$skill" "$target"
        fi
    fi
done

echo ""
echo "=========================================="
echo "  Installation complete!"
echo "=========================================="
echo ""
echo "Skills installed:"
ls -la "$SKILLS_DIR" | grep "deng-" | awk '{print "  " $NF " -> " $(NF-2)}'
echo ""
echo "Available commands:"
echo "  /deng-catalog-refresh  - Rebuild database metadata catalog"
echo "  /deng-find-data        - Search catalog for tables/columns"
echo "  /deng-build-ontology   - Build JSON-LD knowledge graph"
echo "  /deng-analyze-procedures - Extract SQL patterns from stored procs"
echo "  /deng-new              - Scaffold new DS project"
echo ""
echo "To uninstall, run:"
echo "  ~/.deng-toolkit/uninstall.sh"
echo ""
