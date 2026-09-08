
import os
import re
import html
import base64
from io import BytesIO

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
    <div class="date-row">
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


def build_html(slide, total, theme="professional_white"):
    """
    Existing deck contract from carousel.py:
      slide_number, slide_type, title, eyebrow, subtitle,
      cards[{label,value,meta}], bullets[], footer_note
    """
    cards = _safe_cards(slide.get("cards") or [])
    stype = _normalise_type(slide.get("slide_type"))
    number = slide.get("slide_number") or 1
    title = clean_text(slide.get("title")) or "Recruitment Update"
    eyebrow = clean_text(slide.get("eyebrow")) or "Government Recruitment"
    subtitle = clean_text(slide.get("subtitle"))
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
        metric = clean_text(cards[0].get("value")) if cards else ""
        metric_label = (
            clean_text(cards[0].get("label")).upper()
            if cards else "VACANCIES"
        )

        hero_bullets = "".join(
            f'<div class="hero-point"><span></span>{esc(x)}</div>'
            for x in bullets[:3]
        )

        hero = f"""
        <section class="hero">
          <div class="hero-grid"></div>

          {f"""
          <div class="hero-stat">
            <div class="hero-stat-number">{esc(metric)}</div>
            <!-- small duplicate vacancy label removed -->
          </div>
          """ if metric else ""}

          {f"""
          <div class="hero-points">
            {hero_bullets}
          </div>
          """ if hero_bullets else ""}

          <div class="hero-bottom">
            <span>SWIPE FOR POSTS • ELIGIBILITY • DATES • APPLICATION</span>
            <span class="hero-arrow">→</span>
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
            body = f'<div class="snapshot-grid">{snapshot_html}</div>'

        elif stype == "eligibility":
            # A single eligibility fact should look intentional, not like
            # an undersized generic card floating in a large empty canvas.
            eligibility_cards = "".join(
                _card_html(card, i) for i, card in enumerate(cards)
            )
            body = f"""
            <div class="eligibility-layout">
              <div class="eligibility-panel">
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
            <div class="dates-composition">
              <section class="dates-panel">
                <div class="section-kicker">APPLICATION SCHEDULE</div>
                <div class="date-list">{cards_html}</div>
              </section>
              {_checklist_panel_html(bullets, "BEFORE YOU SUBMIT")}
            </div>
            """

        elif stype == "links":
            body = f"""
            <div class="links-composition">
              <section class="links-panel">
                <div class="section-kicker">OFFICIAL SOURCE</div>
                <div class="links-wrap {density}">{cards_html}</div>
              </section>
              {_checklist_panel_html(bullets, "BEFORE YOU APPLY")}
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
        <div class="footer-brand">
          <svg class="instagram-icon" viewBox="0 0 24 24" aria-hidden="true">
            <rect x="3" y="3" width="18" height="18" rx="5"></rect>
            <circle cx="12" cy="12" r="4"></circle>
            <circle class="instagram-dot" cx="17.5" cy="6.5" r="1"></circle>
          </svg>
          <span>@shaktidootam</span>
        </div>
        <div class="footer-note">{esc(note)}</div>
        <div class="footer-page">{int(number):02d}/{int(total):02d}</div>
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

.topbar {{
  min-height:54px;
  display:flex;
  align-items:center;
  position:relative;
  z-index:3;
}}

.brand {{ display:flex; align-items:center; gap:11px; }}

.brand-mark {{
  width:38px; height:38px;
  border-radius:10px;
  background:{NAVY}; color:{WHITE};
  display:flex; align-items:center; justify-content:center;
  font-size:13px; font-weight:950;
}}

.brand-copy {{ display:flex; flex-direction:column; }}

.brand-name {{
  color:{NAVY};
  font-size:20px;
  line-height:1;
  font-weight:950;
  letter-spacing:.8px;
  text-transform:uppercase;
}}

.brand-sub {{
  color:{NAVY};
  font-size:24px;
  line-height:1;
  font-weight:950;
  letter-spacing:.4px;
}}

