from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from html import escape
from pathlib import Path
from typing import Any

from .copy import copy_for, slot_label, day_label, profile_label, format_training_summary
from .helpers import (
    local_food_name,
    local_category_name,
    local_recipe_name,
    local_template_name,
    local_purchase_quantity,
    local_warning,
    rounded,
    review_warning_lines,
)
from .models import DocumentContext


_FONTS_CACHE: str | None = None
MAX_CONCURRENT_PDF_RENDERS = int(os.getenv("MAX_CONCURRENT_PDF_RENDERS", "3"))
_RENDER_SEMAPHORE = threading.BoundedSemaphore(MAX_CONCURRENT_PDF_RENDERS)


def _get_embedded_fonts_css() -> str:
    """Generate @font-face rules with inlined base64 fonts for zero external dependency."""
    global _FONTS_CACHE
    if _FONTS_CACHE is not None:
        return _FONTS_CACHE

    fonts_dir = Path(__file__).parent / "fonts"
    font_files = {
        ("NotoSerifCustom", 400): fonts_dir / "NotoSerifEthiopic-Regular.ttf",
        ("NotoSerifCustom", 500): fonts_dir / "NotoSerifEthiopic-Medium.ttf",
        ("NotoSerifCustom", 700): fonts_dir / "NotoSerifEthiopic-Bold.ttf",
        ("NotoSansCustom", 400): fonts_dir / "NotoSansEthiopic-Regular.ttf",
        ("NotoSansCustom", 500): fonts_dir / "NotoSansEthiopic-Medium.ttf",
        ("NotoSansCustom", 700): fonts_dir / "NotoSansEthiopic-Bold.ttf",
    }

    css_rules = []
    for (family, weight), font_path in font_files.items():
        if font_path.exists():
            b64 = base64.b64encode(font_path.read_bytes()).decode("ascii")
            css_rules.append(f"""
@font-face {{
  font-family: '{family}';
  src: url('data:font/truetype;charset=utf-8;base64,{b64}') format('truetype');
  font-weight: {weight};
  font-style: normal;
  font-display: block;
}}""")

    _FONTS_CACHE = "\n".join(css_rules)
    return _FONTS_CACHE


def find_chromium_executable() -> str | None:
    """Auto-detect Chromium-based browser (Chrome or Edge) across platforms."""
    # 1. Check environment variables
    for env_var in ("CHROME_PATH", "CHROMIUM_PATH", "EDGE_PATH"):
        val = os.environ.get(env_var)
        if val and Path(val).exists():
            return val

    # 2. Check PATH
    for name in ("chrome", "google-chrome", "chromium", "msedge", "edge"):
        found = shutil.which(name)
        if found and Path(found).exists():
            return found

    # 3. Known Windows locations
    win_paths = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    for p in win_paths:
        if p.exists():
            return str(p)

    # 4. Known Linux locations
    linux_paths = [
        Path("/usr/bin/google-chrome"),
        Path("/usr/bin/chromium"),
        Path("/usr/bin/chromium-browser"),
        Path("/snap/bin/chromium"),
    ]
    for p in linux_paths:
        if p.exists():
            return str(p)

    # 5. Known macOS locations
    mac_paths = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    ]
    for p in mac_paths:
        if p.exists():
            return str(p)

    return None


# Daily coaching wisdom tips to keep meal pages balanced and aesthetically full
_DAILY_COACH_TIPS_AM = [
    {
        "title": "የቀኑ የህላዌ ወርቃማ ምክር · የምግብ መፈጨት እና እንጀራ",
        "text": "እንጀራ ከጤፍ ስለሚዘጋጅ የተፈጥሮ ማዕድናትና ውስብስብ ካርቦሃይድሬት በብዛት ይዟል። በፕላኑ ላይ የተቀመጠውን መጠን ሳይጨምሩ በልክ መመገብ እና ከምግብ በኋላ 10 ደቂቃ በእግር መጓዝ ለቀሊል መፈጨት ይረዳል።",
    },
    {
        "title": "የቀኑ የህላዌ ወርቃማ ምክር · የአካል ብቃት እንቅስቃሴ እና ፕሮቲን",
        "text": "የልምምድ ሰዓትዎ ከመድረሱ 1-2 ሰዓት በፊት ቀለል ያለ ካርቦሃይድሬት ይውሰዱ። ከልምምድ በኋላ ደግሞ በፕላኑ ላይ የተመደበውን ፕሮቲን መመገብ የጡንቻ ጥገናን እና ማገገምን ያፋጥናል።",
    },
    {
        "title": "የቀኑ የህላዌ ወርቃማ ምክር · የውሃ አወሳሰድ ስልት",
        "text": "ውሃ ከምግብ ጋር አብሮ ከመጠጣት ይልቅ ከምግብ 30 ደቂቃ በፊት ወይም ከምግብ 45 ደቂቃ በኋላ መጠጣት የምግብ መፈጨት ጭማቂዎች እንዳይቀጥኑ በማድረግ የሆድ መነፋትን ይከላከላል።",
    },
    {
        "title": "የቀኑ የህላዌ ወርቃማ ምክር · የረሃብ ስሜት መቆጣጠሪያ ዘዴዎች",
        "text": "በቀን ውስጥ ድንገተኛ የረሃብ ስሜት ከተሰማዎት መጀመሪያ አንድ ትልቅ ብርጭቆ ለብ ያለ ውሃ ይጠጡ። ብዙ ጊዜ የሰውነታችን የውሃ ጥም ምልክት በስህተት እንደ ምግብ ረሃብ ሊሰማን ይችላል።",
    },
    {
        "title": "የቀኑ የህላዌ ወርቃማ ምክር · አትክልቶች እና የፋይበር ጥንካሬ",
        "text": "በምሳ እና በእራትዎ ላይ የተካተቱት ጎመን፣ ፎሶሊያና ሰላጣዎች ሆድ እንዳይደነድን እና የምግብ ስርዓትዎ ሚዛናዊ እንዲሆን ከፍተኛ አስተዋጽኦ ያደርጋሉ። በቂ ፋይበር የሙሉነት ስሜትን ያረዝማል።",
    },
    {
        "title": "የቀኑ የህላዌ ወርቃማ ምክር · እንቅልፍ እና የሰውነት ቅርጽ",
        "text": "የምግብ ፕላንዎ ውጤታማ የሚሆነው በቀን ከ7-8 ሰዓት ጥራት ያለው እንቅልፍ ሲያገኙ ነው። በእንቅልፍ ወቅት ነው ሰውነታችን ስብ የሚያቃጥለው እና ጡንቻዎችን የሚያድሰው።",
    },
    {
        "title": "የቀኑ የህላዌ ወርቃማ ምክር · ሳምንታዊ ወጥነት እና ግስጋሴ",
        "text": "ስኬት የሚገነባው በአንድ ቀን ፍጹምነት ሳይሆን በሳምንታት ወጥነት ነው። ይህንን ሳምንት በሚገባ በማጠናቀቅዎ እንኳን ደስ አለዎት! ለሚቀጥለው ሳምንት የገበያ ዝርዝርዎን አስቀድመው ያዘጋጁ።",
    },
]

_DAILY_COACH_TIPS_EN = [
    {
        "title": "Daily Coach Hilawe Insight · Digestion & Complex Carbs",
        "text": "Teff injera is rich in iron, minerals, and slow-digesting complex carbohydrates. Sticking to your prescribed portion and taking a light 10-minute walk post-meal supports optimal nutrient absorption.",
    },
    {
        "title": "Daily Coach Hilawe Insight · Pre & Post-Workout Fueling",
        "text": "Consume complex carbs 1-2 hours prior to training for sustained glycogen. Consuming your designated protein source within 90 minutes post-workout maximizes muscle protein synthesis.",
    },
    {
        "title": "Daily Coach Hilawe Insight · Strategic Hydration",
        "text": "Drink water between meals rather than during them. Hydrating 30 minutes before or 45 minutes after eating keeps digestive enzymes at peak efficiency and eliminates bloating.",
    },
    {
        "title": "Daily Coach Hilawe Insight · Mastering Cravings",
        "text": "If sudden hunger strikes outside planned meals, drink a large glass of water first. Mild dehydration is frequently misinterpreted by the brain as appetite.",
    },
    {
        "title": "Daily Coach Hilawe Insight · Vegetables & Satiety",
        "text": "Greens, cabbage, and salads provide essential micronutrients and dietary fiber that slow gastric emptying, keeping you energized and full for hours.",
    },
    {
        "title": "Daily Coach Hilawe Insight · Sleep & Recovery",
        "text": "Fat oxidation and muscular adaptation occur predominantly during deep sleep. Prioritize 7-8 hours of uninterrupted rest to solidify your dietary results.",
    },
    {
        "title": "Daily Coach Hilawe Insight · Consistency Over Perfection",
        "text": "Transformation is a repeatable system. Congratulations on completing this core week! Prep your groceries ahead for the upcoming cycle to maintain momentum.",
    },
]


