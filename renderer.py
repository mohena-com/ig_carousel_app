
import os
import re
import html
import base64
from io import BytesIO
from urllib.parse import urlparse
from urllib.request import urlopen

import qrcode
from playwright.async_api import async_playwright

W, H = 1080, 1350

NAVY = "#0B2E59"
BLUE = "#145DA0"
INK = "#152235"
MUTED = "#667085"
LINE = "#D8E1EA"
SOFT = "#F5F8FB"
SOFT_BLUE = "#EAF3FA"
GOLD = "#E4A51C"
WHITE = "#FFFFFF"


def qr_data_uri(url):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color=NAVY, back_color=WHITE).convert("RGB")
    b = BytesIO()
    img.save(b, format="PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


def fetch_logo_data_uri(logo_domain):
    if not logo_domain:
        return ""

    logo_url = f"https://logos.hunter.io/{logo_domain}"
    try:
        with urlopen(logo_url, timeout=10) as response:
            content_type = response.headers.get_content_type() or "image/png"
            payload = response.read()
    except Exception as exc:
        print(f"Failed to fetch logo from {logo_url}: {exc}")
        return ""

    if not payload:
        return ""

    return f"data:{content_type};base64,{base64.b64encode(payload).decode('ascii')}"


def esc(x):
    return html.escape(str(x or ""))


def clean_text(x):
    """Remove presentation noise without changing the underlying fact."""
    if x is None:
        return ""
    s = str(x).replace("\r", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^[•●▪◦\-\–\—]\s*", "", s)
    return s


def _brand_mark():
    return "SD"


def _safe_cards(cards):
    return [c for c in cards if isinstance(c, dict)]


def _card_html(card, index=0):
    label = clean_text(card.get("label")) or "Details"
    value = clean_text(card.get("value"))
    meta = clean_text(card.get("meta"))
    return f"""
    <div class="info-card">
      <div class="card-top">
        <span class="card-dot"></span>
        <span class="label">{esc(label)}</span>
      </div>
      <div class="value">{esc(value)}</div>
      {f'<div class="meta">{esc(meta)}</div>' if meta else ""}
    </div>
    """


def _post_card_html(card, index=0):
    label = clean_text(card.get("label")) or "Post"
    value = clean_text(card.get("value"))
    meta = clean_text(card.get("meta"))
    count_label = "VACANCIES" if re.search(r"vacanc|post", label, re.I) else "DETAIL"
    return f"""
    <div class="post-row">
      <div class="post-index">{index + 1:02d}</div>
      <div class="post-copy">
        <div class="post-name">{esc(label)}</div>
        {f'<div class="post-meta">{esc(meta)}</div>' if meta else ""}
      </div>
      <div class="post-count">
        <div class="post-count-number">{esc(value) if value else "—"}</div>
        <div class="post-count-label">{count_label}</div>
      </div>
    </div>
    """


def _snapshot_card_html(card, index=0):
    """Dashboard-style card for the Recruitment Snapshot slide."""
    label = clean_text(card.get("label")) or "Details"
    value = clean_text(card.get("value"))
    meta = clean_text(card.get("meta"))
    cls = "snapshot-card snapshot-feature" if index == 0 else "snapshot-card"
    return f"""
    <div class="{cls}">
      <div class="snapshot-index">{index + 1:02d}</div>
      <div class="snapshot-copy">
        <div class="snapshot-label">{esc(label)}</div>
        <div class="snapshot-value">{esc(value) if value else "—"}</div>
        {f'<div class="snapshot-meta">{esc(meta)}</div>' if meta else ""}
      </div>
    </div>
    """


def _eligibility_tags_html(value):
    s = clean_text(value)
    tags = []
    degree_patterns = [
        r"\bB\.?\s*\.?(?:Tech|E)\b",
        r"\bM\.?\s*\.?(?:Tech|E)\b",
        r"\bMBA\b", r"\bMCA\b", r"\bBCA\b", r"\bBBA\b",
        r"\bBachelor(?:'s)?\s+Degree\b",
        r"\bEngineering\s+Degree\b",
        r"\bDiploma\b", r"\bITI\b",
        r"\bChartered\s+Accountant\b",
        r"\bCompany\s+Secretary\b",
        r"\bGraduate\b", r"\bPost\s+Graduate\b",
    ]
    qualification = ""
    for pattern in degree_patterns:
        m = re.search(pattern, s, re.I)
        if m:
            qualification = m.group(0)
            break
    if qualification:
        tags.append(("Q", "QUALIFICATION", qualification))

    marks = re.search(r"\b(\d{1,3})\s*%\s*(?:marks|aggregate)?", s, re.I)
    if marks:
        tags.append(("%", "MIN. MARKS", f"{marks.group(1)}%"))

    experience = re.search(r"\b(\d+(?:\.\d+)?)\s*(Years?|Months?)\b", s, re.I)
    if experience and re.search(r"\bexperience\b", s, re.I):
        tags.append(("E", "EXPERIENCE", experience.group(0)))

    return "".join(
        f"""
        <span class="eligibility-tag">
          <span class="eligibility-tag-icon">{esc(icon)}</span>
          <span class="eligibility-tag-label">{esc(label)}</span>
          <strong>{esc(val)}</strong>
        </span>
        """
        for icon, label, val in tags
    )


def _eligibility_card_html(card, index=0, compact=False):
    """Compact post-wise eligibility card that keeps all supplied text visible."""
    label = clean_text(card.get("label")) or "Post"
    value = clean_text(card.get("value"))
    meta = clean_text(card.get("meta"))
    cls = "eligibility-card eligibility-card-compact" if compact else "eligibility-card"
    return f"""
    <article class="{cls}">
      <div class="eligibility-card-head">
        <span class="card-dot"></span>
        <span class="eligibility-code">{esc(label)}</span>
      </div>
      {f'<div class="eligibility-tags">{_eligibility_tags_html(value)}</div>' if value else ""}
      <div class="eligibility-value">{esc(value) if value else "—"}</div>
      {f'<div class="eligibility-meta">{esc(meta)}</div>' if meta else ""}
    </article>
    """


def _fee_card_html(card, index=0, primary=False):
    """Financial card with stronger visual hierarchy for fee information."""
    label = clean_text(card.get("label")) or "Details"
    value = clean_text(card.get("value"))
    meta = clean_text(card.get("meta"))
    cls = "fee-card fee-primary-card" if primary else "fee-card"
    return f"""
    <div class="{cls}">
      <div class="card-top">
        <span class="card-dot"></span>
        <span class="label">{esc(label)}</span>
      </div>
      <div class="value">{esc(value) if value else "—"}</div>
      {f'<div class="meta">{esc(meta)}</div>' if meta else ""}
    </div>
    """


def _checklist_panel_html(bullets, title):
    """Render supplied bullets as a contained checklist panel."""
    if not bullets:
        return ""
    items = "".join(
        f"""
        <li>
          <span class="bullet-check">✓</span>
          <span>{esc(x)}</span>
        </li>
        """
        for x in bullets
    )
    return f"""
    <section class="checklist-panel">
      <div class="checklist-title">{esc(title)}</div>
      <ul class="bullet-list">{items}</ul>
    </section>
    """


def _date_card_html(card, index=0):
    label = clean_text(card.get("label")) or "Important date"
    value = clean_text(card.get("value"))
    meta = clean_text(card.get("meta"))
    return f"""
    <div class="date-row{' correction-row' if 'correction' in label.lower() else ''}{' long-date-row' if len(label) > 18 or len(value) > 24 else ''}">
      <div class="date-marker">{index + 1}</div>
      <div class="date-copy">
        <div class="label">{esc(label)}</div>
        <div class="date-value">{esc(value)}</div>
        {f'<div class="meta">{esc(meta)}</div>' if meta else ""}
      </div>
    </div>
    """


def _link_card_html(card):
    label = clean_text(card.get("label")) or "Official link"
    url = clean_text(card.get("value"))
    if not url:
        return ""
    return f"""
    <div class="link-card">
      <div class="link-copy">
        <div class="link-title">{esc(label)}</div>
        <div class="url">{esc(url)}</div>
      </div>
      <div class="qr-wrap">
        <img src="{qr_data_uri(url)}" alt="QR code">
      </div>
    </div>
    """


def _normalise_type(stype):
    s = clean_text(stype).lower()
    aliases = {
        "vacancy": "posts",
        "vacancies": "posts",
        "post": "posts",
        "eligibility_age": "eligibility",
        "eligibility & age": "eligibility",
        "fee": "fees",
        "application": "links",
        "official_links": "links",
        "timeline": "dates",
    }
    return aliases.get(s, s or "content")



def _extract_vacancy_total(deck):
    """
    Prefer the explicit deck-level total_vacancies field when it exists.
    If that field is missing, fall back to scanning slide cards for a
    vacancy value and strip out any textual label so only the number remains.
    """
    if isinstance(deck, dict):
        direct = deck.get("total_vacancies")
        if direct not in (None, ""):
            direct_text = clean_text(str(direct))
            if re.search(r"\d", direct_text):
                return direct_text

    candidates = []

    for slide in (deck.get("slides") or []):
        for card in (slide.get("cards") or []):
            if not isinstance(card, dict):
                continue

            label = clean_text(card.get("label")).lower()
            value = clean_text(card.get("value"))

            if not value:
                continue

            if any(term in label for term in (
                "total vacancies",
                "total vacancy",
                "vacancies",
                "vacancy",
            )):
                candidates.append(value)

    # Prefer an explicit "total vacancies" label.
    for slide in (deck.get("slides") or []):
        for card in (slide.get("cards") or []):
            if not isinstance(card, dict):
                continue
            label = clean_text(card.get("label")).lower()
            value = clean_text(card.get("value"))
            if value and "total vacancies" in label:
                match = re.search(r"(\d[\d,]*)", value)
                if match:
                    return match.group(1)

    for value in candidates:
        match = re.search(r"(\d[\d,]*)", value)
        if match:
            return match.group(1)

    return ""


def _extract_logo_domain(deck):
    """Extract the most likely organization domain from the deck's official links."""
    if not isinstance(deck, dict):
        return ""

    for slide in (deck.get("slides") or []):
        if not isinstance(slide, dict):
            continue

        for card in (slide.get("cards") or []):
            if not isinstance(card, dict):
                continue

            value = clean_text(card.get("value") or card.get("url") or card.get("link"))
            if not re.match(r"^https?://", value, re.I):
                continue

            parsed = urlparse(value)
            if parsed.netloc:
                return parsed.netloc

    return ""


def _extract_application_url(deck):
    """Find the most likely application/form URL for the Slide 1 QR."""
    candidates = []
    for slide in (deck.get("slides") or []) if isinstance(deck, dict) else []:
        if not isinstance(slide, dict):
            continue
        for card in (slide.get("cards") or []):
            if not isinstance(card, dict):
                continue
            url = clean_text(card.get("value") or card.get("url") or card.get("link"))
            if not re.match(r"^https?://", url, re.I):
                continue
            label = clean_text(card.get("label")).lower()
            score = 0
            if any(k in label for k in ("apply", "application", "online form", "registration")):
                score += 10
            if any(k in url.lower() for k in ("apply", "application", "registration", "register", "online-form", "form")):
                score += 5
            candidates.append((score, url))
    if not candidates:
        return ""
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _extract_application_dates(text):
    """Extract available application dates, including ISO dates."""
    value = clean_text(text)
    dates = re.findall(
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|20\d{2}-\d{2}-\d{2})\b",
        value,
    )
    return (dates[0], dates[1]) if len(dates) >= 2 else ((dates[0], "") if dates else ("", ""))


def _hook_highlight(subtitle):
    """Create a concise recruitment highlight from the source subtitle."""
    s = clean_text(subtitle)
    if not s:
        return "Government Recruitment"
    s = re.sub(r"\b(?:recruitment|online form|main online form)\b.*$", "", s, flags=re.I)
    s = re.sub(r"\b(?:20\d{2}|20\d{2}-\d{2})\b", "", s)
    s = re.sub(r"\s+", " ", s).strip(" -–—,|")
    s = re.sub(r"\bnon[\s-]+teaching\s+post\b", "Non-Teaching Posts", s, flags=re.I)
    s = re.sub(r"\bnon[\s-]+teaching\s+posts?\b", "Non-Teaching Posts", s, flags=re.I)
    return s or clean_text(subtitle) or "Government Recruitment"


def _extract_application_highlight(bullets):
    """Use the supplied application/date bullet without inventing dates."""
    for bullet in bullets:
        b = clean_text(bullet)
        if not b:
            continue
        if re.search(r"\bapplications?\b", b, re.I) or re.search(
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", b
        ):
            return b
    return ""

def _looks_like_qualification(text):
    """Detect qualification/eligibility text accidentally placed in the eyebrow."""
    s = clean_text(text).lower()
    if not s:
        return False
    patterns = (
        r"\b(b\.?\s*tech|b\.?\s*e\.?|m\.?\s*tech|m\.?\s*e\.?|mca|mba|m\.c\.a)\b",
        r"\b(bachelor|master|degree|diploma|ph\.?d)\b",
        r"\b(qualification|recognized university|recognised university)\b",
        r"\bminimum\s+\d+\s*%",
        r"\bmarks\b|\bcgpa\b",
        r"\bany\s+(recognized|recognised)\s+university\b",
    )
    return any(re.search(p, s, re.I) for p in patterns)


_PORTAL_HOSTS = {
    "sarkariresult.com",
    "sarkariresult.org",
    "freejobalert.com",
    "jagranjosh.com",
    "careerpower.in",
    "adda247.com",
    "testbook.com",
    "rojgarresult.com",
    "indgovtjobs.in",
    "fresherslive.com",
    "govtjobguru.in",
    "naukrinama.com",
    "jobapply.in",
    "sarkariexam.com",
    "india.gov.in",
    "gov.in",  # handled as a suffix below
}


def _iter_deck_urls(deck):
    """Collect URLs from cards/bullets without assuming a particular slide layout."""
    urls = []
    if not isinstance(deck, dict):
        return urls

    for slide in (deck.get("slides") or []):
        if not isinstance(slide, dict):
            continue

        for card in (slide.get("cards") or []):
            if not isinstance(card, dict):
                continue
            for key in ("value", "url", "link"):
                value = clean_text(card.get(key))
                if re.match(r"^https?://", value, re.I):
                    urls.append(value)

        for bullet in (slide.get("bullets") or []):
            value = clean_text(bullet)
            urls.extend(re.findall(r"https?://[^\s<>\"]+", value, re.I))

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(urls))