.page-pill {{
  background:{WHITE};
  border:1px solid {LINE};
  color:{NAVY};
  border-radius:999px;
  padding:8px 13px;
  font-size:12px;
  font-weight:900;
  letter-spacing:.4px;
}}

.eyebrow {{
  position:relative;
  z-index:2;
  margin-top:0;
  display:inline-flex;
  align-self:flex-start;
  background:{GOLD};
  color:{NAVY};
  border-radius:10px;
  padding:15px 22px;
  font-size:27px;
  line-height:1.12;
  font-weight:1000;
  letter-spacing:.35px;
  text-transform:uppercase;
  max-width:900px;
  box-shadow:0 4px 12px rgba(228,165,28,.16);
}}

h1 {{
  position:relative;
  z-index:2;
  margin:15px 0 0;
  color:{NAVY};
  font-size:52px;
  line-height:1.04;
  letter-spacing:-1.9px;
  font-weight:950;
  max-width:920px;
}}

.sub {{
  position:relative;
  z-index:2;
  margin-top:10px;
  color:{MUTED};
  font-size:21px;
  line-height:1.28;
  font-weight:600;
  max-width:900px;
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
  flex:1;
  min-height:0;
  position:relative;
  z-index:2;
  display:flex;
  flex-direction:column;
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
  grid-template-columns:1fr 1fr;
  gap:16px;
  align-content:start;
}}

.snapshot-card {{
  min-height:190px;
  position:relative;
  background:{WHITE};
  border:1px solid {LINE};
  border-radius:20px;
  padding:23px 24px;
  box-shadow:0 8px 24px rgba(11,46,89,.055);
  overflow:hidden;
  display:flex;
  flex-direction:column;
  justify-content:space-between;
}}

.snapshot-card:after {{
  content:"";
  position:absolute;
  right:-55px;
  bottom:-65px;
  width:170px;
  height:170px;
  border:18px solid {SOFT_BLUE};
  border-radius:50%;
}}

.snapshot-index {{
  width:34px;
  height:34px;
  border-radius:50%;
  background:{SOFT_BLUE};
  color:{NAVY};
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:11px;
  font-weight:950;
  position:relative;
  z-index:1;
}}

.snapshot-copy {{
  position:relative;
  z-index:1;
  margin-top:20px;
}}

.snapshot-label {{
  color:{BLUE};
  font-size:12px;
  line-height:1.1;
  font-weight:950;
  letter-spacing:.8px;
  text-transform:uppercase;
}}

.snapshot-value {{
  color:{NAVY};
  font-size:27px;
  line-height:1.12;
  font-weight:900;
  margin-top:9px;
  overflow-wrap:anywhere;
}}

.snapshot-feature {{
  background:{NAVY};
  border-color:{NAVY};
}}

.snapshot-feature .snapshot-index {{
  background:{GOLD};
  color:{NAVY};
}}

.snapshot-feature .snapshot-label {{
  color:#BCD7EA;
}}

.snapshot-feature .snapshot-value {{
  color:{WHITE};
  font-size:52px;
  line-height:.95;
  letter-spacing:-1.5px;
}}

.snapshot-feature:after {{
  border-color:rgba(228,165,28,.12);
}}

.snapshot-meta {{
  color:{MUTED};
  font-size:13px;
  line-height:1.25;
  margin-top:6px;
  overflow-wrap:anywhere;
}}

/* SLIDE 3 — ELIGIBILITY */
.eligibility-layout {{
  width:100%;
}}

.eligibility-panel {{
  background:{SOFT};
  border:1px solid {LINE};
  border-left:6px solid {BLUE};
  border-radius:20px;
  padding:24px 26px;
  box-shadow:0 10px 28px rgba(11,46,89,.055);
}}

.eligibility-panel .info-card {{
  min-height:185px;
  border:0;
  border-radius:0;
  padding:0;
  background:transparent;
  box-shadow:none;
}}

.eligibility-panel .card-top {{
  margin-bottom:12px;
}}

.eligibility-panel .label {{
  font-size:12px;
}}

