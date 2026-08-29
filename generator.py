import json
import os
from typing import Any

import requests

from schema import IGCarouselDeck


class CarouselGenerator:
    """
    Instagram carousel JSON generator using local Ollama.

    Default:
        Ollama: http://webmaster-ai.local:11434
        Model : qwen3:8b
    """

    def __init__(
        self,
        ollama_host: str | None = None,
        model: str | None = None,
        timeout: int = 300,
    ):
        self.ollama_host = (
            ollama_host
            or os.getenv("OLLAMA_HOST")
            or "http://webmaster-ai.local:11434"
        ).rstrip("/")

        self.model = (
            model
            or os.getenv("OLLAMA_MODEL")
            or "qwen3:8b"
        )

        self.timeout = timeout

        self.chat_url = f"{self.ollama_host}/api/chat"

        print(f"Ollama host : {self.ollama_host}")
        print(f"Ollama model: {self.model}")

    def check_connection(self) -> None:
        """Verify that Ollama is reachable and the requested model exists."""

        try:
            response = requests.get(
                f"{self.ollama_host}/api/tags",
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.ollama_host}: {exc}"
            ) from exc

        models = response.json().get("models", [])

        installed = {
            m.get("name")
            for m in models
            if m.get("name")
        }

        # Ollama may report qwen3:8b exactly, so first try exact.
        if self.model not in installed:
            raise RuntimeError(
                f"Ollama model '{self.model}' is not installed.\n"
                f"Installed models: {sorted(installed)}\n\n"
                f"Run:\n"
                f"  ollama pull {self.model}"
            )

    def _build_prompt(self, source_text: str) -> list[dict[str, str]]:
        system_prompt = """
You are a professional Instagram carousel designer.

Your task is to transform the supplied source material into a
high-quality Instagram carousel.

IMPORTANT RULES:

1. Return JSON only.
2. Do not return Markdown.
3. Do not invent facts.
4. Use only information supported by the supplied source.
5. Keep every slide concise enough to fit visually.
6. Do not overload slides with paragraphs.
7. Prioritize the most important information.
8. Use short headlines and compact bullet points.
9. The carousel should look professionally designed.
10. Preserve important numbers, dates, names and URLs exactly.
11. If information is unavailable, do not fabricate it.
12. Follow the IGCarouselDeck schema supplied by the application.

The output must be valid JSON suitable for Pydantic validation.
""".strip()

        user_prompt = f"""
Create the Instagram carousel from the following source material.

SOURCE MATERIAL
================
{source_text}
================

Return ONLY the JSON object.
""".strip()

        return [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]

    def generate_carousel_json(
        self,
        source_text: str,
    ) -> dict[str, Any]:

        self.check_connection()

        payload = {
            "model": self.model,
            "messages": self._build_prompt(source_text),
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2,
            },
        }

        try:
            response = requests.post(
                self.chat_url,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

        except requests.RequestException as exc:
            detail = ""

            if getattr(exc, "response", None) is not None:
                try:
                    detail = exc.response.text[:2000]
                except Exception:
                    pass

            raise RuntimeError(
                f"Ollama generation failed: {exc}\n"
                f"{detail}"
            ) from exc

        result = response.json()

        content = (
            result.get("message", {})
            .get("content", "")
            .strip()
        )

        if not content:
            raise RuntimeError(
                "Ollama returned an empty response."
            )

        # Defensive cleanup in case the model ignored the
        # JSON-only instruction.
        if content.startswith("```"):
            content = content.replace(
                "```json",
                "",
                1,
            ).replace(
                "```",
                "",
            ).strip()

        try:
            data = json.loads(content)

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Ollama returned invalid JSON.\n\n"
                f"RAW RESPONSE:\n{content}"
            ) from exc

        # Validate against the project's existing Pydantic schema.
        try:
            validated = IGCarouselDeck.model_validate(data)
        except Exception as exc:
            raise RuntimeError(
                "Generated carousel JSON failed schema validation.\n\n"
                f"{exc}\n\n"
                f"GENERATED JSON:\n"
                f"{json.dumps(data, indent=2, ensure_ascii=False)}"
            ) from exc

        return validated.model_dump()