def _build_css() -> str:
    fonts_css = _get_embedded_fonts_css()
    return f"""
{fonts_css}

@page {{
  size: A4 portrait;
  margin: 0;
}}

* {{
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}}

body {{
  font-family: 'NotoSansCustom', -apple-system, BlinkMacSystemFont, sans-serif;
  color: #0F172A;
  background: #FFFFFF;
  font-size: 13.5px;
  line-height: 1.45;
  -webkit-font-smoothing: antialiased;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}}

.page {{
  width: 210mm;
  height: 297mm;
  max-height: 297mm;
  padding: 13mm 16mm 12mm 16mm;
  box-sizing: border-box;
  page-break-after: always;
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  background: #FFFFFF;
  overflow: hidden;
}}

.page:last-child {{
  page-break-after: auto;
}}

/* Header & Footer */
.running-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 2.2mm;
  border-bottom: 1px solid #E2E8F0;
  margin-bottom: 3.5mm;
  font-size: 10.5px;
  color: #64748B;
  letter-spacing: 0.2px;
}}

.running-header .brand {{
  font-family: 'NotoSerifCustom', serif;
  font-weight: 700;
  color: #0F172A;
  font-size: 11px;
}}

.running-header .badge {{
  background: #FEF3C7;
  color: #B45309;
  padding: 2px 7px;
  border-radius: 4px;
  font-weight: 700;
  font-size: 9.5px;
}}

.running-footer {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 2.2mm;
  border-top: 1px solid #E2E8F0;
  margin-top: 3.5mm;
  font-size: 9.5px;
  color: #64748B;
}}

.running-footer .notice {{
  max-width: 82%;
  line-height: 1.35;
}}

.running-footer .page-num {{
  font-family: 'NotoSansCustom', sans-serif;
  font-weight: 700;
  color: #0F172A;
  background: #F1F5F9;
  padding: 2px 8px;
  border-radius: 4px;
}}

/* Typography */
h1.page-title {{
  font-family: 'NotoSerifCustom', serif;
  font-size: 24px;
  font-weight: 700;
  color: #0F172A;
  line-height: 1.25;
  margin-bottom: 2mm;
}}

.kicker {{
  font-family: 'NotoSansCustom', sans-serif;
  font-size: 10.5px;
  font-weight: 700;
  color: #D97706;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  margin-bottom: 1.2mm;
}}

.page-intro {{
  font-size: 12.5px;
  color: #475569;
  line-height: 1.45;
  margin-bottom: 3.5mm;
}}

/* Cards & Layouts */
.card {{
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 3.5mm 4.5mm;
}}

.card-subtle {{
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 3.5mm 4.5mm;
}}

/* Macro Pills Banner */
.macro-banner {{
  display: flex;
  gap: 2.5mm;
  margin-bottom: 3.5mm;
}}

.macro-pill {{
  flex: 1;
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  padding: 2mm 2.5mm;
  text-align: center;
}}

.macro-pill .label {{
  font-size: 9.5px;
  color: #64748B;
  font-weight: 500;
  margin-bottom: 0.8mm;
}}

.macro-pill .val {{
  font-size: 13px;
  font-weight: 700;
  color: #0F172A;
}}

/* Meal Blocks */
.meals-container {{
  display: flex;
  flex-direction: column;
  gap: 2.6mm;
  flex: 1;
}}

.meal-card {{
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 7px;
  padding: 2.8mm 3.8mm;
  box-shadow: 0 1px 2px rgba(0,0,0,0.02);
}}

.meal-header {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 1.2mm;
}}

.meal-title-group {{
  display: flex;
  align-items: center;
  gap: 2.5mm;
}}

.slot-tag {{
  background: #FEF3C7;
  color: #B45309;
  font-size: 10px;
  font-weight: 700;
  padding: 1.5px 6.5px;
  border-radius: 4px;
}}

.meal-title {{
  font-family: 'NotoSerifCustom', serif;
  font-size: 15px;
  font-weight: 700;
  color: #0F172A;
}}

.meal-macros {{
  font-size: 11px;
  color: #64748B;
  font-weight: 500;
}}

.meal-items {{
  margin-top: 1.5mm;
  padding-left: 2mm;
}}

.meal-item-line {{
  font-size: 12.5px;
  color: #334155;
  margin-bottom: 0.8mm;
  line-height: 1.35;
}}

.meal-item-line strong {{
  color: #0F172A;
  font-weight: 700;
}}

.meal-swap {{
  margin-top: 1.5mm;
  background: #FFFBEB;
  border: 1px dashed #FCD34D;
  border-radius: 5px;
  padding: 1.5mm 2.5mm;
  font-size: 11px;
  color: #92400E;
}}

/* Coach Tip Box */
.coach-tip-card {{
  background: #F8FAFC;
  border-left: 3.5px solid #D97706;
  border-radius: 4px;
  padding: 2.5mm 3.5mm;
  margin-top: 2.5mm;
}}

.coach-tip-card .tip-header {{
  font-family: 'NotoSerifCustom', serif;
  font-size: 11.5px;
  font-weight: 700;
  color: #B45309;
  margin-bottom: 0.8mm;
}}

.coach-tip-card .tip-content {{
  font-size: 11px;
  color: #334155;
  line-height: 1.4;
}}

/* Hydration tracker */
.hydration-check-box {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #F0FDF4;
  border: 1px solid #BBF7D0;
  border-radius: 5px;
  padding: 1.8mm 3mm;
  margin-top: 2mm;
}}

.hydration-check-box .htitle {{
  font-size: 10.5px;
  font-weight: 700;
  color: #166534;
}}

.hydration-cups {{
  display: flex;
  gap: 2mm;
}}

.cup-circle {{
  width: 14px;
  height: 14px;
  border: 1.5px solid #16A34A;
  border-radius: 50%;
  display: inline-block;
}}

/* Tables */
.modern-table {{
  width: 100%;
  border-collapse: collapse;
  margin-top: 2mm;
}}

.modern-table th {{
  background: #0F172A;
  color: #FFFFFF;
  font-size: 11.5px;
  font-weight: 700;
  padding: 2.5mm 3.5mm;
  text-align: left;
}}

.modern-table td {{
  padding: 2.2mm 3.5mm;
  font-size: 11.5px;
  border-bottom: 1px solid #E2E8F0;
  color: #334155;
}}

.modern-table tr:nth-child(even) td {{
  background: #F8FAFC;
}}

/* Cover Specifics */
.cover-page {{
  padding: 18mm 20mm;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 297mm;
}}

.cover-brand-seal {{
  display: flex;
  align-items: center;
  gap: 3.5mm;
  padding-bottom: 5mm;
  border-bottom: 2px solid #0F172A;
}}

.brand-monogram {{
  width: 44px;
  height: 44px;
  background: #D97706;
  color: #FFFFFF;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'NotoSerifCustom', serif;
  font-size: 22px;
  font-weight: 700;
}}

.brand-text-hilawe {{
  font-family: 'NotoSerifCustom', serif;
  font-size: 19px;
  font-weight: 700;
  color: #0F172A;
  letter-spacing: 0.3px;
}}

.brand-sub-hilawe {{
  font-size: 11px;
  color: #64748B;
  letter-spacing: 0.5px;
}}

.cover-hero {{
  margin: 10mm 0;
}}

.cover-tag {{
  display: inline-block;
  background: #FEF3C7;
  color: #B45309;
  font-weight: 700;
  font-size: 11.5px;
  padding: 3px 10px;
  border-radius: 5px;
  margin-bottom: 4mm;
}}

.cover-main-title {{
  font-family: 'NotoSerifCustom', serif;
  font-size: 34px;
  font-weight: 700;
  color: #0F172A;
  line-height: 1.25;
  margin-bottom: 4mm;
}}

.cover-client-card {{
  background: #F8FAFC;
  border: 1.5px solid #E2E8F0;
  border-radius: 10px;
  padding: 6mm 8mm;
  margin-top: 6mm;
}}

.cover-field-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4.5mm 8mm;
  margin-top: 4mm;
}}

.cover-field-label {{
  font-size: 11px;
  color: #64748B;
  margin-bottom: 1mm;
}}

.cover-field-val {{
  font-size: 15px;
  font-weight: 700;
  color: #0F172A;
}}

.cover-security-seal {{
  background: #FFFFFF;
  border: 1px dashed #CBD5E1;
  border-radius: 8px;
  padding: 4mm 6mm;
  display: flex;
  align-items: center;
  gap: 4mm;
  margin-top: 8mm;
}}

.shield-icon {{
  font-size: 22px;
  color: #16A34A;
}}

.security-text {{
  font-size: 11px;
  color: #475569;
  line-height: 1.35;
}}

.cover-disclaimer-card {{
  margin-top: 3.5mm;
  padding: 2.5mm 4mm;
  background: #FFFBEB;
  border-left: 3.5px solid #D97706;
  border-radius: 5px;
  font-size: 10px;
  line-height: 1.4;
  color: #92400E;
}}

.phase-card {{
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-left: 4.5px solid #D97706;
  border-radius: 8px;
  padding: 3.5mm 5mm;
  margin-bottom: 3mm;
}}

.phase-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.8mm;
}}

.phase-badge {{
  font-weight: 700;
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 4px;
}}

.phase-title {{
  font-family: 'NotoSerifCustom', serif;
  font-size: 13px;
  font-weight: 700;
  color: #0F172A;
}}

.phase-bullets {{
  font-size: 10.5px;
  color: #475569;
  line-height: 1.45;
  margin: 0;
  padding-left: 4.5mm;
}}

.phase-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 3mm;
  margin-top: 3mm;
  margin-bottom: 3.5mm;
}}

.worksheet-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4mm;
  margin-top: 4mm;
  margin-bottom: 4mm;
}}

.worksheet-card {{
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 4mm 4.5mm;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}}

.worksheet-card-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #F1F5F9;
  padding-bottom: 2mm;
  margin-bottom: 2.5mm;
}}

.worksheet-card-title {{
  font-family: 'NotoSerifCustom', serif;
  font-size: 12.5px;
  font-weight: 700;
  color: #0F172A;
}}

.worksheet-card-badge {{
  font-size: 9.5px;
  font-weight: 700;
  padding: 1.5px 6.5px;
  border-radius: 4px;
}}

.worksheet-field {{
  margin-bottom: 2.2mm;
  font-size: 10.5px;
  color: #334155;
  line-height: 1.4;
}}

.worksheet-line {{
  display: inline-block;
  border-bottom: 1.5px dotted #94A3B8;
  width: 52%;
  margin-left: 2mm;
  vertical-align: middle;
}}

.worksheet-scale {{
  display: flex;
  gap: 1.5mm;
  margin-top: 1mm;
}}

.worksheet-scale-box {{
  flex: 1;
  height: 13px;
  border: 1px solid #CBD5E1;
  border-radius: 2px;
  font-size: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748B;
  font-weight: 600;
}}
"""