def _url_host(url):
    m = re.match(r"^https?://([^/]+)", clean_text(url), re.I)
    return m.group(1).lower().split(":")[0] if m else ""


def _is_job_portal_host(host):
    if not host:
        return False
    host = host.lower().lstrip("www.")
    if host in _PORTAL_HOSTS:
        return True
    if host.endswith(".gov.in") or host.endswith(".nic.in"):
        # A government domain is not automatically a recruitment portal.
        # It remains a useful source-domain clue, not a guaranteed org name.
        return False
    return any(host.endswith("." + p) for p in _PORTAL_HOSTS if "." in p)


def _org_from_url(url):
    """
    Extract a conservative organisation candidate from a URL.

    We deliberately do NOT turn a job-portal hostname into an organisation.
    Path/slug terms are only used when they strongly resemble an organisation
    and are not generic recruitment/job words.
    """
    host = _url_host(url)
    if not host or _is_job_portal_host(host):
        return ""

    # Hostname candidate: nic.in/gov.in subdomains often identify the authority.
    host_parts = host.split(".")
    if len(host_parts) >= 3:
        candidate = host_parts[-3]
    else:
        candidate = host_parts[0]

    generic = {
        "www", "apply", "recruitment", "career", "careers", "jobs", "job",
        "online", "portal", "vacancy", "vacancies", "notice", "notices",
        "login", "registration", "reg", "exam", "admit", "result", "results",
        "official", "notification", "notifications", "portal",
    }
    if candidate and candidate.lower() not in generic:
        return candidate.replace("-", " ").replace("_", " ").strip()

    # Fall back to a meaningful URL path segment.
    path = re.sub(r"^https?://[^/]+/?", "", clean_text(url), flags=re.I)
    for segment in re.split(r"[/_\-]+", path):
        seg = re.sub(r"\.(pdf|html?|php)$", "", segment, flags=re.I).strip()
        if (
            len(seg) >= 3
            and seg.lower() not in generic
            and not re.fullmatch(r"\d+", seg)
            and not re.search(r"\b(202[0-9]|20[0-9]{2})\b", seg)
        ):
            return seg.replace("-", " ").replace("_", " ").strip()

    return ""


def _looks_like_organisation(text):
    """Score obvious organisation-name shapes without pretending every title is one."""
    s = clean_text(text)
    low = s.lower()
    if not s or _looks_like_qualification(s):
        return False

    bad = (
        "recruitment", "vacancy", "vacancies", "notification", "application",
        "apply online", "main exam", "admit card", "result", "answer key",
        "job", "career", "government job", "online form",
    )
    if any(x in low for x in bad):
        return False

    # Strong institutional markers.
    strong = (
        "bank", "limited", "ltd", "corporation", "commission", "board",
        "authority", "university", "institute", "organisation", "organization",
        "department", "ministry", "railway", "selection", "service",
        "research", "space", "fertilizer", "chemical",
    )
    if any(x in low for x in strong):
        return True

    # Acronym-heavy names such as "ISRO", "NIC", "IBPS".
    words = re.findall(r"[A-Za-z][A-Za-z&.()'-]*", s)
    return len(words) <= 8 and any(
        len(w.strip("().")) >= 2 and w.strip("().").isupper()
        for w in words
    )


def _infer_organisation_from_context(deck):
    """
    Conservative fallback chain:
      1) explicit deck organisation fields
      2) a plausible slide eyebrow
      3) a plausible organisation-looking URL candidate

    Portal URLs are never blindly displayed as the employer name.
    """
    explicit = _organisation_from_deck(deck)
    if explicit and not _looks_like_qualification(explicit):
        return explicit

    for slide in (deck.get("slides") or []):
        if not isinstance(slide, dict):
            continue
        candidate = clean_text(slide.get("eyebrow"))
        if candidate and _looks_like_organisation(candidate):
            return candidate

    for url in _iter_deck_urls(deck):
        candidate = _org_from_url(url)
        if candidate and _looks_like_organisation(candidate):
            return candidate

    return ""


def _organisation_from_deck(deck):
    """Prefer the authoritative deck-level organisation over slide eyebrow data."""
    if not isinstance(deck, dict):
        return ""
    return clean_text(
        deck.get("organisation")
        or deck.get("organization")
        or deck.get("recruitment_organisation")
        or deck.get("recruitment_organization")
    )


