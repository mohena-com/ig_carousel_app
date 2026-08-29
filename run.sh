#!/usr/bin/env bash
set -euo pipefail

export OLLAMA_HOST="${OLLAMA_HOST:-http://webmaster-ai.local:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3:8b}"

exec python app.py "$@"