def _render_running_header(context: DocumentContext, c: dict[str, str], is_client: bool) -> str:
    brand = "አሰልጣኝ ህላዌ ሰማ · ይፋዊ የግል የአመጋገብ ፕላን" if context.normalized_language == "AM" else "Coach Hilawe Semma · Official Nutrition Plan"
    if is_client:
        badge = "የጸደቀ ይፋዊ ፕላን" if context.normalized_language == "AM" else "APPROVED CLIENT PLAN"
    else:
        badge = f"{context.plan_public_id} · V{context.version_number}"
    return f"""
    <div class="running-header">
      <div class="brand">{escape(brand)}</div>
      <div class="badge">{escape(badge)}</div>
    </div>
    """


def _render_running_footer(context: DocumentContext, page_num: int, total_pages: int, is_client: bool) -> str:
    if context.normalized_language == "AM":
        notice = f"ይህ ፕላን የተዘጋጀው ለ<strong>{escape(context.client_name)}</strong> ብቻ ነው። ያለ አሰልጣኝ ህላዌ ሰማ ፈቃድ ማባዛት፣ ማሰራጨት ወይም መሸጥ በህግ ያስቀጣል።"
        pg_label = f"ገጽ {page_num} / {total_pages}"
    else:
        notice = f"Prepared exclusively for <strong>{escape(context.client_name)}</strong>. Unauthorized redistribution or resale is strictly prohibited."
        pg_label = f"Page {page_num} / {total_pages}"
    return f"""
    <div class="running-footer">
      <div class="notice">{notice}</div>
      <div class="page-num">{pg_label}</div>
    </div>
    """


def build_cover_html(plan: dict[str, Any], context: DocumentContext, c: dict[str, str], is_client: bool) -> str:
    duration = int((plan.get("product") or {}).get("duration_days") or 7)
    profile = plan.get("profile_summary") or {}
    targets = plan.get("nutrition_targets") or {}
    is_am = context.normalized_language == "AM"

    title = "የአሰልጣኝ ህላዌ ሰማ ይፋዊ የግል የአመጋገብ ፕላን" if is_am else "Coach Hilawe Semma Official Nutrition Plan"
    sub_title = f"{duration} ቀን · {c.get('nutrition_system', 'የአመጋገብ ስርዓት')}" if is_am else f"{duration} Day · {c.get('nutrition_system', 'Nutrition System')}"
    goal_lbl = profile_label(profile.get("goal") or "", context.normalized_language)
    cuisine_lbl = profile_label(profile.get("cuisine_style") or "", context.normalized_language)
    target_kcal = f"{rounded(targets.get('target_kcal'))} {c.get('macro_kcal', 'ካሎሪ' if is_am else 'kcal')}"
    protein_g = f"{rounded(targets.get('protein_g'))} {c.get('g_unit', 'ግ' if is_am else 'g')}"

    brand_title = "አሰልጣኝ ህላዌ ሰማ" if is_am else "Coach Hilawe Semma"
    brand_sub = "የአካል ብቃት እና የአመጋገብ ስርዓት" if is_am else "Fitness & Nutrition System"

    footer_meta = f"ስሪት {context.version_number}" if is_client and is_am else f"Version {context.version_number}" if is_client else f"{context.plan_public_id} · V{context.version_number}"

    return f"""
    <div class="page cover-page">
      <div class="cover-brand-seal">
        <div class="brand-monogram">ህ</div>
        <div>
          <div class="brand-text-hilawe">{escape(brand_title)}</div>
          <div class="brand-sub-hilawe">{escape(brand_sub)}</div>
        </div>
      </div>

      <div class="cover-hero">
        <div class="cover-tag">{escape(sub_title)}</div>
        <div class="cover-main-title">{escape(title)}</div>
        <p style="font-size: 14px; color: #475569; line-height: 1.5;">
          {"ለተሻለ ጤና፣ ቅልጥፍና እና የሰውነት ቅርጽ በሳይንሳዊ መንገድ የተዘጋጀ የግል መመሪያ።" if is_am else "Scientifically calibrated nutrition guide engineered for sustainable transformation."}
        </p>

        <div class="cover-client-card">
          <div style="font-size: 11px; font-weight: 700; color: #D97706; text-transform: uppercase; letter-spacing: 0.8px;">
            {"የደንበኛ መረጃ እና የፕላኑ መዋቅር" if is_am else "CLIENT PROFILE & ARCHITECTURE"}
          </div>
          <div class="cover-field-grid">
            <div>
              <div class="cover-field-label">{"የተዘጋጀለት ደንበኛ" if is_am else "Prepared For"}</div>
              <div class="cover-field-val">{escape(context.client_name)}</div>
            </div>
            <div>
              <div class="cover-field-label">{"ዋና ዓላማ" if is_am else "Primary Goal"}</div>
              <div class="cover-field-val">{escape(goal_lbl)}</div>
            </div>
            <div>
              <div class="cover-field-label">{"የቀን ካሎሪ ኢላማ" if is_am else "Daily Energy"}</div>
              <div class="cover-field-val">{escape(target_kcal)}</div>
            </div>
            <div>
              <div class="cover-field-label">{"የቀን ፕሮቲን ኢላማ" if is_am else "Daily Protein"}</div>
              <div class="cover-field-val">{escape(protein_g)}</div>
            </div>
            <div>
              <div class="cover-field-label">{"የምግብ ባህል" if is_am else "Cuisine Style"}</div>
              <div class="cover-field-val">{escape(cuisine_lbl)}</div>
            </div>
            <div>
              <div class="cover-field-label">{"የፕላኑ ቆይታ" if is_am else "Duration"}</div>
              <div class="cover-field-val">{duration} {"ቀናት" if is_am else "Days"}</div>
            </div>
          </div>
        </div>

        <div class="cover-security-seal">
          <div class="shield-icon">✓</div>
          <div class="security-text">
            <strong>{"ይፋዊ የተረጋገጠ ሰነድ" if is_am else "Officially Certified Document"}</strong><br>
            {"ይህ ፕላን በአሰልጣኝ ህላዌ ሰማ ቀጥተኛ ክትትል የተረጋገጠ ሲሆን ለተጠቃሚው ብቻ የተሰጠ የግል ፍቃድ ነው። ማባዛት ወይም ለሶስተኛ ወገን ማስተላለፍ በጥብቅ የተከለከለ ነው።" if is_am else "Verified under Coach Hilawe Semma supervision. Issued exclusively to the designated client. Unauthorized transfer prohibited."}
          </div>
        </div>

        <div class="cover-disclaimer-card">
          <strong>{"የህክምና ማስታወሻ፦" if is_am else "Medical Notice:"}</strong>
          {"ይህ ፕላን ለአጠቃላይ የአካል ብቃት እና የአመጋገብ ግንዛቤ የተዘጋጀ ሲሆን የህክምና ምክርን ወይም የክሊኒካል ህክምናን አይተካም። ማንኛውንም አዲስ የአመጋገብ ፕሮግራም ከመጀመርዎ በፊት ሀኪምዎን ያማክሩ።" if is_am else "This nutrition plan is designed for general fitness and nutritional guidance and does not replace clinical medical advice. Consult your physician before starting any new nutrition program."}
        </div>
      </div>

      <div style="display: flex; justify-content: space-between; align-items: flex-end; border-top: 1px solid #E2E8F0; padding-top: 4mm; font-size: 11px; color: #64748B;">
        <div>
          <strong>{escape(brand_title)}</strong>
        </div>
        <div>
          {escape(footer_meta)}
        </div>
      </div>
    </div>
    """


def build_glance_html(plan: dict[str, Any], context: DocumentContext, c: dict[str, str], is_client: bool, page_num: int, total_pages: int) -> str:
    targets = plan.get("nutrition_targets") or {}
    product = plan.get("product") or {}
    profile = plan.get("profile_summary") or {}
    client = context.client_profile or {}
    is_am = context.normalized_language == "AM"

    kg_lbl = c.get("kg_unit", "ኪ.ግ" if is_am else "kg")
    kcal_lbl = c.get("macro_kcal", "ካሎሪ" if is_am else "kcal")
    g_lbl = c.get("g_unit", "ግ" if is_am else "g")

    metrics = [
        (c.get("current_weight", "የአሁኑ ክብደት"), f"{rounded(client.get('current_weight_kg'), 1)} {kg_lbl}" if client.get("current_weight_kg") else c.get("not_provided", "አልተጠቀሰም")),
        (c.get("target_weight", "የታለመ ክብደት"), f"{rounded(client.get('target_weight_kg'), 1)} {kg_lbl}" if client.get("target_weight_kg") else c.get("not_provided", "አልተጠቀሰም")),
        (c.get("daily_energy", "የቀን ካሎሪ"), f"{rounded(targets.get('target_kcal'))} {kcal_lbl}"),
        (c.get("protein", "ፕሮቲን"), f"{rounded(targets.get('protein_g'))} {g_lbl}"),
        (c.get("meals_day", "ምግብ / ቀን"), f"{product.get('meals_per_day', 4)} {'ምግቦች' if is_am else 'meals'}"),
        (c.get("food_style", "የምግብ ምርጫ"), profile_label(profile.get("cuisine_style"), context.normalized_language)),
    ]

    metric_cards = "".join(f"""
      <div class="card-subtle" style="text-align: center;">
        <div style="font-size: 11px; color: #64748B; margin-bottom: 1.5mm;">{escape(label)}</div>
        <div style="font-size: 18px; font-weight: 700; color: #0F172A;">{escape(val)}</div>
      </div>
    """ for label, val in metrics)

    summary_rows = [
        (c.get("goal", "ዓላማ"), profile_label(profile.get("goal"), context.normalized_language)),
        (c.get("training", "የአካል ብቃት እንቅስቃሴ"), format_training_summary(profile.get("training_days_per_week"), profile.get("training_type"), context.normalized_language)),
        (c.get("budget", "የገበያ በጀት"), profile_label(profile.get("grocery_budget"), context.normalized_language)),
        (c.get("diet", "የአመጋገብ ስርዓት"), profile_label(profile.get("dietary_pattern"), context.normalized_language)),
        (c.get("fasting", "ጾም"), profile_label(profile.get("orthodox_fasting"), context.normalized_language)),
    ]

    summary_table_rows = "".join(f"""
      <tr>
        <td style="font-weight: 700; width: 35%; background: #F8FAFC; color: #0F172A;">{escape(k)}</td>
        <td style="color: #334155;">{escape(v)}</td>
      </tr>
    """ for k, v in summary_rows)

    return f"""
    <div class="page">
      <div>
        {_render_running_header(context, c, is_client)}
        <div class="kicker">{"ክፍል 01" if is_am else "SECTION 01"}</div>
        <h1 class="page-title">{escape(c.get("plan_glance", "የፕላንዎ አጭር ማጠቃለያ"))}</h1>
        <div class="page-intro">
          {"ይህ ገጽ የእርስዎን ቁልፍ የሰውነት መለኪያዎች፣ የቀን የሃይል ግቦችን እና በሳይንሳዊ መንገድ የተሰሉ የማክሮ ንጥረ ነገሮች ስሌትን ያጠቃልላል።" if is_am else "Overview of key physiological metrics, calibrated target energy expenditure, and macronutrient distributions."}
        </div>

        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 3mm; margin-bottom: 5mm;">
          {metric_cards}
        </div>

        <div class="card" style="padding: 0; overflow: hidden; margin-bottom: 5mm;">
          <table class="modern-table" style="margin-top: 0;">
            <thead>
              <tr>
                <th colspan="2">{"የደንበኛ የአኗኗር ዘይቤ እና ምርጫዎች" if is_am else "CLIENT PROFILE SPECIFICATIONS"}</th>
              </tr>
            </thead>
            <tbody>
              {summary_table_rows}
            </tbody>
          </table>
        </div>

        <div class="coach-tip-card">
          <div class="tip-header">{"የአሰልጣኝ ህላዌ ወርቃማ መመሪያ" if is_am else "Coach Hilawe Core Principle"}</div>
          <div class="tip-content">
            {"«ውጤታማነት የሚመጣው ከወጥነት ነው። በፕላኑ ላይ የተቀመጡትን መጠኖች በትክክል መመገብ፣ በቂ ውሃ መጠጣት እና እንቅልፍን በአግባቡ መውሰድ የታለመውን ግብ በአጭር ጊዜ ውስጥ ለማሳካት ወሳኝ ነው።»" if is_am else "Transformation is built by consistency, not perfection. Follow the structure, use the approved swaps when needed, and judge progress across time rather than one meal."}
          </div>
        </div>
      </div>

      {_render_running_footer(context, page_num, total_pages, is_client)}
    </div>
    """


