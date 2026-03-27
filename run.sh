#!/bin/bash
# ============================================================================
# SOLID Analyzer - Full Pipeline Runner
# CS437 Project - Ahmet Yağız Sarıdoğan
#
# Usage:
#   ./run.sh              # Run everything (all 3 repos)
#   ./run.sh flask        # Run only flask
#   ./run.sh detect       # Run only detection for all repos
#   ./run.sh refactor     # Run only refactoring for all repos
# ============================================================================

set -e

# ---- Configuration ----
# Set your Gemini API key here if not already exported
if [ -z "$GEMINI_API_KEY" ]; then
    export GEMINI_API_KEY="AIzaSyA0tWMtYrGf_sUe_Qwks5pBOQNmQnKHQaw"
fi

REPOS=("fastjson2" "kotlinx-coroutines" "flask")

# ---- Setup ----
echo "============================================"
echo "SOLID Analyzer - CS437 Project"
echo "Student: Ahmet Yağız Sarıdoğan"
echo "============================================"

# Install if needed
if ! command -v solid-analyzer &> /dev/null; then
    echo "[SETUP] Installing solid-analyzer..."
    pip install -e . --quiet
fi

# ---- Determine mode ----
MODE="${1:-all}"
REPO="${2:-}"

run_for_repo() {
    local repo=$1
    echo ""
    echo "============================================"
    echo "Processing: $repo"
    echo "============================================"

    # Clone/update
    echo "[1/7] Cloning/updating repository..."
    solid-analyzer clone "$repo"

    # Detection
    echo "[2/7] Running detection (60 scans)..."
    solid-analyzer -v detect "$repo"

    # Auto-annotate detections
    echo "[3/7] Auto-annotating detection findings..."
    solid-analyzer auto-annotate "$repo"

    # Refactoring
    echo "[4/7] Running refactoring (60 attempts)..."
    solid-analyzer -v refactor "$repo"

    # Auto-annotate refactorings
    echo "[5/7] Auto-annotating refactoring results..."
    solid-analyzer auto-annotate "$repo"

    # Report
    echo "[6/7] Generating reports..."
    solid-analyzer report "$repo"

    # Status
    echo "[7/7] Budget status:"
    solid-analyzer status "$repo"

    echo ""
    echo "Done with $repo!"
}

case "$MODE" in
    all)
        # Clone all repos first
        echo "[SETUP] Cloning all repositories..."
        solid-analyzer clone all

        for repo in "${REPOS[@]}"; do
            run_for_repo "$repo"
        done
        ;;
    detect)
        for repo in "${REPOS[@]}"; do
            echo "Detecting for $repo..."
            solid-analyzer -v detect "$repo"
        done
        ;;
    refactor)
        for repo in "${REPOS[@]}"; do
            echo "Refactoring for $repo..."
            solid-analyzer -v refactor "$repo"
        done
        ;;
    report)
        for repo in "${REPOS[@]}"; do
            solid-analyzer report "$repo"
        done
        ;;
    status)
        solid-analyzer status all
        ;;
    annotate)
        for repo in "${REPOS[@]}"; do
            solid-analyzer annotate "$repo" --type detections
            solid-analyzer annotate "$repo" --type refactorings
        done
        ;;
    *)
        # Assume it's a repo name
        run_for_repo "$MODE"
        ;;
esac

echo ""
echo "============================================"
echo "All done! Check output/ for results."
echo ""
echo "All detections, refactorings, and annotations are complete!"
echo ""
echo "Results are in the output/ directory:"
echo "  - output/findings/     (detection results + annotations)"
echo "  - output/refactors/    (refactoring results + PR reports)"
echo "  - output/reports/      (summary reports with precision/recall/F1)"
echo ""
echo "Optional: manually review auto-annotations with:"
echo "  solid-analyzer annotate <repo> --type detections"
echo "============================================"
