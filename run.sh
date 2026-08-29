#!/usr/bin/env bash

set -e

OLLAMA_HOST=http://webmaster-ai.local:11434 \
OLLAMA_MODEL=qwen3:8b \
python app.py "$@"