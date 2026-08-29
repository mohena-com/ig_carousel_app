from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class JobPost(BaseModel):
    name: str
    vacancies: Optional[int] = None
    qualification: Optional[str] = None
    experience: Optional[str] = None

class LinkItem(BaseModel):
    label: str
    url: str

class IGCard(BaseModel):
    label: Optional[str] = None
    value: str
    meta: Optional[str] = None

class IGSlide(BaseModel):
    slide_number: int
    slide_type: str
    title: str = Field(max_length=100)
    eyebrow: Optional[str] = None
    subtitle: Optional[str] = None
    cards: List[IGCard] = Field(default_factory=list)
    bullets: List[str] = Field(default_factory=list)
    footer_note: Optional[str] = None

class JobFacts(BaseModel):
    organisation: Optional[str] = None
    recruitment_name: Optional[str] = None
    advertisement_no: Optional[str] = None
    total_vacancies: Optional[int] = None
    posts: List[JobPost] = Field(default_factory=list)
    application_start: Optional[str] = None
    application_end: Optional[str] = None
    fee_payment_last_date: Optional[str] = None
    correction_dates: List[str] = Field(default_factory=list)
    exam_dates: List[str] = Field(default_factory=list)
    other_dates: List[str] = Field(default_factory=list)
    age_limit: Optional[str] = None
    age_relaxation: Optional[str] = None
    fees: List[str] = Field(default_factory=list)
    payment_mode: Optional[str] = None
    selection_process: List[str] = Field(default_factory=list)
    salary: Optional[str] = None
    stipend: Optional[str] = None
    work_location: Optional[str] = None
    application_steps: List[str] = Field(default_factory=list)
    links: List[LinkItem] = Field(default_factory=list)
    source_url: Optional[str] = None
    conflicts: List[str] = Field(default_factory=list)
    raw_sections: Dict[str, str] = Field(default_factory=dict)
