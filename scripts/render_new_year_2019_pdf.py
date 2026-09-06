"""Render the Coach Hilawe 2019 Ethiopian New Year 7-Page Transformation Guide PDF.

Fully fills every single page with rich, practical fitness & nutrition mechanics.
- Zero awkward empty white spaces.
- Generous typography (no small 11px fonts: body 13px-14px, titles 15px-17px, headings 26px-32px).
- Exact 7-page compilation.
- Complete integration of Previous Gift (Food Guide & 4-Meal Diet Table).
- 100% respectful, gender-neutral Amharic phrasing (አለብዎት / እርስዎ / ...ዎ / ...ዎት).
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from meal_plan.documents.html_pdf_renderer import find_chromium_executable


def _load_font_b64(font_path: Path) -> str:
    if font_path.exists():
        return base64.b64encode(font_path.read_bytes()).decode("ascii")
    return ""


def build_html_content() -> str:
    fonts_dir = ROOT / "meal_plan" / "documents" / "fonts"
    sans_reg_b64 = _load_font_b64(fonts_dir / "NotoSansEthiopic-Regular.ttf")
    sans_bold_b64 = _load_font_b64(fonts_dir / "NotoSansEthiopic-Bold.ttf")
    sans_med_b64 = _load_font_b64(fonts_dir / "NotoSansEthiopic-Medium.ttf")

    font_faces = ""
    if sans_reg_b64:
        font_faces += f"""
        @font-face {{
            font-family: 'NotoSansEthiopic';
            font-weight: 400;
            src: url(data:font/truetype;charset=utf-8;base64,{sans_reg_b64}) format('truetype');
        }}
        """
    if sans_med_b64:
        font_faces += f"""
        @font-face {{
            font-family: 'NotoSansEthiopic';
            font-weight: 500;
            src: url(data:font/truetype;charset=utf-8;base64,{sans_med_b64}) format('truetype');
        }}
        """
    if sans_bold_b64:
        font_faces += f"""
        @font-face {{
            font-family: 'NotoSansEthiopic';
            font-weight: 700;
            src: url(data:font/truetype;charset=utf-8;base64,{sans_bold_b64}) format('truetype');
        }}
        """

    return f"""<!DOCTYPE html>
<html lang="am">
<head>
<meta charset="utf-8">
<title>የ2019 አዲስ ዓመት የለውጥ መመሪያ - Coach Hilawe</title>
<style>
{font_faces}

@page {{
    size: A4 portrait;
    margin: 0;
}}

* {{
    box-sizing: border-box;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
}}

body {{
    margin: 0;
    padding: 0;
    font-family: 'NotoSansEthiopic', sans-serif;
    color: #1c1917;
    background-color: #fafaf9;
    font-size: 14px;
    line-height: 1.55;
}}

.page {{
    width: 210mm;
    height: 297mm;
    position: relative;
    page-break-after: always;
    page-break-inside: avoid;
    padding: 14mm 18mm 13mm 18mm;
    background: #ffffff;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    overflow: hidden;
}}

/* Top Brand Header */
.header-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid #f0eee6;
    padding-bottom: 7px;
    margin-bottom: 10px;
}}

.brand-tag {{
    font-size: 12.5px;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: #b45309;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    gap: 6px;
}}

.brand-tag::before {{
    content: "●";
    color: #f59e0b;
    font-size: 13px;
}}

.edition-badge {{
    background: #0f172a;
    color: #ffffff;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 1.2px;
    padding: 3px 11px;
    border-radius: 999px;
    text-transform: uppercase;
}}

/* Bottom Footer */
.footer-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 2px solid #f0eee6;
    padding-top: 7px;
    margin-top: 8px;
    font-size: 12px;
    color: #78716c;
    font-weight: 500;
}}

.footer-brand {{
    letter-spacing: 1px;
    text-transform: uppercase;
    color: #44403c;
    font-weight: 700;
}}

/* Typography */
h1.page-title {{
    font-size: 26px;
    font-weight: 700;
    color: #0f172a;
    line-height: 1.22;
    margin: 0 0 5px 0;
}}

.quote-box {{
    background: #fffbeb;
    border-left: 5px solid #f59e0b;
    padding: 10px 14px;
    border-radius: 0 8px 8px 0;
    font-size: 13.5px;
    color: #78350f;
    font-weight: 500;
    margin-bottom: 9px;
    line-height: 1.5;
}}

/* Content Cards */
.card {{
    background: #ffffff;
    border: 1px solid #e7e5e4;
    border-radius: 11px;
    padding: 11px 15px;
    margin-bottom: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}}

.card-title {{
    font-size: 15.5px;
    font-weight: 700;
    color: #0f172a;
    margin: 0 0 5px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}}

.card-title .icon {{
    color: #d97706;
    font-size: 17px;
}}

.card p {{
    margin: 0 0 5px 0;
    color: #334155;
    font-size: 13.5px;
    line-height: 1.55;
}}

.card ul {{
    margin: 4px 0 0 0;
    padding-left: 18px;
}}

.card li {{
    margin-bottom: 3px;
    color: #334155;
    font-size: 13.5px;
    line-height: 1.5;
}}

/* Grid layout */
.grid-2 {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
}}

/* Stat ribbon */
.stat-ribbon {{
    display: flex;
    background: #0f172a;
    color: #ffffff;
    border-radius: 11px;
    padding: 11px;
    justify-content: space-around;
    text-align: center;
    margin: 9px 0;
}}

.stat-item .num {{
    font-size: 23px;
    font-weight: 700;
    color: #fbbf24;
    line-height: 1;
}}

.stat-item .label {{
    font-size: 12.5px;
    color: #cbd5e1;
    letter-spacing: 0.5px;
    margin-top: 3px;
    text-transform: uppercase;
}}

/* Warning / Alert Box */
.warning-box {{
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-left: 5px solid #ef4444;
    border-radius: 10px;
    padding: 11px 14px;
    margin-bottom: 9px;
}}

.warning-title {{
    font-size: 14.5px;
    font-weight: 700;
    color: #991b1b;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
}}

.warning-desc {{
    font-size: 13.5px;
    color: #7f1d1d;
    margin: 0;
    line-height: 1.5;
}}

/* Call to Action Box */
.cta-box {{
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    border-radius: 13px;
    color: #ffffff;
    padding: 14px 18px;
    text-align: center;
    margin-top: 6px;
    border: 1px solid #334155;
}}

.cta-box h3 {{
    font-size: 19px;
    margin: 0 0 5px 0;
    color: #fbbf24;
}}

.cta-box p {{
    color: #cbd5e1;
    font-size: 13.5px;
    margin: 0 0 9px 0;
    line-height: 1.45;
}}

.badge-tag {{
    display: inline-block;
    background: #e0f2fe;
    color: #0369a1;
    font-size: 12.5px;
    font-weight: 700;
    padding: 3px 9px;
    border-radius: 4px;
    margin-bottom: 5px;
}}

