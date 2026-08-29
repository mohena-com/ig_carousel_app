#!/usr/bin/env bash
set -euo pipefail

# Batch launcher for IG carousel generation.
# Defaults are relative to this workspace:
#   input : ../reports/jobs/*.txt
#   output: ../output_carousel/<job-file-stem>/
#
# Usage:
#   ./run.sh
#   ./run.sh --reports-dir "/path/to/reports/jobs" --output-dir "/path/to/output_carousel"
#   ./run.sh --reports-dir "/path/to/reports" --output-dir "/path/to/output_carousel"
#
# The script accepts either a jobs directory or its parent reports directory.
# If the supplied directory contains a "jobs" subdirectory, that subdirectory
# is used automatically.

export OLLAMA_HOST="${OLLAMA_HOST:-http://webmaster-ai.local:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3:8b}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV="$SCRIPT_DIR/.venv"
PYTHON="$VENV/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    echo "ERROR: Python virtual environment not found: $VENV"
    echo "Create it with: python3 -m venv .venv"
    exit 1
fi

REPORTS_DIR="../reports/jobs"
OUTPUT_DIR="../output_carousel"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --reports-dir)
            [[ $# -ge 2 ]] || { echo "ERROR: --reports-dir requires a path"; exit 2; }
            REPORTS_DIR="$2"
            shift 2
            ;;
        --output-dir)
            [[ $# -ge 2 ]] || { echo "ERROR: --output-dir requires a path"; exit 2; }
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            cat <<EOF
Usage:
  ./run.sh
  ./run.sh --reports-dir PATH --output-dir PATH

Defaults:
  reports: ../reports/jobs/*.txt
  output : ../output_carousel/<job-file-stem>/

Each TXT file is processed independently and produces exactly six slides
inside its own output folder.
EOF
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument: $1"
            echo "Use ./run.sh --help"
            exit 2
            ;;
    esac
done

# Allow --reports-dir to point either to reports/jobs or to reports.
if [[ -d "$REPORTS_DIR/jobs" ]]; then
    REPORTS_DIR="$REPORTS_DIR/jobs"
fi

REPORTS_DIR="$(cd "$REPORTS_DIR" 2>/dev/null && pwd)" || {
    echo "ERROR: Reports directory does not exist: $REPORTS_DIR"
    exit 1
}

OUTPUT_DIR="$(mkdir -p "$OUTPUT_DIR" && cd "$OUTPUT_DIR" && pwd)"

shopt -s nullglob
FILES=("$REPORTS_DIR"/*.txt)
shopt -u nullglob

if [[ ${#FILES[@]} -eq 0 ]]; then
    echo "No .txt job reports found in:"
    echo "  $REPORTS_DIR"
    exit 0
fi

echo "=============================================="
echo "IG Carousel Batch Generator"
echo "=============================================="
echo "Input : $REPORTS_DIR/*.txt"
echo "Output: $OUTPUT_DIR/<job-file-stem>/"
echo "Files : ${#FILES[@]}"
echo "Python: $PYTHON"
echo "=============================================="

SUCCESS=0
FAILED=0

for INPUT in "${FILES[@]}"; do
    STEM="$(basename "$INPUT" .txt)"
    JOB_OUTPUT="$OUTPUT_DIR/$STEM"
    mkdir -p "$JOB_OUTPUT"

    echo
    echo "----------------------------------------------"
    echo "Processing: $(basename "$INPUT")"
    echo "Output    : $JOB_OUTPUT"
    echo "----------------------------------------------"

    if "$PYTHON" app.py --input "$INPUT" --output "$JOB_OUTPUT"; then
        SUCCESS=$((SUCCESS + 1))
    else
        FAILED=$((FAILED + 1))
        echo "ERROR: Failed to generate carousel for $(basename "$INPUT")"
    fi
done

echo
echo "=============================================="
echo "Batch complete"
echo "Successful: $SUCCESS"
echo "Failed    : $FAILED"
echo "Output    : $OUTPUT_DIR"
echo "=============================================="

# Do not hide failures from automation/CI.
if [[ "$FAILED" -gt 0 ]]; then
    exit 1
fi