def build_html(
    slide,
    total,
    theme="professional_white",
    total_vacancies="",
    organisation="",
    application_url="",
    logo_url=""
):
    """
    Existing deck contract from carousel.py:
      slide_number, slide_type, title, eyebrow, subtitle,
      cards[{label,value,meta}], bullets[], footer_note
    """
    cards = _safe_cards(slide.get("cards") or [])
    stype = _normalise_type(slide.get("slide_type"))
    number = slide.get("slide_number") or 1
    title = clean_text(slide.get("title")) or "Recruitment Update"
    # Keep the standard, user-facing title for the final links/CTA slide.
    if stype == "links":
        title = "Official Links & How to Apply"
    raw_eyebrow = clean_text(slide.get("eyebrow"))
    eyebrow = clean_text(organisation) or raw_eyebrow or "Government Recruitment"
    subtitle = clean_text(slide.get("subtitle"))
    brand_markup = (
        f'<img class="top-brand-logo" src="{esc(logo_url)}" alt="{esc(eyebrow)} logo" />'
        if logo_url and _normalise_type(slide.get("slide_type")) == "hook"
        else '<div class="top-brand-mark">SD</div>'
    )
    bullets = [
        clean_text(x)
        for x in (slide.get("bullets") or [])
        if clean_text(x)
    ]

    count = len(cards)
    if count >= 13:
        density = "ultra-dense"
    elif count >= 9:
        density = "dense"
    elif count >= 6:
        density = "compact"
    else:
        density = "normal"

    if stype == "posts":
        cards_html = "".join(
            _post_card_html(card, i) for i, card in enumerate(cards)
        )
    elif stype == "dates":
        cards_html = "".join(
            _date_card_html(card, i) for i, card in enumerate(cards)
        )
    elif stype == "links":
        url_cards = [
            c for c in cards
            if isinstance(c.get("value"), str)
            and re.match(r"^https?://", c.get("value", "").strip())
        ]
        cards_html = "".join(
            _link_card_html(card) for card in url_cards[:2]
        )
        remaining = url_cards[2:]
        if remaining:
            rows = []
            for card in remaining:
                label = clean_text(card.get("label")) or "Official link"
                url = clean_text(card.get("value"))
                rows.append(
                    f"""
                    <div class="link-row">
                      <span class="label">{esc(label)}</span>
                      <span class="url">{esc(url)}</span>
                    </div>
                    """
                )
            cards_html += '<div class="link-list">' + "".join(rows) + "</div>"
    else:
        cards_html = "".join(
            _card_html(card, i) for i, card in enumerate(cards)
        )

    bullets_html = "".join(
        f"""
        <li>
          <span class="bullet-check">✓</span>
          <span>{esc(x)}</span>
        </li>
        """
        for x in bullets
    )

    hero = ""
    if stype == "hook":
        # Slide 1 is deliberately a cover: only the highest-value facts remain.
        metric = clean_text(total_vacancies)
        highlight = _hook_highlight(subtitle)
        application_highlight = _extract_application_highlight(bullets)
        application_start, application_end = _extract_application_dates(application_highlight)

        hero = f"""
        <section class="hero">
          <div class="hero-grid"></div>

          <div class="hero-kicker-row">
            <span class="hero-kicker">RECRUITMENT HIGHLIGHTS</span>
            {f'<span class="hero-count">TOTAL VACANCIES</span>' if metric else ""}
          </div>

          <div class="hero-main hero-cover-main">
            <div class="hero-highlight-badge">
              {esc(highlight)}
            </div>

            {f"""
            <div class="hero-vacancy-focus">
              <div class="hero-vacancy-label">TOTAL VACANCIES</div>
              <div class="hero-vacancy-focus-row">
                <div class="hero-stat-number-wrap">
                  <div class="hero-stat-number">{esc(metric)}</div>
                </div>
                <div class="hero-stat-caption">VACANCIES</div>
              </div>
            </div>
            """ if metric else ""}

            {f"""
            <div class="hero-date-tablet hero-date-tablet-cover">
              <div class="hero-date-item">
                <div class="hero-date-label">{"APPLICATION START" if application_end else "APPLICATION DEADLINE"}</div>
                <div class="hero-date-value">{esc(application_start or application_end)}</div>
              </div>
              {f"""
              <div class="hero-date-arrow">↓</div>
              <div class="hero-date-item">
                <div class="hero-date-label">APPLICATION END</div>
                <div class="hero-date-value">{esc(application_end)}</div>
              </div>
              """ if application_end else ""}
            </div>
            """ if application_start or application_end else ""}

            <div class="hero-cover-message">
              <strong>Swipe to explore</strong>
              <span>Posts • Eligibility • Dates • Application</span>
            </div>

            <div class="hero-cover-decor">
              <div class="hero-gear gear-large">⚙</div>
              <div class="hero-gear gear-small">⚙</div>
              <div class="hero-cover-callout">
                <strong>MASSIVE</strong>
                <strong>HIRING ↗</strong>
              </div>
            </div>
          </div>

          <div class="hero-bottom">
            <span>SWIPE FOR POSTS • ELIGIBILITY • DATES • APPLICATION</span>
            <span class="hero-arrow">SWIPE →</span>
          </div>
        </section>
        """


    content = ""
    if stype != "hook":
        if stype == "posts":
            # Recruitment Snapshot: four facts become a deliberate 2x2 dashboard.
            snapshot_html = "".join(
                _snapshot_card_html(card, i) for i, card in enumerate(cards)
            )
            if len(cards) == 1:
                snapshot_mode = "snapshot-one"
            elif len(cards) == 2:
                snapshot_mode = "snapshot-two"
            elif len(cards) >= 11:
                snapshot_mode = "snapshot-many snapshot-extra-dense"
            else:
                snapshot_mode = "snapshot-many"
            posts_layout = (
                "posts-one" if len(cards) == 1
                else "posts-two" if len(cards) == 2
                else "posts-many"
            )
            body = f'<div class="snapshot-grid {snapshot_mode} posts-v2 {posts_layout}">{snapshot_html}</div>'

        elif stype == "eligibility":
            # Post-wise eligibility can contain many long qualifications.
            # Use a responsive 2-column card layout so all supplied content
            # stays inside the 1080x1350 canvas instead of stacking forever.
            moved_qualification = clean_text(slide.get("_moved_qualification"))
            eligibility_cards_source = list(cards)

            if moved_qualification:
                duplicate = any(
                    moved_qualification.lower() in clean_text(c.get("value")).lower()
                    or clean_text(c.get("value")).lower() in moved_qualification.lower()
                    for c in eligibility_cards_source
                    if isinstance(c, dict)
                )
                if not duplicate:
                    eligibility_cards_source.insert(
                        0,
                        {
                            "label": "QUALIFICATION / ELIGIBILITY",
                            "value": moved_qualification,
                            "meta": "",
                        },
                    )

            eligibility_count = len(eligibility_cards_source)
            compact = eligibility_count >= 4
            eligibility_density = (
                "eligibility-many" if eligibility_count >= 6
                else "eligibility-medium" if eligibility_count >= 4
                else "eligibility-few"
            )
            eligibility_cards = "".join(
                _eligibility_card_html(card, i, compact=compact)
                for i, card in enumerate(eligibility_cards_source)
            )

            body = f"""
            <div class="eligibility-layout {eligibility_density}">
              <div class="eligibility-grid">
                {eligibility_cards}
              </div>
            </div>
            """

            if bullets_html:
                body += f"""
                <section class="eligibility-checklist">
                  <div class="checklist-title">CHECK BEFORE APPLYING</div>
                  <ul class="bullet-list">{bullets_html}</ul>
                </section>
                """

        elif stype == "fees":
            primary = "".join(
                _fee_card_html(card, i, primary=True)
                for i, card in enumerate(cards[:2])
            )
            secondary = "".join(
                _fee_card_html(card, i + 2, primary=False)
                for i, card in enumerate(cards[2:])
            )
            body = f"""
            <div class="fees-layout">
              {f'<div class="fee-primary-grid">{primary}</div>' if primary else ""}
              {f'<div class="fee-secondary-grid">{secondary}</div>' if secondary else ""}
            </div>
            """

            if bullets_html:
                body += f"""
                <section class="fees-checklist">
                  <div class="checklist-title">IMPORTANT</div>
                  <ul class="bullet-list">{bullets_html}</ul>
                </section>
                """

        elif stype == "dates":
            body = f"""
            <div class="dates-v3">
              <section class="dates-hero-panel">
                <div class="dates-hero-top">
                  <div>
                    <div class="dates-hero-kicker">APPLICATION SCHEDULE</div>
                    <div class="dates-hero-title">Important Dates</div>
                  </div>
                  <div class="dates-live-badge">
                    <span class="dates-live-dot"></span>
                    APPLICATIONS OPEN
                  </div>
                </div>

                <div class="dates-step-timeline">
                  {cards_html}
                </div>

                <div class="dates-open-banner">
                  <div class="dates-open-icon">✓</div>
                  <div>
                    <div class="dates-open-title">APPLICATIONS OPEN NOW!</div>
                    <div class="dates-open-subtitle">Apply before the deadline shown above.</div>
                  </div>
                </div>
              </section>

              {_checklist_panel_html(bullets, "BEFORE YOU SUBMIT")}
            </div>
            """

        elif stype == "links":
            # Slide 6 is a deliberate CTA/outro: make the official source,
            # QR access and three user actions visually dominant.
            url_cards = [
                c for c in cards
                if isinstance(c.get("value"), str)
                and re.match(r"^https?://", c.get("value", "").strip())
            ]

            qr_blocks = []
            qr_labels = [
                ("SCAN TO APPLY", "APPLICATION FORM"),
                ("SCAN FOR PDF", "RECRUITMENT NOTIFICATION"),
            ]
            for i, card in enumerate(url_cards[:2]):
                label1, label2 = qr_labels[min(i, len(qr_labels) - 1)]
                qr_blocks.append(
                    f"""
                    <div class="outro-qr-card">
                      <div class="outro-qr-label">
                        <strong>{esc(label1)}</strong>
                        <span>{esc(label2)}</span>
                      </div>
                      <div class="outro-qr-box">
                        {_link_card_html(card)}
                      </div>
                    </div>
                    """
                )

            qr_html = "".join(qr_blocks)
            first_url = clean_text(url_cards[0].get("value")) if url_cards else ""

            action_defaults = [
                ("SAVE THIS POST", "Save this post so you don't miss the application deadline.", "calendar"),
                ("SHARE WITH FRIENDS", "Share this recruitment update with friends looking for a Government Job.", "share"),
                ("Official Links & How to Apply", "Use the official links to continue to the application page.", "link"),
            ]

            checklist_cards = []
            for i, x in enumerate(bullets[:3]):
                title, fallback_text, icon_name = action_defaults[i]
                raw = clean_text(x)
                # Keep the source bullet when it contains useful content;
                # otherwise use the standard CTA wording.
                step_text = raw or fallback_text
                checklist_cards.append(
                    f"""
                    <div class="outro-action-card {'outro-action-primary' if i == 2 else ''}">
                      <div class="outro-action-top">
                        <div class="outro-action-number">{i+1:02d}</div>
                        <div class="outro-action-copy">
                          <div class="outro-action-title">{esc(title)}</div>
                          <div class="outro-action-text">{esc(step_text)}</div>
                        </div>
                      </div>
                      <div class="outro-action-art outro-art-{icon_name}" aria-hidden="true">
                        <svg viewBox="0 0 72 58">
                          {(
                            '<rect x="14" y="7" width="34" height="42" rx="5"></rect>'
                            '<line x1="21" y1="14" x2="41" y2="14"></line>'
                            '<circle cx="31" cy="42" r="2"></circle>'
                            '<circle cx="51" cy="39" r="12"></circle>'
                            '<line x1="51" y1="32" x2="51" y2="39"></line>'
                            '<line x1="51" y1="39" x2="56" y2="42"></line>'
                          ) if icon_name == "calendar" else (
                            '<path d="M13 30c8-5 14-10 21-10 6 0 9 5 13 5 4 0 8-4 12-9"></path>'
                            '<path d="M47 12h12v12"></path>'
                            '<path d="M19 38c4 7 12 10 18 5l8-8"></path>'
                            '<path d="M25 23l-8 8 7 7 8-8"></path>'
                          ) if icon_name == "share" else (
                            '<rect x="22" y="5" width="28" height="48" rx="5"></rect>'
                            '<circle cx="36" cy="47" r="2"></circle>'
                            '<path d="M29 31l5-5 4 4 8-10"></path>'
                            '<path d="M42 20h4v4"></path>'
                          )}
                        </svg>
                      </div>
                    </div>
                    """
                )

            # If the source contains fewer than three bullets, fill the visual
            # CTA row with the standard actions rather than leaving it sparse.
            while len(checklist_cards) < 3:
                i = len(checklist_cards)
                title, fallback_text, icon_name = action_defaults[i]
                checklist_cards.append(
                    f"""
                    <div class="outro-action-card {'outro-action-primary' if i == 2 else ''}">
                      <div class="outro-action-top">
                        <div class="outro-action-number">{i+1:02d}</div>
                        <div class="outro-action-copy">
                          <div class="outro-action-title">{esc(title)}</div>
                          <div class="outro-action-text">{esc(fallback_text)}</div>
                        </div>
                      </div>
                      <div class="outro-action-art outro-art-{icon_name}" aria-hidden="true">
                        <svg viewBox="0 0 72 58">
                          {(
                            '<rect x="14" y="7" width="34" height="42" rx="5"></rect><line x1="21" y1="14" x2="41" y2="14"></line><circle cx="31" cy="42" r="2"></circle><circle cx="51" cy="39" r="12"></circle><line x1="51" y1="32" x2="51" y2="39"></line><line x1="51" y1="39" x2="56" y2="42"></line>'
                          ) if icon_name == "calendar" else (
                            '<path d="M13 30c8-5 14-10 21-10 6 0 9 5 13 5 4 0 8-4 12-9"></path><path d="M47 12h12v12"></path><path d="M19 38c4 7 12 10 18 5l8-8"></path>'
                          ) if icon_name == "share" else (
                            '<rect x="22" y="5" width="28" height="48" rx="5"></rect><circle cx="36" cy="47" r="2"></circle><path d="M29 31l5-5 4 4 8-10"></path>'
                          )}
                        </svg>
                      </div>
                    </div>
                    """
                )

            body = f"""
            <div class="outro-v4">
              <section class="outro-official">
                <div class="outro-official-copy">
                  <div class="outro-kicker">OFFICIAL APPLICATION ACCESS</div>
                  <div class="outro-official-title">
                    Scan to open the official<br>recruitment application
                  </div>
                  <div class="outro-official-url">{esc(first_url)}</div>
                  <div class="outro-verify">VERIFY DETAILS BEFORE APPLYING</div>
                </div>

                <div class="outro-qr-stack">
                  {qr_html}
                </div>
              </section>

              <section class="outro-actions">
                <div class="outro-actions-head">
                  <div class="outro-actions-kicker">DON'T MISS THE DEADLINE</div>
                  <div class="outro-actions-title">3 things to do before you leave</div>
                </div>
                <div class="outro-action-grid">
                  {''.join(checklist_cards)}
                </div>
              </section>
            </div>
            """


        else:
            body = f'<div class="card-grid {density}">{cards_html}</div>'
            if bullets_html:
                body += f'<ul class="bullet-list {density}">{bullets_html}</ul>'

        content = f"""
        <section class="content-block {stype} {density}">
          {body}
        </section>
        """

    note = clean_text(slide.get("footer_note")) or (
        "Save this post • Check the official notification before applying."
    )

    footer = f"""
      <footer>
        <div class="benefit-strip">
          <div class="benefit-item">
            <div class="benefit-icon">
              <svg viewBox="0 0 32 32" aria-hidden="true">
                <circle cx="16" cy="9" r="4"></circle>
                <path d="M8 24c.8-4.4 3.7-7 8-7s7.2 2.6 8 7"></path>
                <path d="M4.5 22c.5-2.7 2.1-4.4 4.6-5.2"></path>
                <path d="M27.5 22c-.5-2.7-2.1-4.4-4.6-5.2"></path>
              </svg>
            </div>
            <div class="benefit-copy">
              <strong>Government</strong>
              <span>Job</span>
            </div>
          </div>

          <div class="benefit-divider"></div>

          <div class="benefit-item">
            <div class="benefit-icon">
              <svg viewBox="0 0 32 32" aria-hidden="true">
                <path d="M6 25V19"></path>
                <path d="M12 25V15"></path>
                <path d="M18 25V11"></path>
                <path d="M24 25V6"></path>
                <path d="M5 9l7 2 6-5 7 1"></path>
                <path d="M21 5h4v4"></path>
              </svg>
            </div>
            <div class="benefit-copy">
              <strong>Stable</strong>
              <span>Career</span>
            </div>
          </div>

          <div class="benefit-divider"></div>

          <div class="benefit-item">
            <div class="benefit-icon">
              <svg viewBox="0 0 32 32" aria-hidden="true">
                <path d="M16 4l9 3v7c0 6.2-3.8 10.5-9 13-5.2-2.5-9-6.8-9-13V7l9-3z"></path>
                <path d="M11 16l3.2 3.2L21 12"></path>
              </svg>
            </div>
            <div class="benefit-copy">
              <strong>Serve</strong>
              <span>the Society</span>
            </div>
          </div>
        </div>

        <div class="footer-bottom">
          <div class="footer-note">{esc(note)}</div>
          <div class="footer-page">{int(number):02d}/{int(total):02d}</div>
        </div>
      </footer>
    """

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ box-sizing:border-box; }}

html, body {{ margin:0; width:{W}px; height:{H}px; }}

body {{
  background:{WHITE};
  color:{INK};
  font-family:Inter, "Segoe UI", Arial, sans-serif;
  padding:48px 58px 34px;
  display:flex;
  flex-direction:column;
  position:relative;
  overflow:hidden;
}}

body:before {{
  content:"";
  position:absolute;
  top:0; left:0;
  width:100%; height:10px;
  background:{NAVY};
}}

body:after {{
  content:"";
  position:absolute;
  right:-170px; top:-160px;
  width:430px; height:430px;
  border:34px solid {SOFT_BLUE};
  border-radius:50%;
  z-index:0;
}}

.page-layer {{
  position:absolute;
  z-index:0;
  left:24px;
  right:24px;
  top:42px;
  bottom:0;
  border-radius:28px;
  background:linear-gradient(180deg, #FBFCFE 0%, {SOFT} 52%, #FBFCFE 100%);
  border:1px solid rgba(216,225,234,.55);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.8);
  pointer-events:none;
}}

.topbar {{
  min-height:48px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  position:relative;
  z-index:3;
}}

.top-brand {{
  display:flex;
  align-items:center;
  gap:9px;
}}

.top-brand-mark {{
  width:34px;
  height:34px;
  border-radius:9px;
  background:{NAVY};
  color:{WHITE};
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:11px;
  font-weight:950;
  letter-spacing:.2px;
}}

.top-brand-logo {{
  width:34px;
  height:34px;
  object-fit:contain;
  display:block;
  border-radius:9px;
  background:#fff;
  padding:3px;
  box-shadow:inset 0 0 0 1px rgba(11,46,89,.12);
}}

.top-brand-copy {{
  display:flex;
  flex-direction:column;
  gap:2px;
}}

.top-brand-name {{
  color:{NAVY};
  font-size:14px;
  line-height:1;
  font-weight:950;
  letter-spacing:.75px;
}}

.top-brand-sub {{
  color:{MUTED};
  font-size:9px;
  line-height:1;
  font-weight:650;
}}

.top-slide {{
  color:{NAVY};
  border:1px solid {LINE};
  border-radius:999px;
  padding:7px 11px;
  font-size:10px;
  line-height:1;
  font-weight:950;
  letter-spacing:.55px;
}}

.org-row {{
  position:relative;
  z-index:3;
  display:flex;
  align-items:flex-start;
  margin-top:10px;
}}

