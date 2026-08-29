import asyncio
import os
from generator import CarouselGenerator
from renderer import render_deck_to_images

def main():
    sample_text = """
    We analyzed 500 tech startups in 2026. The top 5% converted 3 times more leads 
    by adopting automated video onboarding. Companies using manual onboarding took 
    14 days to activate users, whereas automated workflows reduced activation 
    to under 2 hours. Start automating your workflow today to keep churn low.
    """

    print("Step 1: Generating JSON structure using fine-tuned SLM...")
    generator = CarouselGenerator(model_path="qwen2.5_ig_carousel_lora")
    carousel_data = generator.generate_carousel_json(sample_text)
    print("JSON generated successfully:")
    print(carousel_data)

    print("\nStep 2: Rendering PNG carousel images...")
    asyncio.run(render_deck_to_images(carousel_data))
    print("\nSuccess! Instagram Carousel generated in folder: ./output_carousel/")

def main():

    generator = CarouselGenerator(
        ollama_host=os.getenv(
            "OLLAMA_HOST",
            "http://webmaster-ai.local:11434",
        ),
        model=os.getenv(
            "OLLAMA_MODEL",
            "qwen3:8b",
        ),
    )

    # Your existing source text / carousel generation code
    # continues below this point.


if __name__ == "__main__":
    main()