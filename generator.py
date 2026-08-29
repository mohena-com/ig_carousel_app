import json
from vllm import LLM, SamplingParams
from vllm.sampling_params import GuidedDecodingParams
from schema import IGCarouselDeck

class CarouselGenerator:
    def __init__(self, model_path="qwen2.5_ig_carousel_lora"):
        self.guided_decoding = GuidedDecodingParams(json=IGCarouselDeck.model_json_schema())
        self.sampling_params = SamplingParams(
            temperature=0.2,
            max_tokens=1800,
            guided_decoding=self.guided_decoding
        )
        self.llm = LLM(model=model_path, quantization="bitsandbytes")

    def generate_carousel_json(self, source_text: str) -> dict:
        prompt = (
            f"<|im_start|>system\nYou are a micro-content copywriter. "
            f"Convert input text into an Instagram Carousel JSON schema.<|im_end|>\n"
            f"<|im_start|>user\n{source_text}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        outputs = self.llm.generate([prompt], self.sampling_params)
        json_str = outputs[0].outputs[0].text
        return json.loads(json_str)