.eyebrow {{
  position:relative;
  z-index:2;
  margin-top:0;
  display:inline-flex;
  align-self:flex-start;
  background:linear-gradient(135deg, {GOLD} 0%, #d79b1a 100%);
  color:{NAVY};
  border:2px solid rgba(7,43,71,.14);
  border-radius:14px;
  padding:16px 24px;
  font-size:30px;
  line-height:1.08;
  font-weight:1000;
  letter-spacing:.5px;
  text-transform:uppercase;
  max-width:900px;
  box-shadow:0 6px 16px rgba(228,165,28,.22);
  text-shadow:0 1px 0 rgba(255,255,255,.12);
}}

.hook-org-row {{
  margin-top:8px;
}}

.hook-eyebrow {{
  background:{NAVY};
  color:#ffffff;
  border-radius:14px;
  padding:18px 28px;
  font-size:32px;
  line-height:1.08;
  letter-spacing:.35px;
  box-shadow:0 8px 20px rgba(18,42,67,.18);
  border:2px solid rgba(255,255,255,.12);
  max-width:none;
}}

h1 {{
  position:relative;
  z-index:2;
  margin:18px 0 0;
  color:{NAVY};
  font-size:42px;
  line-height:1.06;
  letter-spacing:-1.5px;
  font-weight:950;
  max-width:920px;
}}

.sub {{
  position:relative;
  z-index:2;
  margin-top:10px;
  color:{MUTED};
  font-size:18px;
  line-height:1.28;
  font-weight:600;
  max-width:900px;
}}

.hook-title {{
  margin-top:18px;
  font-size:38px;
  line-height:1.06;
}}

.hook-subtitle {{
  margin-top:10px;
  font-size:18px;
  line-height:1.2;
  color:{NAVY};
}}

.rule {{
  position:relative;
  z-index:2;
  margin-top:17px;
  width:72px;
  height:5px;
  border-radius:6px;
  background:{GOLD};
}}

.content-block {{
  margin-top:23px;
  flex:1 1 auto;
  min-height:0;
  max-height:100%;
  position:relative;
  z-index:2;
  display:flex;
  flex-direction:column;
  overflow:visible;
  transform-origin:top center;
}}

.card-grid {{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:13px;
  align-content:start;
}}

.info-card {{
  min-height:105px;
  background:{WHITE};
  border:1px solid {LINE};
  border-radius:15px;
  padding:16px 17px;
  box-shadow:0 7px 20px rgba(11,46,89,.045);
  overflow:hidden;
}}

.card-top {{
  display:flex;
  align-items:center;
  gap:8px;
  margin-bottom:7px;
}}

.card-dot {{
  width:7px; height:7px;
  border-radius:50%;
  background:{GOLD};
  flex:none;
}}

.label {{
  color:{BLUE};
  font-size:11px;
  line-height:1.1;
  font-weight:950;
  letter-spacing:.65px;
  text-transform:uppercase;
}}

.value {{
  color:{INK};
  font-size:22px;
  line-height:1.18;
  font-weight:850;
  overflow-wrap:anywhere;
}}

.meta {{
  color:{MUTED};
  font-size:14px;
  line-height:1.25;
  margin-top:5px;
  overflow-wrap:anywhere;
}}

.card-grid.compact .info-card {{ min-height:92px; padding:13px 14px; }}
.card-grid.compact .value {{ font-size:19px; }}
.card-grid.compact .meta {{ font-size:13px; }}

.card-grid.dense {{ gap:10px; }}
.card-grid.dense .info-card {{ min-height:83px; padding:11px 13px; border-radius:13px; }}
.card-grid.dense .label {{ font-size:10px; }}
.card-grid.dense .value {{ font-size:17px; line-height:1.16; }}
.card-grid.dense .meta {{ font-size:12px; margin-top:4px; }}

.card-grid.ultra-dense {{ gap:8px; }}
.card-grid.ultra-dense .info-card {{ min-height:69px; padding:8px 11px; border-radius:11px; }}
.card-grid.ultra-dense .card-top {{ margin-bottom:4px; }}
.card-grid.ultra-dense .label {{ font-size:9px; }}
.card-grid.ultra-dense .value {{ font-size:15px; line-height:1.12; }}
.card-grid.ultra-dense .meta {{ font-size:10px; margin-top:3px; }}

/* SLIDE 2 — RECRUITMENT SNAPSHOT */
.snapshot-grid {{
  display:grid;
  grid-template-columns:1.12fr .88fr;
  grid-template-rows:auto auto;
  gap:16px;
  align-content:start;
}}

.snapshot-card {{
  min-height:150px;
  position:relative;
  background:{WHITE};
  border:1px solid {LINE};
  border-radius:19px;
  padding:20px 21px;
  box-shadow:0 8px 24px rgba(11,46,89,.055);
  overflow:hidden;
  display:flex;
  flex-direction:column;
  justify-content:flex-end;
}}

.snapshot-card:after {{
  content:"";
  position:absolute;
  right:-55px;
  bottom:-70px;
  width:180px;
  height:180px;
  border:19px solid {SOFT_BLUE};
  border-radius:50%;
}}

.snapshot-index {{
  position:absolute;
  top:18px;
  right:19px;
  width:30px;
  height:30px;
  border-radius:50%;
  background:{SOFT_BLUE};
  color:{BLUE};
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:9px;
  font-weight:950;
  z-index:1;
}}

.snapshot-copy {{
  position:relative;
  z-index:1;
  max-width:100%;
}}

.snapshot-label {{
  color:{BLUE};
  font-size:11px;
  line-height:1.1;
  font-weight:950;
  letter-spacing:.8px;
  text-transform:uppercase;
}}

.snapshot-value {{
  color:{NAVY};
  font-size:25px;
  line-height:1.12;
  font-weight:900;
  margin-top:8px;
  overflow-wrap:anywhere;
}}

.snapshot-feature {{
  grid-row:1 / span 2;
  min-height:340px;
  justify-content:center;
  padding:29px;
  background:{NAVY};
  border-color:{NAVY};
}}

.snapshot-feature:after {{
  border-color:rgba(255,255,255,.07);
  width:320px;
  height:320px;
  right:-160px;
  bottom:-170px;
}}

.snapshot-feature .snapshot-index {{
  top:25px;
  left:25px;
  right:auto;
  background:{GOLD};
  color:{NAVY};
}}

.snapshot-feature .snapshot-copy {{
  margin-top:35px;
}}

.snapshot-feature .snapshot-label {{
  color:#BFD5E5;
  font-size:13px;
  letter-spacing:1.1px;
}}

.snapshot-feature .snapshot-value {{
  color:{WHITE};
  font-size:72px;
  line-height:.92;
  letter-spacing:-3px;
  margin-top:14px;
}}

.snapshot-feature .snapshot-meta {{
  color:#D7E5F0;
  font-size:14px;
  line-height:1.3;
  margin-top:15px;
  max-width:400px;
}}

.snapshot-meta {{
  color:{MUTED};
  font-size:12px;
  line-height:1.25;
  margin-top:6px;
  overflow-wrap:anywhere;
}}

.snapshot-grid .snapshot-card:nth-child(2),
.snapshot-grid .snapshot-card:nth-child(3) {{
  min-height:162px;
}}

.snapshot-grid .snapshot-card:nth-child(4) {{
  grid-column:2;
  min-height:120px;
  background:{SOFT};
  border-top:4px solid {GOLD};
}}

.snapshot-two {{
  grid-template-columns:1fr 1fr;
  grid-template-rows:auto;
}}

.snapshot-two .snapshot-card {{
  min-height:245px;
}}

.snapshot-two .snapshot-card:first-child {{
  grid-row:auto;
}}

.snapshot-two .snapshot-card:first-child .snapshot-value {{
  font-size:64px;
}}

.snapshot-one {{
  grid-template-columns:1fr;
}}

.snapshot-one .snapshot-card {{
  min-height:330px;
}}

.snapshot-one .snapshot-card:first-child .snapshot-value {{
  font-size:78px;
}}

.snapshot-many {{
  grid-template-columns:1.05fr .95fr;
}}
.snapshot-grid.posts-v2 {{
  grid-template-rows:auto;
  gap:13px;
}}
.posts-v2 .snapshot-card {{
  min-height:128px;
  padding:17px 18px;
  justify-content:center;
}}
.posts-v2 .snapshot-card:after {{
  width:135px;
  height:135px;
  right:-58px;
  bottom:-62px;
  border-width:14px;
}}
.posts-v2 .snapshot-index {{
  top:12px;
  right:13px;
  width:26px;
  height:26px;
  font-size:8px;
}}
.posts-v2 .snapshot-label {{
  font-size:10px;
  line-height:1.15;
  padding-right:30px;
}}
.posts-v2 .snapshot-value {{
  font-size:35px;
  line-height:1;
  margin-top:6px;
  letter-spacing:-1px;
}}
.posts-v2 .snapshot-meta {{
  font-size:11px;
  margin-top:5px;
}}
.posts-v2.posts-many {{
  grid-template-columns:repeat(3,1fr);
}}
.posts-v2.posts-many .snapshot-card {{
  min-height:122px;
}}
.posts-v2.posts-many .snapshot-card:first-child {{
  grid-row:auto;
}}
.posts-v2.posts-many .snapshot-card:first-child .snapshot-value {{
  font-size:40px;
}}
.posts-v2.posts-two {{
  grid-template-columns:1fr 1fr;
}}
.posts-v2.posts-two .snapshot-card {{
  min-height:185px;
}}
.posts-v2.posts-two .snapshot-card:first-child .snapshot-value {{
  font-size:50px;
}}
.posts-v2.posts-one {{
  grid-template-columns:1fr;
}}
.posts-v2.posts-one .snapshot-card {{
  min-height:220px;
}}
.posts-v2.posts-one .snapshot-card:first-child .snapshot-value {{
  font-size:64px;
}}

/* SLIDE 3 — ELIGIBILITY */
.eligibility-layout {{
  width:100%;
}}

.eligibility-grid {{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:14px;
  align-items:stretch;
}}

.eligibility-card {{
  min-height:142px;
  position:relative;
  background:{WHITE};
  border:1px solid {LINE};
  border-radius:17px;
  padding:17px 18px 16px 20px;
  box-shadow:0 7px 20px rgba(11,46,89,.05);
  overflow:hidden;
}}

.eligibility-card:before {{
  content:"";
  position:absolute;
  left:0; top:0; bottom:0;
  width:5px;
  background:{BLUE};
}}

.eligibility-card-head {{
  display:flex;
  align-items:center;
  gap:7px;
  margin-bottom:8px;
}}

.eligibility-card-head .card-dot {{
  width:8px;
  height:8px;
}}

.eligibility-code {{
  color:{BLUE};
  font-size:10px;
  line-height:1;
  font-weight:950;
  letter-spacing:.65px;
  text-transform:uppercase;
}}

.eligibility-tags {{
  display:flex;
  flex-wrap:wrap;
  gap:6px;
  margin:0 0 9px;
}}
.eligibility-tag {{
  display:inline-flex;
  align-items:center;
  gap:5px;
  padding:5px 8px;
  border-radius:999px;
  background:{SOFT_BLUE};
  color:{NAVY};
  font-size:9px;
  line-height:1;
  font-weight:800;
  white-space:nowrap;
}}
.eligibility-tag-icon {{
  width:16px;
  height:16px;
  border-radius:50%;
  display:flex;
  align-items:center;
  justify-content:center;
  background:{NAVY};
  color:{GOLD};
  font-size:8px;
  font-weight:950;
}}
.eligibility-tag-label {{
  color:{BLUE};
  font-size:8px;
  font-weight:950;
  letter-spacing:.45px;
}}
.eligibility-tag strong {{
  font-size:10px;
  font-weight:950;
}}
.eligibility-value {{
  color:{INK};
  font-size:19px;
  line-height:1.17;
  font-weight:800;
  overflow-wrap:anywhere;
}}

.eligibility-meta {{
  color:{MUTED};
  font-size:11px;
  line-height:1.25;
  margin-top:6px;
  overflow-wrap:anywhere;
}}

.eligibility-few .eligibility-grid {{
  grid-template-columns:1fr;
  gap:15px;
}}

.eligibility-few .eligibility-card {{
  min-height:175px;
  padding:22px 24px;
}}

.eligibility-few .eligibility-value {{
  font-size:28px;
  line-height:1.16;
}}

.eligibility-medium .eligibility-card {{
  min-height:150px;
}}

.eligibility-medium .eligibility-value {{
  font-size:18px;
}}

.eligibility-many .eligibility-grid {{
  gap:12px;
}}

.eligibility-many .eligibility-card {{
  min-height:140px;
  padding:14px 15px 13px 17px;
  border-radius:15px;
}}

.eligibility-many .eligibility-value {{
  font-size:17px;
  line-height:1.16;
}}

.eligibility-many .eligibility-code {{
  font-size:9px;
}}

.eligibility-checklist {{
  margin-top:16px;
  background:{SOFT};
  border:1px solid {LINE};
  border-radius:16px;
  padding:16px 19px;
}}

/* SLIDE 4 — FEES / SELECTION / PAY */
.fees-layout {{
  display:flex;
  flex-direction:column;
  gap:15px;
}}

.fee-primary-grid {{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:15px;
}}

.fee-secondary-grid {{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:15px;
}}

.fee-card {{
  min-height:140px;
  position:relative;
  background:{WHITE};
  border:1px solid {LINE};
  border-radius:18px;
  padding:18px 20px;
  box-shadow:0 8px 24px rgba(11,46,89,.05);
  overflow:hidden;
}}

.fee-card:after {{
  content:"";
  position:absolute;
  right:-60px;
  bottom:-70px;
  width:150px;
  height:150px;
  border:16px solid {SOFT_BLUE};
  border-radius:50%;
}}

.fee-primary-card {{
  min-height:175px;
  background:{NAVY};
  border-color:{NAVY};
  border-top:4px solid {GOLD};
  padding:21px 22px;
}}

.fee-primary-card:nth-child(2) {{
  background:{SOFT};
  border-color:{LINE};
  border-top-color:{GOLD};
}}

.fee-primary-card .card-top,
.fee-primary-card .value,
.fee-primary-card .meta {{
  position:relative;
  z-index:1;
}}

.fee-primary-card:first-child .label {{
  color:{GOLD};
}}

.fee-primary-card:first-child .value {{
  color:{WHITE};
}}

.fee-primary-card:first-child .meta {{
  color:#C5D8E7;
}}

.fee-primary-card .label {{
  font-size:11px;
}}

.fee-primary-card .value {{
  color:{NAVY};
  font-size:31px;
  line-height:1.1;
  margin-top:13px;
}}

.fee-secondary-grid .fee-card {{
  min-height:150px;
  border-top:3px solid {BLUE};
}}

.fee-secondary-grid .value {{
  font-size:19px;
  line-height:1.2;
}}

.fees-checklist {{
  margin-top:0;
  background:{SOFT};
  border:1px solid {LINE};
  border-radius:16px;
  padding:15px 19px;
}}


/* SLIDE 5 — DATES V3 / SAMPLE-INSPIRED */
.dates-v3 {{
  display:flex;
  flex-direction:column;
  gap:16px;
}}

.dates-hero-panel {{
  position:relative;
  overflow:hidden;
  border-radius:24px;
  background:{NAVY};
  color:{WHITE};
  padding:27px 34px 25px;
  box-shadow:0 14px 30px rgba(11,46,89,.14);
}}

.dates-hero-panel:before {{
  content:"";
  position:absolute;
  width:380px;
  height:380px;
  right:-210px;
  top:-220px;
  border:38px solid rgba(255,255,255,.065);
  border-radius:50%;
}}

.dates-hero-panel:after {{
  content:"";
  position:absolute;
  width:250px;
  height:250px;
  left:-180px;
  bottom:-175px;
  border:30px solid rgba(228,165,28,.09);
  border-radius:50%;
}}

.dates-hero-top,
.dates-step-timeline,
.dates-open-banner {{
  position:relative;
  z-index:2;
}}

.dates-hero-top {{
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:18px;
}}

.dates-hero-kicker {{
  color:{GOLD};
  font-size:12px;
  font-weight:950;
  letter-spacing:1.1px;
  text-transform:uppercase;
}}

.dates-hero-title {{
  margin-top:5px;
  color:{WHITE};
  font-size:31px;
  line-height:1;
  font-weight:950;
}}

.dates-live-badge {{
  display:flex;
  align-items:center;
  gap:7px;
  flex:none;
  padding:8px 11px;
  border:1px solid rgba(228,165,28,.65);
  border-radius:999px;
  color:{GOLD};
  font-size:10px;
  font-weight:950;
  letter-spacing:.55px;
}}

.dates-live-dot {{
  width:8px;
  height:8px;
  border-radius:50%;
  background:#55B56A;
  box-shadow:0 0 0 3px rgba(85,181,106,.14);
}}

.dates-step-timeline {{
  width:700px;
  max-width:100%;
  margin:26px auto 0;
  padding:0 8px;
}}

.dates-step-timeline .date-row {{
  position:relative;
  display:grid;
  grid-template-columns:1fr 70px 1fr;
  align-items:center;
  min-height:118px;
  padding:0;
}}

.dates-step-timeline .date-row:not(:last-child):before {{
  content:"";
  position:absolute;
  left:50%;
  top:59px;
  bottom:-1px;
  width:4px;
  transform:translateX(-50%);
  background:linear-gradient({BLUE}, {GOLD});
  border-radius:4px;
}}

.dates-step-timeline .date-marker {{
  grid-column:2;
  grid-row:1;
  justify-self:center;
  width:52px;
  height:52px;
  border-radius:50%;
  display:flex;
  align-items:center;
  justify-content:center;
  background:{NAVY};
  color:{WHITE};
  border:4px solid {GOLD};
  box-shadow:0 0 0 5px rgba(228,165,28,.12);
  font-size:13px;
  font-weight:950;
  z-index:3;
}}

.dates-step-timeline .date-row:first-child .date-marker {{
  border-color:#55B56A;
  box-shadow:0 0 0 5px rgba(85,181,106,.12);
}}

.dates-step-timeline .date-copy {{
  grid-column:1;
  grid-row:1;
  justify-self:end;
  width:100%;
  max-width:270px;
  padding:14px 22px;
  border:1px solid rgba(255,255,255,.18);
  border-radius:15px;
  background:rgba(255,255,255,.075);
  text-align:right;
}}

.dates-step-timeline .date-row:nth-child(2) .date-copy {{
  grid-column:3;
  justify-self:start;
  text-align:left;
  border-color:rgba(228,165,28,.55);
  background:rgba(228,165,28,.10);
}}

.dates-step-timeline .date-copy .label {{
  color:{GOLD};
  font-size:13px;
  font-weight:950;
  letter-spacing:.65px;
  text-transform:uppercase;
}}

.dates-step-timeline .date-row:first-child .date-copy .label {{
  color:#7DDB91;
}}

/* Long correction / revised-date entries stay inside their tablet. */
.dates-step-timeline .correction-row .date-copy {{
  padding:13px 18px;
}}

.dates-step-timeline .correction-row .date-value {{
  font-size:22px;
  line-height:1.12;
  white-space:normal;
  overflow-wrap:anywhere;
  text-wrap:balance;
}}

/* Any long timeline value gets its own compact, wrapping treatment. */
.dates-step-timeline .long-date-row .date-copy {{
  padding:12px 18px;
}}

.dates-step-timeline .long-date-row .date-value {{
  font-size:21px;
  line-height:1.12;
  white-space:normal;
  overflow-wrap:anywhere;
  word-break:normal;
  text-wrap:balance;
}}

.dates-step-timeline .long-date-row .date-copy .label {{
  margin-bottom:2px;
}}

.dates-step-timeline .correction-row .date-marker {{
  border-color:{GOLD};
}}


.dates-step-timeline .date-value {{
  margin-top:6px;
  color:{WHITE};
  font-size:30px;
  line-height:1.05;
  font-weight:950;
  white-space:nowrap;
}}

.dates-step-timeline .meta {{
  margin-top:5px;
  color:rgba(255,255,255,.68);
  font-size:11px;
}}

.dates-open-banner {{
  display:flex;
  align-items:center;
  justify-content:center;
  gap:12px;
  margin:13px auto 0;
  width:fit-content;
  max-width:100%;
  padding:11px 20px;
  border-radius:15px;
  background:{GOLD};
  color:{NAVY};
  box-shadow:0 7px 16px rgba(0,0,0,.13);
}}

.dates-open-icon {{
  width:32px;
  height:32px;
  flex:none;
  border-radius:50%;
  display:flex;
  align-items:center;
  justify-content:center;
  background:{NAVY};
  color:{GOLD};
  font-size:17px;
  font-weight:950;
}}

.dates-open-title {{
  font-size:14px;
  font-weight:950;
  letter-spacing:.55px;
}}

.dates-open-subtitle {{
  margin-top:2px;
  font-size:11px;
  font-weight:750;
}}

.dates-v3 .checklist-panel {{
  padding:17px 21px;
}}

.dates-v3 .checklist-panel .bullet-list {{
  margin-top:12px;
}}

@media (max-width: 900px) {{
  .dates-hero-panel {{
    padding:24px 27px 22px;
  }}
  .dates-step-timeline .date-copy {{
    max-width:245px;
  }}
  .dates-step-timeline .date-value {{
    font-size:27px;
  }}
}}

/* SLIDE 5 — DATES + CHECKLIST */
.dates-v2 {{
  display:flex;
  flex-direction:column;
  gap:18px;
}}
.dates-timeline-card {{
  border:1px solid {LINE};
  border-radius:22px;
  background:{SOFT};
  padding:28px 34px 25px;
  box-shadow:0 8px 22px rgba(11,46,89,.06);
}}
.dates-timeline-card > .section-kicker {{ text-align:center; }}
.dates-timeline {{
  position:relative;
  width:640px;
  max-width:100%;
  margin:22px auto 0;
}}
.dates-timeline:before {{
  content:"";
  position:absolute;
  left:50%;
  top:27px;
  bottom:27px;
  width:4px;
  transform:translateX(-50%);
  background:linear-gradient({BLUE} 0 50%, {GOLD} 50% 100%);
  border-radius:4px;
}}
.dates-timeline .date-row {{
  position:relative;
  display:grid;
  grid-template-columns:1fr 58px 1fr;
  align-items:center;
  min-height:105px;
}}
.dates-timeline .date-marker {{
  grid-column:2;
  grid-row:1;
  justify-self:center;
  width:48px;
  height:48px;
  border-radius:50%;
  display:flex;
  align-items:center;
  justify-content:center;
  background:{WHITE};
  border:4px solid {BLUE};
  color:{BLUE};
  font-size:13px;
  font-weight:950;
  z-index:2;
}}
.dates-timeline .date-row:nth-child(2) .date-marker {{
  border-color:{GOLD};
  color:{NAVY};
}}
.dates-timeline .date-copy {{
  grid-column:3;
  grid-row:1;
  padding-left:20px;
  text-align:left;
}}
.dates-timeline .date-row:nth-child(odd) .date-copy {{
  grid-column:1;
  padding-left:0;
  padding-right:20px;
  text-align:right;
}}
.dates-timeline .date-copy .label {{
  color:{BLUE};
  font-size:15px;
  font-weight:950;
  letter-spacing:.8px;
  text-transform:uppercase;
}}
.dates-timeline .date-row:nth-child(2) .date-copy .label {{ color:#C58A00; }}
.dates-timeline .date-value {{
  margin-top:5px;
  color:{NAVY};
  font-size:30px;
  line-height:1.05;
  font-weight:950;
}}
.dates-status {{
  margin:18px auto 0;
  width:max-content;
  max-width:100%;
  display:flex;
  align-items:center;
  gap:9px;
  padding:10px 18px;
  border-radius:999px;
  background:{NAVY};
  color:{WHITE};
  font-size:14px;
  letter-spacing:.6px;
}}
.status-dot {{
  width:10px;
  height:10px;
  border-radius:50%;
  background:#43B97F;
  box-shadow:0 0 0 4px rgba(67,185,127,.16);
}}
.cta-steps {{
  margin-top:20px;
  padding:22px 24px 24px;
  border-radius:20px;
  background:{SOFT};
  border:1px solid {LINE};
}}
.cta-step-grid {{
  display:grid;
  grid-template-columns:repeat(3,1fr);
  gap:12px;
}}
.cta-step {{
  display:flex;
  align-items:flex-start;
  gap:12px;
  padding:16px;
  min-height:90px;
  border:1px solid {LINE};
  border-radius:15px;
  background:{WHITE};
}}
.cta-step-primary {{ border:1.5px solid {GOLD}; }}
.cta-step-icon {{
  width:38px;
  height:38px;
  flex:none;
  border-radius:50%;
  display:flex;
  align-items:center;
  justify-content:center;
  background:{NAVY};
  color:{GOLD};
  font-size:11px;
  font-weight:950;
}}
.cta-step-title {{
  color:{NAVY};
  font-size:13px;
  font-weight:950;
  letter-spacing:.65px;
}}
.cta-step-text {{
  margin-top:6px;
  color:{INK};
  font-size:13px;
  line-height:1.25;
  font-weight:700;
}}

.dates-composition {{
  display:grid;
  grid-template-columns:1.05fr 1fr;
  gap:16px;
  align-items:stretch;
}}

.dates-panel,
.checklist-panel {{
  background:{SOFT};
  border:1px solid {LINE};
  border-radius:20px;
  padding:20px 21px;
  box-shadow:0 8px 24px rgba(11,46,89,.045);
}}

.dates-panel {{
  position:relative;
  overflow:hidden;
}}

.dates-panel:after {{
  content:"";
  position:absolute;
  width:230px;
  height:230px;
  right:-145px;
  bottom:-155px;
  border:25px solid {SOFT_BLUE};
  border-radius:50%;
}}

.dates-panel .date-list {{
  margin-top:20px;
  padding:0;
  position:relative;
  z-index:1;
}}

.date-row {{
  position:relative;
  display:flex;
  gap:14px;
  min-height:93px;
  padding:0 0 18px;
}}

.date-row:not(:last-child):before {{
  content:"";
  position:absolute;
  left:13px; top:30px; bottom:0;
  width:3px;
  background:{GOLD};
}}

.date-marker {{
  width:28px; height:28px;
  border-radius:50%;
  background:{NAVY};
  color:{WHITE};
  flex:none;
  position:relative;
  z-index:1;
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:9px;
  font-weight:950;
  border:4px solid {SOFT_BLUE};
}}

.date-copy {{
  padding-top:1px;
  min-width:0;
}}

.date-value {{
  color:{NAVY};
  font-size:28px;
  line-height:1.08;
  font-weight:950;
  overflow-wrap:anywhere;
}}

.date-list .label {{
  font-size:10px;
}}

.date-list .meta {{
  font-size:11px;
  margin-top:5px;
}}

.checklist-panel {{
  background:{WHITE};
}}

.checklist-panel .bullet-list {{
  margin-top:18px;
  gap:12px;
}}

.checklist-panel .bullet-list li {{
  font-size:15px;
  line-height:1.28;
}}

.checklist-panel .bullet-check {{
  width:26px;
  height:26px;
}}

/* SLIDE 6 — OFFICIAL LINKS + CHECKLIST */

/* SLIDE 6 — OUTRO V4 / SAMPLE-INSPIRED CTA */
.outro-v4 {{
  display:flex;
  flex-direction:column;
  gap:17px;
}}

.outro-official {{
  position:relative;
  min-height:276px;
  display:grid;
  grid-template-columns:minmax(0,1fr) 330px;
  gap:22px;
  align-items:center;
  background:{NAVY};
  border-radius:24px;
  padding:28px 30px 27px;
  overflow:hidden;
  box-shadow:0 15px 32px rgba(11,46,89,.16);
}}

.outro-official:before {{
  content:"";
  position:absolute;
  width:360px;
  height:360px;
  right:-175px;
  top:-155px;
  border:31px solid rgba(255,255,255,.065);
  border-radius:50%;
}}

.outro-official:after {{
  content:"";
  position:absolute;
  width:245px;
  height:245px;
  left:-105px;
  bottom:-160px;
  border:23px solid rgba(228,165,28,.09);
  border-radius:50%;
}}

.outro-official-copy,
.outro-qr-stack {{
  position:relative;
  z-index:2;
}}

.outro-kicker {{
  color:{GOLD};
  font-size:12px;
  font-weight:950;
  letter-spacing:1px;
  text-transform:uppercase;
}}

.outro-official-title {{
  margin-top:12px;
  color:{WHITE};
  font-size:29px;
  line-height:1.08;
  font-weight:950;
  letter-spacing:-.5px;
}}

.outro-official-url {{
  margin-top:13px;
  max-width:540px;
  color:#BCD7EA;
  font-size:11px;
  line-height:1.3;
  overflow-wrap:anywhere;
}}

.outro-verify {{
  display:inline-flex;
  margin-top:14px;
  padding:8px 13px;
  border-radius:999px;
  background:{GOLD};
  color:{NAVY};
  font-size:10px;
  font-weight:950;
  letter-spacing:.65px;
}}

.outro-qr-stack {{
  display:flex;
  flex-direction:column;
  align-items:flex-end;
  justify-content:center;
  gap:12px;
}}

.outro-qr-card {{
  display:flex;
  align-items:center;
  justify-content:flex-end;
  gap:11px;
  width:100%;
}}

.outro-qr-label {{
  width:105px;
  color:{WHITE};
  text-align:right;
  font-size:10px;
  line-height:1.12;
  text-transform:uppercase;
}}

.outro-qr-label strong {{
  display:block;
  color:{GOLD};
  font-size:12px;
  letter-spacing:.5px;
}}

.outro-qr-label span {{
  display:block;
  margin-top:3px;
  color:{WHITE};
  font-size:9px;
  font-weight:800;
}}

.outro-qr-box {{
  width:132px;
  height:132px;
  flex:none;
  display:flex;
  align-items:center;
  justify-content:center;
  padding:8px;
  border:2px solid {GOLD};
  border-radius:16px;
  background:{WHITE};
  box-shadow:0 7px 16px rgba(0,0,0,.18);
}}

.outro-qr-box .link-card {{
  display:block;
  width:100%;
  margin:0;
  padding:0;
  border:0;
  background:{WHITE};
  box-shadow:none;
}}

.outro-qr-box .link-copy {{
  display:none;
}}

.outro-qr-box .qr-wrap {{
  padding:0;
  border:0;
  background:{WHITE};
}}

.outro-qr-box .qr-wrap img {{
  display:block;
  width:112px;
  height:112px;
}}

.outro-actions {{
  padding:17px 20px 19px;
  border:1px solid {LINE};
  border-radius:21px;
  background:{SOFT};
  box-shadow:0 8px 22px rgba(11,46,89,.045);
}}

.outro-actions-head {{
  display:flex;
  align-items:baseline;
  justify-content:space-between;
  gap:18px;
  padding:0 3px 11px;
}}

.outro-actions-kicker {{
  color:{NAVY};
  font-size:13px;
  font-weight:950;
  letter-spacing:.65px;
  text-transform:uppercase;
}}

.outro-actions-title {{
  color:{MUTED};
  font-size:10px;
  font-weight:800;
  letter-spacing:.35px;
}}

.outro-action-grid {{
  display:grid;
  grid-template-columns:repeat(3,1fr);
  gap:11px;
}}

.outro-action-card {{
  min-height:154px;
  display:flex;
  flex-direction:column;
  justify-content:space-between;
  overflow:hidden;
  border:1px solid {LINE};
  border-radius:16px;
  background:{WHITE};
}}

.outro-action-primary {{
  border:1.5px solid {GOLD};
}}

.outro-action-top {{
  display:flex;
  gap:11px;
  padding:13px 13px 8px;
}}

.outro-action-number {{
  width:31px;
  height:31px;
  flex:none;
  display:flex;
  align-items:center;
  justify-content:center;
  border-radius:50%;
  background:{NAVY};
  color:{GOLD};
  font-size:10px;
  font-weight:950;
}}

.outro-action-title {{
  color:{NAVY};
  font-size:13px;
  line-height:1.05;
  font-weight:950;
  letter-spacing:.35px;
}}

.outro-action-text {{
  margin-top:5px;
  color:{INK};
  font-size:11px;
  line-height:1.23;
  font-weight:700;
}}

.outro-action-art {{
  height:66px;
  display:flex;
  align-items:center;
  justify-content:center;
  background:{SOFT};
  border-top:1px solid {LINE};
}}

.outro-action-art svg {{
  width:64px;
  height:52px;
  fill:none;
  stroke:{NAVY};
  stroke-width:2.1;
  stroke-linecap:round;
  stroke-linejoin:round;
}}

.outro-art-calendar svg {{
  stroke:{NAVY};
}}

.outro-art-share svg {{
  stroke:{NAVY};
}}

.outro-art-link svg {{
  stroke:{NAVY};
}}

.links-v3 {{
  display:flex;
  flex-direction:column;
  gap:20px;
}}

.official-cta {{
  position:relative;
  min-height:250px;
  display:grid;
  grid-template-columns:minmax(0,1fr) 190px;
  gap:25px;
  align-items:center;
  background:{NAVY};
  border-radius:24px;
  padding:27px 30px;
  overflow:hidden;
  box-shadow:0 14px 32px rgba(11,46,89,.15);
}}

.official-cta:before {{
  content:"";
  position:absolute;
  right:-105px;
  top:-125px;
  width:330px;
  height:330px;
  border:30px solid rgba(255,255,255,.07);
  border-radius:50%;
}}

.official-cta:after {{
  content:"";
  position:absolute;
  left:-80px;
  bottom:-115px;
  width:230px;
  height:230px;
  border:22px solid rgba(228,165,28,.10);
  border-radius:50%;
}}

.official-cta-copy {{
  position:relative;
  z-index:2;
  min-width:0;
}}

.official-cta .section-kicker {{
  color:{GOLD};
}}

.official-cta-title {{
  color:{WHITE};
  font-size:30px;
  line-height:1.12;
  font-weight:900;
  letter-spacing:-.5px;
  max-width:610px;
  margin-top:13px;
}}

.official-cta-url {{
  color:#BCD7EA;
  font-size:12px;
  line-height:1.35;
  margin-top:12px;
  max-width:610px;
  overflow-wrap:anywhere;
}}

.official-cta-badge {{
  display:inline-flex;
  margin-top:17px;
  padding:8px 12px;
  border-radius:999px;
  background:{GOLD};
  color:{NAVY};
  font-size:9px;
  line-height:1;
  font-weight:950;
  letter-spacing:.7px;
}}

.official-cta-qr {{
  position:relative;
  z-index:2;
}}

.official-cta .link-card {{
  display:block;
  margin:0;
  padding:10px;
  background:{WHITE};
  border:0;
  border-radius:17px;
  box-shadow:0 10px 25px rgba(0,0,0,.14);
}}

.official-cta .link-copy {{
  display:none;
}}

.official-cta .qr-wrap {{
  padding:5px;
  border:0;
  border-radius:10px;
  background:{WHITE};
}}

.official-cta .qr-wrap img {{
  width:160px;
  height:160px;
  display:block;
}}

.apply-section {{
  background:{SOFT};
  border:1px solid {LINE};
  border-radius:22px;
  padding:22px 24px 24px;
  box-shadow:0 8px 24px rgba(11,46,89,.045);
}}

.apply-section-head {{
  display:flex;
  align-items:flex-end;
  justify-content:space-between;
  gap:20px;
}}

.apply-section-title {{
  color:{NAVY};
  font-size:27px;
  line-height:1.05;
  font-weight:900;
  margin-top:7px;
}}

.apply-section-note {{
  color:{MUTED};
  font-size:11px;
  line-height:1;
  font-weight:800;
  letter-spacing:.4px;
  white-space:nowrap;
}}

.apply-check-grid {{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:11px 13px;
  margin-top:18px;
}}

.apply-check-card {{
  min-height:86px;
  display:flex;
  align-items:flex-start;
  gap:12px;
  background:{WHITE};
  border:1px solid {LINE};
  border-radius:15px;
  padding:14px 15px;
}}

.apply-check-number {{
  width:28px;
  height:28px;
  border-radius:50%;
  flex:none;
  display:flex;
  align-items:center;
  justify-content:center;
  background:{SOFT_BLUE};
  color:{BLUE};
  font-size:9px;
  font-weight:950;
}}

.apply-check-text {{
  color:{INK};
  font-size:15px;
  line-height:1.28;
  font-weight:700;
  overflow-wrap:anywhere;
}}

/* Existing link-list fallback for additional URLs */
.link-list {{
  background:{WHITE};
  border:1px solid {LINE};
  border-radius:15px;
  padding:4px 16px;
}}

.link-row {{ padding:11px 0; border-bottom:1px solid {LINE}; }}
.link-row:last-child {{ border-bottom:0; }}
.link-row .label {{ display:block; margin-bottom:3px; }}
.link-row .url {{ margin-top:0; }}

.links-wrap.dense .link-card {{
  grid-template-columns:minmax(0,1fr) 96px;
  gap:12px;
  padding:12px;
}}
.links-wrap.dense .qr-wrap img {{ width:82px; height:82px; }}
.links-wrap.dense .link-title {{ font-size:17px; }}

.links-wrap.ultra-dense .link-card {{
  grid-template-columns:minmax(0,1fr) 82px;
  gap:9px;
  padding:9px;
}}
.links-wrap.ultra-dense .qr-wrap img {{ width:68px; height:68px; }}
.links-wrap.ultra-dense .link-title {{ font-size:14px; }}
.links-wrap.ultra-dense .url {{ font-size:9px; }}

/* FALLBACK CONTENT */
.content-block.eligibility .info-card {{ border-left:4px solid {BLUE}; }}
.content-block.fees .info-card {{ border-top:3px solid {GOLD}; }}
.content-block.links {{ margin-top:25px; }}
.content-block.posts {{ margin-top:22px; }}
.content-block.dates {{ margin-top:22px; }}
/* HERO */
.hero {{
  margin-top:28px;
  min-height:650px;
  position:relative;
  overflow:hidden;
  border-radius:28px;
  background:{NAVY};
  padding:32px 40px 30px;
  color:{WHITE};
  box-shadow:0 18px 40px rgba(11,46,89,.17);
}}

.hero:before {{
  content:"";
  position:absolute;
  width:470px; height:470px;
  right:-245px; top:-250px;
  border:46px solid rgba(255,255,255,.065);
  border-radius:50%;
}}

.hero:after {{
  content:"";
  position:absolute;
  width:285px; height:285px;
  left:-190px; bottom:-190px;
  border:36px solid rgba(228,165,28,.12);
  border-radius:50%;
}}

.hero-grid {{
  position:absolute;
  inset:0;
  opacity:.13;
  background-image:
    linear-gradient(rgba(255,255,255,.18) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.18) 1px, transparent 1px);
  background-size:44px 44px;
  mask-image:linear-gradient(to bottom right, black, transparent 68%);
}}

.hero-kicker-row {{
  position:relative;
  z-index:2;
  display:flex;
  justify-content:space-between;
  align-items:center;
}}

.hero-kicker {{
  display:inline-flex;
  align-items:center;
  padding:8px 11px;
  border:1px solid rgba(228,165,28,.42);
  border-radius:999px;
  color:{GOLD};
  font-size:12px;
  line-height:1;
  font-weight:950;
  letter-spacing:1.2px;
}}

.hero-count {{
  color:{GOLD};
  font-size:10px;
  line-height:1;
  font-weight:950;
  letter-spacing:1px;
}}

.hero-main {{
  position:relative;
  z-index:2;
  margin-top:28px;
}}

.hero-vacancy-block {{
  display:inline-block;
}}

.hero-vacancy-label {{
  color:#D7E5F0;
  font-size:12px;
  line-height:1;
  font-weight:950;
  letter-spacing:3px;
  margin-bottom:13px;
}}

.hero-vacancy-row {{
  display:flex;
  align-items:flex-end;
  gap:15px;
}}

.hero-stat-number {{
  color:{WHITE};
  font-size:108px;
  line-height:.78;
  font-weight:950;
  letter-spacing:-5px;
}}

.hero-stat-caption {{
  color:{GOLD};
  font-size:14px;
  line-height:1.05;
  font-weight:950;
  letter-spacing:1.2px;
  padding-bottom:6px;
}}

.hero-application-row {{
  display:flex;
  align-items:stretch;
  gap:16px;
  margin-top:25px;
  max-width:890px;
}}

.hero-date-tablet {{
  width:310px;
  min-height:215px;
  flex:none;
  padding:18px 20px;
  border:1px solid rgba(255,255,255,.24);
  border-radius:20px;
  background:rgba(255,255,255,.065);
  display:flex;
  flex-direction:column;
  justify-content:center;
}}

.hero-date-item {{
  display:flex;
  flex-direction:column;
  gap:5px;
}}

.hero-date-label {{
  color:{GOLD};
  font-size:11px;
  line-height:1;
  font-weight:950;
  letter-spacing:1.25px;
}}

.hero-date-value {{
  color:{WHITE};
  font-size:25px;
  line-height:1.08;
  font-weight:900;
  letter-spacing:-.4px;
}}

.hero-date-arrow {{
  color:{GOLD};
  font-size:30px;
  line-height:.8;
  font-weight:900;
  margin:7px 0;
  padding-left:2px;
}}

.hero-qr-card {{
  min-width:0;
  flex:1;
  min-height:215px;
  padding:17px 18px;
  border:1px solid rgba(228,165,28,.55);
  border-radius:20px;
  background:rgba(255,255,255,.09);
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:15px;
}}

.hero-qr-copy {{
  min-width:0;
  flex:1;
}}

.hero-qr-label {{
  color:{GOLD};
  font-size:11px;
  line-height:1;
  font-weight:950;
  letter-spacing:1.3px;
}}

.hero-qr-title {{
  color:{WHITE};
  font-size:20px;
  line-height:1.12;
  font-weight:900;
  margin-top:9px;
}}

.hero-qr-url {{
  color:#BFD5E5;
  font-size:10px;
  line-height:1.25;
  margin-top:10px;
  overflow-wrap:anywhere;
  max-height:38px;
  overflow:hidden;
}}

.hero-qr-image {{
  width:145px;
  height:145px;
  flex:none;
  padding:7px;
  border-radius:14px;
  background:{WHITE};
  object-fit:contain;
}}

.hero-date-pill {{
  width:max-content;
  max-width:890px;
  display:flex;
  align-items:center;
  gap:13px;
  margin-top:27px;
  padding:13px 18px;
  border:1px solid rgba(255,255,255,.24);
  border-radius:999px;
  background:rgba(255,255,255,.055);
  color:{WHITE};
  font-size:16px;
  line-height:1.15;
  font-weight:750;
}}

.hero-date-icon {{
  width:34px;
  height:34px;
  border-radius:50%;
  flex:none;
  display:flex;
  align-items:center;
  justify-content:center;
  background:{WHITE};
  color:{NAVY};
  font-size:15px;
  font-weight:950;
}}

.hero-info-grid {{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:12px;
  max-width:890px;
  margin-top:22px;
}}

.hero-info-card {{
  min-height:72px;
  display:flex;
  align-items:flex-start;
  gap:11px;
  padding:14px 15px;
  border:1px solid rgba(255,255,255,.13);
  border-radius:15px;
  background:rgba(255,255,255,.065);
}}

.hero-info-icon {{
  width:25px;
  height:25px;
  border-radius:50%;
  flex:none;
  display:flex;
  align-items:center;
  justify-content:center;
  background:rgba(228,165,28,.17);
  color:{GOLD};
  font-size:12px;
  font-weight:950;
}}

.hero-info-text {{
  color:{WHITE};
  font-size:14px;
  line-height:1.25;
  font-weight:700;
  overflow-wrap:anywhere;
}}

.hero-callout {{
  position:absolute;
  z-index:2;
  left:40px;
  right:40px;
  bottom:73px;
  display:flex;
  align-items:center;
  gap:14px;
  padding:15px 18px;
  border-radius:17px;
  background:{GOLD};
  color:{NAVY};
}}

.hero-callout-icon {{
  width:34px;
  height:34px;
  border-radius:50%;
  flex:none;
  display:flex;
  align-items:center;
  justify-content:center;
  background:{NAVY};
  color:{GOLD};
  font-size:21px;
  font-weight:900;
}}

.hero-callout-title {{
  font-size:11px;
  line-height:1;
  font-weight:950;
  letter-spacing:.9px;
}}

.hero-callout-text {{
  font-size:12px;
  line-height:1.25;
  font-weight:700;
  margin-top:5px;
}}

.hero-bottom {{
  position:absolute;
  z-index:3;
  left:40px; right:40px; bottom:28px;
  padding-top:15px;
  border-top:1px solid rgba(255,255,255,.18);
  display:flex;
  justify-content:space-between;
  align-items:center;
  color:#AFC8DC;
  font-size:10px;
  line-height:1.1;
  font-weight:900;
  letter-spacing:.8px;
}}

.hero-arrow {{
  color:{GOLD};
  font-size:24px;
  line-height:1;
}}

/* FOOTER */
footer {{
  position:relative;
  z-index:4;
  margin-top:auto;
  padding:12px 0 8px;
}}

.benefit-strip:before {{
  content:"";
  position:absolute;
  left:0;
  right:0;
  top:-8px;
  height:8px;
  background:linear-gradient(90deg, transparent 0%, rgba(11,46,89,.10) 18%, rgba(11,46,89,.10) 82%, transparent 100%);
}}

.benefit-strip {{
  min-height:70px;
  width:100%;
  display:grid;
  grid-template-columns:1fr 1px 1fr 1px 1fr;
  align-items:center;
  border-radius:17px;
  background:{NAVY};
  padding:10px 24px;
  box-shadow:0 8px 20px rgba(11,46,89,.10);
  overflow:hidden;
  position:relative;
}}

.benefit-strip:after {{
  content:"";
  position:absolute;
  right:-40px;
  top:-75px;
  width:145px;
  height:145px;
  border:16px solid rgba(255,255,255,.055);
  border-radius:50%;
}}

.benefit-item {{
  display:flex;
  align-items:center;
  justify-content:center;
  gap:10px;
  min-width:0;
  position:relative;
  z-index:1;
}}

.benefit-icon {{
  width:40px;
  height:40px;
  flex:none;
  border:1.5px solid rgba(228,165,28,.85);
  border-radius:50%;
  display:flex;
  align-items:center;
  justify-content:center;
}}

.benefit-icon svg {{
  width:23px;
  height:23px;
  fill:none;
  stroke:{WHITE};
  stroke-width:1.8;
  stroke-linecap:round;
  stroke-linejoin:round;
}}

.benefit-copy {{
  display:flex;
  flex-direction:column;
  gap:2px;
  color:{WHITE};
  font-size:12px;
  line-height:1.05;
  font-weight:700;
  min-width:0;
}}

.benefit-copy strong {{
  font-weight:900;
}}

.benefit-copy span {{
  color:#D8E6F1;
  font-weight:650;
}}

.benefit-divider {{
  width:1px;
  height:36px;
  background:rgba(255,255,255,.22);
}}

.footer-bottom {{
  min-height:31px;
  display:grid;
  grid-template-columns:minmax(0,1fr) 50px;
  gap:12px;
  align-items:center;
  padding-top:8px;
}}

.footer-note {{
  color:{MUTED};
  font-size:9px;
  line-height:1.2;
  text-align:center;
}}

.footer-page {{
  color:{NAVY};
  font-size:11px;
  font-weight:950;
  text-align:right;
}}

.content-block.eligibility .info-card {{ border-left:4px solid {BLUE}; }}
.content-block.fees .info-card {{ border-top:3px solid {GOLD}; }}
.content-block.links {{ margin-top:25px; }}
.content-block.posts {{ margin-top:22px; }}
.content-block.dates {{ margin-top:22px; }}

/* ============================================================
   MOBILE-FIRST TYPE SCALE
   The artwork is rendered at 1080x1350 but is primarily viewed
   as a small Instagram image. Keep essential facts comfortably
   readable after down-scaling.
   ============================================================ */

/* Global hierarchy */
.top-brand-mark {{ width:40px; height:40px; font-size:13px; }}
.top-brand-name {{ font-size:16px; }}
.top-brand-sub {{ font-size:10px; }}
.top-slide {{ font-size:11px; padding:8px 12px; }}

.eyebrow {{
  font-size:28px;
  line-height:1.08;
  padding:15px 22px;
}}

h1 {{
  font-size:46px;
  line-height:1.03;
}}

.sub {{
  font-size:20px;
  line-height:1.25;
}}

.label {{
  font-size:14px;
}}

.value {{
  font-size:24px;
  line-height:1.18;
}}

.meta {{
  font-size:15px;
  line-height:1.28;
}}

/* Dense fallback cards: raise the floor so source facts don't
   become microscopic. The JS fit routine handles truly dense slides. */
.card-grid.compact .value {{ font-size:21px; }}
.card-grid.compact .meta {{ font-size:14px; }}
.card-grid.dense .label {{ font-size:13px; }}
.card-grid.dense .value {{ font-size:19px; line-height:1.17; }}
.card-grid.dense .meta {{ font-size:13px; }}
.card-grid.ultra-dense .label {{ font-size:12px; }}
.card-grid.ultra-dense .value {{ font-size:17px; line-height:1.15; }}
.card-grid.ultra-dense .meta {{ font-size:12px; }}

/* Slide 1 — cover / hook */
.hero-cover-main {{
  margin-top:24px;
}}

.hero-highlight-badge {{
  display:inline-flex;
  align-items:center;
  max-width:860px;
  padding:12px 18px;
  border-radius:12px;
  background:{GOLD};
  color:{NAVY};
  font-size:23px;
  line-height:1.12;
  font-weight:950;
  letter-spacing:.1px;
  box-shadow:0 7px 18px rgba(228,165,28,.18);
}}

.hero-vacancy-focus {{
  position:relative;
  z-index:3;
}}
.hero-stat-number-wrap {{
  display:flex;
  align-items:center;
  padding:5px 15px 7px;
  border:3px solid rgba(228,165,28,.82);
  border-radius:18px;
  background:linear-gradient(145deg, rgba(255,255,255,.13), rgba(255,255,255,.035));
  box-shadow:
    inset 0 0 0 2px rgba(255,255,255,.12),
    0 8px 18px rgba(0,0,0,.16);
}}
.hero-stat-number-wrap .hero-stat-number {{
  text-shadow:0 3px 0 rgba(0,0,0,.15);
}}
.hero-cover-decor {{
  position:absolute;
  right:30px;
  top:180px;
  width:410px;
  height:340px;
  pointer-events:none;
  z-index:1;
}}
.hero-gear {{
  position:absolute;
  color:rgba(228,165,28,.34);
  font-family:Arial, sans-serif;
  line-height:1;
  filter:drop-shadow(0 2px 1px rgba(0,0,0,.08));
}}
.gear-large {{
  right:80px;
  top:70px;
  font-size:245px;
}}
.gear-small {{
  right:5px;
  top:145px;
  font-size:135px;
}}
.hero-cover-callout {{
  position:absolute;
  right:10px;
  top:235px;
  display:flex;
  flex-direction:column;
  align-items:flex-start;
  padding:12px 17px 13px;
  border-radius:15px;
  background:linear-gradient(145deg, #F7C43A, {GOLD});
  color:{NAVY};
  box-shadow:0 7px 18px rgba(0,0,0,.16);
  transform:rotate(-1deg);
}}
.hero-cover-callout strong {{
  font-size:22px;
  line-height:.92;
  font-weight:950;
  letter-spacing:-.5px;
}}
.hero-cover-callout strong:last-child {{
  font-size:20px;
  margin-top:2px;
}}
.hero-vacancy-focus {{
  margin-top:30px;
}}

.hero-vacancy-focus-row {{
  display:flex;
  align-items:flex-end;
  justify-content:flex-start;
  gap:20px;
}}

.hero-vacancy-focus .hero-stat-number {{
  color:{WHITE};
  font-size:126px;
  line-height:.82;
  font-weight:950;
  letter-spacing:-6px;
}}

.hero-vacancy-focus .hero-stat-caption {{
  color:{GOLD};
  font-size:22px;
  line-height:1;
  font-weight:950;
  letter-spacing:1.5px;
  padding-bottom:8px;
}}

.hero-cover-message {{
  margin-top:34px;
  display:flex;
  flex-direction:column;
  gap:5px;
  color:{WHITE};
}}

.hero-cover-message strong {{
  color:{GOLD};
  font-size:20px;
  line-height:1.1;
  font-weight:950;
  letter-spacing:.3px;
}}

.hero-cover-message span {{
  color:#D7E5F0;
  font-size:17px;
  line-height:1.2;
  font-weight:700;
}}

/* Slide 1 — make the application window unmistakable */
.hero-vacancy-label {{
  font-size:14px;
  letter-spacing:3.2px;
}}

.hero-stat-number {{
  font-size:116px;
}}

.hero-stat-caption {{
  font-size:16px;
}}

.hero-date-pill {{
  font-size:21px;
  line-height:1.15;
  padding:14px 19px;
}}

.hero-date-icon {{
  width:38px;
  height:38px;
  font-size:16px;
}}

.hero-callout-title {{
  font-size:12px;
}}

.hero-callout-text {{
  font-size:13px;
}}

.hero-bottom {{
  font-size:11px;
}}

.hero-arrow {{
  font-size:26px;
}}

.hero-application-row {{
  gap:14px;
  margin-top:22px;
}}
.hero-date-tablet {{
  width:300px;
  min-height:205px;
  padding:16px 18px;
}}
.hero-date-value {{ font-size:24px; }}
.hero-date-arrow {{ font-size:29px; }}
.hero-qr-card {{
  min-height:205px;
  padding:15px 16px;
}}
.hero-qr-title {{ font-size:19px; }}
.hero-qr-image {{
  width:132px;
  height:132px;
}}

.hero-cover-decor {{
  opacity:.72;
  transform:scale(.88);
  transform-origin:right top;
}}

/* Slide 1 — retain the vertical application-date tablet */
.hero-date-tablet-cover {{
  position:relative;
  overflow:hidden;
}}
.hero-date-tablet-cover:after {{
  content:"";
  position:absolute;
  right:68px;
  top:16px;
  bottom:16px;
  width:1px;
  background:rgba(255,255,255,.22);
}}
.hero-date-tablet-cover {{
  width:360px;
  min-height:150px;
  margin-top:28px;
  padding:16px 20px;
  display:flex;
  flex-direction:column;
  justify-content:center;
  border:1px solid rgba(255,255,255,.28);
  border-radius:16px;
  background:rgba(255,255,255,.075);
  box-sizing:border-box;
}}

.hero-date-tablet-cover .hero-date-item {{
  display:flex;
  align-items:baseline;
  justify-content:space-between;
  gap:18px;
}}

.hero-date-tablet-cover .hero-date-label {{
  color:{GOLD};
  font-size:12px;
  font-weight:950;
  letter-spacing:1px;
}}

.hero-date-tablet-cover .hero-date-value {{
  color:{WHITE};
  font-size:23px;
  line-height:1.05;
  font-weight:900;
  white-space:nowrap;
}}

.hero-date-tablet-cover .hero-date-arrow {{
  color:{GOLD};
  font-size:22px;
  line-height:1;
  margin:3px 0;
  padding-left:2px;
}}

/* Final Slide 1 cover sizing */
.hero-cover-main .hero-vacancy-label {{
  font-size:14px;
  letter-spacing:3px;
  margin-bottom:14px;
}}

.hero-cover-main .hero-stat-number {{
  font-size:126px;
}}

.hero-cover-main .hero-stat-caption {{
  font-size:22px;
}}

.hero-bottom .hero-arrow {{
  font-size:23px;
}}

/* Slide 2 — recruitment snapshot */
.snapshot-label {{ font-size:14px; }}
.snapshot-value {{ font-size:27px; }}
.snapshot-meta {{ font-size:14px; }}

.snapshot-feature .snapshot-label {{ font-size:16px; }}
.snapshot-feature .snapshot-value {{ font-size:76px; }}
.snapshot-feature .snapshot-meta {{ font-size:15px; }}

.snapshot-two .snapshot-card:first-child .snapshot-value {{ font-size:68px; }}
.snapshot-one .snapshot-card:first-child .snapshot-value {{ font-size:82px; }}

/* Slide 3 — eligibility */
.eligibility-code {{ font-size:13px; }}
.eligibility-value {{ font-size:21px; line-height:1.18; }}
.eligibility-meta {{ font-size:13px; }}

.eligibility-few .eligibility-value {{ font-size:30px; }}
.eligibility-medium .eligibility-value {{ font-size:20px; }}
.eligibility-many .eligibility-value {{ font-size:18px; }}
.eligibility-many .eligibility-code {{ font-size:12px; }}

/* Slide 4 — fees / selection / pay */
.fee-primary-card .label {{ font-size:14px; }}
.fee-primary-card .value {{ font-size:34px; }}
.fee-secondary-grid .value {{ font-size:21px; }}

/* Slide 5 — dates */
.date-marker {{
  width:32px;
  height:32px;
  font-size:10px;
}}

.date-row:not(:last-child):before {{
  left:15px;
}}

.date-value {{
  font-size:35px;
  line-height:1.08;
}}

.date-list .label {{
  font-size:14px;
}}

.date-list .meta {{
  font-size:13px;
}}

.checklist-panel .bullet-list li {{
  font-size:17px;
  line-height:1.3;
}}

.checklist-panel .bullet-check {{
  width:29px;
  height:29px;
}}

.section-kicker {{
  font-size:14px;
  line-height:1.15;
  font-weight:950;
  letter-spacing:.8px;
}}

/* Slide 6 — official notification */
.official-cta-title {{
  font-size:33px;
}}

.official-cta-url {{
  font-size:14px;
}}

.official-cta-badge {{
  font-size:10px;
}}

.apply-section-title {{
  font-size:29px;
}}

.apply-section-note {{
  font-size:12px;
}}

.apply-check-text {{
  font-size:17px;
  line-height:1.3;
}}

.apply-check-number {{
  width:31px;
  height:31px;
  font-size:10px;
}}

/* Footer — deliberately larger because it is viewed very small
   on phones. */
.benefit-strip {{
  min-height:82px;
  padding:12px 25px;
  border-radius:18px;
}}

.benefit-item {{
  gap:12px;
}}

.benefit-icon {{
  width:48px;
  height:48px;
  border-width:2px;
}}

.benefit-icon svg {{
  width:28px;
  height:28px;
  stroke-width:2;
}}

.benefit-copy {{
  font-size:14px;
  line-height:1.08;
}}

.benefit-divider {{
  height:42px;
}}

.footer-bottom {{
  min-height:35px;
  padding-top:9px;
}}

.footer-note {{
  font-size:11px;
  line-height:1.2;
}}

.footer-page {{
  font-size:13px;
}}


/* ============================================================
   SLIDE 2 — MOBILE DENSE POST CARDS
   More information should fit by reducing card chrome/spacing,
   NOT by making the post name microscopic.
   ============================================================ */

/* Many-post slides: compact the cards vertically while keeping
   the actual post title strong and readable. */
.snapshot-many {{
  gap:11px;
  grid-auto-rows:minmax(108px, auto);
}}

.snapshot-many .snapshot-card {{
  min-height:108px;
  padding:14px 16px;
  border-radius:16px;
}}

.snapshot-many .snapshot-card:nth-child(2),
.snapshot-many .snapshot-card:nth-child(3) {{
  min-height:108px;
}}

.snapshot-many .snapshot-card:nth-child(4) {{
  min-height:100px;
  border-top-width:3px;
}}

.snapshot-many .snapshot-index {{
  top:12px;
  right:13px;
  width:27px;
  height:27px;
  font-size:8px;
}}

.snapshot-many .snapshot-copy {{
  padding-right:30px;
}}

.snapshot-many .snapshot-label {{
  font-size:11px;
  line-height:1.08;
  letter-spacing:.65px;
}}

.snapshot-many .snapshot-value {{
  font-size:25px;
  line-height:1.08;
  margin-top:5px;
}}

.snapshot-many .snapshot-meta {{
  font-size:12px;
  line-height:1.18;
  margin-top:4px;
}}

/* Extra-dense: preserve a readable title but remove more vertical
   chrome. Content is allowed to grow naturally if a title wraps. */
.snapshot-many.snapshot-extra-dense .snapshot-card {{
  min-height:96px;
  padding:12px 14px;
}}

.snapshot-many.snapshot-extra-dense .snapshot-value {{
  font-size:23px;
  line-height:1.06;
}}

.snapshot-many.snapshot-extra-dense .snapshot-label {{
  font-size:10px;
}}

.snapshot-many.snapshot-extra-dense .snapshot-index {{
  width:25px;
  height:25px;
  top:10px;
  right:11px;
}}

/* Two-card slides can also be tighter; this prevents an unusually
   long post title from consuming excessive vertical space. */
.snapshot-two {{
  gap:13px;
}}

.snapshot-two .snapshot-card {{
  min-height:205px;
  padding:18px 19px;
}}

.snapshot-two .snapshot-card:first-child .snapshot-value {{
  font-size:68px;
}}

/* The post title is the important information — make it stronger
   than the small category label. */
.snapshot-card:not(.snapshot-feature) .snapshot-value {{
  font-size:27px;
  line-height:1.08;
}}

.snapshot-card:not(.snapshot-feature) .snapshot-label {{
  font-size:12px;
}}

/* Long titles get slightly tighter line spacing rather than being
   clipped or pushed underneath the footer. */
.snapshot-card .snapshot-value {{
  overflow-wrap:break-word;
  word-break:normal;
  hyphens:auto;
}}


@media (max-width: 900px) {{
  .outro-official {{
    grid-template-columns:minmax(0,1fr) 285px;
    gap:14px;
    padding:24px 25px;
  }}
  .outro-official-title {{
    font-size:26px;
  }}
  .outro-qr-box {{
    width:116px;
    height:116px;
  }}
  .outro-qr-box .qr-wrap img {{
    width:98px;
    height:98px;
  }}
  .outro-qr-label {{
    width:90px;
  }}
  .outro-action-text {{
    font-size:10px;
  }}
}}
</style>
</head>

<body>
  <div class="page-layer" aria-hidden="true"></div>

  <div class="topbar">
    <div class="top-brand">
      {brand_markup}
      <div class="top-brand-copy">
        <div class="top-brand-name">SHAKTIDOOTAM</div>
        <div class="top-brand-sub">Government Job Updates</div>
      </div>
    </div>
    <div class="top-slide">SLIDE {int(number):02d} OF {int(total):02d}</div>
  </div>

  <div class="org-row{' hook-org-row' if stype == 'hook' else ''}">
    <div class="eyebrow{' hook-eyebrow' if stype == 'hook' else ''}">{esc(eyebrow)}</div>
  </div>

  <h1 class="{'hook-title' if stype == 'hook' else ''}">{esc(title)}</h1>
  {f'<div class="sub{' hook-subtitle' if stype == 'hook' else ''}">{esc(subtitle)}</div>' if subtitle else ""}
  <div class="rule"></div>

  {hero}
  {content}
  {footer}
<script>
(function () {{
  function fitContent() {{
    const content = document.querySelector(".content-block");
    const footer = document.querySelector("footer");
    if (!content || !footer) return;

    content.style.transform = "";
    content.style.transformOrigin = "";
    content.style.width = "";
    content.style.marginLeft = "";

    const contentTop = content.getBoundingClientRect().top;
    const footerTop = footer.getBoundingClientRect().top;
    const available = Math.max(1, footerTop - contentTop - 14);
    const actual = Math.max(
      content.scrollHeight,
      content.getBoundingClientRect().height
    );

    if (actual > available) {{
      // Never let dense source content collide with the footer.
      // 0.72 is a safety floor to keep type readable.
      const scale = Math.max(0.72, Math.min(1, available / actual));
      content.style.transformOrigin = "top center";
      content.style.transform = "scale(" + scale.toFixed(4) + ")";
      content.style.width = (100 / scale).toFixed(3) + "%";
      content.style.marginLeft = ((100 - (100 / scale)) / 2).toFixed(3) + "%";
    }}
  }}

  window.addEventListener("load", function () {{
    requestAnimationFrame(function () {{
      requestAnimationFrame(fitContent);
    }});
  }});

  window.fitCarouselContent = fitContent;
}})();
</script>
</body>
</html>"""


async def render(deck, out):
    """
    Preserve the exact interface used by app.py:
        asyncio.run(render(deck, str(out)))
    """
    os.makedirs(out, exist_ok=True)

    slides = deck.get("slides") or []
    if not slides:
        raise ValueError("Deck contains no slides.")

    slides = sorted(
        slides,
        key=lambda s: int(s.get("slide_number") or 0)
    )

    async with async_playwright() as p:  

        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox"],
        )

        page = await browser.new_page(
            viewport={"width": W, "height": H},
            device_scale_factor=1,
        )

        total = len(slides)
        vacancy_total = _extract_vacancy_total(deck)
        organisation = _infer_organisation_from_context(deck)
        application_url = _extract_application_url(deck)
        logo_domain = _extract_logo_domain(deck)
        print(f"Rendering {total} slides for {organisation} (logo: {logo_domain})")
        logo_url = fetch_logo_data_uri(logo_domain)
        print(f"Logo data URI loaded: {bool(logo_url)}")
        # Repair a common upstream mapping error without changing the source
        # facts: if Slide 1's eyebrow contains a qualification instead of the
        # organisation, move that qualification to the eligibility slide.
        moved_qualification = ""
        hook_slide = next(
            (s for s in slides if _normalise_type(s.get("slide_type")) == "hook"),
            None,
        )
        if hook_slide:
            raw_eyebrow = clean_text(hook_slide.get("eyebrow"))
            if _looks_like_qualification(raw_eyebrow):
                moved_qualification = raw_eyebrow

        if moved_qualification:
            for s in slides:
                if _normalise_type(s.get("slide_type")) == "eligibility":
                    s["_moved_qualification"] = moved_qualification
                    break

        for s in slides:
            slide_no = int(s.get("slide_number") or 1)

            await page.set_content(
                build_html(
                    s,
                    total,
                    total_vacancies=vacancy_total,
                    organisation=organisation,
                    application_url=application_url,
                    logo_url=logo_url if _normalise_type(s.get("slide_type")) == "hook" else "",
                ),
                wait_until="load",
            )

            await page.evaluate("document.fonts && document.fonts.ready")

            await page.screenshot(
                path=os.path.join(out, f"slide_{slide_no}.png"),
                type="png",
            )

        await browser.close()
