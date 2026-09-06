"""Render the Coach Hilawe 2019 Ethiopian New Year Free Transformation Guide PDF.

Preserves the visual design and branding while upgrading the content with
practical exercise mechanics, Habesha nutrition hacks, the 3 fatal New Year
mistakes, and the high-converting bridge to the 8-Week Personalized Program.
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
    font-size: 13.5px;
    line-height: 1.55;
}}

.page {{
    width: 210mm;
    height: 297mm;
    position: relative;
    page-break-after: always;
    page-break-inside: avoid;
    padding: 20mm 20mm 18mm 20mm;
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
    border-bottom: 1px solid #f0eee6;
    padding-bottom: 10px;
    margin-bottom: 16px;
}}

.brand-tag {{
    font-size: 10.5px;
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
    font-size: 11px;
}}

.edition-badge {{
    background: #0f172a;
    color: #ffffff;
    font-size: 9.5px;
    font-weight: 700;
    letter-spacing: 1.2px;
    padding: 4px 10px;
    border-radius: 999px;
    text-transform: uppercase;
}}

/* Bottom Footer */
.footer-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid #f0eee6;
    padding-top: 10px;
    margin-top: 14px;
    font-size: 10px;
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
    font-size: 28px;
    font-weight: 700;
    color: #0f172a;
    line-height: 1.25;
    margin: 0 0 8px 0;
}}

.quote-box {{
    background: #fffbeb;
    border-left: 4px solid #f59e0b;
    padding: 10px 14px;
    border-radius: 0 8px 8px 0;
    font-size: 12.5px;
    color: #78350f;
    font-weight: 500;
    margin-bottom: 16px;
}}

/* Content Cards */
.card {{
    background: #ffffff;
    border: 1px solid #e7e5e4;
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}}

.card-title {{
    font-size: 15px;
    font-weight: 700;
    color: #0f172a;
    margin: 0 0 6px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}}

.card-title .icon {{
    color: #d97706;
    font-size: 17px;
}}

.card p {{
    margin: 0 0 6px 0;
    color: #44403c;
}}

.card ul {{
    margin: 4px 0 0 0;
    padding-left: 18px;
}}

.card li {{
    margin-bottom: 4px;
    color: #334155;
}}

/* Grid layout */
.grid-2 {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}}

/* Stat ribbon */
.stat-ribbon {{
    display: flex;
    background: #0f172a;
    color: #ffffff;
    border-radius: 12px;
    padding: 14px;
    justify-content: space-around;
    text-align: center;
    margin: 18px 0;
}}

.stat-item .num {{
    font-size: 24px;
    font-weight: 700;
    color: #fbbf24;
    line-height: 1;
}}

.stat-item .label {{
    font-size: 10px;
    color: #cbd5e1;
    letter-spacing: 0.5px;
    margin-top: 4px;
    text-transform: uppercase;
}}

/* Warning / Alert Box */
.warning-box {{
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-left: 4px solid #ef4444;
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 12px;
}}

.warning-title {{
    font-size: 13.5px;
    font-weight: 700;
    color: #991b1b;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
}}

.warning-desc {{
    font-size: 12px;
    color: #7f1d1d;
    margin: 0;
}}

/* Call to Action Box */
.cta-box {{
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    border-radius: 14px;
    color: #ffffff;
    padding: 22px 20px;
    text-align: center;
    margin-top: 14px;
    border: 1px solid #334155;
}}

.cta-box h3 {{
    font-size: 20px;
    margin: 0 0 8px 0;
    color: #fbbf24;
}}

.cta-box p {{
    color: #cbd5e1;
    font-size: 13px;
    margin: 0 0 16px 0;
    line-height: 1.5;
}}

.cta-btn {{
    display: inline-block;
    background: #f59e0b;
    color: #0f172a;
    font-weight: 700;
    font-size: 13.5px;
    padding: 11px 26px;
    border-radius: 999px;
    text-decoration: none;
    letter-spacing: 0.5px;
}}

.badge-tag {{
    display: inline-block;
    background: #e0f2fe;
    color: #0369a1;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
    margin-bottom: 6px;
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

    <div style="flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 10px 0;">
        <div class="badge-tag">የ2019 አዲስ ዓመት ልዩ እትም</div>
        <h1 class="page-title" style="font-size: 34px; margin-bottom: 12px;">
            ፍላጎቱ ካለ፣<br>
            <span style="color: #d97706;">መንገዱ ይኸው።</span>
        </h1>
        
        <div class="quote-box" style="font-size: 14px; padding: 14px; margin-bottom: 22px;">
            “አዲስ ዓመት ማለት የቀን መቁጠሪያ መቀየር ብቻ አይደለም፤ ራስህን የምትቀይርበት፣ ተስፋህን ወደ እውነተኛ ውጤት የምትለውጥበት ቅጽበት ነው።”<br>
            <strong style="color: #0f172a;">— አሰልጣኝ ህላዌ</strong>
        </div>

        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; margin-bottom: 20px;">
            <div style="font-weight: 700; font-size: 15px; color: #0f172a; margin-bottom: 8px;">
                ይህ መመሪያ ለምን ልዩ ሆነ?
            </div>
            <p style="margin: 0; color: #475569; font-size: 13.5px; line-height: 1.6;">
                ይህ በ2019 ዓ.ም አዲሱን ሰውነትዎን ለመገንባት የሚያስፈልጉዎትን <strong>እውነተኛ የስፖርት ሚስጥሮች</strong>፣ <strong>በኢትዮጵያ ውስጥ ተግባራዊ የሆኑ የአመጋገብ ጥበቦች</strong> እና <strong>95% ሰዎችን ወደኋላ የሚያስቀሩ አደገኛ ስህተቶችን</strong> በግልጽ የሚያሳይ ልዩ ስጦታ ነው። ይህ መነሻዎ ነው፤ ሙሉውን መንገድ በጋራ እንጓዘዋለን።
            </p>
        </div>

        <div class="stat-ribbon">
            <div class="stat-item">
                <div class="num">2019</div>
                <div class="label">የለውጥ ዓመት</div>
            </div>
            <div class="stat-item">
                <div class="num">8</div>
                <div class="label">ሳምንታት</div>
            </div>
            <div class="stat-item">
                <div class="num">100%</div>
                <div class="label">ሳይንሳዊ ስልት</div>
            </div>
        </div>

        <div style="font-size: 12px; color: #64748b; line-height: 1.5; padding: 0 4px;">
            ✓ ትክክለኛ የሰውነት እንቅስቃሴ ህጎች &nbsp;•&nbsp; ✓ ተጨባጭ የሀበሻ ምግቦች ፕሮቲን ስሌት &nbsp;•&nbsp; ✓ የቅፅበት ውጤት ማግኛ ስልቶች
        </div>
    </div>

    <div class="footer-row">
        <div class="footer-brand">COACH HILAWE · ADDIS ABABA</div>
        <div>ገጽ 01 · መግቢያ</div>
    </div>
</div>

<!-- ================= PAGE 2: EXERCISE SECRETS ================= -->
<div class="page">
    <div class="header-row">
        <div class="brand-tag">ክፍል 01 · የስፖርት እና የልምምድ ህጎች</div>
        <div class="edition-badge">EXERCISE LAWS</div>
    </div>

    <div style="flex: 1;">
        <h1 class="page-title">3ቱ የ2019 የስፖርት ወርቃማ ህጎች</h1>
        <p style="color: #64748b; margin-top: 0; margin-bottom: 14px;">
            አብዛኛው ሰው ጂም ወይም ቤት ውስጥ ለወራት ደክሞ ለውጥ የሚያጣው ስላልሰራ ሳይሆን <strong>ትክክለኛውን የሰውነት ግንባታ ህግ ስለማያውቅ</strong> ነው።
        </p>

        <div class="card" style="border-left: 4px solid #f59e0b;">
            <div class="card-title">
                <span class="icon">⚖️</span> 1. ክብደትን በየጊዜው የማሳደግ ህግ (Progressive Overload)
            </div>
            <p>
                ሰውነትዎ እንዲቀየር አዲስ ፈተና ማግኘት አለበት። በየሳምንቱ አንድ አይነት ክብደት በተመሳሳይ ድግግሞሽ (Reps) ማንሳት ሰውነትን ያደክማል እንጂ አያሳድገውም።
            </p>
            <ul>
                <li><strong>ሚስጥሩ፦</strong> በየሳምንቱ ወይ 1 ድግግሞሽ ጨምሩ፣ ወይም ክብደቱን በትንሹ (በ1 ኪሎ እንኳን) ከፍ አድርጉ።</li>
                <li>ይህ ጡንቻዎ ያለማቋረጥ እንዲያድግ እና ቅርጽ እንዲያወጣ ብቸኛው ሳይንሳዊ መንገድ ነው።</li>
            </ul>
        </div>

        <div class="card" style="border-left: 4px solid #f59e0b;">
            <div class="card-title">
                <span class="icon">⏱️</span> 2. እንቅስቃሴን ረጋ ብሎ የመቆጣጠር ጥበብ (Time Under Tension)
            </div>
            <p>
                ክብደቱን በፍጥነት መወርወር እና ማንሳት ጉዳት እንጂ ለውጥ አያመጣም። ትልቁ ውጤት የሚመጣው <strong>ክብደቱን ወደ ታች ስታወርዱ</strong> ነው።
            </p>
            <ul>
                <li><strong>የ3 ሰከንድ ህግ፦</strong> ለምሳሌ ፑሽአፕ (Push-up) ስትሰሩ ወደ ታች በ3 ሰከንድ ረጋ ብላችሁ ውረዱ፤ ወደ ላይ በ1 ሰከንድ በፍጥነት ግፉ።</li>
                <li>ይህ የጡንቻ ፋይበርን በ2 እጥፍ በማንቃት ሰውነት በአጭር ጊዜ እንዲጠነክር ያደርጋል።</li>
            </ul>
        </div>

        <div class="card" style="border-left: 4px solid #f59e0b;">
            <div class="card-title">
                <span class="icon">🔥</span> 3. የሆድ ስብን የማጥፋት ትክክለኛው ሳይንስ
            </div>
            <p>
                በቀን 200 የሆድ ስፖርት (Sit-ups) መስራት የሆድ ስብን አይቀንስም! ስብ ከአንድ የሰውነት ክፍል ብቻ ተነጥሎ አይቀንስም።
            </p>
            <ul>
                <li><strong>ትክክለኛው መንገድ፦</strong> ትልልቅ የሰውነት ክፍሎችን (እግር፣ ጀርባ፣ ደረት) የሚያሰሩ እንቅስቃሴዎችን (እንደ ስኳት እና ዴድሊፍት) ስትሰሩ ሰውነታችሁ በቀን ሙሉ ካሎሪ ያቃጥላል፤ የሆድ ስብም አብሮ ይጠፋል።</li>
            </ul>
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

    <div style="flex: 1;">
        <h1 class="page-title">3ቱ የሀበሻ ምግቦች እና የፕሮቲን ሚስጥሮች</h1>
        <p style="color: #64748b; margin-top: 0; margin-bottom: 14px;">
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
                <li>እንቁላል ስትመገቡ ሙሉውን አስኳል ጨምራችሁ መብላት ጤናማ ቅባት እና ቴስቶስትሮን ይገነባል።</li>
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
                <li>ከስፖርት 45 ደቂቃ በፊት ይውሰዱ፤ በስራ ሰዓት ድካም ሳይሰማዎት በሙሉ ኃይል እንዲሰሩ ይረዳል።</li>
            </ul>
        </div>
    </div>

    <div class="footer-row">
        <div class="footer-brand">COACH HILAWE · NUTRITION SYSTEM</div>
        <div>ገጽ 03 · የአመጋገብ ጥበቦች</div>
    </div>
</div>

<!-- ================= PAGE 4: FATAL MISTAKES ================= -->
<div class="page">
    <div class="header-row">
        <div class="brand-tag">ክፍል 03 · ጥንቃቄ እና ግንዛቤ</div>
        <div class="edition-badge">AVOID THESE</div>
    </div>

    <div style="flex: 1;">
        <h1 class="page-title">በአዲስ ዓመት ሰዎችን የሚያጠፉ 3 ስህተቶች</h1>
        <p style="color: #64748b; margin-top: 0; margin-bottom: 14px;">
            በየዓመቱ በመስከረም ወር ሺዎች ስፖርት ጀምረው በጥቅምት ወር ያቆማሉ። እነዚህን 3 ስህተቶች ካስወገዱ ግን ለውጥዎ ዘላቂ ይሆናል።
        </p>

        <div class="warning-box">
            <div class="warning-title">
                <span>⚠️</span> ስህተት 1፦ ያለ የተዋቀረ እቅድ ወደ ጂም መግባት
            </div>
            <p class="warning-desc">
                ወደ ስፖርት ቦታ ሄዶ ዛሬ ደረት፣ ነገ እጅ እያሉ በስሜት መስራት ጊዜን ከማባከን ውጭ ለውጥ አያመጣም። በየትኛው ቀን፣ የትኛውን ጡንቻ፣ በምን ያህል ክብደትና ድግግሞሽ እንደሚሰሩ አስቀድሞ የተጻፈ መመሪያ ሊኖርዎት ይገባል።
            </p>
        </div>

        <div class="warning-box">
            <div class="warning-title">
                <span>⚠️</span> ስህተት 2፦ ምግብን በከፍተኛ ሁኔታ ማቋረጥ (Starvation Diets)
            </div>
            <p class="warning-desc">
                ክብደት ለመቀነስ ቁርስ ወይም እራትን ሙሉ በሙሉ መተው ሜታቦሊዝምን ያቀዘቅዛል፤ ሰውነት በረሃብ ፍርሃት ስብ ማከማቸት ይጀምራል። ትክክለኛው መንገድ ምግብ መቀነስ ሳይሆን የተስተካከለ ካሎሪ እና ፕሮቲን መመገብ ነው።
            </p>
        </div>

        <div class="warning-box">
            <div class="warning-title">
                <span>⚠️</span> ስህተት 3፦ ተከታታይነት ማጣት (Inconsistency)
            </div>
            <p class="warning-desc">
                ለአንድ ሳምንት በቀን 2 ሰዓት ሰርቶ ለሁለት ሳምንት መጥፋት ሰውነትን ያደክማል። በሳምንት 3 ወይም 4 ቀናት ለ45 ደቂቃ ብቻ ጠንክሮ በተከታታይ የሚሰራ ሰው በ3 ወር ውስጥ ሌሎችን በሙሉ ይቀድማል።
            </p>
        </div>

        <div class="card" style="background: #f8fafc; border: 1px solid #cbd5e1; margin-top: 14px;">
            <div style="font-weight: 700; color: #0f172a; margin-bottom: 4px;">
                💡 የወርቅ ህግ፦
            </div>
            <p style="margin: 0; color: #475569; font-size: 13px;">
                “ውጤት የሚመጣው ፍጹም በመሆን ሳይሆን ባልተቋረጠ ጥረት ነው። ዛሬ የጀመርከው ትንሽ ልምምድ ነገ አዲሱን ሰውነትህን ይፈጥራል።”
            </p>
        </div>
    </div>

    <div class="footer-row">
        <div class="footer-brand">COACH HILAWE · DISCIPLINE FIRST</div>
        <div>ገጽ 04 · መወገድ ያለባቸው ስህተቶች</div>
    </div>
</div>

<!-- ================= PAGE 5: NEXT STEPS & PITCH ================= -->
<div class="page">
    <div class="header-row">
        <div class="brand-tag">ክፍል 04 · ቀጣዩ ትልቅ እርምጃዎ</div>
        <div class="edition-badge">NEXT LEVEL</div>
    </div>

    <div style="flex: 1; display: flex; flex-direction: column; justify-content: space-between;">
        <div>
            <h1 class="page-title" style="font-size: 26px;">ይህ ገና መጀመሪያው ነው!</h1>
            <div class="quote-box">
                እስካሁን ያገኛችሁት መመሪያ የለውጥ መነሻችሁ ነው። ነገር ግን የሰውነትዎ ክብደት፣ ቅርጽና አኗኗር ከሌላው ሰው ጋር አንድ አይደለም።
            </div>

            <p style="color: #334155; line-height: 1.6; margin-bottom: 12px;">
                እውነተኛውን እና ፈጣኑን ለውጥ ለማምጣት <strong>ሙሉ በሙሉ ለእርስዎ ብቻ የተዘጋጀ የ8-ሳምንት ግላዊ እቅድ</strong> ያስፈልግዎታል።
            </p>

            <div class="card" style="border: 2px solid #fde68a; background: #fffdf5;">
                <div style="font-weight: 700; color: #92400e; font-size: 14px; margin-bottom: 8px;">
                    👑 በእርስዎ ግላዊ የ8-ሳምንት ፕሮግራም ውስጥ የሚያገኟቸው፦
                </div>
                <ul style="padding-left: 18px; margin: 0; color: #451a03; font-size: 13px;">
                    <li style="margin-bottom: 6px;"><strong>የተዋቀረ የስፖርት እቅድ፦</strong> በሳምንት 3፣ 4 ወይም 5 ቀን እንደ ፍላጎትዎ የተከፋፈለ</li>
                    <li style="margin-bottom: 6px;"><strong>የእንቅስቃሴ ቪዲዮ መመሪያዎች፦</strong> ለእያንዳንዱ ልምምድ ትክክለኛ አሰራር የሚያሳይ</li>
                    <li style="margin-bottom: 6px;"><strong>ለክብደትዎ የተሰላ የአመጋገብ ስሌት፦</strong> ትክክለኛ የፕሮቲን እና የካሎሪ መጠን</li>
                    <li style="margin-bottom: 6px;"><strong>ሳምንታዊ የሂደት መከታተያ Checklist፦</strong> ለውጥዎን ደረጃ በደረጃ የሚመዝኑበት</li>
                    <li><strong>በቴሌግራም ቦት ቀጥተኛ ድጋፍ፦</strong> ጥያቄዎችን የሚመልስ የቅርብ ክትትል</li>
                </ul>
            </div>
        </div>

        <div class="cta-box">
            <h3>አዲሱን ሰውነትዎን ለመገንባት ዝግጁ ነዎት?</h3>
            <p>
                ወደ ቴሌግራም ቦቱ በመመለስ ጥቂት ጥያቄዎችን ይመልሱ፤<br>
                ለእርስዎ ብቻ የተዘጋጀውን <strong>የ8-ሳምንት ሙሉ ፕሮግራም</strong> አሁኑኑ ያግኙ!
            </p>
            <div style="background: rgba(255,255,255,0.1); border-radius: 8px; padding: 10px; font-size: 12.5px; color: #fde68a; margin-bottom: 14px;">
                ⚡️ በቴሌግራም ቦቱ ውስጥ የሚገኝ ልዩ የአዲስ ዓመት 40% ቅናሽ ተዘጋጅቷል
            </div>
            <div style="font-weight: 700; font-size: 14px; color: #fbbf24;">
                👉 ወደ ቴሌግራም ቦቱ ተመልሰው ምዘናዎን አሁኑኑ ይጀምሩ!
            </div>
        </div>
    </div>

    <div class="footer-row">
        <div class="footer-brand">COACH HILAWE · THE TRANSFORMATION SYSTEM</div>
        <div>ገጽ 05 · የለውጥ ጥሪ</div>
    </div>
</div>

</body>
</html>
"""


def render_pdf(output_path: Path) -> Path:
    browser = find_chromium_executable()
    if not browser:
        raise RuntimeError("No Chromium executable found for rendering.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_content = build_html_content()

    with tempfile.NamedTemporaryFile("w", suffix=".html", encoding="utf-8", delete=False) as tmp:
        tmp.write(html_content)
        tmp_path = Path(tmp.name)

    try:
        cmd = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-software-rasterizer",
            "--no-pdf-header-footer",
            f"--print-to-pdf={output_path.resolve()}",
            str(tmp_path.resolve()),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        if res.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
            err = res.stderr or res.stdout or f"Exit {res.returncode}"
            raise RuntimeError(f"Chromium PDF generation failed: {err}")

        print(f"Successfully generated 2019 Guide PDF: {output_path} ({output_path.stat().st_size} bytes)")
        return output_path
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    target = ROOT / "assets" / "new_year_2019_guide.pdf"
    render_pdf(target)
