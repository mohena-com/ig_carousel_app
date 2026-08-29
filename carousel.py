"""Build a six-slide deck without lossy summarisation.

Facts are never generated here. This module only decides how extracted facts
are laid out. It can therefore guarantee that available fields are not silently
lost because an LLM decided to return only three bullets.
"""
from schema import JobFacts, IGSlide, IGCard
from parser import parse_eligibility_sections


def c(label, value, meta=None):
    return IGCard(label=label, value=str(value), meta=meta)


def chunks(items, n):
    for i in range(0,len(items),n): yield items[i:i+n]


def make_deck(f: JobFacts):
    org=f.organisation or "Government Recruitment"
    name=f.recruitment_name or "Recruitment / Examination 2026"
    total=f.total_vacancies
    total_label=f"{total:,} Vacancies" if total is not None else "Recruitment Details"

    slides=[]
    hero_cards=[c("VACANCIES",total_label)] if total is not None else []
    hero_bullets=[]
    if f.application_start and f.application_end:
        hero_bullets.append(f"Applications: {f.application_start} → {f.application_end}")
    slides.append(IGSlide(slide_number=1,slide_type="hook",title="New Recruitment Alert",eyebrow=org,subtitle=name,cards=hero_cards,bullets=hero_bullets,footer_note=("⚠ Source conflict: " + f.conflicts[0] if f.conflicts else None)))

    # Posts are usually short enough for one dense two-column slide. The current
    # source set has at most 15 structured posts; the renderer can switch to a
    # tighter card style for larger sets.
    post_cards=[c(p.name, f"{p.vacancies:,}" if p.vacancies is not None else "") for p in f.posts]
    if post_cards:
        slides.append(IGSlide(slide_number=2,slide_type="posts",title="Posts & Vacancies",eyebrow=org,cards=post_cards,footer_note="Vacancy counts are reproduced from the source."))
    else:
        fallback=[]
        if total is not None: fallback.append(c("Total vacancies",f"{total:,}"))
        if f.advertisement_no: fallback.append(c("Advertisement",f.advertisement_no))
        slides.append(IGSlide(slide_number=2,slide_type="posts",title="Recruitment Snapshot",eyebrow=org,cards=fallback))

    elig_cards=[c(p.name,p.qualification,p.experience) for p in f.posts if p.qualification]
    # When there are many post-specific entries, reserve slide 4 as the second
    # eligibility page and append administrative facts after them.
    split=len(elig_cards)>7
    first_elig=elig_cards[:7] if split else elig_cards
    rest_elig=elig_cards[7:] if split else []
    if not first_elig:
        blocks=parse_eligibility_sections(f.raw_sections.get("ELIGIBILITY", "") + "\n" + f.raw_sections.get("APPLICATION FEE", ""))
        for h,b in blocks[:4]:
            # Preserve alternatives as separate compact cards instead of one
            # giant paragraph. This is especially useful for CTET-style data.
            clauses=[x.strip() for x in __import__("re").split(r"\s+OR\s+",b) if x.strip()]
            expanded=[]
            for clause in clauses:
                if len(clause)<=300: expanded.append(clause); continue
                parts=[x.strip() for x in __import__("re").split(r"(?<=\.)\s+",clause) if x.strip()]
                buf=""
                for part in parts:
                    if buf and len(buf)+1+len(part)>300:
                        expanded.append(buf); buf=part
                    else: buf=(buf+" "+part).strip()
                if buf: expanded.append(buf)
            for idx,clause in enumerate(expanded):
                first_elig.append(c(f"{h.split(':')[0]} • Option {idx+1}",clause))
        if f.age_limit: first_elig.append(c("Age limit",f.age_limit,f.age_relaxation))
    # Fallback eligibility (e.g. CTET) can also create many cards. Split it
    # before rendering so no content is clipped.
    if not split and len(first_elig)>7:
        split=True
        rest_elig=first_elig[7:]
        first_elig=first_elig[:7]
    elig_title=("Post-wise Eligibility" + (" • 1/2" if split else "")) if f.posts else ("Eligibility & Age" + (" • 1/2" if split else ""))
    slides.append(IGSlide(slide_number=3,slide_type="eligibility",title=elig_title,eyebrow=org,cards=first_elig,footer_note="Check the official notification for complete conditions." if first_elig else None))

    admin=[]
    if f.age_limit: admin.append(c("Age limit",f.age_limit,f.age_relaxation))
    for x in f.fees: admin.append(c("Application fee",x))
    if f.fee_payment_last_date: admin.append(c("Fee payment last date",f.fee_payment_last_date))
    if f.salary: admin.append(c("Salary / Pay",f.salary))
    if f.stipend: admin.append(c("Stipend",f.stipend))
    for x in f.selection_process[:4]: admin.append(c("Selection",x))
    if rest_elig:
        # Keep slide 4 focused: it is the continuation of the eligibility
        # list. Administrative facts move to slide 5 so no card is clipped.
        slides.append(IGSlide(slide_number=4,slide_type="eligibility",title=("Post-wise Eligibility • 2/2" if f.posts else "Eligibility & Age • 2/2"),eyebrow=org,cards=rest_elig,footer_note="Continued from the previous slide."))
    else:
        if not admin:
            for x in f.application_steps[:5]: admin.append(c("Application step",x))
        slides.append(IGSlide(slide_number=4,slide_type="fees",title="Fees • Age • Selection • Pay",eyebrow=org,cards=admin,footer_note="Only information available in the source is shown." if admin else None))

    dates=[]
    if f.application_start: dates.append(c("Application starts",f.application_start))
    if f.application_end: dates.append(c("Application closes",f.application_end))
    if f.fee_payment_last_date and not rest_elig: dates.append(c("Fee payment",f.fee_payment_last_date))
    for x in f.correction_dates: dates.append(c("Correction",x))
    for x in f.exam_dates: dates.append(c("Exam",x))
    for x in f.other_dates: dates.append(c("Other important date",x))
    if rest_elig:
        # In the long-eligibility case, slide 5 carries the admin information.
        dates = dates + admin
    usable_steps=[x for x in f.application_steps if x not in {".","September 2026","Exam Online Form"}]
    bullets=usable_steps[:6]
    slides.append(IGSlide(slide_number=5,slide_type="dates",title="Important Dates & Checklist",eyebrow=org,cards=dates,bullets=bullets,footer_note="Verify the final schedule in the official notification."))

    link_cards=[c(x.label,x.url) for x in f.links]
    if f.source_url: link_cards.append(c("Source page",f.source_url))
    slides.append(IGSlide(slide_number=6,slide_type="links",title="Official Links & How to Apply",eyebrow=org,cards=link_cards,bullets=usable_steps[:4],footer_note="Scan the QR code to open an official link. Check the notification before applying."))
    return {"topic":name,"organisation":org,"slides":[s.model_dump() for s in slides]}
