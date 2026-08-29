"""Deterministic parser for the normalized job-post TXT files.

Design goal: never ask an LLM to decide which facts deserve to survive into
an Instagram carousel. The TXT files already have predictable section
boundaries, so we extract first and design second.
"""
import re
from pathlib import Path
from typing import Optional
from schema import JobFacts, JobPost, LinkItem

SECTION_RE = re.compile(r"^([A-Z][A-Z /&-]+)\n[-=]{3,}\n(.*?)(?=\n[A-Z][A-Z /&-]+\n[-=]{3,}\n|\Z)", re.S | re.M)
DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
MONTH_DATE_RE = re.compile(r"\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b", re.I)
URL_RE = re.compile(r"https?://[^\s<>\"]+")
MONEY_RE = re.compile(r"(?:₹|Rs\.?\s*)?\d[\d,]*(?:\.\d+)?\s*/?-?", re.I)
GENERIC = re.compile(r"^(?:not found|not available|n/?a|unknown|null|see the advertisement.*|read the notification.*)$", re.I)


def clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s


def is_generic(s: str) -> bool:
    return not s or bool(GENERIC.match(clean(s)))


def split_sections(text: str) -> dict[str, str]:
    return {m.group(1).strip(): m.group(2).strip() for m in SECTION_RE.finditer(text)}


def first_non_generic(lines, predicate=lambda x: True) -> Optional[str]:
    for x in lines:
        x = clean(x)
        if x and not is_generic(x) and predicate(x):
            return x
    return None


def parse_org_and_name(lines):
    org = None; recruitment = None; adv = None
    cleaned=[clean(x) for x in lines if clean(x)]
    # Prefer the canonical "... Advt. No. ... : Short Details ..." row.
    for i,line in enumerate(cleaned):
        if "short details" in line.lower() and re.search(r"\bAdvt\.?\s*No\.?",line,re.I):
            m=re.search(r"\bAdvt\.?\s*No\.?\s*[:.]?\s*(.*?)\s*(?::\s*Short Details|$)",line,re.I)
            if m: adv=clean(m.group(1))
            if i>0: recruitment=clean(cleaned[i-1])
            if i>1 and not re.search(r"Age Limit|Minimum Age|Maximum Age|Published|Vacancies|Application",cleaned[i-2],re.I):
                org=cleaned[i-2]
            break
    # If the organisation was not in KEY INFORMATION, use the first strong
    # institutional name from the complete source in parse_job's fallback.
    if not recruitment:
        for x in cleaned:
            if len(x)<180 and re.search(r"\b(?:Recruitment|Online Form|Examination|Exam)\b",x,re.I) and not re.search(r"Short Details|Read the|See the|Age Relaxation|Advt\.?\s*No",x,re.I):
                recruitment=x; break
    return org, recruitment, adv

def extract_total(title: str, text: str) -> Optional[int]:
    # Explicit totals in the title are source facts. Handle both singular and
    # plural wording. Do not sum post counts here.
    m = re.search(r"(?:for|with|of)\s+(\d[\d,]*)\s+(?:Post|Posts|Vacanc(?:y|ies))\b", title, re.I)
    if not m:
        m = re.search(r"\b(\d[\d,]*)\s+(?:Post|Posts|Vacanc(?:y|ies))\b", title, re.I)
    return int(m.group(1).replace(",", "")) if m else None


def normalize_date_range(s: str):
    s = clean(s)
    # Keep original source wording when parsing dates; only normalize spaces.
    m = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})\s+(?:to|through|until|till|-|–)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})", s, re.I)
    return (m.group(1), m.group(2)) if m else (None, None)


def parse_application_dates(how: str):
    patterns = [
        r"(?:apply online|candidate can apply online|apply between|candidate can apply between|apply).*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})\s+(?:to|through|until|till|-|–)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})",
    ]
    for p in patterns:
        m=re.search(p,how,re.I|re.S)
        if m: return m.group(1),m.group(2)
    return normalize_date_range(how)


def parse_age(key: str):
    if not key: return None,None
    # Explicit scraper format: Minimum Age / Maximum Age values on following lines.
    m1=re.search(r"Minimum Age\s*:\s*\n?\s*(\d+\s*Years?)",key,re.I)
    m2=re.search(r"Maximum Age\s*:\s*\n?\s*(\d+\s*Years?)",key,re.I)
    age=None
    if m1 and m2: age=f"{m1.group(1)} to {m2.group(1)}"
    elif m1: age=f"Minimum {m1.group(1)}"
    elif m2: age=f"Maximum {m2.group(1)}"
    relax=None
    mr=re.search(r"Age Relaxation[^\n]*",key,re.I)
    if mr: relax=clean(mr.group(0))
    return age,relax


