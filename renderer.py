import os, re, html, base64
from io import BytesIO
import qrcode
from playwright.async_api import async_playwright

W,H=1080,1350


def qr_data_uri(url):
    qr=qrcode.QRCode(version=None,error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=8,border=3)
    qr.add_data(url); qr.make(fit=True)
    img=qr.make_image(fill_color="black",back_color="white").convert("RGB")
    b=BytesIO(); img.save(b,format="PNG")
    return "data:image/png;base64,"+base64.b64encode(b.getvalue()).decode()


def esc(x): return html.escape(str(x or ""))

def build_html(slide,total,theme="dark_mode"):
    bg="#08111F"; panel="#111D2D"; text="#F7FAFC"; muted="#91A4BC"; accent="#38BDF8"; yellow="#FACC15"
    cards=slide.get("cards") or []
    stype=slide.get("slide_type")
    # For links, QR codes make long URLs usable on Instagram. Limit to official
    # links first; source page is rendered as text below.
    card_html=[]
    if stype=="links":
        url_cards=[x for x in cards if isinstance(x.get("value"),str) and re.match(r"https?://",x.get("value",""))]
        # QR is most useful for the first two links; every additional URL is
        # still preserved as compact text so large link sets cannot overflow.
        for card in url_cards[:2]:
            card_html.append(f"<div class='linkcard'><div><div class='label'>{esc(card.get('label'))}</div><div class='url'>{esc(card.get('value'))}</div></div><img src='{qr_data_uri(card.get('value'))}'></div>")
        remaining=url_cards[2:]
        if remaining:
            rows=[]
            for card in remaining:
                rows.append(f"<div class='linkrow'><span class='label'>{esc(card.get('label'))}</span><span class='url'>{esc(card.get('value'))}</span></div>")
            card_html.append("<div class='linklist'>"+"".join(rows)+"</div>")
    else:
        for card in cards:
            label=card.get("label"); value=card.get("value"); meta=card.get("meta")
            card_html.append(f"<div class='card'><div class='label'>{esc(label)}</div><div class='value'>{esc(value)}</div>{f'<div class=\"meta\">{esc(meta)}</div>' if meta else ''}</div>")
    cards_html="".join(card_html)
    bullets="".join(f"<li>{esc(x)}</li>" for x in (slide.get("bullets") or []))
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
    *{{box-sizing:border-box}}body{{margin:0;width:{W}px;height:{H}px;background:{bg};color:{text};font-family:Inter,Arial,sans-serif;padding:66px 64px 48px;display:flex;flex-direction:column}}
    .top{{display:flex;justify-content:space-between;align-items:center;font-size:22px;font-weight:800;letter-spacing:1px;color:{accent};text-transform:uppercase}}
    .num{{color:{muted};letter-spacing:0}}
    h1{{font-size:64px;line-height:1.03;margin:30px 0 10px;font-weight:900;letter-spacing:-2px}} .sub{{font-size:26px;color:{muted};line-height:1.25;max-width:920px}}
    .cards{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:30px;align-content:start}} .posts{{grid-template-columns:repeat(2,minmax(0,1fr))}}
    .card{{background:{panel};border:1px solid #23334A;border-radius:18px;padding:15px 17px;min-height:88px;overflow:hidden}}
    .cards.eligibility{{gap:11px}} .cards.eligibility .card{{padding:12px 15px}} .cards.eligibility .value{{font-size:18px;line-height:1.12}} .cards.eligibility .label{{font-size:14px;margin-bottom:5px}} .cards.eligibility .meta{{font-size:15px}} .cards.eligibility.sparse .card{{min-height:220px;padding:26px}} .cards.eligibility.sparse .value{{font-size:30px}} .cards.eligibility.sparse .label{{font-size:17px}}
    .label{{font-size:16px;font-weight:800;color:{yellow};text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px}} .value{{font-size:25px;font-weight:800;line-height:1.18;overflow-wrap:anywhere}} .meta{{font-size:18px;line-height:1.2;color:{muted};margin-top:7px}}
    .linkcard{{background:{panel};border:1px solid #23334A;border-radius:18px;padding:16px;display:grid;grid-template-columns:1fr 120px;gap:12px;align-items:center;min-height:150px}}
    .linkcard img{{width:112px;height:112px;background:white;padding:5px;border-radius:8px}} .linklist{{grid-column:1 / -1;background:{panel};border:1px solid #23334A;border-radius:18px;padding:15px 18px}} .linkrow{{padding:9px 0;border-bottom:1px solid #23334A}} .linkrow:last-child{{border-bottom:0}} .linkrow .label{{display:inline-block;margin:0 10px 0 0}} .linkrow .url{{font-size:16px;display:inline;word-break:break-all}} .url{{font-size:16px;color:{muted};line-height:1.2;overflow-wrap:anywhere}}
    ul{{margin:24px 0 0;padding-left:30px;font-size:23px;line-height:1.35}} li{{margin:8px 0}}
    .note{{margin-top:auto;padding-top:22px;border-top:1px solid #23334A;color:{muted};font-size:18px;line-height:1.25}}
    .hero{{margin-top:44px;border-radius:26px;background:{panel};padding:34px;border:1px solid #23334A}} .hero .big{{font-size:86px;font-weight:900;color:{accent};line-height:1}} .hero .hl{{font-size:22px;color:{muted};font-weight:700;margin-top:6px}}
    </style></head><body><div class="top"><span>@shaktidootam</span><span class="num">{slide.get('slide_number')}/{total}</span></div>
    <h1>{esc(slide.get('title'))}</h1><div class="sub">{esc(slide.get('eyebrow'))}{' · ' if slide.get('eyebrow') and slide.get('subtitle') else ''}{esc(slide.get('subtitle'))}</div>
    {('<div class="hero"><div class="big">'+esc(cards[0].get('value'))+'</div><div class="hl">'+esc(cards[0].get('label'))+'</div></div>' if stype=='hook' and cards else '')}
    {('' if stype=='hook' else '<div class="cards '+stype+(' sparse' if stype=='eligibility' and len(cards)<=2 else '')+'">'+cards_html+'</div>')}
    {('<ul>'+bullets+'</ul>' if bullets else '')}
    {('<div class="note">'+esc(slide.get('footer_note'))+'</div>' if slide.get('footer_note') else '')}
    </body></html>'''

async def render(deck,out):
    os.makedirs(out,exist_ok=True)
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path="/usr/bin/chromium", headless=True, args=["--no-sandbox"])
        page=await browser.new_page(viewport={"width":W,"height":H},device_scale_factor=1)
        for s in deck["slides"]:
            await page.set_content(build_html(s,len(deck["slides"])))
            await page.screenshot(path=os.path.join(out,f"slide_{s['slide_number']}.png"))
        await browser.close()