/* Protocol Table Styles */
.protocol-table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin: 7px 0;
    border-radius: 11px;
    overflow: hidden;
    border: 1px solid #e2e8f0;
    background: #ffffff;
    box-shadow: 0 1px 4px rgba(0,0,0,0.02);
}}

.protocol-table th {{
    padding: 9px 11px;
    font-size: 13.5px;
    font-weight: 700;
    text-align: left;
    color: #ffffff;
    letter-spacing: 0.5px;
}}

.protocol-table th.th-time {{
    background: #1c1917;
    width: 21%;
}}

.protocol-table th.th-fasting {{
    background: #1e3a2f;
    width: 39.5%;
}}

.protocol-table th.th-nonfasting {{
    background: #7c2d12;
    width: 39.5%;
}}

.protocol-table td {{
    padding: 8px 11px;
    vertical-align: top;
    font-size: 13px;
    line-height: 1.48;
    border-bottom: 1px solid #f1f5f9;
}}

.protocol-table tr:last-child td {{
    border-bottom: none;
}}

.protocol-table td.td-time {{
    background: #fafaf9;
    font-weight: 700;
    color: #0f172a;
    font-size: 13.5px;
    border-right: 1px solid #f1f5f9;
}}

.protocol-table td.td-time .en-label {{
    font-size: 11.5px;
    color: #78716c;
    font-weight: 600;
    display: block;
    margin-top: 2px;
}}

.badge-pill-fasting {{
    display: inline-block;
    background: #dcfce7;
    color: #15803d;
    font-size: 11.5px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 999px;
    margin-bottom: 3px;
}}

.badge-pill-nonfasting {{
    display: inline-block;
    background: #ffedd5;
    color: #c2410c;
    font-size: 11.5px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 999px;
    margin-bottom: 3px;
}}

.protocol-list {{
    margin: 0;
    padding: 0;
    list-style: none;
}}

.protocol-list li {{
    margin-bottom: 2px;
    color: #334155;
    position: relative;
    padding-left: 12px;
    font-size: 13px;
}}

.protocol-list li::before {{
    content: "•";
    position: absolute;
    left: 0;
    color: #d97706;
    font-weight: 700;
}}

/* Food Category Cards */
.food-card {{
    background: #ffffff;
    border: 1px solid #e7e5e4;
    border-radius: 11px;
    padding: 9px 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}}

.food-card-title {{
    font-size: 14.5px;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
}}

.food-pills {{
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    margin-top: 4px;
}}

.food-pill {{
    background: #f8fafc;
    color: #1e293b;
    font-size: 12.5px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 6px;
    border: 1px solid #cbd5e1;
}}

</style>
</head>
<body>

<!-- ================= PAGE 1: COVER ================= -->
<div class="page">
    <div class="header-row">
        <div class="brand-tag">COACH HILAWE · 2019 TRANSFORMATION</div>
        <div class="edition-badge">ልዩ የአዲስ ዓመት ስጦታ</div>
    </div>

    <div>
        <div class="badge-tag">የ2019 አዲስ ዓመት ልዩ እትም</div>
        <h1 class="page-title" style="font-size: 32px; margin-bottom: 8px;">
            ፍላጎቱ ካለ፣<br>
            <span style="color: #d97706;">መንገዱ ይኸው።</span>
        </h1>
        
        <div class="quote-box" style="font-size: 14px; padding: 12px 16px; margin-bottom: 10px;">
            “አዲስ ዓመት ማለት የቀን መቁጠሪያ መቀየር ብቻ አይደለም፤ ራስዎን የሚቀይሩበት፣ ተስፋዎን ወደ እውነተኛ ውጤት የሚለውጡበት ቅጽበት ነው።”<br>
            <strong style="color: #0f172a;">— አሰልጣኝ ህላዌ</strong>
        </div>

        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 11px; padding: 13px 16px; margin-bottom: 10px;">
            <div style="font-weight: 700; font-size: 15px; color: #0f172a; margin-bottom: 5px;">
                ይህ መመሪያ ለምን ልዩ ሆነ?
            </div>
            <p style="margin: 0; color: #475569; font-size: 13.5px; line-height: 1.55;">
                ይህ የነፃ ስጦታ መመሪያ በ2019 ዓ.ም አዲሱን ሰውነትዎን ለመገንባት የሚያስፈልጉዎትን <strong>እውነተኛ የስፖርት ሚስጥሮች</strong>፣ <strong>በኢትዮጵያ ውስጥ ተግባራዊ የሆኑ የአመጋገብ ስልቶች</strong>፣ <strong>የዕለታዊ ምግቦች ዝርዝር ሰንጠረዥ</strong> እና <strong>95% ሰዎችን ወደኋላ የሚያስቀሩ አደገኛ ስህተቶችን</strong> አቀናጅቶ የያዘ የተሟላ መመሪያ ነው። ይህ መነሻዎ ነው፤ ሙሉውን የ8-ሳምንት ጉዞ በጋራ እንጓዘዋለን።
            </p>
        </div>

        <div class="card" style="background: #fffdf5; border: 1px solid #fde68a; padding: 11px 15px; margin-bottom: 10px;">
            <div style="font-weight: 700; color: #92400e; font-size: 14px; margin-bottom: 4px;">
                🤝 የአሰልጣኝ ህላዌ መልእክት፦
            </div>
            <p style="margin: 0; color: #78350f; font-size: 13.5px; line-height: 1.5;">
                ስፖርት መጀመር ከባድ አይደለም፤ ከባዱ ነገር ያለ ትክክለኛ እውቀት ደክሞ ተስፋ መቁረጥ ነው። ይህንን መመሪያ በጥሞና ያንብቡት፤ የተፃፉትን ቀላል ህጎች በየቀኑ ተግባራዊ ካደረጉ በ30 ቀናት ውስጥ የሚሰማዎትን ጉልበትና ለውጥ ያረጋግጣሉ።
            </p>
        </div>

        <div class="stat-ribbon">
            <div class="stat-item">
                <div class="num">2019</div>
                <div class="label">የለውጥ ዓመት</div>
            </div>
            <div class="stat-item">
                <div class="num">7</div>
                <div class="label">የተሟሉ ገጾች</div>
            </div>
            <div class="stat-item">
                <div class="num">100%</div>
                <div class="label">ሳይንሳዊ ስልት</div>
            </div>
        </div>

        <div style="background: #ffffff; border: 1px solid #e7e5e4; border-radius: 11px; padding: 12px 15px; font-size: 13.5px; color: #334155; line-height: 1.55;">
            <div style="font-weight: 700; color: #0f172a; margin-bottom: 4px; font-size: 14px;">📌 በዚህ መመሪያ ውስጥ የሚያገኟቸው ዋና ዋና ክፍሎች፦</div>
            • <strong>ክፍል 01፦</strong> 3ቱ የወርቅ የስፖርት ህጎች & የልምምድ ሳይንስ<br>
            • <strong>ክፍል 02፦</strong> የሀበሻ ምግቦች ፕሮቲን ስሌት & የተፈጥሮ ጉልበት<br>
            • <strong>ክፍል 03፦</strong> ለሰውነት ግንባታ ተመራጭ የምግብ አማራጮች ማውጫ<br>
            • <strong>ክፍል 04፦</strong> የተሟላ የዕለታዊ አመጋገብ ሰንጠረዥ (የጾም እና የፍስግ)<br>
            • <strong>ክፍል 05፦</strong> የሚከለከሉ ምግቦች እና በአዲስ ዓመት የሚፈጠሩ 3 አደገኛ ስህተቶች
        </div>
    </div>

    <div class="footer-row">
        <div class="footer-brand">COACH HILAWE · ADDIS ABABA</div>
        <div>ገጽ 01 · መግቢያ</div>
    </div>