def build_how_to_use_html(context: DocumentContext, c: dict[str, str], is_client: bool, page_num: int, total_pages: int) -> str:
    is_am = context.normalized_language == "AM"
    steps = [
        ("01", c.get("how_1_title", "የቀኑን መዋቅር ይከተሉ"), c.get("how_1", "በየቀኑ የተጻፉትን ምግቦች እና መጠኖች እንደ ዋና መመሪያዎ ይጠቀሙ።")),
        ("02", c.get("how_2_title", "ሲያስፈልግ ተቀያሪ ይጠቀሙ"), c.get("how_2", "የተፈቀዱ ተቀያሪዎች ፕላኑን ወደ ግምት ሳይቀይሩ ምቾት ይሰጡዎታል።")),
        ("03", c.get("how_3_title", "ወጥነት ከፍጹምነት ይበልጣል"), c.get("how_3", "አብዛኛውን ጊዜ መዋቅሩን ይከተሉ እና ፕላኑን እንደ ቋሚ ስርዓት ይጠቀሙበት።")),
    ]

    steps_html = "".join(f"""
      <div class="card" style="display: flex; gap: 4.5mm; align-items: flex-start; margin-bottom: 3.5mm;">
        <div style="background: #0F172A; color: #FFFFFF; font-size: 16px; font-weight: 700; width: 36px; height: 36px; border-radius: 6px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
          {num}
        </div>
        <div>
          <div style="font-family: 'NotoSerifCustom', serif; font-size: 15px; font-weight: 700; color: #0F172A; margin-bottom: 1.2mm;">
            {escape(title)}
          </div>
          <div style="font-size: 13px; color: #475569; line-height: 1.45;">
            {escape(desc)}
          </div>
        </div>
      </div>
    """ for num, title, desc in steps)

    return f"""
    <div class="page">
      <div>
        {_render_running_header(context, c, is_client)}
        <div class="kicker">{"ክፍል 02" if is_am else "SECTION 02"}</div>
        <h1 class="page-title">{escape(c.get("how_to_use", "ፕላኑን እንዴት ይጠቀሙ?"))}</h1>
        <div class="page-intro">
          {"ይህ የአመጋገብ ፕላን የተዘጋጀው ለዕለታዊ ኑሮዎ ምቹ፣ ተግባራዊ እና በቀላሉ የሚተገበር ሆኖ ነው። የሚከተሉትን 3 ዋና ደረጃዎች ያክብሩ።" if is_am else "This nutrition system is engineered to seamlessly integrate into your daily life. Adhere to these three operational principles."}
        </div>

        {steps_html}

        <div class="card-subtle" style="margin-top: 5mm; border-left: 3.5px solid #16A34A;">
          <div style="font-weight: 700; color: #166534; font-size: 13px; margin-bottom: 1.5mm;">
            {"ሳምንታዊ የቅድመ-ዝግጅት ምክሮች" if is_am else "Weekly Preparation Checklist"}
          </div>
          <div style="font-size: 12px; color: #334155; line-height: 1.45;">
            {"1. እንደ ሽሮ፣ ምስር እና ዶሮ ያሉ ምግቦችን ለ2-3 ቀናት አስቀድመው በማብሰል በማቀዝቀዣ ያስቀምጡ።<br>2. እንቁላል አስቀድመው ቀቅለው በማስቀመጥ የቁርስ ሰዓትዎን ያሳጥሩ።<br>3. አትክልቶችን አስቀድመው አጥበውና ከታትፈው በማዘጋጀት በቀላሉ ለመጠቀም ዝግጁ ያድርጉ።" if is_am else "1. Batch-cook staple stews (Shiro, Misir, Chicken) in advance for 2-3 days.<br>2. Boil eggs in advance for zero-friction morning prep.<br>3. Wash and portion fresh vegetables to prevent daily cooking friction."}
          </div>
        </div>
      </div>

      {_render_running_footer(context, page_num, total_pages, is_client)}
    </div>
    """