.eligibility-panel .value {{
  font-size:31px;
  line-height:1.18;
  max-width:820px;
}}

.eligibility-panel .meta {{
  font-size:15px;
  margin-top:12px;
}}

.eligibility-checklist {{
  margin-top:18px;
  background:{WHITE};
  border:1px solid {LINE};
  border-radius:17px;
  padding:18px 21px;
}}

/* SLIDE 4 — FEES / SELECTION / PAY */
.fees-layout {{
  display:flex;
  flex-direction:column;
  gap:17px;
}}

.fee-primary-grid {{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:16px;
}}

.fee-secondary-grid {{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:16px;
}}

.fee-card {{
  min-height:145px;
  background:{WHITE};
  border:1px solid {LINE};
  border-top:4px solid {GOLD};
  border-radius:18px;
  padding:19px 20px;
  box-shadow:0 8px 24px rgba(11,46,89,.05);
  overflow:hidden;
}}

.fee-primary-card {{
  min-height:175px;
  background:{SOFT};
  padding:22px 23px;
}}

.fee-primary-card .label {{
  font-size:12px;
}}

.fee-primary-card .value {{
  color:{NAVY};
  font-size:31px;
  line-height:1.12;
  margin-top:10px;
}}

.fee-secondary-grid .fee-card {{
  min-height:165px;
  border-top-width:2px;
}}

.fee-secondary-grid .value {{
  font-size:21px;
  line-height:1.2;
}}

.fees-checklist {{
  margin-top:2px;
  background:{SOFT};
  border:1px solid {LINE};
  border-radius:17px;
  padding:17px 20px;
}}

/* BULLETS / CHECKLIST */
.bullet-list {{
  list-style:none;
  padding:0;
  margin:14px 0 0;
  display:flex;
  flex-direction:column;
  gap:9px;
}}

.bullet-list li {{
  display:flex;
  align-items:flex-start;
  gap:10px;
  color:{INK};
  font-size:17px;
  line-height:1.25;
  font-weight:650;
}}

.bullet-check {{
  flex:none;
  width:25px; height:25px;
  border-radius:50%;
  background:{SOFT_BLUE};
  color:{BLUE};
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:13px;
  font-weight:950;
}}

.checklist-title,
.section-kicker {{
  color:{BLUE};
  font-size:12px;
  line-height:1;
  font-weight:950;
  letter-spacing:1px;
  text-transform:uppercase;
}}

.bullet-list.compact li {{ font-size:16px; }}
.bullet-list.dense li {{ font-size:14px; gap:8px; }}
.bullet-list.dense .bullet-check {{ width:20px; height:20px; font-size:11px; }}
.bullet-list.ultra-dense li {{ font-size:12px; gap:7px; }}
.bullet-list.ultra-dense .bullet-check {{ width:18px; height:18px; font-size:10px; }}

/* SLIDE 5 — DATES + CHECKLIST */
.dates-composition {{
  display:grid;
  grid-template-columns:0.9fr 1.5fr;
  gap:18px;
  align-items:stretch;
}}

.dates-panel,
.checklist-panel {{
  background:{SOFT};
  border:1px solid {LINE};
  border-radius:20px;
  padding:21px 22px;
  box-shadow:0 8px 24px rgba(11,46,89,.045);
}}

.dates-panel .date-list {{
  margin-top:22px;
  padding:0;
}}

.date-row {{
  position:relative;
  display:flex;
  gap:15px;
  min-height:91px;
  padding:0 0 18px;
}}

.date-row:not(:last-child):before {{
  content:"";
  position:absolute;
  left:13px; top:29px; bottom:0;
  width:2px;
  background:{LINE};
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
  font-size:10px;
  font-weight:950;
  border:4px solid {SOFT_BLUE};
}}

.date-copy {{ padding-top:2px; min-width:0; }}
.date-value {{
  color:{NAVY};
  font-size:27px;
  line-height:1.1;
  font-weight:900;
  overflow-wrap:anywhere;
}}