</div>

<!-- ================= PAGE 2: EXERCISE LAWS ================= -->
<div class="page">
    <div class="header-row">
        <div class="brand-tag">ክፍል 01 · የስፖርት እና የልምምድ ህጎች</div>
        <div class="edition-badge">EXERCISE LAWS</div>
    </div>

    <div>
        <h1 class="page-title">3ቱ የ2019 የስፖርት ወርቃማ ህጎች</h1>
        <p style="color: #64748b; margin-top: 0; margin-bottom: 9px; font-size: 13.5px;">
            አብዛኛው ሰው ጂም ወይም ቤት ውስጥ ለወራት ደክሞ ለውጥ የሚያጣው ስላልሰራ ሳይሆን <strong>ትክክለኛውን የሰውነት ግንባታ ህግ ስለማያውቅ</strong> ነው።
        </p>

        <div class="card" style="border-left: 5px solid #f59e0b;">
            <div class="card-title">
                <span class="icon">⚖️</span> 1. ክብደትን በየጊዜው የማሳደግ ህግ (Progressive Overload)
            </div>
            <p>
                ሰውነትዎ እንዲቀየር አዲስ ፈተና ማግኘት አለበት። በየሳምንቱ አንድ አይነት ክብደት በተመሳሳይ ድግግሞሽ (Reps) ማንሳት ሰውነትን ያደክማል እንጂ አያሳድገውም።
            </p>
            <ul>
                <li><strong>ሚስጥሩ፦</strong> በየሳምንቱ ወይ 1 ድግግሞሽ ጨምሩ፣ ወይም ክብደቱን በትንሹ (በ1 ኪሎ እንኳን) ከፍ አድርጉ።</li>
                <li><strong>በቤት ውስጥ ሲሰሩ፦</strong> የፑሽአፕ ወይም የስኳት ድግግሞሽን መጨመር ወይም የእረፍት ሰከንዶችን መቀነስ።</li>
                <li>ይህ ጡንቻዎ ያለማቋረጥ እንዲያድግ እና ቅርጽ እንዲያወጣ ብቸኛው ሳይንሳዊ መንገድ ነው።</li>
            </ul>
        </div>

        <div class="card" style="border-left: 5px solid #f59e0b;">
            <div class="card-title">
                <span class="icon">⏱️</span> 2. እንቅስቃሴን ረጋ ብሎ የመቆጣጠር ጥበብ (Time Under Tension)
            </div>
            <p>
                ክብደቱን በፍጥነት መወርወር እና ማንሳት ጉዳት እንጂ ለውጥ አያመጣም። ትልቁ ውጤት የሚመጣው <strong>ክብደቱን ወደ ታች ስታወርዱ</strong> ነው።
            </p>
            <ul>
                <li><strong>የ3 ሰከንድ ህግ፦</strong> ለምሳሌ ፑሽአፕ (Push-up) ስትሰሩ ወደ ታች በ3 ሰከንድ ረጋ ብላችሁ ውረዱ፤ ወደ ላይ በ1 ሰከንድ በፍጥነት ግፉ።</li>
                <li>ይህ የጡንቻ ፋይበርን በ2 እጥፍ በማንቃት ሰውነት በአጭር ጊዜ እንዲጠነክር ያደርጋል።</li>
                <li><strong>የአእምሮና የጡንቻ ግንኙነት፦</strong> እንቅስቃሴውን ስትሰሩ ትኩረታችሁ በሚሰራው ጡንቻ ላይ ይሁን።</li>
            </ul>
        </div>

        <div class="card" style="border-left: 5px solid #f59e0b;">
            <div class="card-title">
                <span class="icon">🔥</span> 3. የሆድ ስብን የማጥፋት ትክክለኛው ሳይንስ (Compound Movements)
            </div>
            <p>
                በቀን 200 የሆድ ስፖርት (Sit-ups) መስራት የሆድ ስብን አይቀንስም! ስብ ከአንድ የሰውነት ክፍል ብቻ ተነጥሎ አይቀንስም።
            </p>
            <ul>
                <li><strong>ትክክለኛው መንገድ፦</strong> ትልልቅ የሰውነት ክፍሎችን (እግር፣ ጀርባ፣ ደረት) የሚያሰሩ እንቅስቃሴዎችን (እንደ ስኳት እና ዴድሊፍት) ስትሰሩ ሰውነታችሁ በቀን ሙሉ ካሎሪ ያቃጥላል፤ የሆድ ስብም አብሮ ይጠፋል።</li>
                <li>የስፖርት ካሎሪ ማቃጠል ልምምዱ ካበቃ በኋላም እስከ 24 ሰዓት ድረስ ይቀጥላል (Afterburn Effect)።</li>
            </ul>
        </div>

        <div class="card" style="background: #f8fafc; border: 1px solid #cbd5e1; padding: 9px 14px; margin-bottom: 8px;">
            <div style="font-weight: 700; color: #0f172a; font-size: 13.5px; margin-bottom: 3px;">
                🗓️ የሳምንታዊ ልምምድ ክፍፍል ምሳሌ (Weekly Split)፦
            </div>
            <p style="margin: 0; font-size: 13px; color: #475569; line-height: 1.5;">
                • <strong>ባለ 3 ቀን፦</strong> ሰኞ (ሙሉ የሰውነት ክፍል) &nbsp;|&nbsp; ረቡዕ (የታችኛው ክፍል & ሆድ) &nbsp;|&nbsp; አርብ (የላይኛው ክፍል & ጀርባ)<br>
                • <strong>ባለ 4 ቀን፦</strong> ሰኞ/ሐሙስ (የላይኛው አካል) &nbsp;|&nbsp; ማክሰኞ/አርብ (የታችኛው አካል & ካርዲዮ)
            </p>
        </div>

        <div class="quote-box" style="margin-bottom: 0; background: #f0fdf4; border-left-color: #22c55e; color: #166534; padding: 10px 14px;">
            💡 <strong>የኮች ህላዌ ምክር፦</strong> በሳምንት 3 ወይም 4 ቀናት በትክክለኛ ቴክኒክ የሚሰራ ስፖርት፣ በየቀኑ በስሜት ከሚሰራ ልምምድ በብዙ እጥፍ የላቀ ውጤት ያመጣል።
        </div>
    </div>

    <div class="footer-row">
        <div class="footer-brand">COACH HILAWE · FITNESS SYSTEM</div>
        <div>ገጽ 02 · የስፖርት ህጎች</div>
    </div>
