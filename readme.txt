ig_carousel_app/
│
├── schema.py          # Pydantic schema for Instagram carousels
├── train.py           # Unsloth Fine-Tuning script (QLoRA for Qwen2.5-3B)
├── generator.py       # Inference engine using vLLM (Guided Decoding)
├── renderer.py        # HTML/CSS to 1080x1350 PNG generator using Playwright
├── app.py             # CLI Entry Point & Pipeline Orchestrator
└── requirements.txt   # Core Dependencies



```bash
python3.1 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3.1 main.py --max-jobs 3
```

```text
http://webmaster-ai.local:11434
```