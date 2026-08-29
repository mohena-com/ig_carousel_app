from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class IGSlide(BaseModel):
    slide_number: int
    slide_type: Literal["hook", "content_list", "key_metric", "cta"]
    title: str = Field(max_length=80)
    subtitle_or_body: Optional[str] = None
    bullets: Optional[List[str]] = Field(default=None, max_length=3)
    highlighted_stat: Optional[str] = None
    stat_label: Optional[str] = None


class IGCarouselDeck(BaseModel):
    topic: str
    theme_color: Literal["dark_mode", "light_clean", "bold_brand"] = "dark_mode"
    slides: List[IGSlide] = Field(min_length=6, max_length=6)