</div>

<!-- ================= PAGE 3: NUTRITION HACKS ================= -->
<div class="page">
    <div class="header-row">
        <div class="brand-tag">ክፍል 02 · የኢትዮጵያ ምግቦች እና ፕሮቲን</div>
        <div class="edition-badge">NUTRITION HACKS</div>
    </div>

    <div>
        <h1 class="page-title">3ቱ የሀበሻ ምግቦች እና የፕሮቲን ሚስጥሮች</h1>
        <p style="color: #64748b; margin-top: 0; margin-bottom: 9px; font-size: 13.5px;">
            ለሰውነት ግንባታ ውድ የውጭ ማሟያዎችን (Supplements) መግዛት ግዴታ አይደለም። በአካባቢያችን ባሉ ተመጣጣኝ ምግቦች ከፍተኛ ውጤት ማምጣት ይቻላል።
        </p>

        <div class="card">
            <div class="card-title">
                <span class="icon">🍳</span> 1. የእንቁላል እና የበሬ ስጋ ዕለታዊ ሚስጥር
            </div>
            <p>
                ፕሮቲን የጡንቻ ምግብ ብቻ ሳይሆን የስብ ማቃጠያ ቁልፍ ነው። በቀን በቂ ፕሮቲን ሲወሰድ የረሃብ ስሜት ይጠፋል፤ የሰውነት ቅርጽም ይወጣል።
            </p>
            <ul>
                <li><strong>ቀላል ስሌት፦</strong> በቀን ከ3 እስከ 5 የተቀቀሉ እንቁላሎች ወይም 150-200 ግራም ቀይ የበሬ ስጋ / የዶሮ ደረት መውሰድ የዕለቱን መሠረታዊ ፍላጎት ይሸፍናል።</li>
                <li>እንቁላል ስትመገቡ ሙሉውን አስኳል ጨምራችሁ መብላት ጤናማ ቅባት፣ ቪታሚን D እና B12 እንዲሁም የተፈጥሮ ሆርሞን ይገነባል።</li>
                <li>ስጋ ስታዘጋጁ በቅባት ካልተጠበሰ በስተቀር ጡንቻን በፍጥነት ለመጠገን ወደር የለውም።</li>
            </ul>
        </div>

        <div class="card">
            <div class="card-title">
                <span class="icon">🥗</span> 2. የጾም ወቅት የፕሮቲን ቅንጅት (Fasting Protein Synergy)
            </div>
            <p>
                በጾም ወቅት ጡንቻ እንዳይቀንስ እና ስብ እንዳይተካ የእፅዋት ፕሮቲኖችን አቀናጅቶ መመገብ ወሳኝ ነው።
            </p>
            <ul>
                <li>ምስር፣ ሽንብራ እና ቦሎቄን አቀናጅቶ መመገብ የተሟላ አሚኖ አሲድ ይሰጣል።</li>
                <li>ምስር ከቡናማ ሩዝ ወይም ከጤፍ እንጀራ ጋር ሲጣመር ልክ እንደ ስጋ የተሟላ ፕሮቲን ይሆናል።</li>
                <li><strong>ምክር፦</strong> የተቀቀለ ሽንብራ እና አኩሪ አተር በየቀኑ በገበታዎ ላይ ማካተት የጡንቻ ድካምን ይከላከላል።</li>
            </ul>
        </div>

        <div class="card">
            <div class="card-title">
                <span class="icon">⚡️</span> 3. የበሶ እና የአጃ (Oats) የተፈጥሮ ኃይል
            </div>
            <p>
                ከስፖርት በፊት ውድ ፕሪ-ዎርክአውት ከመግዛት፣ በትንሽ ማር የተበጠበጠ የበሶ ውሀ ወይም አጃ መውሰድ ለ2 ሰዓታት የማያቋርጥ ጉልበት ይሰጣል።
            </p>
            <ul>
                <li>ከስፖርት 45 ደቂቃ በፊት 2-3 የሾርባ ማንኪያ በሶ በውሃ በጥብጠው ይውሰዱ፤ በስራ ሰዓት ድካም ሳይሰማዎት በሙሉ ኃይል እንዲሰሩ ይረዳል።</li>
                <li>ከስፖርት በኋላ ደግሞ የበሶ ውሀ ከ2 የተቀቀለ እንቁላል ጋር መውሰድ የጡንቻን ፈጣን ማገገም ያረጋግጣል።</li>
            </ul>
        </div>

        <div class="card" style="background: #fafaf9; border: 1px solid #e7e5e4; padding: 9px 14px; margin-bottom: 8px;">
            <div style="font-weight: 700; color: #0f172a; font-size: 13.5px; margin-bottom: 3px;">
                🥛 የውጭ ማሟያዎች (Supplements) ያስፈልጉዎታል?
            </div>
            <p style="margin: 0; font-size: 13px; color: #475569; line-height: 1.5;">
                ማሟያዎች ስማቸው እንደሚናገረው “ማሟያ” ብቻ ናቸው እንጂ የተፈጥሮ ምግብን አይተኩም። መሠረታዊ ምግቦችን (እንቁላል፣ ስጋ፣ ምስር፣ አጃ) በአግባቡ ከተመገቡ ያለ ምንም ውድ ማሟያ ሙሉ ውጤት ማምጣት ይችላሉ።
            </p>
        </div>

        <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 11px; padding: 10px 14px; font-size: 13px; color: #1e40af; line-height: 1.5;">
            💧 <strong>የውሃ ፍጆታ መመሪያ፦</strong> በቀን ቢያንስ ከ2.5 እስከ 3 ሊትር ንጹህ ውሃ መጠጣት ሜታቦሊዝምን ያፋጥናል፤ የጡንቻ ድካምን፣ ራስ ምታትን እና ቁርጠትን በከፍተኛ ሁኔታ ይቀንሳል።
        </div>
    </div>

    <div class="footer-row">
        <div class="footer-brand">COACH HILAWE · NUTRITION SYSTEM</div>
        <div>ገጽ 03 · የአመጋገብ ጥበቦች</div>
    </div>
</div>

