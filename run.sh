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
    echo "[1/5] Cloning/updating repository..."
    solid-analyzer clone "$repo"

    # Detection
    echo "[2/5] Running detection (60 scans)..."
    solid-analyzer -v detect "$repo"

    # Refactoring
    echo "[3/5] Running refactoring (60 attempts)..."
    solid-analyzer -v refactor "$repo"

    # Report
    echo "[4/5] Generating reports..."
    solid-analyzer report "$repo"

    # Status
    echo "[5/5] Budget status:"
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
echo "Next steps:"
echo "  1. Run: solid-analyzer annotate <repo> --type detections"
echo "     (manually review each finding as correct/incorrect)"
echo "  2. Run: solid-analyzer annotate <repo> --type refactorings"
echo "     (manually review each refactoring)"
echo "  3. Run: solid-analyzer report all"
echo "     (regenerate reports with annotation data)"
echo "============================================"
