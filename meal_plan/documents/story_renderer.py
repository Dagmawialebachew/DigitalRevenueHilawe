"""Hilawe Flex 9:16 Instagram & Telegram Story Card Renderer.

Generates a viral, high-energy 1080x1920 announcement story card for clients
celebrating Day 01 of their transformation journey with Coach Hilawe Semma.
Designed for maximum social sharing, client pride, and viral reposting.
"""

from __future__ import annotations

import html
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .models import DocumentContext

logger = logging.getLogger(__name__)

# Standard Chrome paths for Windows and Linux environments
POSSIBLE_CHROME_PATHS = [
    os.environ.get("CHROME_PATH"),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Users\%USERNAME%\AppData\Local\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    shutil.which("google-chrome"),
    shutil.which("chromium"),
    shutil.which("chrome"),
]


def find_chrome_executable() -> Path | None:
    for candidate in POSSIBLE_CHROME_PATHS:
        if not candidate:
            continue
        expanded = os.path.expandvars(candidate)
        p = Path(expanded)
        if p.is_file() and os.access(p, os.X_OK):
            return p
    return None


GOAL_LABELS_AM = {
    "FAT_LOSS": "የስብ / የክብደት ቅነሳ",
    "MUSCLE_GAIN": "የጡንቻ ግንባታ እና ጥንካሬ",
    "RECOMPOSITION": "የሰውነት ቅርጽ እና የጡንቻ ግንባታ",
    "MAINTAIN": "ክብደት እና ቅርጽ መጠበቅ",
    "PERFORMANCE": "የአካል ብቃት ማሻሻል",
}

GOAL_LABELS_EN = {
    "FAT_LOSS": "Fat Loss & Conditioning",
    "MUSCLE_GAIN": "Lean Muscle & Strength",
    "RECOMPOSITION": "Body Recomposition & Muscle",
    "MAINTAIN": "Maintenance & Health",
    "PERFORMANCE": "Athletic Performance",
}