def build_rotation_html(plan: dict[str, Any], context: DocumentContext, c: dict[str, str], is_client: bool, page_num: int, total_pages: int) -> str:
    is_am = context.normalized_language == "AM"
    rotation = plan.get("rotation") or []
    weeks: dict[int, set[str]] = {}
    for row in rotation:
        weeks.setdefault(int(row.get("week") or 1), set()).add(str(row.get("mode") or "PRIMARY"))
    if not weeks:
        weeks = {1: {"PRIMARY"}}

    rows_html = []
    for week, modes in sorted(weeks.items()):
        mode = "SWAP" if "SWAP" in modes else "PRIMARY"
        mode_text = c.get("swap_rotation", "የልውውጥ ሳምንት") if mode == "SWAP" else c.get("primary", "ዋና ሳምንት")
        badge_style = "background: #FEF3C7; color: #B45309;" if mode == "SWAP" else "background: #E0F2FE; color: #0369A1;"
        rows_html.append(f"""
          <tr>
            <td style="font-weight: 700; width: 30%;">
              {c.get('week', 'ሳምንት' if is_am else 'Week')} {week}
            </td>
            <td>
              <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 11px; {badge_style}">
                {escape(mode_text)}
              </span>
            </td>
          </tr>
        """)

    fasting_dates = [str(row.get("date")) for row in rotation if row.get("core_source") == "FASTING"]
    fasting_banner = ""
    if fasting_dates:
        lbl = "የወቅታዊ ጾም መዋቅር የሚጠቀሙ ቀናት: " if is_am else "Dates designated for seasonal fasting core: "
        fasting_banner = f"""
        <div style="margin-top: 4mm; background: #FEF2F2; border: 1px solid #FECACA; border-radius: 6px; padding: 2.5mm 3.5mm; font-size: 11.5px; color: #991B1B;">
          <strong>{lbl}</strong> {escape(", ".join(fasting_dates))}
        </div>
        """

    return f"""
    <div class="page">
      <div>
        {_render_running_header(context, c, is_client)}
        <div class="kicker">{"ክፍል 03" if is_am else "SECTION 03"}</div>
        <h1 class="page-title">{escape(c.get("month_map", "የፕላንዎ ካርታ"))}</h1>
        <div class="page-intro">
          {escape(c.get("core_rotation_note", "7 ቀናት = አንድ የተገመገመ ዋና ሳምንት። የ14 እና 30 ቀን ፕላኖች ይህንኑ የተረጋገጠ መዋቅር በሳምንታዊ ዑደት ይጠቀማሉ።"))}
        </div>

        <div class="card" style="padding: 0; overflow: hidden; margin-bottom: 3.5mm;">
          <table class="modern-table" style="margin-top: 0;">
            <thead>
              <tr>
                <th>{"ሳምንት" if is_am else "Week"}</th>
                <th>{"የሳምንቱ አወቃቀር" if is_am else "Rotation Structure"}</th>
              </tr>
            </thead>
            <tbody>
              {"".join(rows_html)}
            </tbody>
          </table>
        </div>

        {fasting_banner}

        <div style="margin-top: 3.5mm;">
          <div style="font-family: 'NotoSerifCustom', serif; font-size: 12.5px; font-weight: 700; color: #0F172A; margin-bottom: 2mm;">
            {"የሳምንታት የለውጥ ጉዞ እና የደረጃ ካርታ" if is_am else "Multi-Week Progression Roadmap"}
          </div>
          <div class="phase-grid">
            <div class="phase-card">
              <div class="phase-header">
                <span class="phase-title">{"ሳምንት 01" if is_am else "Week 01"}</span>
                <span class="phase-badge" style="background: #E0F2FE; color: #0369A1;">{"ምዕራፍ 1" if is_am else "Phase 1"}</span>
              </div>
              <div style="font-size: 10.5px; font-weight: 700; color: #0F172A; margin-bottom: 1mm;">{"መሰረታዊ ግንባታ" if is_am else "Foundation"}</div>
              <ul class="phase-bullets">
                <li>{"ወጥ የሆነ የምግብ ሰዓትና የውሃ አወሳሰድ ልማድ መመስረት።" if is_am else "Establish meal timing consistency and hydration baseline."}</li>
                <li>{"የምግብ መጠኖችን በመዳፍ እና ሲኒ መለካት መልመድ።" if is_am else "Calibrate precise portioning using familiar household measures."}</li>
              </ul>
            </div>

            <div class="phase-card">
              <div class="phase-header">
                <span class="phase-title">{"ሳምንት 02" if is_am else "Week 02"}</span>
                <span class="phase-badge" style="background: #FEF3C7; color: #B45309;">{"ምዕራፍ 2" if is_am else "Phase 2"}</span>
              </div>
              <div style="font-size: 10.5px; font-weight: 700; color: #0F172A; margin-bottom: 1mm;">{"ልውውጥ እና ቅልጥፍና" if is_am else "Swap Diversity"}</div>
              <ul class="phase-bullets">
                <li>{"ተመሳሳይ ምግቦችን ያለ ማክሮ መዛባት መለዋወጥ።" if is_am else "Introduce calculated food swaps without macro deviation."}</li>
                <li>{"የስራና የልምምድ ቀናትን የሃይል ሚዛን መጠበቅ።" if is_am else "Optimize daily energy availability and recovery."}</li>
              </ul>
            </div>

            <div class="phase-card">
              <div class="phase-header">
                <span class="phase-title">{"ሳምንት 03" if is_am else "Week 03"}</span>
                <span class="phase-badge" style="background: #DCFCE7; color: #15803D;">{"ምዕራፍ 3" if is_am else "Phase 3"}</span>
              </div>
              <div style="font-size: 10.5px; font-weight: 700; color: #0F172A; margin-bottom: 1mm;">{"ሜታቦሊክ ማስተካከያ" if is_am else "Re-calibration"}</div>
              <ul class="phase-bullets">
                <li>{"የክብደት መቀዛቀዝን (Plateau) መከላከል እና ማፋጠን።" if is_am else "Prevent metabolic plateau and maintain steady progress."}</li>
                <li>{"የጥጋብ እና የረሃብ ምልክቶችን መቆጣጠር።" if is_am else "Refine intuitive satiety and effortless adherence."}</li>
              </ul>
            </div>

            <div class="phase-card">
              <div class="phase-header">
                <span class="phase-title">{"ሳምንት 04" if is_am else "Week 04"}</span>
                <span class="phase-badge" style="background: #F3E8FF; color: #7E22CE;">{"ምዕራፍ 4" if is_am else "Phase 4"}</span>
              </div>
              <div style="font-size: 10.5px; font-weight: 700; color: #0F172A; margin-bottom: 1mm;">{"ከፍተኛ ውጤት" if is_am else "Peak Conditioning"}</div>
              <ul class="phase-bullets">
                <li>{"የተገኙትን ውጤቶች ማጠናከር እና ዘላቂ ልማድ ማድረግ።" if is_am else "Consolidate body composition into permanent habits."}</li>
                <li>{"ለቀጣዩ የለውጥ ምዕራፍ የሰውነት ዝግጁነት ማረጋገጥ።" if is_am else "Finalize milestone assessments for long-term lifestyle."}</li>
              </ul>
            </div>
          </div>
        </div>

        <div class="card-subtle" style="margin-top: 3mm;">
          <div style="font-weight: 700; color: #0F172A; font-size: 12px; margin-bottom: 1mm;">
            {"የምግብ ዑደት ስትራቴጂ" if is_am else "Rotation Strategy"}
          </div>
          <div style="font-size: 11px; color: #475569; line-height: 1.4;">
            {"የምግብ ዑደቱ ዋና ዓላማ ሰውነት በአንድ አይነት ምግብ እንዳይሰለችና የተለያዩ ንጥረ ነገሮችን እንዲያገኝ ማድረግ ነው። በዋናው ሳምንት የተዘረዘሩትን ምግቦች ከለመዱ በኋላ በልውውጥ ሳምንት አማራጭ ምግቦችን በቀላሉ መተካት ይችላሉ።" if is_am else "The purpose of structured rotation is dietary variety without macro variance. Once the primary week is mastered, swap rotations provide flavor diversity while keeping metabolic targets identical."}
          </div>
        </div>
      </div>

      {_render_running_footer(context, page_num, total_pages, is_client)}
    </div>
    """


def build_day_html(
    day: dict[str, Any],
    day_idx: int,
    context: DocumentContext,
    c: dict[str, str],
    is_client: bool,
    page_num: int,
    total_pages: int,
    is_fasting_core: bool = False,
) -> str:
    is_am = context.normalized_language == "AM"
    totals = day.get("totals") or {}
    meals = day.get("meals") or []
    day_num = int(day.get("day_index", day_idx)) + 1
    day_name = day_label(str(day.get("day_name") or "Day"), context.normalized_language)
    date_str = str(day.get("date") or "")

    # Header kicker & title
    prefix = c.get("day_prefix", "ቀን" if is_am else "DAY")
    title_text = f"{prefix} {day_num:02d} · {day_name}"
    if date_str:
        title_text += f" ({date_str})"

    fasting_chip = ""
    if day.get("fasting") or is_fasting_core:
        fasting_chip = f'<span style="background: #FEF3C7; color: #B45309; font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 4px; margin-left: 2mm;">{escape(c.get("fasting_day", "የጾም ቀን"))}</span>'

    # Macro pills
    kcal_val = f"{rounded(totals.get('kcal'))} {c.get('macro_kcal', 'ካሎሪ' if is_am else 'kcal')}"
    prot_val = f"{rounded(totals.get('protein'))} {c.get('g_unit', 'ግ' if is_am else 'g')}"
    carb_val = f"{rounded(totals.get('carbs'))} {c.get('g_unit', 'ግ' if is_am else 'g')}"
    fat_val = f"{rounded(totals.get('fat'))} {c.get('g_unit', 'ግ' if is_am else 'g')}"

    macro_banner_html = f"""
    <div class="macro-banner">
      <div class="macro-pill">
        <div class="label">{"የቀን ካሎሪ" if is_am else "Calories"}</div>
        <div class="val">{kcal_val}</div>
      </div>
      <div class="macro-pill">
        <div class="label">{"ፕሮቲን" if is_am else "Protein"}</div>
        <div class="val">{prot_val}</div>
      </div>
      <div class="macro-pill">
        <div class="label">{"ካርቦሃይድሬት" if is_am else "Carbs"}</div>
        <div class="val">{carb_val}</div>
      </div>
      <div class="macro-pill">
        <div class="label">{"ቅባት" if is_am else "Fat"}</div>
        <div class="val">{fat_val}</div>
      </div>
    </div>
    """

    # Build meal cards
    g_lbl = c.get("g_unit", "ግ" if is_am else "g")
    meal_cards_html = []
    for meal in meals:
        slot = slot_label(str(meal.get("slot") or "Meal"), context.normalized_language)
        meal_title = str(meal.get("meal_name") or "Meal")
        template_id = str(meal.get("template_id") or "")
        if is_am:
            if template_id:
                meal_title = local_template_name(template_id, meal_title, context.normalized_language)
            elif meal.get("recipe_ids"):
                meal_title = local_recipe_name(meal["recipe_ids"][0], meal_title, context.normalized_language)
            else:
                items = meal.get("items") or []
                if items:
                    meal_title = local_food_name(str(items[0].get("food_id") or ""), meal_title, context.normalized_language)

        m_macros = meal.get("macros") or {}
        if is_am:
            macro_sub = f"{rounded(m_macros.get('kcal'))} ካሎሪ · ፕሮቲን {rounded(m_macros.get('protein'))}ግ · ካርቦሃይድሬት {rounded(m_macros.get('carbs'))}ግ · ቅባት {rounded(m_macros.get('fat'))}ግ"
        else:
            macro_sub = f"{rounded(m_macros.get('kcal'))} kcal · P {rounded(m_macros.get('protein'))}g · C {rounded(m_macros.get('carbs'))}g · F {rounded(m_macros.get('fat'))}g"

        # Food items
        item_lines = []
        for item in meal.get("items") or []:
            if item.get("recipe_id"):
                name = local_recipe_name(item["recipe_id"], str(item.get("recipe_name") or item.get("food_name") or "Recipe"), context.normalized_language)
            else:
                name = local_food_name(str(item.get("food_id") or ""), str(item.get("food_name") or "Food"), context.normalized_language)
            grams = f"{rounded(item.get('grams'))} {g_lbl}"
            familiar = str(item.get("familiar_am") or item.get("familiar") or "").strip()
            if familiar:
                if is_am:
                    from meal_plan.generation.formatting import familiar_portion
                    familiar_str = familiar_portion(1.0, familiar, language="AM")
                else:
                    familiar_str = familiar
                item_lines.append(f'<div class="meal-item-line">• <strong>{escape(name)}</strong> — {grams} <span style="color: #64748B;">({escape(familiar_str)})</span></div>')
            else:
                item_lines.append(f'<div class="meal-item-line">• <strong>{escape(name)}</strong> — {grams}</div>')

        # Swap option
        swap_html = ""
        exchanges = meal.get("exchange_options") or []
        if exchanges and exchanges[0].get("options"):
            opt = exchanges[0]["options"][0]
            if opt.get("recipe_id"):
                swap_name = local_recipe_name(opt["recipe_id"], str(opt.get("recipe_name") or opt.get("food_name") or ""), context.normalized_language)
            else:
                swap_name = local_food_name(str(opt.get("food_id") or ""), str(opt.get("food_name") or ""), context.normalized_language)
            swap_grams = f"{rounded(opt.get('exchange_weight_g'))} {g_lbl}"
            swap_lbl = c.get("swap", "ተቀያሪ ምግብ" if is_am else "SWAP")
            swap_html = f'<div class="meal-swap">🔄 <strong>{escape(swap_lbl)}:</strong> {escape(swap_name)} ({swap_grams})</div>'

        meal_cards_html.append(f"""
        <div class="meal-card">
          <div class="meal-header">
            <div class="meal-title-group">
              <span class="slot-tag">{escape(slot)}</span>
              <span class="meal-title">{escape(meal_title)}</span>
            </div>
            <div class="meal-macros">{macro_sub}</div>
          </div>
          <div class="meal-items">
            {"".join(item_lines)}
          </div>
          {swap_html}
        </div>
        """)

    # Pick daily coach wisdom tip (mod by day index)
    tips_pool = _DAILY_COACH_TIPS_AM if is_am else _DAILY_COACH_TIPS_EN
    tip = tips_pool[day_idx % len(tips_pool)]

    # Hydration tracker filler
    h_cups = "".join('<span class="cup-circle"></span>' for _ in range(8))
    htitle = "የቀኑ የውሃ መከታተያ (8 ብርጭቆዎች / 2.5+ ሊትር)" if is_am else "Daily Hydration Checklist (8 Glasses / 2.5+ L)"

    return f"""
    <div class="page">
      <div>
        {_render_running_header(context, c, is_client)}
        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 2mm;">
          <h1 class="page-title" style="margin-bottom: 0;">{escape(title_text)}{fasting_chip}</h1>
          <span style="font-size: 11px; color: #64748B; font-weight: 700;">{"የተመጣጠነ ምግብ" if is_am else "BALANCED"}</span>
        </div>

        {macro_banner_html}

        <div class="meals-container">
          {"".join(meal_cards_html)}
        </div>

        <div class="coach-tip-card">
          <div class="tip-header">{escape(tip["title"])}</div>
          <div class="tip-content">{escape(tip["text"])}</div>
        </div>

        <div class="hydration-check-box">
          <div class="htitle">{htitle}</div>
          <div class="hydration-cups">{h_cups}</div>
        </div>
      </div>

      {_render_running_footer(context, page_num, total_pages, is_client)}
    </div>
    """


