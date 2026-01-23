#!/bin/bash
# deng-toolkit uninstall script
# Removes symlinks that point to this toolkit

set -e

TOOLKIT_DIR="$HOME/.deng-toolkit"
SKILLS_DIR="$HOME/.claude/skills"

echo "=========================================="
echo "  deng-toolkit uninstaller"
echo "=========================================="
echo ""

removed_count=0

for skill in "$SKILLS_DIR/deng-"*; do
    if [ -L "$skill" ]; then
        # Check if symlink points to our toolkit
        target=$(readlink "$skill")
        if [[ "$target" == "$TOOLKIT_DIR"* ]]; then
            echo "  Removing: $(basename "$skill")"
            rm "$skill"
            ((removed_count++))
        else
            echo "  Skipping: $(basename "$skill") (points elsewhere: $target)"
        fi
    elif [ -e "$skill" ]; then
        echo "  Skipping: $(basename "$skill") (not a symlink)"
    fi
done

echo ""
echo "=========================================="
echo "  Uninstall complete!"
echo "=========================================="
echo ""

if [ $removed_count -eq 0 ]; then
    echo "No toolkit symlinks were found to remove."
else
    echo "Removed $removed_count skill symlinks."
fi

echo ""
echo "The toolkit files remain at: $TOOLKIT_DIR"
echo ""
echo "To completely remove the toolkit, run:"
echo "  rm -rf $TOOLKIT_DIR"
echo ""
echo "To reinstall later, run:"
echo "  git clone <repo-url> ~/.deng-toolkit"
echo "  ~/.deng-toolkit/setup.sh"
echo ""
