cat > run.sh <<'EOF'
#!/usr/bin/env bash

set -e

export OLLAMA_HOST="${OLLAMA_HOST:-http://webmaster-ai.local:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3:8b}"

echo "=============================================="
echo " Instagram Carousel Generator"
echo "=============================================="
echo "Ollama host : $OLLAMA_HOST"
echo "Ollama model: $OLLAMA_MODEL"
echo

echo "[1] Testing Ollama..."
curl -fsS "$OLLAMA_HOST/api/tags" >/tmp/ig_ollama_tags.json

echo "[2] Ollama is reachable."
echo

echo "[3] Running application..."
python app.py

echo
echo "=============================================="
echo " Application finished"
echo "=============================================="
EOF

chmod 777 run.sh
./run.sh