# ig_carousel_app — Ollama six-slide version

This version uses the existing Ollama model instead of vLLM.

Default:
- Ollama: `http://webmaster-ai.local:11434`
- Model: `qwen3:8b`

## Run

```bash
./run.sh --input article.txt
```

or:

```bash
OLLAMA_HOST=http://localhost:11434 \
OLLAMA_MODEL=qwen3:8b \
./run.sh --input article.txt
```

Output:

```text
output_carousel/carousel.json
output_carousel/slide_1.png
...
output_carousel/slide_6.png
```

The generator normalizes common Qwen field mistakes (`headline`/`body`) into
the project's canonical schema and guarantees six slides before validation.
It does not invent source facts; missing factual content is replaced by
generic presentation-safe filler.
