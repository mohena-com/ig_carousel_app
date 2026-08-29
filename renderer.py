import os
import asyncio
from playwright.async_api import async_playwright

def build_slide_html(slide: dict, theme: str, total_slides: int) -> str:
    bg_color = "#0F172A" if theme == "dark_mode" else "#FFFFFF"
    text_color = "#F8FAFC" if theme == "dark_mode" else "#0F172A"
    accent_color = "#38BDF8"

    content_html = ""
    if slide.get("highlighted_stat"):
        content_html += f"""
        <div class="stat-container">
            <div class="stat">{slide['highlighted_stat']}</div>
            <div class="stat-label">{slide.get('stat_label', '')}</div>
        </div>
        """
    elif slide.get("bullets"):
        bullets_items = "".join([f"<li>{b}</li>" for b in slide["bullets"]])
        content_html += f"<ul class='bullets'>{bullets_items}</ul>"

    if slide.get("subtitle_or_body"):
        content_html += f"<p class='body-text'>{slide['subtitle_or_body']}</p>"

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
            .footer {{ display: flex; justify-content: space-between; font-size: 24px; color: #64748B; }}
        </style>
    </head>
    <body>
        <div>
            <div class="tag">SLIDE {slide['slide_number']}</div>
            <h1 class="title">{slide['title']}</h1>
            {content_html}
        </div>
        <div class="footer">
            <span>@yourbrand</span>
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