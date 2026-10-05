#!/bin/bash
# ---------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Version Bump Script
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
#
# Usage:
#   ./bump_version.sh          # dry-run, zobrazí čo by zmenil
#   ./bump_version.sh apply    # naozaj prepíše súbory
# ---------------------------------------------------------------------

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# --- Configuration ---
# Old versions to replace (in file headers, comments, etc.)
OLD_VERSIONS=("0.8" "0.9")
NEW_VERSION="0.9.5"

# Files to update (relative to project root)
# We only touch source files and docs — not .git, not build artifacts.
FILE_PATTERNS=(
    "src/*.py"
    "src/**/*.py"
    "src/**/**/*.py"
    "tests/*.py"
    "scripts/*.sh"
    "resources/**/*.css"
    "resources/**/*.desktop"
    "README.md"
    "CONTRIBUTING.md"
    "ROADMAP.md"
    "pyproject.toml"
)

# Skip these directories entirely
SKIP_DIRS=(".git" "build" "dist" "__pycache__" ".pytest_cache" "node_modules")

# --- Mode ---
MODE="${1:-dry-run}"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}SQL Schema Studio — Version Bump${NC}"
echo -e "${BLUE}=================================${NC}"
echo -e "Old versions: ${YELLOW}${OLD_VERSIONS[*]}${NC}"
echo -e "New version:  ${GREEN}${NEW_VERSION}${NC}"
echo -e "Mode:         ${YELLOW}${MODE}${NC}"
echo ""

# --- Find files ---
FILES=()
for pattern in "${FILE_PATTERNS[@]}"; do
    while IFS= read -r -d '' file; do
        skip=0
        for dir in "${SKIP_DIRS[@]}"; do
            if [[ "$file" == *"/$dir/"* ]]; then
                skip=1
                break
            fi
        done
        [[ $skip -eq 0 ]] && FILES+=("$file")
    done < <(find . -path "./$pattern" -type f -print0 2>/dev/null || true)
done

# Deduplicate
FILES=($(printf "%s\n" "${FILES[@]}" | sort -u))

echo -e "${BLUE}Scanning ${#FILES[@]} files...${NC}"
echo ""

# --- Process each file ---
CHANGED_COUNT=0

for file in "${FILES[@]}"; do
    # Skip if file doesn't exist (in case find produced a dead path)
    [[ -f "$file" ]] || continue

    # Count matches in this file
    matches=0
    for old in "${OLD_VERSIONS[@]}"; do
        count=$(grep -c "$old" "$file" 2>/dev/null || true)
        matches=$((matches + count))
    done

    if [[ $matches -gt 0 ]]; then
        CHANGED_COUNT=$((CHANGED_COUNT + 1))
        echo -e "${GREEN}▶${NC} $file ${YELLOW}($matches matches)${NC}"

        if [[ "$MODE" == "apply" ]]; then
            # Make a backup of each file before editing (in case of failure)
            cp "$file" "$file.bak"

            for old in "${OLD_VERSIONS[@]}"; do
                # Careful: only replace version-like occurrences.
                # We use word boundaries so "0.9" doesn't match "10.9" or "0.95".
                # But we DO want to match "0.9.5" → "0.9.5.5"? No.
                # We want "0.9" → "0.9.5", but NOT "0.9.5" → "0.9.5.5".
                #
                # Regex: match "old" only if it is NOT followed by a digit
                #        or a dot+digit (i.e. not already part of a longer version).
                #
                # Example: "0.9" in "0.9.0"  → skip (already versioned)
                #          "0.9" in "0.9 -"  → replace with "0.9.5"
                #          "0.9" in "0.9.5"  → skip (already current)
                sed -i -E "s/\b${old}([^0-9.]|$)/${NEW_VERSION}\1/g" "$file"
            done

            # Show diff for the file
            if diff -q "$file.bak" "$file" >/dev/null; then
                # No change after all (regex didn't match anything)
                rm "$file.bak"
                echo -e "  ${YELLOW}(no actual change, backup removed)${NC}"
            else
                echo -e "  ${GREEN}✓ updated (backup at $file.bak)${NC}"
            fi
        fi
    fi
done

echo ""
echo -e "${BLUE}=================================${NC}"
echo -e "Files with matches: ${YELLOW}$CHANGED_COUNT${NC}"

if [[ "$MODE" == "dry-run" ]]; then
    echo ""
    echo -e "${YELLOW}This was a DRY RUN. No files were modified.${NC}"
    echo -e "To apply changes, run: ${GREEN}./bump_version.sh apply${NC}"
fi

if [[ "$MODE" == "apply" ]]; then
    echo ""
    echo -e "${GREEN}Done.${NC}"
    echo -e "Backups are at ${YELLOW}*.bak${NC} — verify with:"
    echo -e "  ${BLUE}git diff${NC}"
    echo -e "  ${BLUE}grep -rn '0\\.8\\|0\\.9' src/ --include='*.py' | grep -v '0.9.5'${NC}"
    echo ""
    echo -e "To revert all changes:"
    echo -e "  ${BLUE}find . -name '*.bak' -exec sh -c 'mv \"\$1\" \"\${1%.bak}\"' _ {} \\;${NC}"
    echo ""
    echo -e "To commit:"
    echo -e "  ${BLUE}git add -A && git commit -m 'chore: bump version to 0.9.5'${NC}"
fi
