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
     Stage 1:
        Source -> canonical semantic facts

    Stage 2:
        Canonical facts + source -> six-slide presentation

    The model is NOT treated as the source of truth. Critical fields are
    extracted and semantically bound before presentation generation.
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
        self.last_facts: dict[str, Any] = {}

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

        if self.model not in installed:
            raise RuntimeError(
                f"Ollama model '{self.model}' is not installed.\n"
                f"Installed models: {sorted(installed)}\n"
                f"Run: ollama pull {self.model}"
            )

    @staticmethod
    def _json_from_response(content: str) -> dict[str, Any]:
        content = (content or "").strip()

        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content).strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            # Recover a JSON object if the SLM added prose around it.
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if not match:
                raise RuntimeError(
                    "Ollama returned invalid JSON.\n\nRAW RESPONSE:\n" + content
                ) from exc
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                raise RuntimeError(
                    "Ollama returned invalid JSON.\n\nRAW RESPONSE:\n" + content
                ) from exc

        if not isinstance(data, dict):
            raise RuntimeError("Ollama JSON response is not an object.")

        return data

    def _ollama_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temperature,
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
        content = result.get("message", {}).get("content", "")

        if not content:
            raise RuntimeError("Ollama returned an empty response.")

        return self._json_from_response(content)

    @staticmethod
    def _text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return " ".join(str(x).strip() for x in value if str(x).strip())
        return str(value).strip()

    @staticmethod
    def _extract_date_candidates(source_text: str) -> list[str]:
        """
        Collect date-like strings for the fact extractor. This is only a
        candidate list; semantic assignment remains an explicit extraction
        step. It prevents the presentation model from freely inventing dates.
        """
        patterns = [
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
            r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
            r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b",
        ]
        found = []
        for pattern in patterns:
            found.extend(re.findall(pattern, source_text, flags=re.IGNORECASE))
        return list(dict.fromkeys(found))

    def _build_fact_prompt(self, source_text: str) -> list[dict[str, str]]:
        date_candidates = self._extract_date_candidates(source_text)

        system = """
You are a meticulous information-extraction engine for an Instagram
government-job/news content pipeline.

Extract CANONICAL FACTS from the ENTIRE source.

This is an extraction task, NOT a writing task.

RULES:
1. Use only facts explicitly supported by the source.
2. Never guess or infer missing numbers, dates, URLs, qualifications,
   salaries, fees, vacancy counts or selection criteria.
3. Search the ENTIRE source, including tables, HOW TO APPLY sections,
   notes, footer links and detailed sections.
4. Do not assume the first occurrence of a date is the application date.
5. Assign every date a semantic meaning from its surrounding context.
6. Application start/end must come from application/registration wording.
7. A notification date, advertisement date, exam date, fee deadline,
   correction date or walk-in date is NOT an application start/end date.
8. Preserve URLs exactly.
9. If a field is genuinely absent, use null or [].
10. Do not use "Not found", "NA", "unknown", or invented placeholders
    as factual values.
11. Post names and vacancy counts must remain separate.
12. If total vacancy is not explicitly stated, total_vacancies must be null.
13. If a source contains contradictory facts, report both in conflicts and
    do not silently choose an unsupported value.

Return ONLY this JSON structure:

{
  "organisation": null,
  "department": null,
  "recruitment_name": null,
  "advertisement_no": null,
  "recruitment_year": null,
  "total_vacancies": null,
  "posts": [
    {
      "name": "...",
      "vacancies": null,
      "qualification": null,
      "experience": null
    }
  ],
  "application_start": null,
  "application_end": null,
  "fee_payment_last_date": null,
  "correction_start": null,
  "correction_end": null,
  "exam_date": null,
  "admit_card_date": null,
  "other_important_dates": [],
  "eligibility": {
    "qualification": null,
    "experience": null,
    "age_limit": null,
    "age_relaxation": null
  },
  "fees": [],
  "selection_process": [],
  "salary": null,
  "stipend": null,
  "work_location": null,
  "official_application_url": null,
  "official_notification_url": null,
  "official_website": null,
  "source_url": null,
  "important_instructions": [],
  "conflicts": []
}

DATE CANDIDATES FOUND BY PRE-SCAN:
""" + json.dumps(date_candidates, ensure_ascii=False)

        return [
            {"role": "system", "content": system.strip()},
            {
                "role": "user",
                "content": (
                    "Extract canonical facts from this complete source. "
                    "Do not omit information merely because it appears later "
                    "in the document.\n\nSOURCE:\n" + source_text
                ),
            },
        ]

    def _extract_canonical_facts(self, source_text: str) -> dict[str, Any]:
        facts = self._ollama_json(
            self._build_fact_prompt(source_text),
            temperature=0.05,
        )

        # Ensure all expected keys exist, while retaining only source-derived
        # values returned by the extractor.
        defaults = {
            "organisation": None,
            "department": None,
            "recruitment_name": None,
            "advertisement_no": None,
            "recruitment_year": None,
            "total_vacancies": None,
            "posts": [],
            "application_start": None,
            "application_end": None,
            "fee_payment_last_date": None,
            "correction_start": None,
            "correction_end": None,
            "exam_date": None,
            "admit_card_date": None,
            "other_important_dates": [],
            "eligibility": {},
            "fees": [],
            "selection_process": [],
            "salary": None,
            "stipend": None,
            "work_location": None,
            "official_application_url": None,
            "official_notification_url": None,
            "official_website": None,
            "source_url": None,
            "important_instructions": [],
            "conflicts": [],
        }

        normalized = defaults.copy()
        normalized.update(facts)

        # Never allow model strings such as "Not found" to masquerade as facts.
        def null_missing(v):
            if isinstance(v, str) and v.strip().lower() in {
                "not found", "not available", "n/a", "na", "unknown", "null"
            }:
                return None
            return v

        for key in (
            "organisation", "department", "recruitment_name",
            "advertisement_no", "recruitment_year", "total_vacancies",
            "application_start", "application_end",
            "fee_payment_last_date", "correction_start", "correction_end",
            "exam_date", "admit_card_date", "salary", "stipend",
            "work_location", "official_application_url",
            "official_notification_url", "official_website", "source_url",
        ):
            normalized[key] = null_missing(normalized.get(key))

        return normalized

    def _build_presentation_prompt(
        self,
        source_text: str,
        facts: dict[str, Any],
    ) -> list[dict[str, str]]:

        system = """
You are a professional Instagram carousel designer specializing in
government jobs and factual informational content.

Create EXACTLY 6 slides.

CRITICAL ARCHITECTURE:
The CANONICAL FACTS below are the factual source of truth.
The original source is supplied only for context.

NEVER invent or alter a canonical fact.

If a fact is null or absent:
- do not display a label for it;
- do not create a fake value;
- do not write "Not Found", "NA", "Unknown", or similar;
- rearrange the available information to keep the slide visually complete.

DATE RULE:
Application dates are semantic fields, not generic dates.

If:
application_start = X
application_end = Y

then use exactly X and Y.

Never replace them with another date from the source.

Never convert:
- notification date
- advertisement date
- exam date
- fee deadline
- correction deadline
- walk-in date
into application start/end.

URL RULE:
Only label a URL according to its canonical semantic field.
An official notification URL must never be labelled "Apply Now".
An application URL may be labelled "Apply Online".
Preserve URLs exactly.

VACANCY RULE:
Do not manufacture total vacancies by adding post counts unless the
canonical facts explicitly provide the total.

POST RULE:
Preserve post names and post-specific vacancy counts.

DYNAMIC LAYOUT:
The six-slide structure is fixed, but each slide's content is dynamic.
Only show cards/labels for facts that exist.

VISUAL DIRECTION:
- professional Instagram editorial design
- strong hierarchy
- blue bars
- yellow sub-bars/highlights
- compact information cards
- short headlines
- clean spacing
- no dense paragraphs
- no empty cards
- no redundant labels

SLIDE 1 — JOB HOOK
Organisation + recruitment/job name + strongest verified metric if available.

SLIDE 2 — POSTS & VACANCIES
Post names and verified vacancy counts.
If counts are absent, emphasize available post names instead.

SLIDE 3 — ELIGIBILITY
Qualification, experience, age and post-specific requirements that exist.

SLIDE 4 — FEES / PAY / SELECTION
Dynamically include only available sections.

SLIDE 5 — APPLICATION / IMPORTANT DATES
Show application_start and application_end prominently when available.
Then show other verified dates only when available.
If application dates are unavailable, turn this into an IMPORTANT DATES
slide using verified dates instead. Do not fabricate an application window.

SLIDE 6 — HOW TO APPLY / OFFICIAL LINKS
Show available official application URL, notification URL, official website
and source URL with correct semantic labels.
Use a generic editorial CTA such as "Check the official notification before
applying." Do not claim that an application is currently open unless the
canonical dates/source support that statement.

OUTPUT:
Return JSON only, matching:
{
  "topic": "string",
  "theme_color": "dark_mode",
  "slides": [
    {
      "slide_number": 1,
      "slide_type": "hook",
      "title": "string",
      "subtitle_or_body": "string or null",
      "bullets": [],
      "highlighted_stat": "string or null",
      "stat_label": "string or null"
    }
  ]
}

Exactly 6 slides. No image_url field.
"""

        user = (
            "CANONICAL FACTS — SOURCE OF TRUTH\n"
            "================================\n"
            + json.dumps(facts, indent=2, ensure_ascii=False)
            + "\n\nORIGINAL SOURCE — CONTEXT ONLY\n"
            "================================\n"
            + source_text
        )

        return [
            {"role": "system", "content": system.strip()},
            {"role": "user", "content": user},
        ]

    @staticmethod
    def _normalize_slide(raw: dict, index: int) -> dict:
        def clean(value: Any) -> str:
            if value is None:
                return ""
            if isinstance(value, list):
                return " ".join(str(x).strip() for x in value if str(x).strip())
            return str(value).strip()

        title = clean(
            raw.get("title")
            or raw.get("headline")
            or raw.get("heading")
            or f"Key point {index}"
        )

        body = clean(
            raw.get("subtitle_or_body")
            or raw.get("body")
            or raw.get("subtitle")
            or raw.get("description")
        )

        bullets = raw.get("bullets") or raw.get("points")
        if isinstance(bullets, str):
            bullets = [
                x.strip(" •-\t")
                for x in re.split(r"[\n;]+", bullets)
                if x.strip()
            ]
        if isinstance(bullets, list):
            bullets = [clean(x) for x in bullets if clean(x)][:3]
        else:
            bullets = None

        slide_type = str(raw.get("slide_type", "")).lower()
        if slide_type not in {"hook", "content_list", "key_metric", "cta"}:
            slide_type = (
                "hook" if index == 1
                else "cta" if index == 6
                else "content_list"
            )

        return {
            "slide_number": index,
            "slide_type": slide_type,
            "title": title[:80],
            "subtitle_or_body": body[:500] or None,
            "bullets": bullets,
            "highlighted_stat": clean(
                raw.get("highlighted_stat") or raw.get("stat")
            ) or None,
            "stat_label": clean(
                raw.get("stat_label") or raw.get("stat_title")
            ) or None,
        }

    def _normalize_deck(
        self,
        data: dict[str, Any],
        facts: dict[str, Any],
    ) -> dict[str, Any]:

        raw_slides = data.get("slides")
        if not isinstance(raw_slides, list):
            raw_slides = []

        slides = [
            self._normalize_slide(raw, i + 1)
            for i, raw in enumerate(raw_slides[:6])
            if isinstance(raw, dict)
        ]

        filler = [
            (
                "Key takeaway",
                "Review the verified details before applying."
            ),
            (
                "Important details",
                "Use the information above as the verified summary."
            ),
            (
                "What to remember",
                "Check the official notification for complete conditions."
            ),
            (
                "Candidate checklist",
                "Confirm eligibility and required documents before applying."
            ),
            (
                "Important dates",
                "Check the verified dates shown in this carousel."
            ),
            (
                "Official information",
                "Check the official notification before applying."
            ),
        ]

        while len(slides) < 6:
            i = len(slides) + 1
            title, body = filler[i - 1]
            slides.append({
                "slide_number": i,
                "slide_type": (
                    "hook" if i == 1 else "cta" if i == 6 else "content_list"
                ),
                "title": title,
                "subtitle_or_body": body,
                "bullets": None,
                "highlighted_stat": None,
                "stat_label": None,
            })

        slides = slides[:6]
        slides[0]["slide_type"] = "hook"
        slides[5]["slide_type"] = "cta"

        for i, slide in enumerate(slides, 1):
            slide["slide_number"] = i

        topic = self._text(
            data.get("topic")
            or facts.get("recruitment_name")
            or facts.get("organisation")
            or "Instagram Update"
        )

        theme = data.get("theme_color", "dark_mode")
        if theme not in {"dark_mode", "light_clean", "bold_brand"}:
            theme = "dark_mode"

        return {
            "topic": topic[:120],
            "theme_color": theme,
            "slides": slides,
        }

    def generate_carousel_json(self, source_text: str) -> dict[str, Any]:
        if not source_text or not source_text.strip():
            raise ValueError("Source text is empty.")

        self.check_connection()

        print("Step 1A: Extracting canonical semantic facts...")
        facts = self._extract_canonical_facts(source_text)
        self.last_facts = facts

        print("Step 1B: Generating six-slide presentation...")
        raw_deck = self._ollama_json(
            self._build_presentation_prompt(source_text, facts),
            temperature=0.15,
        )

        deck = self._normalize_deck(raw_deck, facts)

        try:
            validated = IGCarouselDeck.model_validate(deck)
        except Exception as exc:
            raise RuntimeError(
                "Normalized carousel JSON failed schema validation.\n\n"
                f"{exc}\n\n"
                f"JSON:\n{json.dumps(deck, indent=2, ensure_ascii=False)}"
            ) from exc

        return validated.model_dump()
