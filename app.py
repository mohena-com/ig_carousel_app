import argparse
import asyncio
import os
from pathlib import Path

from generator import CarouselGenerator
from renderer import render_deck_to_images


DEFAULT_SAMPLE = """
We analyzed 500 tech startups in 2026. The top 5% converted 3 times more leads
by adopting automated video onboarding. Companies using manual onboarding took
14 days to activate users, whereas automated workflows reduced activation
to under 2 hours. Start automating your workflow today to keep churn low.
""".strip()


def load_source(path: str | None) -> str:
    if not path:
        return DEFAULT_SAMPLE

    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Input file not found: {source}")

    text = source.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Input file is empty: {source}")

    return text


def main():
    parser = argparse.ArgumentParser(
        description="Generate an Instagram carousel using Ollama and render PNG slides."
    )
    parser.add_argument(
        "--input",
        "-i",
        help="UTF-8 text file containing the source material.",
    )
    parser.add_argument(
        "--ollama-host",
        default=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        help="Ollama URL.",
    )
    parser.add_argument(
        "--ollama-model",
        default=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        help="Ollama model name.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Ollama request timeout in seconds.",
    )

    args = parser.parse_args()

    source_text = load_source(args.input)

    print("==============================================")
    print(" Instagram Carousel Generator")
    print("==============================================")
    print(f"Ollama host : {args.ollama_host}")
    print(f"Ollama model: {args.ollama_model}")
    print()

    print("Step 1: Checking Ollama and generating JSON...")
    generator = CarouselGenerator(
        ollama_host=args.ollama_host,
        model=args.ollama_model,
        timeout=args.timeout,
    )

    carousel_data = generator.generate_carousel_json(source_text)

    print("JSON generated successfully.")
    print()

    print("Step 2: Rendering PNG carousel images...")
    asyncio.run(render_deck_to_images(carousel_data))

    print()
    print("Success! Instagram Carousel generated in:")
    print("./output_carousel/")


if __name__ == "__main__":
    main()