.date-list.compact .date-row {{ min-height:82px; }}
.date-list.compact .date-value {{ font-size:24px; }}

.date-list.dense .date-row {{ min-height:70px; gap:12px; padding-bottom:12px; }}
.date-list.dense .date-marker {{ width:25px; height:25px; border-width:3px; font-size:8px; }}
.date-list.dense .date-row:not(:last-child):before {{ left:11px; top:26px; }}
.date-list.dense .date-value {{ font-size:20px; }}
.date-list.dense .label {{ font-size:9px; }}
.date-list.dense .meta {{ font-size:11px; }}

.date-list.ultra-dense .date-row {{ min-height:58px; gap:9px; padding-bottom:8px; }}
.date-list.ultra-dense .date-marker {{ width:21px; height:21px; border-width:2px; font-size:7px; }}
.date-list.ultra-dense .date-row:not(:last-child):before {{ left:9px; top:21px; }}
.date-list.ultra-dense .date-value {{ font-size:16px; }}
.date-list.ultra-dense .label {{ font-size:8px; }}

.checklist-panel {{
  background:{WHITE};
}}

.checklist-panel .bullet-list {{
  margin-top:20px;
  gap:13px;
}}

.checklist-panel .bullet-list li {{
  font-size:17px;
  line-height:1.28;
}}

.checklist-panel .bullet-check {{
  width:27px;
  height:27px;
  background:{SOFT_BLUE};
}}

/* SLIDE 6 — OFFICIAL LINKS + CHECKLIST */
.links-composition {{
  display:grid;
  grid-template-columns:1.35fr 0.95fr;
  gap:18px;
  align-items:stretch;
}}

.links-panel {{
  background:{SOFT};
  border:1px solid {LINE};
  border-radius:20px;
  padding:21px 22px;
  box-shadow:0 8px 24px rgba(11,46,89,.045);
}}

.links-panel .links-wrap {{
  margin-top:20px;
}}

.link-card {{
  display:grid;
  grid-template-columns:minmax(0,1fr) 132px;
  gap:20px;
  align-items:center;
  background:{WHITE};
  border:1px solid {LINE};
  border-radius:17px;
  padding:19px;
  margin-bottom:12px;
  box-shadow:0 6px 18px rgba(11,46,89,.04);
}}

.link-title {{
  color:{NAVY};
  font-size:25px;
  line-height:1.12;
  font-weight:900;
}}

.url {{
  color:{MUTED};
  font-size:12px;
  line-height:1.3;
  overflow-wrap:anywhere;
  margin-top:8px;
}}

.qr-wrap {{
  background:{WHITE};
  padding:8px;
  border-radius:13px;
  border:1px solid {LINE};
}}

.qr-wrap img {{ width:114px; height:114px; display:block; }}

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
  grid-template-columns:minmax(0,1fr) 102px;
  gap:13px;
  padding:13px;
}}
.links-wrap.dense .qr-wrap img {{ width:88px; height:88px; }}
.links-wrap.dense .link-title {{ font-size:19px; }}

.links-wrap.ultra-dense .link-card {{
  grid-template-columns:minmax(0,1fr) 86px;
  gap:10px;
  padding:10px;
}}
.links-wrap.ultra-dense .qr-wrap img {{ width:72px; height:72px; }}
.links-wrap.ultra-dense .link-title {{ font-size:15px; }}
.links-wrap.ultra-dense .url {{ font-size:9px; }}

.links-composition .checklist-panel {{
  min-height:100%;
}}

.links-composition .checklist-panel .bullet-list {{
  gap:15px;
}}

.links-composition .checklist-panel .bullet-list li {{
  font-size:16px;
  line-height:1.3;
}}

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
  padding:37px 40px 30px;
  color:{WHITE};
  box-shadow:0 18px 40px rgba(11,46,89,.17);
}}

.hero:before {{
  content:"";
  position:absolute;
  width:440px; height:440px;
  right:-225px; top:-235px;
  border:45px solid rgba(255,255,255,.065);
  border-radius:50%;
}}