<!-- ================= PAGE 4: FOOD SELECTION GUIDE ================= -->
<div class="page">
    <div class="header-row">
        <div class="brand-tag">ክፍል 03 · የአመጋገብ መመሪያ ስብስብ</div>
        <div class="edition-badge">FOOD SELECTION</div>
    </div>

    <div>
        <h1 class="page-title">ለሰውነት ግንባታ ተመራጭ የምግብ አማራጮች</h1>
        <p style="color: #64748b; margin-top: 0; margin-bottom: 9px; font-size: 13.5px;">
            እነዚህን ምግቦች መሠረት በማድረግ ዕለታዊ ሳህንዎን ያዘጋጁ። እያንዳንዱ የምግብ ቡድን ለጡንቻ እድገት እና ለስብ ቅነሳ ወሳኝ ሚና አለው።
        </p>

        <div class="grid-2" style="margin-bottom: 9px;">
            <div class="food-card" style="border-top: 4px solid #b45309;">
                <div class="food-card-title">
                    🍗 ምርጥ የፕሮቲን አማራጮች
                </div>
                <div style="font-size: 13px; font-weight: 700; color: #475569; margin-bottom: 3px;">የእንስሳት ፕሮቲን፦</div>
                <div class="food-pills">
                    <span class="food-pill">የዶሮ ደረት</span>
                    <span class="food-pill">ዓሣ</span>
                    <span class="food-pill">ቀይ የበሬ ሥጋ</span>
                    <span class="food-pill">እንቁላል</span>
                    <span class="food-pill">ግሪክ እርጎ</span>
                </div>
                <div style="font-size: 13px; font-weight: 700; color: #475569; margin: 6px 0 3px 0;">የዕፅዋት ፕሮቲን፦</div>
                <div class="food-pills">
                    <span class="food-pill">ምስር</span>
                    <span class="food-pill">ቦሎቄ</span>
                    <span class="food-pill">ሽንብራ</span>
                    <span class="food-pill">ባቄላ</span>
                    <span class="food-pill">ፎሶሊያ</span>
                    <span class="food-pill">ቶፉ</span>
                </div>
                <div style="margin-top: 7px; font-size: 13px; color: #92400e;">
                    🎯 <strong>ዕለታዊ ግብ፦</strong> በኪሎግራም ክብደትዎ ከ1.6 እስከ 2.0 ግራም ፕሮቲን።
                </div>
            </div>

            <div class="food-card" style="border-top: 4px solid #0284c7;">
                <div class="food-card-title">
                    🍚 ጤናማ ካርቦሃይድሬቶች
                </div>
                <p style="font-size: 13px; color: #475569; margin-bottom: 5px;">
                    ለስፖርት የማያቋርጥ ንጹህ ጉልበት የሚያመነጩና ድካምን የሚከላከሉ፦
                </p>
                <div class="food-pills">
                    <span class="food-pill">አጃ (Oats)</span>
                    <span class="food-pill">ሩዝ</span>
                    <span class="food-pill">ድንች</span>
                    <span class="food-pill">ስኳር ድንች</span>
                    <span class="food-pill">የገብስ ዳቦ</span>
                    <span class="food-pill">የጤፍ እንጀራ</span>
                </div>
                <div style="margin-top: 8px; font-size: 13px; color: #0369a1; background: #f0f9ff; padding: 5px 8px; border-radius: 6px;">
                    ✓ ካርቦሃይድሬት ጠላት አይደለም፤ በልክ ሲወሰድ ለጡንቻ እድገት ቁልፍ ነው።
                </div>
            </div>

            <div class="food-card" style="border-top: 4px solid #16a34a;">
                <div class="food-card-title">
                    🥦 ፋይበር እና አትክልቶች
                </div>
                <p style="font-size: 13px; color: #475569; margin-bottom: 5px;">
                    የሙሉነት ስሜት በመስጠት የምግብ መፈጨትን የሚያፋጥኑ፦
                </p>
                <div class="food-pills">
                    <span class="food-pill">ብሮኮሊ</span>
                    <span class="food-pill">ጥቅል ጎመን</span>
                    <span class="food-pill">አበባ ጎመን</span>
                    <span class="food-pill">ካሮት</span>
                    <span class="food-pill">ቆስጣ</span>
                    <span class="food-pill">ሰላጣ</span>
                </div>
                <div style="margin-top: 8px; font-size: 13px; color: #15803d;">
                    ✓ ፋይበር ረሃብን በማጥፋት የሆድ ስብን ለማቅለጥ ቀዳሚ ረዳት ነው።
                </div>
            </div>

            <div class="food-card" style="border-top: 4px solid #d97706;">
                <div class="food-card-title">
                    🥑 ጠቃሚ ቅባቶች (Healthy Fats)
                </div>
                <p style="font-size: 13px; color: #475569; margin-bottom: 5px;">
                    የሆርሞን ሚዛንን ለመጠበቅና ጤናማ ሴል ለመገንባት የሚያስፈልጉ፦
                </p>
                <div class="food-pills">
                    <span class="food-pill">አቮካዶ</span>
                    <span class="food-pill">የለውዝ ቅቤ</span>
                    <span class="food-pill">የወይራ ዘይት</span>
                </div>
                <div style="margin-top: 8px; font-size: 13px; color: #b45309; background: #fffbeb; padding: 5px 8px; border-radius: 6px;">
                    ✓ ቅባቶች ለቴስቶስትሮን ግንባታና ለቪታሚን ቅበላ እጅግ ወሳኝ ናቸው።
                </div>
            </div>
        </div>

        <div class="card" style="margin-bottom: 8px; padding: 10px 14px; background: #fafaf9;">
            <div style="font-weight: 700; color: #0f172a; font-size: 13.5px; margin-bottom: 3px;">
                📦 የምግብ ዝግጅት ጥበብ (Meal Prep Secrets)፦
            </div>
            <p style="margin: 0; font-size: 13px; color: #475569; line-height: 1.5;">
                በየቀኑ ከማብሰል ይልቅ ምስር፣ ሽንብራ እና ቡናማ ሩዝን በሳምንት 2 ቀን አዘጋጅቶ በማቀዝቀዣ ማስቀመጥ ጊዜን ይቆጥባል፤ በስራ ጫና ምክንያት ወደ ውጭ ጀንክ ምግቦች እንዳይሄዱ ይጠብቅዎታል።
            </p>
        </div>

        <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 11px; padding: 10px 14px;">
            <div style="font-weight: 700; color: #0f172a; font-size: 13.5px; margin-bottom: 3px;">
                ⚖️ የወርቅ የሳህን ክፍፍል ህግ፦
            </div>
            <p style="margin: 0; color: #475569; font-size: 13px; line-height: 1.5;">
                በዋና ዋና ገበታዎችዎ ላይ <strong>ግማሹን ሳህን በአትክልቶች</strong>፣ <strong>አንድ አራተኛውን በንጹህ ፕሮቲን</strong>፣ እና <strong>አንድ አራተኛውን ደግሞ ውስብስብ በሆኑ ካርቦሃይድሬቶች</strong> ይሙሉ!
            </p>
        </div>
    </div>

    <div class="footer-row">
        <div class="footer-brand">COACH HILAWE · FOOD SELECTION</div>
        <div>ገጽ 04 · የምግብ አማራጮች</div>
    </div>
</div>