def parse_posts(elig: str):
    lines=[clean(x) for x in elig.splitlines() if clean(x)]
    posts=[]; i=0
    stop_words=("More Eligibility","Notification","Short Details","Skip to content","Post Date")
    while i < len(lines):
        line=lines[i]
        if any(w.lower() in line.lower() for w in stop_words): i+=1; continue
        # A post name followed by a standalone integer is the common format.
        if i+1<len(lines) and re.fullmatch(r"\d[\d,]*",lines[i+1]):
            name=line; count=int(lines[i+1].replace(",","")); j=i+2; q=[]
            while j<len(lines):
                if j+1<len(lines) and re.fullmatch(r"\d[\d,]*",lines[j+1]): break
                if any(w.lower() in lines[j].lower() for w in stop_words): break
                q.append(lines[j]); j+=1
            qualification=clean(" ".join(q))
            # Remove the boilerplate tail frequently appended by the scraper.
            qualification=re.sub(r"\s*(?:More Eligibility.*|.*Notification.*)$","",qualification,flags=re.I).strip()
            experience=None
            ex=re.findall(r"(?:Minimum |Post[- ]?qualification )?Experience[^.\n]*\.?|\b\d+\s*(?:Year|Years)\s+Experience\.?",qualification,re.I)
            if ex: experience=clean(" ".join(ex))
            posts.append(JobPost(name=name,vacancies=count,qualification=qualification or None,experience=experience))
            i=j; continue
        i+=1
    # Deduplicate exact repeats.
    out=[]; seen=set()
    for p in posts:
        key=(p.name,p.vacancies,p.qualification)
        if key not in seen: out.append(p); seen.add(key)
    return out


def parse_fees(fee: str):
    out=[]; payment=None
    for raw in fee.splitlines():
        x=clean(raw)
        if not x: continue
        if re.search(r"Eligibility Code|CTET Primary Level|Eligibility with Code",x,re.I): break
        if re.search(r"Pay the (?:Exam|Examination) Fee|Fee Through",x,re.I):
            payment=x; continue
        if re.search(r"(?:Last Date|Correction|Exam Date|Admit Card|Online Form|Schedule)",x,re.I):
            continue
        # Fee rows normally contain a category plus an amount.
        if re.search(r"(?:General|OBC|EWS|SC|ST|PH|Female|UR|MBC|BC|Other State|Divyang|All Category|Single Paper|Both Paper|Portal Charges)",x,re.I) and re.search(r"\d[\d,]*(?:\.\d+)?\s*/?-?",x):
            out.append(x)
    return out,payment

def parse_dates(fee: str):
    correction=[]; exams=[]; other=[]; fee_last=None
    lines=[clean(x) for x in fee.splitlines() if clean(x)]
    pending=None
    for i,x in enumerate(lines):
        dm=DATE_RE.search(x) or MONTH_DATE_RE.search(x)
        # Labels and values are sometimes split onto adjacent lines.
        if re.search(r"(?:Pay Exam Fee Last Date|Last Date Pay Exam Fee|Fee Payment Last Date)",x,re.I):
            pending="fee"; continue
        if re.search(r"(?:Correction Date|Correction|Form Correction)",x,re.I):
            pending="correction"; 
            if dm: correction.append(x); pending=None
            continue
        if re.search(r"(?:Exam Date|Paper .*Exam Date|Merit List)",x,re.I):
            pending="exam"
            if dm: exams.append(x); pending=None
            continue
        if pending and dm:
            if pending=="fee": fee_last=dm.group(0)
            elif pending=="correction": correction.append(x)
            elif pending=="exam": exams.append(x)
            pending=None; continue
        if dm and re.search(r"Last Date|Result|Admit Card|Exam|Merit List|City|Schedule|Correction|Application",x,re.I):
            other.append(x)
    return fee_last,correction,exams,other

def parse_links(section: str):
    links=[]
    # Split by line but also support several labels on one line.
    for raw in section.splitlines():
        x=clean(raw)
        for m in URL_RE.finditer(x):
            url=m.group(0).rstrip(".,;:)]}")
            before=x[:m.start()].strip(" -:")
            label="Official Notification"
            if re.search(r"Apply Online|Application",before,re.I): label="Apply Online"
            elif re.search(r"Official Website|Website",before,re.I): label="Official Website"
            elif re.search(r"Source",before,re.I): label="Source"
            links.append(LinkItem(label=label,url=url))
    return links



def parse_eligibility_sections(elig: str):
    """Extract named eligibility blocks when the scraper did not produce post/count rows."""
    lines=[clean(x) for x in elig.splitlines() if clean(x)]
    heads=[]
    for i,x in enumerate(lines):
        if re.search(r"Eligibility with Code|Eligibility Criteria",x,re.I) and not re.search(r"More Eligibility",x,re.I):
            heads.append((i,x))
    cards=[]
    for n,(i,h) in enumerate(heads):
        j=heads[n+1][0] if n+1<len(heads) else len(lines)
        body=clean(" ".join(lines[i+1:j]))
        body=re.sub(r"\s*More Eligibility.*$","",body,flags=re.I).strip()
        if body: cards.append((h,body))
    return cards

