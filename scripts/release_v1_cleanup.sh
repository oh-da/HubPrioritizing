#!/bin/bash
# =============================================================================
# Release v1.0 Cleanup Script
# =============================================================================
# This script:
#   1. Creates and pushes the v1.0 tag on main
#   2. Deletes all stale remote branches (claude/*, cleanup/*)
#   3. Cleans up local tracking references
#
# Usage: bash scripts/release_v1_cleanup.sh
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo "  Release v1.0 - Cleanup Script"
echo "=========================================="
echo ""

# --- Step 1: Tag v1.0 on main ---
echo "[1/3] Creating and pushing v1.0 tag..."

if git tag -l | grep -q "^v1.0$"; then
    echo "  Tag v1.0 already exists locally, deleting to recreate..."
    git tag -d v1.0
fi

git tag -a v1.0 -m "Release v1.0 - Hub Prioritization Framework

Complete implementation of the integrated transport hub (מתח״מ)
prioritization framework including:
- H3-based hub identification and spatial analysis
- Hub classification (ארצי/מטרופוליני/עירוני hierarchy)
- Multi-criteria scoring (activity, service, location, demographics, terminals)
- Monte Carlo weighted aggregation (10,000 iterations)
- AHP expert-driven scoring (optional)
- Interactive visualization and results export
- 86 hubs evaluated across Israel" origin/main

git push origin v1.0
echo "  ✓ Tag v1.0 pushed successfully"
echo ""

# --- Step 2: Delete remote branches ---
echo "[2/3] Deleting stale remote branches..."

BRANCHES_TO_DELETE=(
    # Merged branches (26)
    "claude/add-ahp-scoring-01LvCgReTjzSdcrgS6GJm8ff"
    "claude/add-grouping-substep-wA8e8"
    "claude/add-hebrew-line-names-LJ9GN"
    "claude/add-postprocess-notebook-8UQs7"
    "claude/add-transit-hub-classification-cZYnF"
    "claude/ahp-questionnaire-streamlit-app-IryiH"
    "claude/ahp-scoring-notebook-0cceu"
    "claude/debug-pipeline-diagnostics-4fGht"
    "claude/executive-summary-criteria-LhGpM"
    "claude/fix-area-column-parsing-atPlK"
    "claude/fix-column-calculations-EDgnx"
    "claude/fix-column-encoding-c2Be0"
    "claude/fix-encoding-add-numpy-3qhFw"
    "claude/fix-hebrew-text-truncation-QErCG"
    "claude/fix-hub-area-tagging-Q5hlT"
    "claude/fix-hub-spatial-tagging-rTd2d"
    "claude/fix-hub-type-ranking-DyqiK"
    "claude/fix-line-name-splitting-m8mYT"
    "claude/fix-mc-import-error-3T7ck"
    "claude/fix-non-rail-filtering-kz2FS"
    "claude/fix-unmatched-lines-P3XQt"
    "claude/hub-data-postprocess-vm2SS"
    "claude/monte-carlo-distribution-reporting-U2p6J"
    "claude/validate-scoring-method-uAxKs"
    "claude/verify-config-transit-pipeline-1p4rG"
    "cleanup/clean-unused-files"
    # Unmerged stale branches (15)
    "claude/add-folium-mapping-notebook-nL6zR"
    "claude/add-hub-notebooks-01EBfEGHS1sezkE4ETvrff5P"
    "claude/add-mode-line-counts-OFsFA"
    "claude/create-results-csv-hebrew-Sk89F"
    "claude/fix-data-cleaning-error-wG908"
    "claude/fix-demand-columns-01HbQHNZafzD3vKgnJnFuGmL"
    "claude/fix-pop-emp-columns-vtp0B"
    "claude/fix-scoring-calculations-fOnHv"
    "claude/influence-area-processing-01RmzP4Xk3NqLPx9aBYGgHa6"
    "claude/review-solid-update-docs-01GaCEcQE3hZ9ycsAD9oZrUG"
    "claude/rewrite-project-code-01FHLdCQmKDLRtNePvfWEkmZ"
    "claude/solid-principles-implementation-013di3QBDmkdiJ5vT1CXxxay"
    "claude/transit-update-planning-UPlGA"
    "claude/update-markdown-files-KbE0t"
    "claude/update-solid-docs-XLO46"
)

DELETED=0
FAILED=0

for branch in "${BRANCHES_TO_DELETE[@]}"; do
    if git push origin --delete "$branch" 2>/dev/null; then
        echo "  ✓ Deleted: $branch"
        ((DELETED++))
    else
        echo "  ✗ Failed:  $branch (may already be deleted)"
        ((FAILED++))
    fi
done

echo ""
echo "  Deleted: $DELETED branches"
echo "  Failed:  $FAILED branches"
echo ""

# --- Step 3: Clean up local references ---
echo "[3/3] Cleaning up local references..."
git fetch origin --prune
git branch -d master 2>/dev/null && echo "  ✓ Deleted local 'master' branch" || echo "  - No local 'master' to delete"
echo "  ✓ Pruned stale remote tracking references"
echo ""

echo "=========================================="
echo "  Cleanup Complete!"
echo "=========================================="
echo ""
echo "Final state:"
echo "  Tag: v1.0 → $(git rev-parse --short v1.0 2>/dev/null || echo 'N/A')"
echo "  Remote branches:"
git branch -r | sed 's/^/    /'
echo ""
echo "  Local branches:"
git branch | sed 's/^/    /'