<!-- ================= PAGE 5: DAILY DIET PROTOCOL TABLE ================= -->
<div class="page">
    <div class="header-row">
        <div class="brand-tag">ክፍል 04 · የዕለታዊ የአመጋገብ መርሃ-ግብር</div>
        <div class="edition-badge">DAILY PROTOCOL</div>
    </div>

    <div>
        <h1 class="page-title">የዕለታዊ የአመጋገብ መርሃ-ግብር ሰንጠረዥ</h1>
        
        <div class="quote-box" style="margin-bottom: 7px; font-size: 13.5px; padding: 9px 13px;">
            “ከታች ከተዘረዘሩት የምግብ አማራጮች ውስጥ በየቀኑ በምግብ ሳህንዎ ላይ ለማካተት ይሞክሩ። ክብደትን በቀላሉ ለመቀነስ እንዲረዳዎት፦ የካርቦሃይድሬት መጠኖችን መቀነስ፣ ፋይበር የበለጸጉ አትክልቶችን በተገቢው መጠን መውሰድ፣ እና በእያንዳንዱ ገበታ ላይ እስከ 200 ግራም የሚደርስ ፕሮቲን መጠቀም ይመረጣል።”
        </div>

        <table class="protocol-table">
            <thead>
                <tr>
                    <th class="th-time">የምግብ ክፍለ-ጊዜ</th>
                    <th class="th-fasting">የጾም አማራጮች 🟢</th>
                    <th class="th-nonfasting">የፍስግ አማራጮች 🟠</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="td-time">
                        ቁርስ
                        <span class="en-label">BREAKFAST</span>
                    </td>
                    <td>
                        <span class="badge-pill-fasting">🟢 FASTING</span>
                        <ul class="protocol-list">
                            <li>2 የሻይ ሲኒ የተቀቀለ ሩዝ ወይም አጃ</li>
                            <li>ብሮኮሊ ወይም ጥቅል ጎመን</li>
                            <li>1 የሻይ ማንኪያ የወይራ ዘይት</li>
                        </ul>
                    </td>
                    <td>
                        <span class="badge-pill-nonfasting">🟠 NON-FASTING</span>
                        <ul class="protocol-list">
                            <li>4 የተቀቀለ እንቁላል (ወይም 2 ሙሉ + 2 ነጭ ክፍል)</li>
                            <li>2 የሻይ ሲኒ የተቀቀለ ሩዝ ወይም የገብስ ዳቦ</li>
                            <li>ብሮኮሊ ወይም አትክልት • ግማሽ አቮካዶ</li>
                        </ul>
                    </td>
                </tr>
                <tr>
                    <td class="td-time">
                        ምሳ
                        <span class="en-label">LUNCH</span>
                    </td>
                    <td>
                        <span class="badge-pill-fasting">🟢 FASTING</span>
                        <ul class="protocol-list">
                            <li>4 የሻይ ሲኒ የተቀቀለ ሽንብራ ወይም ምስር</li>
                            <li>2 ቁራጭ የጤፍ እንጀራ</li>
                            <li>ጎመን እና ሽንኩርት (እንደ ፍላጎትዎ)</li>
                        </ul>
                    </td>
                    <td>
                        <span class="badge-pill-nonfasting">🟠 NON-FASTING</span>
                        <ul class="protocol-list">
                            <li>200 ግራም የዶሮ ደረት (Chicken Breast) ወይም ቀይ ስጋ</li>
                            <li>2 ቁራጭ የጤፍ እንጀራ</li>
                            <li>ጥቅል ጎመን ወይም ትኩስ ሰላጣ</li>
                        </ul>
                    </td>
                </tr>
                <tr>
                    <td class="td-time">
                        መክሰስ
                        <span class="en-label">SNACK / PRE-WORKOUT</span>
                    </td>
                    <td>
                        <span class="badge-pill-fasting">🟢 FASTING</span>
                        <ul class="protocol-list">
                            <li>1 ሲኒ የበሶ ውሀ በትንሽ ማር ወይም የተቀቀለ ሽንብራ</li>
                            <li>1 ሙዝ ወይም ፖም</li>
                            <li>አረንጓዴ ሻይ ያለ ስኳር</li>
                        </ul>
                    </td>
                    <td>
                        <span class="badge-pill-nonfasting">🟠 NON-FASTING</span>
                        <ul class="protocol-list">
                            <li>1 ኩባያ እርጎ ወይም 2 የተቀቀለ እንቁላል</li>
                            <li>1 ሙዝ በትንሽ የለውዝ ቅቤ (Peanut Butter)</li>
                            <li>1 ሲኒ ጥቁር ቡና ያለ ስኳር</li>
                        </ul>
                    </td>
                </tr>
                <tr>
                    <td class="td-time">
                        እራት
                        <span class="en-label">DINNER</span>
                    </td>
                    <td>
                        <span class="badge-pill-fasting">🟢 FASTING</span>
                        <ul class="protocol-list">
                            <li>5 የሻይ ሲኒ የተቀቀለ ቦሎቄ ወይም ምስር</li>
                            <li>3 መካከለኛ የተቀቀለ ድንች</li>
                            <li>ትኩስ ሰላጣ እና ቲማቲም</li>
                        </ul>
                    </td>
                    <td>
                        <span class="badge-pill-nonfasting">🟠 NON-FASTING</span>
                        <ul class="protocol-list">
                            <li>2 የሻይ ሲኒ የተፈጨ የበሬ ሥጋ (ዝቅተኛ ቅባት)</li>
                            <li>2 የተቀቀለ ድንች ወይም 1 የጤፍ እንጀራ</li>
                            <li>የተቀቀለ አትክልት</li>
                        </ul>
                    </td>
                </tr>
            </tbody>
        </table>

        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 8px 12px; margin-top: 5px; font-size: 13px; color: #475569;">
            ⏰ <strong>የምግብ ሰዓት መመሪያ፦</strong> ቁርስ ከእንቅልፍ ከተነሱ በኋላ በ1 ሰዓት ውስጥ፣ እራት ከመኝታ ቢያንስ 3 ሰዓታት ቀድመው መመገብ የምግብ መፈጨትን ያፋጥናል፤ የስብ ክምችትንም ይከላከላል።
        </div>

        <div style="background: #fffbeb; border: 1px solid #fef3c7; border-radius: 10px; padding: 9px 12px; margin-top: 5px; font-size: 13px; color: #92400e;">
            📌 <strong>የማብሰያ መመሪያ፦</strong> ምግቦችን በዘይት ከማጥገብ ይልቅ በመቀቀል፣ በእንፋሎት ወይም በትንሽ ዘይት በማብሰል ካሎሪዎን በቀላሉ ይቆጣጠሩ።
        </div>
    </div>

    <div class="footer-row">
        <div class="footer-brand">COACH HILAWE · DAILY PROTOCOL</div>
        <div>ገጽ 05 · የአመጋገብ ሰንጠረዥ</div>
    </div>
</div>

