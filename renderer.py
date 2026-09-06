import os, re, html, base64
from io import BytesIO
import qrcode
from playwright.async_api import async_playwright

# Instagram portrait carousel: 1080 x 1350 (4:5)
W, H = 1080, 1350

# Visual system: white editorial / corporate recruitment style.
NAVY = "#0B2E59"
BLUE = "#145DA0"
BLUE_2 = "#2D78B7"
INK = "#152235"
MUTED = "#667085"
LINE = "#D9E2EC"
SOFT = "#F4F8FC"
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


def _brand_mark():
    return "SD"


def _card_html(card, index=0):
    label = card.get("label") or "Details"
    value = card.get("value") or ""
    meta = card.get("meta")
    return f"""
    <div class='card'>
      <div class='card-top'><span class='card-dot'></span><span class='label'>{esc(label)}</span></div>
      <div class='value'>{esc(value)}</div>
      {f"<div class='meta'>{esc(meta)}</div>" if meta else ""}
    </div>
    """


def _date_card_html(card):
    label = card.get("label") or "Important date"
    value = card.get("value") or ""
    meta = card.get("meta")
    return f"""
    <div class='date-row'>
      <div class='date-marker'></div>
      <div class='date-copy'>
        <div class='label'>{esc(label)}</div>
        <div class='date-value'>{esc(value)}</div>
        {f"<div class='meta'>{esc(meta)}</div>" if meta else ""}
      </div>
    </div>
    """