def build_story_html(
    client_name: str,
    goal: str,
    target_kcal: int | float,
    protein_g: int | float,
    carbs_g: int | float | None = None,
    fat_g: int | float | None = None,
    language: str = "AM",
) -> str:
    lang = "AM" if str(language).upper() == "AM" else "EN"
    safe_name = html.escape(client_name.strip() or "Client")
    
    if lang == "AM":
        goal_text = GOAL_LABELS_AM.get(str(goal).upper(), "የጡንቻ ግንባታ እና ጥንካሬ")
        return f"""<!DOCTYPE html>
<html lang="am">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Ethiopic:wght@400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@500;600;700;800;900&display=swap');
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    width: 1080px; height: 1920px;
    background-color: #ffffff;
    font-family: 'Noto Sans Ethiopic', 'Plus Jakarta Sans', sans-serif;
    color: #0f172a; overflow: hidden; position: relative;
    -webkit-font-smoothing: antialiased;
  }}
  .canvas {{
    width: 1080px; height: 1920px;
    padding: 170px 80px 150px 80px;
    display: flex; flex-direction: column;
    justify-content: space-between; align-items: center;
    text-align: center; position: relative;
    background: 
      radial-gradient(circle at 50% 10%, rgba(255, 84, 0, 0.08) 0%, transparent 55%),
      radial-gradient(circle at 50% 90%, rgba(255, 84, 0, 0.04) 0%, transparent 50%),
      #ffffff;
  }}
  .announcement-badge {{
    display: inline-flex; align-items: center; gap: 10px;
    background: #ff5400; color: #ffffff;
    padding: 12px 28px; border-radius: 999px;
    font-size: 17px; font-weight: 800;
    box-shadow: 0 10px 25px -5px rgba(255, 84, 0, 0.4);
  }}
  .headline-section {{
    display: flex; flex-direction: column; align-items: center;
    margin-top: 24px; max-width: 900px;
  }}
  .statement-subtitle {{ font-size: 20px; font-weight: 700; color: #64748b; margin-bottom: 8px; }}
  .statement-main {{
    font-size: 54px; font-weight: 900; line-height: 1.15;
    color: #0f172a; letter-spacing: -0.02em;
  }}
  .statement-main span {{
    color: #ff5400; text-decoration: underline;
    text-decoration-color: rgba(255, 84, 0, 0.3); text-underline-offset: 8px;
  }}
  .client-tag-box {{
    margin-top: 18px; display: flex; align-items: center; gap: 12px;
  }}
  .client-name-chip {{
    background: #f8fafc; border: 1px solid #e2e8f0;
    padding: 10px 24px; border-radius: 999px;
    font-size: 20px; font-weight: 800; color: #0f172a;
  }}
  .day-one-chip {{
    background: #fff7ed; border: 1px solid #ffedd5;
    color: #ea580c; padding: 10px 20px; border-radius: 999px;
    font-size: 16px; font-weight: 800;
  }}
  .targets-wrapper {{ width: 100%; margin: 30px 0; }}
  .targets-title {{
    font-size: 15px; font-weight: 800; color: #94a3b8;
    letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 16px;
  }}
  .cards-grid {{
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 20px; width: 100%;
  }}
  .target-card {{
    background: #ffffff; border: 2px solid #ffedd5;
    border-radius: 28px; padding: 36px 24px;
    display: flex; flex-direction: column; align-items: center;
    box-shadow: 0 18px 36px -10px rgba(0, 0, 0, 0.04);
    position: relative;
  }}
  .target-card::after {{
    content: ''; position: absolute; bottom: 0; left: 20%; right: 20%;
    height: 4px; background: #ff5400; border-radius: 4px 4px 0 0;
  }}
  .card-label {{ font-size: 16px; font-weight: 700; color: #64748b; margin-bottom: 10px; }}
  .card-val {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 68px; font-weight: 900; line-height: 1;
    color: #ff5400; letter-spacing: -0.03em;
  }}
  .card-unit {{ font-size: 18px; font-weight: 700; color: #94a3b8; margin-top: 8px; }}
  .social-repost-box {{
    width: 100%; background: #fafafa; border: 1px solid #f1f5f9;
    border-radius: 24px; padding: 24px 28px;
    display: flex; flex-direction: column; align-items: center; gap: 12px;
  }}
  .repost-title {{ font-size: 15px; font-weight: 700; color: #64748b; }}
  .handles-row {{ display: flex; gap: 14px; flex-wrap: wrap; justify-content: center; }}
  .handle-tag {{
    background: #ffffff; border: 1px solid #e2e8f0;
    padding: 8px 18px; border-radius: 999px;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 15px; font-weight: 800; color: #0f172a;
  }}
  .handle-tag .platform {{ color: #ff5400; font-weight: 900; }}
  .footer-viral {{
    display: flex; flex-direction: column; align-items: center;
    gap: 14px; width: 100%;
  }}
  .friends-hook {{ font-size: 17px; font-weight: 700; color: #0f172a; }}
  .cta-pill {{
    background: #0f172a; color: #ffffff;
    padding: 16px 40px; border-radius: 999px;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 20px; font-weight: 900;
    display: inline-flex; align-items: center; gap: 12px;
    box-shadow: 0 16px 32px -8px rgba(15, 23, 42, 0.35);
  }}
  .cta-pill span {{ color: #ff5400; }}
</style>
</head>
<body>
  <div class="canvas">
    <div class="announcement-badge">⚡ አዲስ ጅማሬ // DAY 01</div>
    <div class="headline-section">
      <p class="statement-subtitle">የ30 ቀን የሰውነት ለውጥ ጉዞ</p>
      <h1 class="statement-main">የአሰልጣኝ ህላዌ ሰማን የግል <span>የአመጋገብ ፕላን</span> ዛሬ ጀመርኩ!</h1>
      <div class="client-tag-box">
        <div class="client-name-chip">{safe_name}</div>
        <div class="day-one-chip">🔥 {goal_text}</div>
      </div>
    </div>
    <div class="targets-wrapper">
      <div class="targets-title">የእኔ የቀን የለውጥ ዒላማዎች</div>
      <div class="cards-grid">
        <div class="target-card">
          <div class="card-label">የቀን ሃይል (ካሎሪ)</div>
          <div class="card-val">{int(round(target_kcal)):,}</div>
          <div class="card-unit">KCAL / ቀን</div>
        </div>
        <div class="target-card">
          <div class="card-label">የጡንቻ ፕሮቲን</div>
          <div class="card-val">{int(round(protein_g))}</div>
          <div class="card-unit">ግራም ፕሮቲን</div>
        </div>
      </div>
    </div>
    <div class="social-repost-box">
      <p class="repost-title">አሰልጣኝ ህላዌ ሰማን Story ላይ Tag አድርጉ:</p>
      <div class="handles-row">
        <div class="handle-tag"><span class="platform">IG:</span> @hilawe_semma</div>
        <div class="handle-tag"><span class="platform">TikTok:</span> @hilawe_semma</div>
        <div class="handle-tag"><span class="platform">Telegram:</span> @CoachHilawe</div>
      </div>
    </div>
    <div class="footer-viral">
      <p class="friends-hook">አብረን እንቀየር! የእርስዎን የግል ፕላን በTelegram ጀምሩ:</p>
      <div class="cta-pill">በቴሌግራም <span>@CoachHilaweBot</span></div>
    </div>
  </div>
</body>
</html>"""
    else:
        goal_text = GOAL_LABELS_EN.get(str(goal).upper(), "Lean Muscle & Strength")
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800;900&display=swap');
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    width: 1080px; height: 1920px;
    background-color: #ffffff;
    font-family: 'Plus Jakarta Sans', sans-serif;
    color: #0f172a; overflow: hidden; position: relative;
    -webkit-font-smoothing: antialiased;
  }}
  .canvas {{
    width: 1080px; height: 1920px;
    padding: 170px 80px 150px 80px;
    display: flex; flex-direction: column;
    justify-content: space-between; align-items: center;
    text-align: center; position: relative;
    background: 
      radial-gradient(circle at 50% 10%, rgba(255, 84, 0, 0.08) 0%, transparent 55%),
      radial-gradient(circle at 50% 90%, rgba(255, 84, 0, 0.04) 0%, transparent 50%),
      #ffffff;
  }}
  .announcement-badge {{
    display: inline-flex; align-items: center; gap: 10px;
    background: #ff5400; color: #ffffff;
    padding: 12px 28px; border-radius: 999px;
    font-size: 17px; font-weight: 800;
    box-shadow: 0 10px 25px -5px rgba(255, 84, 0, 0.4);
  }}
  .headline-section {{
    display: flex; flex-direction: column; align-items: center;
    margin-top: 24px; max-width: 900px;
  }}
  .statement-subtitle {{ font-size: 20px; font-weight: 700; color: #64748b; margin-bottom: 8px; }}
  .statement-main {{
    font-size: 54px; font-weight: 900; line-height: 1.15;
    color: #0f172a; letter-spacing: -0.02em;
  }}
  .statement-main span {{
    color: #ff5400; text-decoration: underline;
    text-decoration-color: rgba(255, 84, 0, 0.3); text-underline-offset: 8px;
  }}
  .client-tag-box {{
    margin-top: 18px; display: flex; align-items: center; gap: 12px;
  }}
  .client-name-chip {{
    background: #f8fafc; border: 1px solid #e2e8f0;
    padding: 10px 24px; border-radius: 999px;
    font-size: 20px; font-weight: 800; color: #0f172a;
  }}
  .day-one-chip {{
    background: #fff7ed; border: 1px solid #ffedd5;
    color: #ea580c; padding: 10px 20px; border-radius: 999px;
    font-size: 16px; font-weight: 800;
  }}
  .targets-wrapper {{ width: 100%; margin: 30px 0; }}
  .targets-title {{
    font-size: 15px; font-weight: 800; color: #94a3b8;
    letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 16px;
  }}
  .cards-grid {{
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 20px; width: 100%;
  }}
  .target-card {{
    background: #ffffff; border: 2px solid #ffedd5;
    border-radius: 28px; padding: 36px 24px;
    display: flex; flex-direction: column; align-items: center;
    box-shadow: 0 18px 36px -10px rgba(0, 0, 0, 0.04);
    position: relative;
  }}
  .target-card::after {{
    content: ''; position: absolute; bottom: 0; left: 20%; right: 20%;
    height: 4px; background: #ff5400; border-radius: 4px 4px 0 0;
  }}
  .card-label {{ font-size: 16px; font-weight: 700; color: #64748b; margin-bottom: 10px; }}
  .card-val {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 68px; font-weight: 900; line-height: 1;
    color: #ff5400; letter-spacing: -0.03em;
  }}
  .card-unit {{ font-size: 18px; font-weight: 700; color: #94a3b8; margin-top: 8px; }}
  .social-repost-box {{
    width: 100%; background: #fafafa; border: 1px solid #f1f5f9;
    border-radius: 24px; padding: 24px 28px;
    display: flex; flex-direction: column; align-items: center; gap: 12px;
  }}
  .repost-title {{ font-size: 15px; font-weight: 700; color: #64748b; }}
  .handles-row {{ display: flex; gap: 14px; flex-wrap: wrap; justify-content: center; }}
  .handle-tag {{
    background: #ffffff; border: 1px solid #e2e8f0;
    padding: 8px 18px; border-radius: 999px;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 15px; font-weight: 800; color: #0f172a;
  }}
  .handle-tag .platform {{ color: #ff5400; font-weight: 900; }}
  .footer-viral {{
    display: flex; flex-direction: column; align-items: center;
    gap: 14px; width: 100%;
  }}
  .friends-hook {{ font-size: 17px; font-weight: 700; color: #0f172a; }}
  .cta-pill {{
    background: #0f172a; color: #ffffff;
    padding: 16px 40px; border-radius: 999px;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 20px; font-weight: 900;
    display: inline-flex; align-items: center; gap: 12px;
    box-shadow: 0 16px 32px -8px rgba(15, 23, 42, 0.35);
  }}
  .cta-pill span {{ color: #ff5400; }}
</style>
</head>
<body>
  <div class="canvas">
    <div class="announcement-badge">⚡ NEW BEGINNING // DAY 01</div>
    <div class="headline-section">
      <p class="statement-subtitle">30-Day Body Transformation Journey</p>
      <h1 class="statement-main">Officially started my <span>Meal Plan</span> with Coach Hilawe!</h1>
      <div class="client-tag-box">
        <div class="client-name-chip">{safe_name}</div>
        <div class="day-one-chip">🔥 {goal_text}</div>
      </div>
    </div>
    <div class="targets-wrapper">
      <div class="targets-title">My Daily Transformation Targets</div>
      <div class="cards-grid">
        <div class="target-card">
          <div class="card-label">Daily Energy Target</div>
          <div class="card-val">{int(round(target_kcal)):,}</div>
          <div class="card-unit">KCAL / DAY</div>
        </div>
        <div class="target-card">
          <div class="card-label">Muscle Protein</div>
          <div class="card-val">{int(round(protein_g))}</div>
          <div class="card-unit">Grams Protein</div>
        </div>
      </div>
    </div>
    <div class="social-repost-box">
      <p class="repost-title">Tag Coach Hilawe Semma on your Story:</p>
      <div class="handles-row">
        <div class="handle-tag"><span class="platform">IG:</span> @hilawe_semma</div>
        <div class="handle-tag"><span class="platform">TikTok:</span> @hilawe_semma</div>
        <div class="handle-tag"><span class="platform">Telegram:</span> @CoachHilawe</div>
      </div>
    </div>
    <div class="footer-viral">
      <p class="friends-hook">Transform with me! Start your custom plan on Telegram:</p>
      <div class="cta-pill">Telegram <span>@CoachHilaweBot</span></div>
    </div>
  </div>
</body>
</html>"""


def render_story_card(
    plan: dict[str, Any],
    context: DocumentContext,
    output_path: str | Path,
) -> Path | None:
    """Render a 1080x1920 Instagram/Telegram Story card graphic for the client."""
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    chrome_bin = find_chrome_executable()
    if not chrome_bin:
        logger.warning("Headless Chrome not found. Skipping Story Card render.")
        return None

    targets = plan.get("nutrition_targets") or {}
    kcal = targets.get("target_kcal") or plan.get("target_calories") or 2450
    protein = targets.get("protein_g") or plan.get("target_protein_g") or 160
    carbs = targets.get("carbs_g") or 220
    fat = targets.get("fat_g") or 55

    profile = plan.get("profile_summary") or context.client_profile or {}
    goal = profile.get("goal") or "RECOMPOSITION"

    html_content = build_story_html(
        client_name=context.client_name,
        goal=goal,
        target_kcal=kcal,
        protein_g=protein,
        carbs_g=carbs,
        fat_g=fat,
        language=context.normalized_language,
    )

    with tempfile.NamedTemporaryFile("w", suffix=".html", encoding="utf-8", delete=False) as tmp:
        tmp.write(html_content)
        tmp_path = Path(tmp.name)

    try:
        cmd = [
            str(chrome_bin),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--hide-scrollbars",
            "--window-size=1080,1920",
            f"--screenshot={out_file.resolve()}",
            str(tmp_path.resolve()),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if res.returncode != 0:
            logger.error("Chrome failed rendering story card: %s", res.stderr)
            return None
        
        if out_file.exists() and out_file.stat().st_size > 1000:
            logger.info("Rendered Hilawe Flex story card: %s (%d bytes)", out_file, out_file.stat().st_size)
            return out_file
        return None
    except Exception as exc:
        logger.exception("Error during story card rendering: %s", exc)
        return None
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