def build_checkin_worksheet_html(
    plan: dict[str, Any],
    context: DocumentContext,
    c: dict[str, str],
    is_client: bool,
    page_num: int,
    total_pages: int,
) -> str:
    is_am = context.normalized_language == "AM"
    scale_boxes = "".join(f'<div class="worksheet-scale-box">{i}</div>' for i in range(1, 11))

    return f"""
    <div class="page">
      <div>
        {_render_running_header(context, c, is_client)}
        <div class="kicker">{"ክፍል 04" if is_am else "SECTION 04"}</div>
        <h1 class="page-title">{"ሳምንታዊ የለውጥ መከታተያ ቅጽ" if is_am else "Weekly Transformation Tracker"}</h1>
        <div class="page-intro">
          {"ውጤት የሚመጣው እድገትን በተጨባጭ ከመለካት ነው። እያንዳንዱን ሳምንት ሲያጠናቅቁ ክብደትዎን፣ የወገብ ስፋትዎን እና የሰውነት ስሜትዎን እዚህ ቅጽ ላይ ይመዝግቡ።" if is_am else "Real transformation is built on measurable consistency. At the end of each milestone week, record your biometric indicators, energy levels, and adherence notes here."}
        </div>

        <div class="worksheet-grid">
          <!-- Milestone 1 -->
          <div class="worksheet-card" style="border-left: 4px solid #0284C7;">
            <div class="worksheet-card-header">
              <span class="worksheet-card-title">{"ሳምንት 01 · ቀን 07 Check-In" if is_am else "Week 01 · Day 07 Check-In"}</span>
              <span class="worksheet-card-badge" style="background: #E0F2FE; color: #0369A1;">{"ምዕራፍ 1" if is_am else "Phase 1"}</span>
            </div>
            <div class="worksheet-field">⚖️ <strong>{"ክብደት፦" if is_am else "Weight:"}</strong> <span class="worksheet-line"></span> {"ኪ.ግ" if is_am else "kg"}</div>
            <div class="worksheet-field">📏 <strong>{"የወገብ ስፋት፦" if is_am else "Waist:"}</strong> <span class="worksheet-line"></span> {"ሳ.ሜ" if is_am else "cm"}</div>
            <div class="worksheet-field">
              ⚡️ <strong>{"የሃይል መጠን (1-10)፦" if is_am else "Energy Level (1-10):"}</strong>
              <div class="worksheet-scale">{scale_boxes}</div>
            </div>
            <div class="worksheet-field">
              💧 <strong>{"የውሃ አወሳሰድ (1-10)፦" if is_am else "Hydration (1-10):"}</strong>
              <div class="worksheet-scale">{scale_boxes}</div>
            </div>
            <div class="worksheet-field" style="margin-top: 1.5mm;">
              📝 <strong>{"የሳምንቱ ማስታወሻ፦" if is_am else "Weekly Notes:"}</strong>
              <div style="border-bottom: 1.5px dotted #94A3B8; margin-top: 3.5mm;"></div>
            </div>
          </div>

          <!-- Milestone 2 -->
          <div class="worksheet-card" style="border-left: 4px solid #D97706;">
            <div class="worksheet-card-header">
              <span class="worksheet-card-title">{"ሳምንት 02 · ቀን 14 Check-In" if is_am else "Week 02 · Day 14 Check-In"}</span>
              <span class="worksheet-card-badge" style="background: #FEF3C7; color: #B45309;">{"ምዕራፍ 2" if is_am else "Phase 2"}</span>
            </div>
            <div class="worksheet-field">⚖️ <strong>{"ክብደት፦" if is_am else "Weight:"}</strong> <span class="worksheet-line"></span> {"ኪ.ግ" if is_am else "kg"}</div>
            <div class="worksheet-field">📏 <strong>{"የወገብ ስፋት፦" if is_am else "Waist:"}</strong> <span class="worksheet-line"></span> {"ሳ.ሜ" if is_am else "cm"}</div>
            <div class="worksheet-field">
              ⚡️ <strong>{"የሃይል መጠን (1-10)፦" if is_am else "Energy Level (1-10):"}</strong>
              <div class="worksheet-scale">{scale_boxes}</div>
            </div>
            <div class="worksheet-field">
              💧 <strong>{"የውሃ አወሳሰድ (1-10)፦" if is_am else "Hydration (1-10):"}</strong>
              <div class="worksheet-scale">{scale_boxes}</div>
            </div>
            <div class="worksheet-field" style="margin-top: 1.5mm;">
              📝 <strong>{"የሳምንቱ ማስታወሻ፦" if is_am else "Weekly Notes:"}</strong>
              <div style="border-bottom: 1.5px dotted #94A3B8; margin-top: 3.5mm;"></div>
            </div>
          </div>

          <!-- Milestone 3 -->
          <div class="worksheet-card" style="border-left: 4px solid #16A34A;">
            <div class="worksheet-card-header">
              <span class="worksheet-card-title">{"ሳምንት 03 · ቀን 21 Check-In" if is_am else "Week 03 · Day 21 Check-In"}</span>
              <span class="worksheet-card-badge" style="background: #DCFCE7; color: #15803D;">{"ምዕራፍ 3" if is_am else "Phase 3"}</span>
            </div>
            <div class="worksheet-field">⚖️ <strong>{"ክብደት፦" if is_am else "Weight:"}</strong> <span class="worksheet-line"></span> {"ኪ.ግ" if is_am else "kg"}</div>
            <div class="worksheet-field">📏 <strong>{"የወገብ ስፋት፦" if is_am else "Waist:"}</strong> <span class="worksheet-line"></span> {"ሳ.ሜ" if is_am else "cm"}</div>
            <div class="worksheet-field">
              ⚡️ <strong>{"የሃይል መጠን (1-10)፦" if is_am else "Energy Level (1-10):"}</strong>
              <div class="worksheet-scale">{scale_boxes}</div>
            </div>
            <div class="worksheet-field">
              💧 <strong>{"የውሃ አወሳሰድ (1-10)፦" if is_am else "Hydration (1-10):"}</strong>
              <div class="worksheet-scale">{scale_boxes}</div>
            </div>
            <div class="worksheet-field" style="margin-top: 1.5mm;">
              📝 <strong>{"የሳምንቱ ማስታወሻ፦" if is_am else "Weekly Notes:"}</strong>
              <div style="border-bottom: 1.5px dotted #94A3B8; margin-top: 3.5mm;"></div>
            </div>
          </div>

          <!-- Milestone 4 -->
          <div class="worksheet-card" style="border-left: 4px solid #7E22CE;">
            <div class="worksheet-card-header">
              <span class="worksheet-card-title">{"ሳምንት 04 · ቀን 30 Final Check-In" if is_am else "Week 04 · Day 30 Final Check-In"}</span>
              <span class="worksheet-card-badge" style="background: #F3E8FF; color: #7E22CE;">{"ምዕራፍ 4" if is_am else "Phase 4"}</span>
            </div>
            <div class="worksheet-field">⚖️ <strong>{"ክብደት፦" if is_am else "Weight:"}</strong> <span class="worksheet-line"></span> {"ኪ.ግ" if is_am else "kg"}</div>
            <div class="worksheet-field">📏 <strong>{"የወገብ ስፋት፦" if is_am else "Waist:"}</strong> <span class="worksheet-line"></span> {"ሳ.ሜ" if is_am else "cm"}</div>
            <div class="worksheet-field">
              ⚡️ <strong>{"የሃይል መጠን (1-10)፦" if is_am else "Energy Level (1-10):"}</strong>
              <div class="worksheet-scale">{scale_boxes}</div>
            </div>
            <div class="worksheet-field">
              💧 <strong>{"የውሃ አወሳሰድ (1-10)፦" if is_am else "Hydration (1-10):"}</strong>
              <div class="worksheet-scale">{scale_boxes}</div>
            </div>
            <div class="worksheet-field" style="margin-top: 1.5mm;">
              📝 <strong>{"የሳምንቱ ማስታወሻ፦" if is_am else "Weekly Notes:"}</strong>
              <div style="border-bottom: 1.5px dotted #94A3B8; margin-top: 3.5mm;"></div>
            </div>
          </div>
        </div>

        <div class="card" style="background: #FFFBEB; border: 1.5px solid #FCD34D; padding: 3.5mm 5mm; margin-top: 3mm;">
          <div style="font-size: 11px; color: #92400E; line-height: 1.45;">
            <strong>{"የአሰልጣኝ ህላዌ ምክር፦" if is_am else "Coach Hilawe Pro Tip:"}</strong>
            {" «ሰውነትህ የሚለወጠው በየቀኑ በምታደርጋቸው ትናንሽ ውሳኔዎች ድምር ውጤት ነው። መለኪያህን በየሳምንቱ በተመሳሳይ ሰዓት (ጠዋት በባዶ ሆድ) መዝግብ!»" if is_am else " \"Progress is the compounding result of small daily disciplines. Log your metrics at the same time each week, ideally first thing in the morning before breakfast.\""}
          </div>
        </div>
      </div>

      {_render_running_footer(context, page_num, total_pages, is_client)}
    </div>
    """