def build_html(slide, total, theme="professional_white"):
    cards = slide.get("cards") or []
    stype = slide.get("slide_type") or "content"
    number = slide.get("slide_number")
    density = "very-dense" if len(cards) >= 10 else ("dense" if len(cards) >= 6 else "normal")
    title = slide.get("title") or "Recruitment Update"
    eyebrow = slide.get("eyebrow") or "Government Recruitment"
    subtitle = slide.get("subtitle") or ""
    bullets = slide.get("bullets") or []

    # ----- cards / content -----
    if stype == "links":
        url_cards = [
            x for x in cards
            if isinstance(x.get("value"), str) and re.match(r"https?://", x.get("value", ""))
        ]
        link_parts = []
        for card in url_cards[:2]:
            url = card.get("value")
            link_parts.append(f"""
            <div class='link-card'>
              <div class='link-copy'>
                <div class='card-top'><span class='card-dot'></span><span class='label'>{esc(card.get('label') or 'Official link')}</span></div>
                <div class='link-title'>{esc(card.get('label') or 'Open official page')}</div>
                <div class='url'>{esc(url)}</div>
              </div>
              <div class='qr-wrap'><img src='{qr_data_uri(url)}'></div>
            </div>
            """)
        remaining = url_cards[2:]
        if remaining:
            rows = []
            for card in remaining:
                rows.append(f"""
                <div class='link-row'>
                  <span class='label'>{esc(card.get('label') or 'Official link')}</span>
                  <span class='url'>{esc(card.get('value'))}</span>
                </div>
                """)
            link_parts.append("<div class='link-list'>" + "".join(rows) + "</div>")
        cards_html = "".join(link_parts)
    elif stype == "dates":
        cards_html = "".join(_date_card_html(c) for c in cards)
    else:
        cards_html = "".join(_card_html(c, i) for i, c in enumerate(cards))

    bullets_html = "".join(
        f"<li><span class='bullet-check'>✓</span><span>{esc(x)}</span></li>" for x in bullets
    )

    # ----- hook / first slide -----
    hero = ""
    if stype == "hook":
        metric = cards[0].get("value") if cards else None
        metric_label = cards[0].get("label") if cards else ""
        hero = f"""
        <section class='hook-hero'>
          <div class='hero-accent'></div>
          <div class='hero-kicker'>LATEST RECRUITMENT</div>
          <div class='hero-title'>{esc(title)}</div>
          {f"<div class='hero-metric'><span class='metric'>{esc(metric)}</span><span class='metric-label'>{esc(metric_label or 'VACANCIES')}</span></div>" if metric else ""}
          {f"<div class='hero-bullets'><div class='mini-rule'></div>{''.join(f'<div>{esc(x)}</div>' for x in bullets[:2])}</div>" if bullets else ""}
        </section>
        """

    # ----- normal content block -----
    content = "" if stype == "hook" else f"""
      <section class='content-block {esc(stype)} {density}'>
        {f"<div class='card-grid'>{cards_html}</div>" if cards_html else ""}
        {f"<ul class='bullet-list'>{bullets_html}</ul>" if bullets_html else ""}
      </section>
    """

    note = slide.get("footer_note")
    footer = f"""
      <footer>
        <div class='footer-brand'>SHAKTIDOOTAM</div>
        <div class='footer-note'>{esc(note) if note else 'Save this post and check the official notification before applying.'}</div>
        <div class='footer-page'>{number}/{total}</div>
      </footer>
    """

    return f'''<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ box-sizing:border-box; }}
html, body {{ margin:0; width:{W}px; height:{H}px; }}
body {{
  background:{WHITE};
  color:{INK};
  font-family: Inter, "Segoe UI", Arial, sans-serif;
  padding:54px 62px 38px;
  display:flex;
  flex-direction:column;
  position:relative;
  overflow:hidden;
}}
body:before {{
  content:"";
  position:absolute;
  top:0; left:0; right:0;
  height:12px;
  background:{NAVY};
}}
body:after {{
  content:"";
  position:absolute;
  right:-120px; top:-135px;
  width:360px; height:360px;
  border:34px solid {SOFT_BLUE};
  border-radius:50%;
  z-index:0;
}}

.topbar {{
  display:flex; justify-content:space-between; align-items:center;
  position:relative; z-index:2;
  min-height:46px;
  z-index:2;
}}
.brand {{ display:flex; align-items:center; gap:11px; }}
.brand-mark {{
  width:36px; height:36px; border-radius:9px;
  background:{NAVY}; color:{WHITE};
  display:flex; align-items:center; justify-content:center;
  font-size:14px; font-weight:900;
}}
.brand-name {{ font-size:17px; font-weight:900; letter-spacing:.6px; color:{NAVY}; text-transform:uppercase; }}
.brand-sub {{ font-size:12px; color:{MUTED}; margin-top:2px; }}
.page-pill {{
  background:{SOFT}; border:1px solid {LINE}; color:{NAVY};
  border-radius:999px; padding:8px 13px;
  font-size:14px; font-weight:800;
}}

.eyebrow {{
  position:relative; z-index:2;
  margin-top:34px; display:inline-flex; align-self:flex-start;
  background:{SOFT_BLUE}; color:{BLUE};
  border-radius:999px; padding:8px 13px;
  font-size:14px; font-weight:900; letter-spacing:.7px;
  text-transform:uppercase; max-width:850px;
}}
h1 {{
  position:relative; z-index:2;
  margin:18px 0 0; color:{NAVY};
  font-size:54px; line-height:1.03;
  letter-spacing:-1.8px; font-weight:900;
  max-width:900px;
}}
.sub {{ position:relative; z-index:2; margin-top:11px; color:{MUTED}; font-size:23px; line-height:1.28; max-width:900px; }}
.rule {{ position:relative; z-index:2; margin-top:18px; width:76px; height:5px; border-radius:5px; background:{GOLD}; }}

.content-block {{ margin-top:28px; flex:1; min-height:0; display:flex; flex-direction:column; }}
.card-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:15px; align-content:start; }}
.card {{
  background:{WHITE}; border:1px solid {LINE}; border-radius:16px;
  padding:18px 19px 17px;
  box-shadow:0 5px 16px rgba(11,46,89,.055);
  min-height:104px;
}}
.card-top {{ display:flex; align-items:center; gap:8px; margin-bottom:8px; }}
.card-dot {{ width:7px; height:7px; border-radius:50%; background:{GOLD}; flex:none; }}
.label {{ color:{BLUE}; font-size:13px; line-height:1.15; font-weight:900; letter-spacing:.55px; text-transform:uppercase; }}
.value {{ color:{INK}; font-size:23px; line-height:1.2; font-weight:800; overflow-wrap:anywhere; }}
.meta {{ color:{MUTED}; font-size:16px; line-height:1.25; margin-top:6px; overflow-wrap:anywhere; }}

.posts .card {{ min-height:112px; }}
.posts .value {{ font-size:25px; }}
.eligibility .card {{ min-height:120px; }}
.eligibility .value {{ font-size:19px; line-height:1.24; }}
.eligibility .meta {{ font-size:15px; }}
.fees .card {{ min-height:116px; }}

.dense .card {{ padding:14px 16px 13px; min-height:92px; }}
.dense .value {{ font-size:19px; }}
.dense .meta {{ font-size:14px; }}
.dense .label {{ font-size:12px; }}
.very-dense .card {{ padding:11px 13px; min-height:78px; border-radius:13px; }}
.very-dense .value {{ font-size:16px; line-height:1.18; }}
.very-dense .meta {{ font-size:12px; margin-top:4px; }}
.very-dense .label {{ font-size:10px; }}

.bullet-list {{ list-style:none; padding:0; margin:22px 0 0; display:flex; flex-direction:column; gap:10px; }}
.bullet-list li {{ display:flex; align-items:flex-start; gap:11px; color:{INK}; font-size:20px; line-height:1.28; }}
.bullet-check {{
  flex:none; width:25px; height:25px; border-radius:50%;
  background:{SOFT_BLUE}; color:{BLUE};
  display:flex; align-items:center; justify-content:center;
  font-size:14px; font-weight:900;
}}

/* Date/timeline treatment */
.dates {{ padding-right:14px; }}
.date-row {{ position:relative; display:flex; gap:17px; padding:0 0 18px; }}
.date-row:not(:last-child):before {{
  content:""; position:absolute; left:8px; top:17px; bottom:0;
  width:2px; background:{LINE};
}}
.date-marker {{ width:17px; height:17px; border-radius:50%; background:{NAVY}; border:4px solid {SOFT_BLUE}; flex:none; position:relative; z-index:1; margin-top:3px; }}
.date-copy {{ padding-bottom:1px; }}
.date-value {{ font-size:23px; line-height:1.18; font-weight:850; color:{INK}; }}
.dates .meta {{ font-size:15px; }}

/* Links */
.link-card {{
  display:grid; grid-template-columns:1fr 124px; gap:18px; align-items:center;
  background:{SOFT}; border:1px solid {LINE}; border-radius:17px;
  padding:18px; margin-bottom:14px;
}}
.link-title {{ color:{NAVY}; font-size:23px; font-weight:850; line-height:1.15; }}
.url {{ color:{MUTED}; font-size:14px; line-height:1.28; overflow-wrap:anywhere; margin-top:7px; }}
.qr-wrap {{ background:{WHITE}; padding:7px; border-radius:12px; border:1px solid {LINE}; }}
.qr-wrap img {{ width:108px; height:108px; display:block; }}
.link-list {{ background:{WHITE}; border:1px solid {LINE}; border-radius:16px; padding:5px 17px; box-shadow:0 5px 16px rgba(11,46,89,.045); }}
.link-row {{ padding:12px 0; border-bottom:1px solid {LINE}; }}
.link-row:last-child {{ border-bottom:0; }}
.link-row .label {{ display:block; margin-bottom:3px; }}
.link-row .url {{ margin-top:0; }}

/* Hook */
.hook-hero {{
  margin-top:42px; position:relative;
  background:{NAVY}; border-radius:26px;
  padding:34px 38px 38px; overflow:hidden;
  box-shadow:0 15px 35px rgba(11,46,89,.15);
}}
.hook-hero:after {{
  content:""; position:absolute; right:-80px; top:-95px;
  width:260px; height:260px; border:28px solid rgba(255,255,255,.08); border-radius:50%;
}}
.hero-accent {{ width:60px; height:5px; background:{GOLD}; border-radius:4px; margin-bottom:20px; }}
.hero-kicker {{ color:#BBD6EA; font-size:14px; font-weight:900; letter-spacing:1px; }}
.hero-title {{ color:{WHITE}; font-size:42px; line-height:1.08; font-weight:900; margin-top:10px; max-width:770px; }}
.hero-metric {{ margin-top:32px; display:flex; align-items:baseline; gap:13px; }}
.metric {{ color:{WHITE}; font-size:104px; line-height:.9; font-weight:950; letter-spacing:-4px; }}
.metric-label {{ color:#BBD6EA; font-size:18px; font-weight:900; letter-spacing:1px; }}
.hero-bullets {{ color:{WHITE}; font-size:19px; line-height:1.35; margin-top:28px; display:flex; flex-direction:column; gap:8px; }}
.mini-rule {{ width:42px; height:3px; background:{GOLD}; border-radius:4px; margin-bottom:1px; }}

footer {{
  margin-top:auto; padding-top:17px; border-top:1px solid {LINE};
  display:grid; grid-template-columns:160px 1fr 48px; gap:14px; align-items:center;
}}
.footer-brand {{ color:{NAVY}; font-size:13px; font-weight:950; letter-spacing:.7px; text-transform:uppercase; }}
.footer-note {{ color:{MUTED}; font-size:13px; line-height:1.25; text-align:center; }}
.footer-page {{ color:{NAVY}; font-size:13px; font-weight:900; text-align:right; }}
</style>
</head>
<body>
  <div class='topbar'>
    <div class='brand'>
      <div class='brand-mark'>{_brand_mark()}</div>
      <div><div class='brand-name'>Shaktidootam</div><div class='brand-sub'>Government Job Updates</div></div>
    </div>
    <div class='page-pill'>SLIDE {number} OF {total}</div>
  </div>

  <div class='eyebrow'>{esc(eyebrow)}</div>
  <h1>{esc(title)}</h1>
  {f"<div class='sub'>{esc(subtitle)}</div>" if subtitle else ""}
  <div class='rule'></div>

  {hero}
  {content}
  {footer}
</body>
</html>'''


async def render(deck, out):
    os.makedirs(out, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path="/usr/bin/chromium",
            headless=True,
            args=["--no-sandbox"],
        )
        page = await browser.new_page(
            viewport={"width": W, "height": H},
            device_scale_factor=1,
        )
        for s in deck["slides"]:
            await page.set_content(build_html(s, len(deck["slides"])))
            await page.screenshot(
                path=os.path.join(out, f"slide_{s['slide_number']}.png"),
                type="png",
            )
        await browser.close()
