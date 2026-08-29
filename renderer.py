import os
import asyncio
import html
import re
import base64
from io import BytesIO

import qrcode
from playwright.async_api import async_playwright

def _extract_urls(slide: dict) -> list[str]:
    """Extract HTTP(S) URLs from all rendered slide text fields."""
    values = []
    for key in ("title", "subtitle_or_body", "highlighted_stat", "stat_label"):
        value = slide.get(key)
        if value:
            values.append(str(value))
    bullets = slide.get("bullets") or []
    if isinstance(bullets, list):
        values.extend(str(x) for x in bullets if x)

    text = "\n".join(values)
    urls = re.findall(r"https?://[^\s<>\"]+", text)
    # Remove punctuation that is commonly attached to URLs in prose.
    cleaned = []
    for url in urls:
        url = url.rstrip(".,;:)]}")
        if url not in cleaned:
            cleaned.append(url)
    return cleaned


def _qr_data_uri(url: str) -> str:
    """Create a self-contained QR PNG so rendering needs no network access."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _link_label(url: str) -> str:
    lowered = url.lower()
    if "pdf" in lowered or "notification" in lowered or "advertisement" in lowered:
        return "Official Notification"
    return "Official Website"


def build_slide_html(slide: dict, theme: str, total_slides: int) -> str:
    bg_color = "#0F172A" if theme == "dark_mode" else "#FFFFFF"
    text_color = "#F8FAFC" if theme == "dark_mode" else "#0F172A"
    accent_color = "#38BDF8"

    # Slide 6 is the official-links slide. Replace raw URLs with
    # scannable QR codes rather than rendering long, unreadable URLs.
    urls = _extract_urls(slide) if slide.get("slide_number") == 6 else []

    content_html = ""

    if slide.get("highlighted_stat"):
        content_html += f"""
        <div class="stat-container">
            <div class="stat">{html.escape(str(slide['highlighted_stat']))}</div>
            <div class="stat-label">{html.escape(str(slide.get('stat_label', '')))}</div>
        </div>
        """
    elif slide.get("bullets"):
        bullets_items = "".join(
            f"<li>{html.escape(str(b))}</li>"
            for b in slide["bullets"]
            if b
        )
        content_html += f"<ul class='bullets'>{bullets_items}</ul>"

    body = str(slide.get("subtitle_or_body") or "")
    # Remove URLs from body text when QR cards are displayed.
    if urls:
        for url in urls:
            body = body.replace(url, "")
    if body.strip():
        content_html += f"<p class='body-text'>{html.escape(body.strip())}</p>"

    if urls:
        qr_cards = []
        for url in urls[:2]:
            data_uri = _qr_data_uri(url)
            label = _link_label(url)
            qr_cards.append(f"""
            <div class="qr-card">
                <div class="qr-copy">
                    <div class="qr-label">{html.escape(label)}</div>
                    <div class="qr-instruction">Scan to open</div>
                </div>
                <img class="qr" src="{data_uri}" alt="{html.escape(label)} QR code">
            </div>
            """)
        content_html += f"<div class='qr-grid'>{''.join(qr_cards)}</div>"
        content_html += (
            "<div class='qr-note'>Scan the QR code to open the official link.</div>"
        )

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{
                width: 1080px;
                height: 1350px;
                background-color: {bg_color};
                color: {text_color};
                font-family: 'Inter', sans-serif;
                padding: 100px 80px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            }}
            .tag {{ font-size: 24px; color: {accent_color}; font-weight: 700; text-transform: uppercase; }}
            .title {{ font-size: 72px; font-weight: 900; line-height: 1.1; margin-top: 30px; }}
            .body-text {{ font-size: 34px; line-height: 1.4; color: #94A3B8; margin-top: 40px; }}
            .bullets {{ font-size: 34px; margin-top: 40px; margin-left: 40px; line-height: 1.6; }}
            .stat-container {{ margin-top: 60px; }}
            .stat {{ font-size: 130px; font-weight: 900; color: {accent_color}; }}
            .stat-label {{ font-size: 36px; font-weight: 700; }}
            .qr-grid {{
                margin-top: 45px;
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 28px;
            }}
            .qr-card {{
                background: rgba(255,255,255,0.06);
                border: 2px solid rgba(56,189,248,0.45);
                border-radius: 24px;
                padding: 22px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: space-between;
                min-height: 370px;
            }}
            .qr-copy {{ width: 100%; text-align: center; margin-bottom: 14px; }}
            .qr-label {{ font-size: 30px; font-weight: 900; color: {text_color}; }}
            .qr-instruction {{ font-size: 22px; color: #94A3B8; margin-top: 8px; }}
            .qr {{
                width: 250px;
                height: 250px;
                background: white;
                padding: 8px;
                border-radius: 12px;
                image-rendering: pixelated;
            }}
            .qr-note {{
                margin-top: 24px;
                font-size: 25px;
                font-weight: 700;
                color: #94A3B8;
                text-align: center;
            }}
            .footer {{ display: flex; justify-content: space-between; font-size: 24px; color: #64748B; }}
        </style>
    </head>
    <body>
        <div>
             
            <h1 class="title">{html.escape(str(slide['title']))}</h1>
            {content_html}
        </div>
        <div class="footer">
            <span>@shaktidootam</span>
            <span>{slide['slide_number']} / {total_slides}</span>
        </div>
    </body>
    </html>
    """

async def render_deck_to_images(deck_data: dict, output_dir="output_carousel"):
    os.makedirs(output_dir, exist_ok=True)
    theme = deck_data.get("theme_color", "dark_mode")
    slides = deck_data["slides"]

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1080, "height": 1350})

        for slide in slides:
            html = build_slide_html(slide, theme, len(slides))
            await page.set_content(html)
            file_path = os.path.join(output_dir, f"slide_{slide['slide_number']}.png")
            await page.screenshot(path=file_path)
            print(f"Saved: {file_path}")

        await browser.close()