def parse_job(text: str) -> JobFacts:
    sections=split_sections(text)
    lines=text.splitlines()
    title=clean(lines[0]) if lines else ""
    key=sections.get("KEY INFORMATION","")
    key_lines=key.splitlines()
    org,recruitment,adv=parse_org_and_name(key_lines)
    # If Organisation: is usable, prefer it. Otherwise search the complete TXT
    # because some records place the institution only in later sections.
    org_candidates=[clean(x.split(":",1)[1]) for x in key_lines if x.lower().startswith("organisation:") and ":" in x]
    if org_candidates and not is_generic(org_candidates[0]): org=org_candidates[0]
    if not org:
        for x in lines:
            x=clean(x)
            if len(x)>160: continue
            if re.search(r"\b(?:Public Service Commission|Subordinate Service Selection Commission|Selection Commission|Examination Board|School Examination Board|Board of Secondary Education|Railway Recruitment Board|Railway Recruitment Cell|Airports Authority|Bank of India|Institute of|University|High Court|Employee Selection Board|Corporation Limited|Rojgar Sangam|Coach Factory|Atal Awasiya Vidyalaya|Local Self Government|Department of Post)\b",x,re.I) and not re.search(r"Eligibility|Notification|Online Form|Short Details|Read the|See the|Minimum Class|Age Relaxation|Advt\.?\s*No",x,re.I):
                org=x; break
    if not adv:
        am=re.search(r"\bAdvt\.?\s*No\.?\s*[:.]?\s*([A-Za-z0-9./‐–-]+)",text,re.I)
        if am: adv=am.group(1)
    total=extract_total(title,text)
    eligibility=sections.get("ELIGIBILITY","")
    posts=parse_posts(eligibility)
    eligibility_blocks=parse_eligibility_sections(eligibility)
    # Conflict check: title total vs explicit post counts.
    conflicts=[]
    if total is not None and posts:
        s=sum(p.vacancies or 0 for p in posts)
        if s and s!=total: conflicts.append(f"Title states {total} vacancies; post-wise eligibility counts sum to {s}.")
    how=sections.get("HOW TO APPLY","")
    fee=sections.get("APPLICATION FEE","")
    # Prefer an explicit application window in KEY INFORMATION. Re-open notices
    # often retain the original application dates in HOW TO APPLY.
    km=re.search(r"(?:Can Apply Online|Apply Online).*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})\s+(?:to|through|until|till|-|–)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})",key,re.I|re.S)
    if km: start,end=km.group(1),km.group(2)
    else: start,end=parse_application_dates(how)
    fee_last,correction,exams,other=parse_dates(fee)
    fees,payment=parse_fees(fee)
    age,relax=parse_age(key)
    selection=[]
    for x in sections.get("SELECTION PROCESS","").splitlines():
        x=clean(x)
        if x.startswith("-"): x=clean(x.lstrip("-• "))
        if x and x.lower() not in {clean(org or "").lower(),clean(recruitment or "").lower()} and not re.search(r"Online Form|Short Details|Advt\.?\s*No|Age Relaxation",x,re.I) and not is_generic(x) and not re.search(r"Short Details|Organisation|See the advertisement|Read the notification",x,re.I): selection.append(x)
    salary=None; stipend=None
    for x in sections.get("PAY / SALARY","").splitlines():
        x=clean(x)
        if x.startswith("-"): x=clean(x.lstrip("-• "))
        if x and x.lower() not in {clean(org or "").lower(),clean(recruitment or "").lower()} and not re.search(r"Online Form|Short Details|Advt\.?\s*No|Age Relaxation",x,re.I) and not is_generic(x) and not re.search(r"Short Details|Organisation|See the advertisement|Read the notification",x,re.I):
            if re.search(r"stipend",x,re.I): stipend=x
            else: salary=x
            break
    steps=[]
    for x in how.splitlines():
        x=clean(x)
        if x.startswith("-"): x=clean(x.lstrip("-• "))
        if x and not re.search(r"How to Fill|Sarkari Result|Candidate Can Apply|Notification.*Form 2026|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s+to\s+\d",x,re.I):
            steps.append(x)
    links=parse_links(sections.get("OFFICIAL LINKS", ""))
    source=None
    for x in URL_RE.findall(sections.get("SOURCE", "")):
        source=x.rstrip(".,;:)]}"); break
    return JobFacts(
        organisation=org,recruitment_name=recruitment,advertisement_no=adv,total_vacancies=total,
        posts=posts,application_start=start,application_end=end,fee_payment_last_date=fee_last,
        correction_dates=correction,exam_dates=exams,other_dates=other,age_limit=age,age_relaxation=relax,
        fees=fees,payment_mode=payment,selection_process=selection,salary=salary,stipend=stipend,
        application_steps=steps[:12],links=links,source_url=source,conflicts=conflicts,raw_sections=sections)


def parse_file(path: str|Path)->JobFacts:
    return parse_job(Path(path).read_text(encoding="utf-8"))