def balanced_chunks(items: list[Any], max_per_page: int = 25) -> list[list[Any]]:
    """Distribute items evenly across pages so there are no trailing orphan rows."""
    if not items:
        return []
    total = len(items)
    if total <= max_per_page:
        return [items]
    num_pages = (total + max_per_page - 1) // max_per_page
    avg = total // num_pages
    rem = total % num_pages
    chunks = []
    start = 0
    for i in range(num_pages):
        size = avg + (1 if i < rem else 0)
        chunks.append(items[start:start + size])
        start += size
    return chunks


def build_grocery_pages(
    plan: dict[str, Any],
    context: DocumentContext,
    c: dict[str, str],
    is_client: bool,
    start_page: int,
    total_pages: int,
    is_fasting: bool = False,
    max_per_page: int = 25,
) -> tuple[list[str], int]:
    """Render grocery items chunked gracefully into distinct A4 pages."""
    is_am = context.normalized_language == "AM"
    grocery_data = (plan.get("fasting_grocery") if is_fasting else plan.get("grocery")) or []
    g_lbl = c.get("g_unit", "ግ" if is_am else "g")

    kicker = "ክፍል 05" if is_am else "SECTION 05"
    base_title = c.get("fasting_grocery" if is_fasting else "grocery", "የገበያ ዝርዝር")

    if not grocery_data:
        html = f"""
        <div class="page">
          <div>
            {_render_running_header(context, c, is_client)}
            <div class="kicker">{kicker}</div>
            <h1 class="page-title">{escape(base_title)}</h1>
            <div class="card" style="padding: 5mm; text-align: center; color: #64748B;">
              {"ምንም የተመዘገበ የገበያ ዝርዝር የለም።" if is_am else "No grocery items recorded."}
            </div>
          </div>
          {_render_running_footer(context, start_page, total_pages, is_client)}
        </div>
        """
        return [html], start_page + 1

    chunks = balanced_chunks(grocery_data, max_per_page=max_per_page)
    pages_html = []
    current_page = start_page

    for chunk_idx, chunk in enumerate(chunks):
        part_suffix = f" ({c.get('part', 'ክፍል' if is_am else 'Part')} {chunk_idx + 1})" if len(chunks) > 1 else ""
        page_title = f"{base_title}{part_suffix}"

        table_rows = []
        for row in chunk:
            item_name = local_food_name(str(row.get("food_id") or ""), str(row.get("buy_item") or ""), context.normalized_language)
            category = local_category_name(str(row.get("category") or ""), context.normalized_language)
            planned = f"{rounded(row.get('planned_grams'))} {g_lbl}"
            buy_qty = local_purchase_quantity(str(row.get("purchase_quantity") or ""), context.normalized_language)

            table_rows.append(f"""
              <tr>
                <td style="font-weight: 700; color: #0F172A;">{escape(item_name)}</td>
                <td><span style="background: #F1F5F9; padding: 1.5px 6px; border-radius: 4px; font-size: 10px; color: #475569;">{escape(category)}</span></td>
                <td>{planned}</td>
                <td style="font-weight: 700; color: #0F172A;">{escape(buy_qty)}</td>
              </tr>
            """)

        tips_card = ""
        if chunk_idx == len(chunks) - 1:
            tips_card = f"""
            <div class="card-subtle" style="border-left: 3.5px solid #D97706; margin-top: 3mm;">
              <div style="font-weight: 700; color: #B45309; font-size: 12px; margin-bottom: 1.2mm;">
                {"የገበያ እና የምግብ አያያዝ ጠቃሚ ምክሮች" if is_am else "Shopping & Storage Pro Tips"}
              </div>
              <div style="font-size: 11px; color: #334155; line-height: 1.4;">
                {"• አትክልቶችን በሳምንት ሁለት ጊዜ ትኩስ ሆነው ቢገዙ የተመጣጠነ ንጥረ ነገራቸውን ሳይለቁ ለመጠቀም ይረዳል።<br>• ጥራጥሬዎችን (ምስር፣ ሽሮ፣ ጓያ) በደረቁ በንጹህ እቃ አስቀምጠው እንደ አስፈላጊነቱ ይጠቀሙ።<br>• እንቁላል በቀዝቃዛ ስፍራ ወይም ፍሪጅ ውስጥ በማስቀመጥ ትኩስነቱን ይጠብቁ።" if is_am else "• Purchase produce twice weekly to retain maximum micronutrient potency.<br>• Store dry legumes in airtight glass jars away from humidity.<br>• Keep eggs refrigerated at consistent temperatures for freshness."}
              </div>
            </div>
            """

        p_html = f"""
        <div class="page">
          <div>
            {_render_running_header(context, c, is_client)}
            <div class="kicker">{kicker}</div>
            <h1 class="page-title">{escape(page_title)}</h1>
            <div class="page-intro">
              {escape(c.get("grocery_intro", "የተገመገሙት የግዢ መጠኖች ለሳምንታዊ ዝግጅት የተሰሉ ናቸው። እንደ ቤተሰብዎ ፍላጎትና ፓኬት መጠን ማስተካከል ይችላሉ።"))}
            </div>

            <div class="card" style="padding: 0; overflow: hidden; margin-bottom: 2mm;">
              <table class="modern-table" style="margin-top: 0;">
                <thead>
                  <tr>
                    <th>{escape(c.get("item", "የምግብ አይነት"))}</th>
                    <th>{escape(c.get("category", "ምድብ"))}</th>
                    <th>{escape(c.get("planned", "በፕላኑ"))}</th>
                    <th>{escape(c.get("buy", "የሚገዛ"))}</th>
                  </tr>
                </thead>
                <tbody>
                  {"".join(table_rows)}
                </tbody>
              </table>
            </div>

            {tips_card}
          </div>

          {_render_running_footer(context, current_page, total_pages, is_client)}
        </div>
        """
        pages_html.append(p_html)
        current_page += 1

    return pages_html, current_page


def build_hydration_html(context: DocumentContext, c: dict[str, str], is_client: bool, page_num: int, total_pages: int) -> str:
    is_am = context.normalized_language == "AM"
    target_l = context.hydration_target_l or 2.6

    brand_name = "አሰልጣኝ ህላዌ ሰማ" if is_am else "Coach Hilawe Semma"

    return f"""
    <div class="page">
      <div>
        {_render_running_header(context, c, is_client)}
        <div class="kicker">{"ክፍል 06" if is_am else "SECTION 06"}</div>
        <h1 class="page-title">{escape(c.get("portion_hydration", "የውሃ እና የአኗኗር መመሪያ"))}</h1>
        <div class="page-intro">
          {"ውሃ ለሰውነት ሜታቦሊዝም፣ ለስብ ማቃጠል እና ለሰውነት ጥንካሬ ዋናው መሰረት ነው። ይህ መመሪያ የውሃ አወሳሰድዎን ለማስተካከል ይረዳዎታል።" if is_am else "Hydration is the metabolic cornerstone for lipolysis and muscular energy. Maintain consistent fluid intake across all waking hours."}
        </div>

        <div class="card-subtle" style="display: flex; align-items: center; justify-content: space-between; padding: 6mm 8mm; margin-bottom: 5mm; border-left: 5px solid #0284C7;">
          <div>
            <div style="font-size: 12px; color: #0284C7; font-weight: 700; text-transform: uppercase;">
              {"የቀን የውሃ ኢላማ" if is_am else "TARGET DAILY HYDRATION"}
            </div>
            <div style="font-size: 32px; font-weight: 700; color: #0F172A; margin: 1mm 0;">
              {target_l:.1f} {c.get('l_day', 'ሊትር / ቀን' if is_am else 'L / day')}
            </div>
            <div style="font-size: 12px; color: #64748B;">
              {"በግምት ከ10-12 መካከለኛ ብርጭቆዎች" if is_am else "Approximately 10-12 standard glasses"}
            </div>
          </div>
          <div style="font-size: 44px; color: #0284C7;">
            💧
          </div>
        </div>

        <div class="card" style="margin-bottom: 5mm;">
          <div style="font-family: 'NotoSerifCustom', serif; font-size: 15px; font-weight: 700; color: #0F172A; margin-bottom: 2.5mm;">
            {"የመለኪያ እና የአመጋገብ መመሪያዎች" if is_am else "Measurement Principles"}
          </div>
          <div style="font-size: 12.5px; color: #475569; line-height: 1.5;">
            {escape(c.get("portion_note", "እያንዳንዱ ምግብ ትክክለኛ ግራም እና በኢትዮጵያ የተለመዱ የቤት ውስጥ መለኪያዎችን (የእጅ መዳፍ፣ ሲኒ፣ የተጠቀለለ እንጀራ) አጣምሮ ያሳያል።"))}
            <br><br>
            {"በሚመገቡበት ወቅት የሚከተሉትን ያስተውሉ፡<br>• <strong>የእጅ መዳፍ (የመዳፍ ስፋት):</strong> ለስጋ እና ለዶሮ ፕሮቲን መለኪያ ይጠቅማል።<br>• <strong>ሲኒ / የሻይ ኩባያ (የሲኒ መጠን):</strong> ለበሰለ ሩዝ፣ ምስር እና አጃ መለኪያ ይጠቅማል።<br>• <strong>የተጠቀለለ እንጀራ:</strong> 1 መካከለኛ ጥቅል እንጀራ በግምት 90-100 ግራም ነው።" if is_am else "• <strong>Palm:</strong> Standard measure for meat/poultry portioning.<br>• <strong>Cup:</strong> Standard measure for cooked grains and legumes.<br>• <strong>Rolled Injera:</strong> 1 medium rolled piece represents ~90-100 grams."}
          </div>
        </div>

        <div class="card" style="background: #FFFBEB; border: 1.5px solid #FCD34D; padding: 5mm 6mm;">
          <div style="font-family: 'NotoSerifCustom', serif; font-size: 14px; font-weight: 700; color: #B45309; margin-bottom: 2mm;">
            {"የአሰልጣኝ ህላዌ ሰማ ማጠቃለያ ማሳሰቢያ" if is_am else "Coach Hilawe Final Note"}
          </div>
          <div style="font-size: 12.5px; color: #78350F; line-height: 1.5;">
            {escape(c.get("coach_text", "ለውጥ የሚመጣው ከወጥነት እንጂ ከአንድ ቀን ፍጹምነት አይደለም። መዋቅሩን ይከተሉ፣ አስፈላጊ ሲሆን የተፈቀዱትን አማራጮች ይጠቀሙ፣ እና እድገትዎን በሳምንታት ሂደት ይመዝኑ።"))}
          </div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4mm; padding-top: 3mm; border-top: 1px dashed #FCD34D; font-size: 11px; color: #92400E;">
            <div><strong>{escape(brand_name)}</strong></div>
            <div>{"ይፋዊ የደንበኛ ሰነድ" if is_am else "Official Client Document"}</div>
          </div>
        </div>

        <div style="margin-top: 3mm; padding: 2.5mm 4mm; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; font-size: 9.5px; color: #64748B; line-height: 1.4;">
          <strong>{"የህክምና እና የህግ ማሳሰቢያ፦" if is_am else "Medical & Legal Notice:"}</strong>
          {" ይህ ፕላን ለአጠቃላይ የአካል ብቃት እና የአመጋገብ ግንዛቤ የተዘጋጀ ሲሆን የህክምና ምክርን ወይም የክሊኒካል ህክምናን አይተካም። ማንኛውንም አዲስ የአመጋገብ ፕሮግራም ከመጀመርዎ በፊት ሀኪምዎን ያማክሩ።" if is_am else " This meal plan is prepared for general fitness and nutritional guidance and does not replace professional medical advice. Consult your physician before initiating any new dietary program."}
        </div>
      </div>

      {_render_running_footer(context, page_num, total_pages, is_client)}
    </div>
    """


