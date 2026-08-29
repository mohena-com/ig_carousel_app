from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class IGSlide(BaseModel):
    slide_number: int
    slide_type: Literal["hook", "content_list", "key_metric", "cta"]
    title: str = Field(description="Bold scroll-stopping headline, max 6-8 words")
    subtitle_or_body: Optional[str] = Field(None, description="Supporting context under 30 words")
    bullets: Optional[List[str]] = Field(None, description="Max 3 concise key points")
    highlighted_stat: Optional[str] = Field(None, description="Large stat callout, e.g. '+145%'")
    stat_label: Optional[str] = Field(None, description="Label for stat callout")

class IGCarouselDeck(BaseModel):
    topic: str
    theme_color: Literal["dark_mode", "light_clean", "bold_brand"] = "dark_mode"
    slides: List[IGSlide] = Field(min_length=5, max_length=8)