.hero:after {{
  content:"";
  position:absolute;
  width:260px; height:260px;
  left:-185px; bottom:-170px;
  border:34px solid rgba(228,165,28,.12);
  border-radius:50%;
}}

.hero-grid {{
  position:absolute;
  inset:0;
  opacity:.16;
  background-image:
    linear-gradient(rgba(255,255,255,.18) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.18) 1px, transparent 1px);
  background-size:44px 44px;
  mask-image:linear-gradient(to bottom right, black, transparent 62%);
}}

.hero-topline {{
  position:relative;
  z-index:2;
  display:flex;
  justify-content:space-between;
  align-items:center;
}}

.hero-tag {{
  color:{GOLD};
  font-size:12px;
  line-height:1;
  font-weight:950;
  letter-spacing:1.4px;
}}

.hero-year {{
  color:rgba(255,255,255,.65);
  font-size:12px;
  font-weight:900;
  letter-spacing:1px;
}}

.hero-title {{
  position:relative;
  z-index:2;
  margin-top:29px;
  color:{WHITE};
  font-size:49px;
  line-height:1.02;
  letter-spacing:-1.8px;
  font-weight:950;
  max-width:820px;
}}

.hero-org {{
  position:relative;
  z-index:2;
  margin-top:14px;
  color:#BCD7EA;
  font-size:18px;
  line-height:1.25;
  font-weight:700;
  max-width:760px;
}}

.hero-stat {{
  position:relative;
  z-index:2;
  margin-top:38px;
  display:flex;
  align-items:flex-end;
  gap:14px;
}}

.hero-stat-number {{
  color:{WHITE};
  font-size:112px;
  line-height:.78;
  font-weight:950;
  letter-spacing:-5px;
}}

.hero-stat-label {{
  color:{GOLD};
  font-size:16px;
  line-height:1.05;
  font-weight:950;
  letter-spacing:1.3px;
  padding-bottom:5px;
  max-width:160px;
}}

.hero-points {{
  position:relative;
  z-index:2;
  margin-top:40px;
  display:flex;
  flex-direction:column;
  gap:10px;
  max-width:760px;
}}

.hero-point {{
  display:flex;
  align-items:flex-start;
  gap:10px;
  color:{WHITE};
  font-size:17px;
  line-height:1.28;
  font-weight:650;
}}

.hero-point span {{
  width:7px; height:7px;
  margin-top:7px;
  border-radius:50%;
  background:{GOLD};
  flex:none;
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

.hero-arrow {{ color:{GOLD}; font-size:24px; line-height:1; }}

/* FOOTER */
footer {{
  position:relative;
  z-index:4;
  margin-top:auto;
  padding-top:13px;
  border-top:1px solid {LINE};
  display:grid;
  grid-template-columns:175px minmax(0,1fr) 50px;
  gap:12px;
  align-items:center;
}}

.footer-brand {{
  display:flex;
  align-items:center;
  gap:7px;
  color:{NAVY};
  font-size:12px;
  font-weight:950;
  letter-spacing:.7px;
}}

.instagram-icon {{
  width:22px; height:22px;
  fill:none;
  stroke:{NAVY};
  stroke-width:1.8;
}}

.instagram-dot {{
  fill:{NAVY};
  stroke:none;
}}

.footer-note {{
  color:{MUTED};
  font-size:10px;
  line-height:1.22;
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
</style>
</head>

<body>
  <div class="topbar">
    <div class="eyebrow">{esc(eyebrow)}</div>
  </div>

  <h1>{esc(title)}</h1>
  {f'<div class="sub">{esc(subtitle)}</div>' if subtitle else ""}
  <div class="rule"></div>

  {hero}
  {content}
  {footer}
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

        for s in slides:
            slide_no = int(s.get("slide_number") or 1)

            await page.set_content(
                build_html(s, total),
                wait_until="load",
            )

            await page.evaluate("document.fonts && document.fonts.ready")

            await page.screenshot(
                path=os.path.join(out, f"slide_{slide_no}.png"),
                type="png",
            )

        await browser.close()
