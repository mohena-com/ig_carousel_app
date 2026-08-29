ig_carousel_app/
│
├── schema.py          # Pydantic schema for Instagram carousels
├── train.py           # Unsloth Fine-Tuning script (QLoRA for Qwen2.5-3B)
├── generator.py       # Inference engine using vLLM (Guided Decoding)
├── renderer.py        # HTML/CSS to 1080x1350 PNG generator using Playwright
├── app.py             # CLI Entry Point & Pipeline Orchestrator
└── requirements.txt   # Core Dependencies