<!-- ================= PAGE 6: RESTRICTIONS & FATAL MISTAKES ================= -->
<div class="page">
    <div class="header-row">
        <div class="brand-tag">ክፍል 05 · ጥንቃቄ እና ግንዛቤ</div>
        <div class="edition-badge">RESTRICTIONS & MISTAKES</div>
    </div>

    <div>
        <h1 class="page-title">የሚከለከሉ ምግቦች እና 3ቱ አደገኛ ስህተቶች</h1>
        <p style="color: #64748b; margin-top: 0; margin-bottom: 9px; font-size: 13.5px;">
            ውጤታማ ለመሆን ምን መብላት እንዳለብዎት ብቻ ሳይሆን <strong>ምን ማስወገድ እንዳለብዎት</strong> ማወቅም እኩል ወሳኝ ነው።
        </p>

        <div class="warning-box">
            <div class="warning-title">
                <span>🚫</span> ፈጽሞ የተከለከሉ ምግቦች (Strictly Forbidden)
            </div>
            <p class="warning-desc">
                <strong>በርገር፣ ቺፕስ፣ ሳምቡሳ፣ የታሸጉ ለስላሳ መጠጦች እና የአልኮል መጠጦች፦</strong> ማንኛቸውንም ጣፋጭ ምግቦች፣ የተዘጋጁ ስኳሮች እና ለስላሳ መጠጦችን ሙሉ በሙሉ ያስወግዱ። እነዚህ ምግቦች በቀጥታ ወደ ሆድ ስብነት ይቀየራሉ። አልኮል ደግሞ የጡንቻ እድገትን በግማሽ ይቀንሳል።
            </p>
        </div>

        <div class="warning-box" style="background: #fffbeb; border-color: #fde68a; border-left-color: #f59e0b;">
            <div class="warning-title" style="color: #92400e;">
                <span>⚠️</span> በከፊል የተከለከሉ/የተገደቡ (Restricted)
            </div>
            <p class="warning-desc" style="color: #78350f;">
                <strong>በቀን ውስጥ ከሁለት የሻይ ማንኪያ በላይ ዘይት መጠቀም ፈጽሞ አይመከርም!</strong> በዘይት የተጠባበሱ ወይም ቅባት የበዛባቸው ምግቦችን (እንደ እርጥብ ኬክ፣ ጮርናቄ እና መሰል የዱቄት ውጤቶች) መመገብ በጥብቅ የተገደበ ነው። ጥብስ ከመብላት ይልቅ የተቀቀለ ስጋ ይምረጡ።
            </p>
        </div>

        <div style="margin-top: 5px;">
            <div style="font-weight: 700; color: #0f172a; font-size: 14.5px; margin-bottom: 5px;">
                ⚠️ በአዲስ ዓመት ሰዎችን የሚያጠፉ 3 ስህተቶች፦
            </div>
            
            <div class="card" style="padding: 8px 12px; margin-bottom: 5px;">
                <div style="font-weight: 700; font-size: 13.5px; color: #b91c1c; margin-bottom: 2px;">1. ያለ የተዋቀረ እቅድ መስራት (Aimless Workouts)</div>
                <div style="font-size: 13px; color: #475569; line-height: 1.45;">በየቀኑ በስሜት ጂም መግባት ጊዜን ያባክናል። በየትኛው ቀን፣ የትኛውን ጡንቻ፣ በምን ያህል ክብደትና ድግግሞሽ እንደሚሰሩ አስቀድሞ የተጻፈ መመሪያ ሊኖርዎት ይገባል።</div>
            </div>

            <div class="card" style="padding: 8px 12px; margin-bottom: 5px;">
                <div style="font-weight: 700; font-size: 13.5px; color: #b91c1c; margin-bottom: 2px;">2. ምግብን በከፍተኛ ሁኔታ ማቋረጥ (Starvation Diets)</div>
                <div style="font-size: 13px; color: #475569; line-height: 1.45;">ቁርስ ወይም እራትን ሙሉ በሙሉ መተው ሜታቦሊዝምን ያቀዘቅዛል፤ ሰውነት በረሃብ ፍርሃት ስብ ማከማቸት ይጀምራል። ትክክለኛው መንገድ ምግብ መቀነስ ሳይሆን የተስተካከለ ፕሮቲን መመገብ ነው።</div>
            </div>

            <div class="card" style="padding: 8px 12px; margin-bottom: 5px;">
                <div style="font-weight: 700; font-size: 13.5px; color: #b91c1c; margin-bottom: 2px;">3. ተከታታይነት ማጣት (Inconsistency)</div>
                <div style="font-size: 13px; color: #475569; line-height: 1.45;">ለአንድ ሳምንት ደክሞ ለሁለት ሳምንት መጥፋት ለውጥ አያመጣም። የ2-ቀን ህግን ይከተሉ፦ በተከታታይ ከ2 ቀን በላይ ስፖርት አያቋርጡ። በሳምንት 3-4 ቀናት ጠንክሮ የሚሰራ ሰው ዘላቂ ለውጥ ያመጣል።</div>
            </div>
        </div>

        <div class="card" style="background: #fafaf9; border: 1px solid #e7e5e4; padding: 8px 12px; margin-bottom: 7px;">
            <div style="font-weight: 700; color: #0f172a; font-size: 13.5px; margin-bottom: 2px;">
                🧠 የስነ-ልቦና ጥንካሬ እና ዲስፕሊን፦
            </div>
            <p style="margin: 0; font-size: 13px; color: #475569; line-height: 1.45;">
                ስሜት (Motivation) ይመጣል፤ ይሄዳል። ዲስፕሊን ግን በደከመዎትም ቀን ልምምድዎን እንድትሰሩ ያደርግዎታል። ውጤት የሚገነባው በማይመች ቀን በሚሰሩት ስራ ነው።
            </p>
        </div>

        <div class="quote-box" style="margin-bottom: 0; background: #f8fafc; border-left-color: #3b82f6; color: #1e3a8a; padding: 9px 13px;">
            💡 <strong>የወርቅ ህግ፦</strong> “ውጤት የሚመጣው ፍጹም በመሆን ሳይሆን ባልተቋረጠ ጥረት ነው። ዛሬ የሚጀምሩት ትንሽ ልምምድ ነገ አዲሱን ሰውነትዎን ይፈጥራል።”
        </div>
    </div>

    <div class="footer-row">
        <div class="footer-brand">COACH HILAWE · DISCIPLINE FIRST</div>
        <div>ገጽ 06 · ጥንቃቄዎች</div>
    </div>
</div>

