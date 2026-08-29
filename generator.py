import json
import os
import re
from typing import Any

import requests

from schema import IGCarouselDeck, IGSlide


class CarouselGenerator:
    """
    Instagram carousel JSON generator using local Ollama.

    Default:
        Ollama: http://webmaster-ai.local:11434
        Model : qwen3:8b
    The model response is normalized before Pydantic validation so that
    harmless schema omissions from an SLM do not stop the pipeline.
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
            or "http://localhost:11434"
        ).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL") or "qwen3:8b"
        self.timeout = timeout
        self.chat_url = f"{self.ollama_host}/api/chat"

        print(f"Ollama host : {self.ollama_host}")
        print(f"Ollama model: {self.model}")
        print(f"Ollama timeout: {self.timeout}")
        print(f"Ollama chat URL: {self.chat_url}")

    def check_connection(self) -> None:
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

        installed = {
            m.get("name")
            for m in response.json().get("models", [])
            if m.get("name")
        }

        # Ollama may report qwen3:8b exactly, so first try exact.
        if self.model not in installed:
            raise RuntimeError(
                f"Ollama model '{self.model}' is not installed.\n"
                f"Installed models: {sorted(installed)}\n"
                f"Run: ollama pull {self.model}"
            )

    def _build_prompt(self, source_text: str) -> list[dict[str, str]]:
        system_prompt = """
You are a professional Instagram carousel designer.

Create EXACTLY 6 Instagram slides from the supplied source.

MANDATORY JSON SCHEMA:
{
  "topic": "short topic",
  "theme_color": "dark_mode",
  "slides": [
    {
      "slide_number": 1,
      "slide_type": "hook",
      "title": "short title",
      "subtitle_or_body": "short supporting text",
      "bullets": [],
      "highlighted_stat": null,
      "stat_label": null
    }
  ]
}

Rules:
- Return JSON only. No Markdown.
- EXACTLY 6 slides.
- slide_number must be 1 through 6.
- slide 1 must be "hook".
- slides 2-5 should be "content_list" or "key_metric".
- slide 6 must be "cta".
- Every slide MUST contain title, slide_number and slide_type.
- Use subtitle_or_body and/or up to 3 bullets.
- Do not invent facts.
- Preserve source numbers, dates and names.
- Keep text concise enough for a 1080x1350 Instagram slide.
- Never output fields named "headline" or "body"; use "title" and "subtitle_or_body".
- Do not create image_url fields.
- If a fact is unavailable, omit that fact rather than inventing it.
- Slide 6 may use a generic editorial CTA such as "Save this post" or
  "Follow for more updates"; it must not claim an unsupported application action.
""".strip()

        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Create the six-slide Instagram carousel from this source:\n\n"
                    + source_text
                ),
            },
        ]

    @staticmethod
    def _clean_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return " ".join(str(x).strip() for x in value if str(x).strip())
        return str(value).strip()

    def _normalize_slide(self, raw: dict, index: int) -> dict:
        # Accept common model aliases so a small model cannot break the pipeline.
        title = self._clean_text(
            raw.get("title")
            or raw.get("headline")
            or raw.get("heading")
            or f"Key point {index}"
        )

        body = self._clean_text(
            raw.get("subtitle_or_body")
            or raw.get("body")
            or raw.get("subtitle")
            or raw.get("description")
        )

        bullets = raw.get("bullets")
        if not bullets and raw.get("points"):
            bullets = raw.get("points")
        if isinstance(bullets, str):
            bullets = [x.strip(" •-\t") for x in re.split(r"[\n;]+", bullets) if x.strip()]
        if isinstance(bullets, list):
            bullets = [self._clean_text(x) for x in bullets if self._clean_text(x)]
            bullets = bullets[:3]
        else:
            bullets = None

        raw_type = str(raw.get("slide_type", "")).lower()
        if raw_type not in {"hook", "content_list", "key_metric", "cta"}:
            raw_type = "hook" if index == 1 else ("cta" if index == 6 else "content_list")

        return {
            "slide_number": index,
            "slide_type": raw_type,
            "title": title[:80],
            "subtitle_or_body": body[:500] or None,
            "bullets": bullets,
            "highlighted_stat": self._clean_text(
                raw.get("highlighted_stat") or raw.get("stat")
            ) or None,
            "stat_label": self._clean_text(
                raw.get("stat_label") or raw.get("stat_title")
            ) or None,
        }

    def _normalize_deck(self, data: dict, source_text: str) -> dict:
        raw_slides = data.get("slides")
        if not isinstance(raw_slides, list):
            raw_slides = []

        # Normalize whatever the model produced.
        slides = [
            self._normalize_slide(raw, i + 1)
            for i, raw in enumerate(raw_slides[:6])
            if isinstance(raw, dict)
        ]

        # Guarantee six usable slides. Missing slides are deterministic,
        # source-safe fillers rather than fabricated facts.
        filler_titles = [
            "The key takeaway",
            "What this means",
            "Key details",
            "What to remember",
            "Bottom line",
            "Save this update",
        ]

        while len(slides) < 6:
            i = len(slides) + 1
            slide_type = "hook" if i == 1 else ("cta" if i == 6 else "content_list")
            slides.append(
                {
                    "slide_number": i,
                    "slide_type": slide_type,
                    "title": filler_titles[i - 1],
                    "subtitle_or_body": (
                        "See the source information in the preceding slides."
                        if i < 6
                        else "Save this post for reference."
                    ),
                    "bullets": None,
                    "highlighted_stat": None,
                    "stat_label": None,
                }
            )

        slides = slides[:6]
        slides[0]["slide_type"] = "hook"
        slides[5]["slide_type"] = "cta"
        for i, slide in enumerate(slides, 1):
            slide["slide_number"] = i

        topic = self._clean_text(data.get("topic")) or "Instagram Update"
        theme = data.get("theme_color", "dark_mode")
        if theme not in {"dark_mode", "light_clean", "bold_brand"}:
            theme = "dark_mode"

        return {
            "topic": topic[:120],
            "theme_color": theme,
            "slides": slides,
        }

    def generate_carousel_json(self, source_text: str) -> dict[str, Any]:
        self.check_connection()

        payload = {
            "model": self.model,
            "messages": self._build_prompt(source_text),
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.15,
                "num_ctx": 8192,
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
                    detail = exc.response.text[:3000]
                except Exception:
                    pass

            raise RuntimeError(
                f"Ollama generation failed: {exc}\n{detail}"
            ) from exc

        result = response.json()

        content = (
            result.get("message", {}).get("content", "")
            or ""
        ).strip()

        if not content:
            raise RuntimeError("Ollama returned an empty response.")

        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content).strip()

        try:
            raw = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Ollama returned invalid JSON.\n\nRAW RESPONSE:\n" + content
            ) from exc

        data = self._normalize_deck(raw, source_text)

        try:
            validated = IGCarouselDeck.model_validate(data)
        except Exception as exc:
            raise RuntimeError(
                "Normalized carousel JSON failed schema validation.\n\n"
                f"{exc}\n\n"
                f"JSON:\n{json.dumps(data, indent=2, ensure_ascii=False)}"
            ) from exc

        return validated.model_dump()