def build_review_html(plan: dict[str, Any], context: DocumentContext, c: dict[str, str], page_num: int, total_pages: int) -> str:
    is_am = context.normalized_language == "AM"
    values = [
        (c.get("plan_id", "የፕላን መለያ"), context.plan_public_id),
        (c.get("version", "ስሪት"), f"V{context.version_number}"),
        (c.get("status", "ሁኔታ"), context.status),
        (c.get("engine", "ሞተር"), str(plan.get("engine_version") or "-")),
        (c.get("dataset", "መረጃ ቋት"), str(plan.get("dataset_version") or "-")),
    ]
    if context.approved_by:
        values.append((c.get("approved_by", "ያጸደቀው"), context.approved_by))
    if context.approved_at:
        values.append((c.get("approved_at", "የጸደቀበት ቀን"), context.approved_at))

    rows_html = "".join(f"""
      <tr>
        <td style="font-weight: 700; width: 35%; background: #F8FAFC;">{escape(k)}</td>
        <td>{escape(v)}</td>
      </tr>
    """ for k, v in values)

    warnings = review_warning_lines(plan, language=context.normalized_language)
    warnings_html = ""
    if warnings:
        warn_items = "".join(f"<li>{escape(w)}</li>" for w in warnings)
        warnings_html = f"""
        <div style="margin-top: 5mm; background: #FEF2F2; border: 1px solid #FECACA; border-radius: 6px; padding: 4mm 5mm;">
          <div style="font-weight: 700; color: #991B1B; font-size: 12px; margin-bottom: 2mm;">
            {escape(c.get("warning", "የግምገማ ማስታወሻዎች"))}
          </div>
          <ul style="padding-left: 5mm; font-size: 11.5px; color: #7F1D1D; line-height: 1.45;">
            {warn_items}
          </ul>
        </div>
        """

    return f"""
    <div class="page">
      <div>
        {_render_running_header(context, c, False)}
        <div class="kicker">{"ክፍል 06" if is_am else "SECTION 06"}</div>
        <h1 class="page-title">{escape(c.get("review", "የፕላን ግምገማ እና ስሪት"))}</h1>
        <div class="page-intro" style="color: #D97706; font-weight: 700;">
          {escape(c.get("review_required", "ይህ ፕላን ለደንበኛው ከመሰጠቱ በፊት የባለሙያ ግምገማ ያስፈልገዋል።"))}
        </div>

        <div class="card" style="padding: 0; overflow: hidden;">
          <table class="modern-table" style="margin-top: 0;">
            <thead>
              <tr>
                <th colspan="2">{"የስርዓት ዝርዝሮች እና ኦዲት" if is_am else "SYSTEM AUDIT TRAIL"}</th>
              </tr>
            </thead>
            <tbody>
              {rows_html}
            </tbody>
          </table>
        </div>

        {warnings_html}
      </div>

      {_render_running_footer(context, page_num, total_pages, False)}
    </div>
    """


def render_html_document(plan: dict[str, Any], context: DocumentContext, *, is_client_delivery: bool = False) -> str:
    """Compile the complete multi-page document into self-contained HTML5."""
    c = copy_for(context.normalized_language)

    core_days = plan.get("core_week") or []
    fasting_core = plan.get("fasting_core_week") or []
    grocery_data = plan.get("grocery") or []
    fasting_grocery = plan.get("fasting_grocery") or []

    # Calculate exact grocery chunk counts
    grocery_chunks_count = len(balanced_chunks(grocery_data, max_per_page=25)) if grocery_data else 1
    fasting_grocery_chunks_count = len(balanced_chunks(fasting_grocery, max_per_page=25)) if fasting_grocery else 0

    total_pages = 1 + 1 + 1 + 1 + len(core_days)
    if fasting_core:
        total_pages += len(fasting_core)
    total_pages += 1  # Weekly transformation tracking worksheet
    total_pages += grocery_chunks_count
    total_pages += fasting_grocery_chunks_count
    total_pages += 1  # hydration

    current_page = 1
    pages_html = []

    # Page 1: Cover
    pages_html.append(build_cover_html(plan, context, c, is_client_delivery))
    current_page += 1

    # Page 2: Glance
    pages_html.append(build_glance_html(plan, context, c, is_client_delivery, current_page, total_pages))
    current_page += 1

    # Page 3: How to use
    pages_html.append(build_how_to_use_html(context, c, is_client_delivery, current_page, total_pages))
    current_page += 1

    # Page 4: Rotation
    pages_html.append(build_rotation_html(plan, context, c, is_client_delivery, current_page, total_pages))
    current_page += 1

    # Daily meal pages
    for i, day in enumerate(core_days):
        pages_html.append(build_day_html(day, i, context, c, is_client_delivery, current_page, total_pages))
        current_page += 1

    # Fasting core meal pages
    if fasting_core:
        for i, day in enumerate(fasting_core):
            pages_html.append(build_day_html(day, i, context, c, is_client_delivery, current_page, total_pages, is_fasting_core=True))
            current_page += 1

    # Weekly Transformation Tracking Worksheet
    pages_html.append(build_checkin_worksheet_html(plan, context, c, is_client_delivery, current_page, total_pages))
    current_page += 1

    # Grocery pages
    g_pages, current_page = build_grocery_pages(plan, context, c, is_client_delivery, current_page, total_pages, is_fasting=False, max_per_page=25)
    pages_html.extend(g_pages)

    if fasting_grocery:
        fg_pages, current_page = build_grocery_pages(plan, context, c, is_client_delivery, current_page, total_pages, is_fasting=True, max_per_page=25)
        pages_html.extend(fg_pages)

    # Hydration & Rules
    pages_html.append(build_hydration_html(context, c, is_client_delivery, current_page, total_pages))
    current_page += 1

    css = _build_css()
    body_content = "\n".join(pages_html)

    doc_title = "የአሰልጣኝ ህላዌ ሰማ ይፋዊ የግል የአመጋገብ ፕላን" if context.normalized_language == "AM" else f"{context.client_name} - Coach Hilawe Meal Plan"

    return f"""<!DOCTYPE html>
<html lang="{'am' if context.normalized_language == 'AM' else 'en'}">
<head>
  <meta charset="utf-8">
  <title>{escape(doc_title)}</title>
  <style>
{css}
  </style>
</head>
<body>
{body_content}
</body>
</html>
"""


def render_html_pdf(
    plan: dict[str, Any],
    context: DocumentContext,
    output_pdf_path: str | Path,
    *,
    is_client_delivery: bool = False,
    keep_html: bool = True,
) -> Path:
    """Render ultra-modern PDF via Headless Chromium."""
    pdf_path = Path(output_pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    browser = find_chromium_executable()
    if not browser:
        raise RuntimeError("No Chromium-based browser (Chrome or Edge) found on the system.")

    html_content = render_html_document(plan, context, is_client_delivery=is_client_delivery)

    html_path = pdf_path.with_suffix(".html") if keep_html else Path(tempfile.mktemp(suffix=".html"))
    html_path.write_text(html_content, encoding="utf-8")

    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-software-rasterizer",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path.resolve()}",
        str(html_path.resolve()),
    ]

    with _RENDER_SEMAPHORE:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    if res.returncode != 0 or not pdf_path.exists() or pdf_path.stat().st_size == 0:
        err_msg = res.stderr or res.stdout or f"Chromium exited with code {res.returncode}"
        raise RuntimeError(f"Headless Chromium PDF print failed: {err_msg}")

    if not keep_html and html_path.exists():
        try:
            html_path.unlink()
        except OSError:
            pass

    return pdf_path