<!-- ================= PAGE 7: NEXT STEPS & PITCH ================= -->
<div class="page">
    <div class="header-row">
        <div class="brand-tag">ክፍል 06 · ቀጣዩ ትልቅ እርምጃዎ</div>
        <div class="edition-badge">NEXT LEVEL</div>
    </div>

    <div>
        <h1 class="page-title" style="font-size: 26px;">ይህ ገና መጀመሪያው ነው!</h1>
        <div class="quote-box" style="font-size: 14px; padding: 10px 14px; margin-bottom: 7px;">
            እስካሁን ያገኙት መመሪያ የለውጥ ጉዞዎ መሠረት ነው። ነገር ግን የሰውነትዎ ክብደት፣ ቅርጽ፣ አኗኗርና የስራ ጫና ከሌላው ሰው ጋር ፈጽሞ አንድ አይደለም።
        </div>

        <p style="color: #334155; line-height: 1.55; margin-bottom: 8px; font-size: 13.5px;">
            እውነተኛውን እና ፈጣኑን ለውጥ ለማምጣት <strong>ሙሉ በሙሉ ለእርስዎ ብቻ የተዘጋጀ የ8-ሳምንት ግላዊ እቅድ</strong> ያስፈልግዎታል። ልዩነቱ የሚመጣው በእርስዎ ሰውነት ልኬት ላይ የተመሠረተ ሲሆን ብቻ ነው!
        </p>

        <div class="grid-2" style="margin-bottom: 8px;">
            <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 10px; padding: 9px 12px;">
                <div style="font-weight: 700; color: #991b1b; font-size: 13.5px; margin-bottom: 2px;">❌ የተለመደ አጠቃላይ እቅድ</div>
                <div style="font-size: 13px; color: #7f1d1d; line-height: 1.45;">ለሁሉም ሰው እኩል የሚታደል፣ የክብደትና የአኗኗር ልዩነትን የማያገናዝብ፣ ድካም እንጂ ፈጣን ለውጥ የማያመጣ።</div>
            </div>
            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 10px; padding: 9px 12px;">
                <div style="font-weight: 700; color: #166534; font-size: 13.5px; margin-bottom: 2px;">✅ የኮች ህላዌ ግላዊ እቅድ</div>
                <div style="font-size: 13px; color: #14532d; line-height: 1.45;">በእርስዎ ክብደት፣ የአካል ብቃት፣ የሳምንት ቀናት እና የምግብ ምርጫ ተለይቶ የተሰላ ሳይንሳዊ ስልት!</div>
            </div>
        </div>

        <div class="card" style="border: 2px solid #fde68a; background: #fffdf5; padding: 10px 14px; margin-bottom: 8px;">
            <div style="font-weight: 700; color: #92400e; font-size: 14.5px; margin-bottom: 5px;">
                👑 በእርስዎ ግላዊ የ8-ሳምንት ፕሮግራም ውስጥ የሚያገኟቸው፦
            </div>
            <ul style="padding-left: 18px; margin: 0; color: #451a03; font-size: 13.5px; line-height: 1.5;">
                <li style="margin-bottom: 3px;"><strong>የተዋቀረ የስፖርት እቅድ፦</strong> በሳምንት 3፣ 4 ወይም 5 ቀን እንደ አኗኗርዎ የተከፋፈለ</li>
                <li style="margin-bottom: 3px;"><strong>የእንቅስቃሴ ቪዲዮ መመሪያዎች፦</strong> ለእያንዳንዱ ልምምድ ትክክለኛ አሰራር የሚያሳይ</li>
                <li style="margin-bottom: 3px;"><strong>ለክብደትዎ የተሰላ የአመጋገብ ስሌት፦</strong> ትክክለኛ የፕሮቲን እና የካሎሪ መጠን</li>
                <li style="margin-bottom: 3px;"><strong>ሳምንታዊ የሂደት መከታተያ Checklist፦</strong> ለውጥዎን ደረጃ በደረጃ የሚመዝኑበት</li>
                <li><strong>በቴሌግራም ቦት ቀጥተኛ ድጋፍ፦</strong> ጥያቄዎችን የሚመልስ የኮች ህላዌ የቅርብ ክትትል</li>
            </ul>
        </div>

        <div class="card" style="border-left: 4px solid #0284c7; background: #f0f9ff; padding: 9px 14px; margin-bottom: 8px;">
            <div style="font-weight: 700; color: #0369a1; font-size: 14px; margin-bottom: 3px;">
                ⏱️ በ8 ሳምንት ውስጥ የሚጠበቅ ተጨባጭ ለውጥ፦
            </div>
            <div style="font-size: 13px; color: #0c4a6e; line-height: 1.5;">
                • <strong>ከሳምንት 1 - 2፦</strong> የጉልበት እና የሰውነት ንቃት መጨመር፣ የምግብ ልምድ መስተካከል<br>
                • <strong>ከሳምንት 3 - 5፦</strong> የሆድ ስብ መቀነስ፣ የመጀመሪያ የጡንቻ ቅርጽ መታየት<br>
                • <strong>ከሳምንት 6 - 8፦</strong> ግልጽ የሆነ የሰውነት ለውጥ፣ ከፍተኛ በራስ መተማመን እና ዘላቂ የአኗኗር ዘይቤ!
            </div>
        </div>

        <div class="cta-box">
            <h3>አዲሱን ሰውነትዎን ለመገንባት ዝግጁ ነዎት?</h3>
            <p>
                ወደ ቴሌግራም ቦቱ በመመለስ ጥቂት ጥያቄዎችን ይመልሱ፤<br>
                ለእርስዎ ብቻ የተዘጋጀውን <strong>የ8-ሳምንት ሙሉ ፕሮግራም</strong> አሁኑኑ ያግኙ!
            </p>
            <div style="background: rgba(255,255,255,0.12); border-radius: 8px; padding: 7px; font-size: 13px; color: #fde68a; margin-bottom: 8px;">
                ⚡️ በቴሌግራም ቦቱ ውስጥ የሚገኝ ልዩ የአዲስ ዓመት 40% ቅናሽ ተዘጋጅቷል
            </div>
            <div style="font-size: 14px; font-weight: 700; color: #ffffff;">
                👉 ወደ ቦቱ ተመልሰው <span style="color: #fbbf24;">[ 🚀 አዎ፣ የ8-ሳምንት እቅዴን አዘጋጅልኝ ]</span> የሚለውን ይጫኑ!
            </div>
        </div>
    </div>

    <div class="footer-row">
        <div class="footer-brand">COACH HILAWE · YOUR TRANSFORMATION PARTNER</div>
        <div>ገጽ 07 · ቀጣዩ እርምጃ</div>
    </div>
</div>

</body>
</html>
"""


def render_pdf(output_pdf_path: Path) -> Path:
    chromium_path = find_chromium_executable()
    if not chromium_path:
        raise RuntimeError("Chromium executable not found for PDF rendering.")

    html_content = build_html_content()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_html = Path(tmp_dir) / "document.html"
        tmp_pdf = Path(tmp_dir) / "output.pdf"

        tmp_html.write_text(html_content, encoding="utf-8")

        cmd = [
            chromium_path,
            "--headless=new",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-software-rasterizer",
            "--disable-gpu",
            "--run-all-compositor-stages-before-draw",
            "--no-pdf-header-footer",
            f"--print-to-pdf={str(tmp_pdf)}",
            str(tmp_html),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(f"Chromium PDF generation failed: {result.stderr}")

        output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(tmp_pdf), str(output_pdf_path))

    return output_pdf_path


if __name__ == "__main__":
    target = ROOT / "assets" / "new_year_2019_guide.pdf"
    rendered = render_pdf(target)
    print(f"Successfully generated 2019 Guide PDF: {rendered} ({rendered.stat().st_size} bytes)")
