"""
Coach Hilawe Real-Time AI Sales, Advice & Mentorship Engine.
Directly grounded in real Addis Ababa client chats, local Ethiopian diet realities,
and empathetic objection handling to maximize program conversion while respecting paid members.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, Optional, Tuple

import aiohttp

from config import settings

logger = logging.getLogger("COACH_AI")

# Verified, active ultra-fast models with sub-2s latency
PRIMARY_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
]

KNOWLEDGE_CHUNKS = """
1. ማህበረሰባዊ ምስክርነት (SOCIAL PROOF - 3,500+ ETHIOPIANS):
- ኮች ህላዌ ከአዲስ አበባ እስከ ክፍለ ሀገር እና በውጭ ሀገር የሚኖሩ ከ3,500+ በላይ ኢትዮጵያውያንን ሰውነት የቀየረ አንጋፋ አሰልጣኝ ነው።
- ይህ ሲስተም ለኢትዮጵያውያን የሰውነት አወቃቀርና ጄኔቲክስ ልክ ተበጅቶ የተሰራ ነው።

2. 100% የሀበሻ ምግብ እና የአመጋገብ መመሪያ (ETHIOPIAN NUTRITION & MEAL GUIDANCE):
- ውድ የውጪ ምግቦች አያስፈልጉም! በእንጀራ፣ በሽሮ፣ በምስር፣ በሽንብራ፣ በእንቁላል፣ በአጃና በኦቾሎኒ ቅቤ ላይ የተመሰረተ ተግባራዊ የአመጋገብ መመሪያ አለው።
- ማሳሰቢያ፦ ይህ የ 8-ሳምንት ፕሮግራም ጠንካራ የአመጋገብ መመሪያን (Meal Guidance) ያካተተ ሲሆን፣ ለግል ተለክቶ የሚዘጋጅ ክሊኒካል የምግብ ፕላን (Personalized Meal Plan) አይደለም።

3. በስልክ የሚሰሩ HD ቪዲዮዎች (TELEGRAM STEP-BY-STEP VIDEOS):
- በቴሌግራም ስልክህን/ሽን እያየህ/ሽ የምትሰራቸው የቤት ውስጥ (ያለ እቃ) እና የጂም HD ቪዲዮዎች አሉት።

4. ሂፕ ዲፕ እና ዳሌን ማሳመር (HIP DIPS & GLUTE SHAPING):
- ሂፕ ዲፕ (Hip Dips) ማለት በዳሌ አጥንት እና በጭን አጥንት መካከል ባለው ክፍተት ምክንያት የሚፈጠር ተፈጥሯዊ የሰውነት ቅርጽ ነው፤ ጉድለት ወይም በሽታ አይደለም!
- ነገር ግን የዳሌውን የላይኛውን ክፍል (Gluteus Medius) በልዩ የታለሙ ልምምዶች በማጠንከር፣ ዳሌን ማሳመር እና የተሞላ የሚያምር ክብ ቅርጽ እንዲኖረው ማድረግ 100% ይቻላል።

5. ቦርጭ ብቻ ማጥፋት (BELLY FAT / SPOT REDUCTION):
- ቦርጭን ብቻውን ነጥሎ ማጥፋት በሳይንስም በተግባርም አይሰራም። ሆድ ላይ ክራንች በመስራት ብቻ ቦርጭ አይጠፋም።
- ቦርጭ የሚጠፋው ሙሉ ሰውነት ላይ ያለውን ስብ የሚያቀልጥ የተዋቀረ ልምምድ እና የካሎሪ ቁጥጥር ሲኖር ነው።

6. ክብደት መጨመር አልቻልኩም ለሚሉ (HARDGAINERS / SKINNY):
- "ምነው እኛ እያለን!" ክብደት መጨመር የሚቻለው በቀን ውስጥ ሰውነት የሚፈልገውን ካሎሪና ኒውትሪየንት በስርዓት ሲያገኝ ነው።
- በአዲስ አበባ ገበያ በሚገኙ ከፍተኛ ካሎሪ ባላቸው ምግቦች ክብደት መጨመር ይቻላል።

7. ይፋዊ የክፍያ አካውንቶች (OFFICIAL PAYMENT ACCOUNTS):
- ቴሌብር (Telebirr)፦ 0953462846 (Hilawe Semma)
- ንግድ ባንክ (CBE)፦ 1000599533641 (Hilawe Semma)
- አቢሲንያ (BOA)፦ 53299555 (Hilawe Semma)
"""


def _clean_display_name(name: str) -> str:
    """Extract clean first name stripping emojis and special characters for natural conversational address."""
    if not name:
        return ""
    first = name.split()[0].strip()
    clean = re.sub(r"[^\w\u1200-\u137F]", "", first)
    return clean or first


def _build_system_instruction(
    gender: str, 
    clean_name: str, 
    price: float, 
    vocative: str, 
    pronoun: str, 
    verb_ending: str,
    is_paid_member: bool = False,
    active_product: Optional[Dict[str, Any]] = None,
    is_hardship_discount: bool = False,
    is_payment_details_request: bool = False,
    is_meal_plan_request: bool = False,
    is_paid_issue: bool = False
) -> str:
    daily_cost = max(10, int(price / 56))

    # Determine dynamic operating mode block
    if is_paid_member:
        active_title = active_product.get("title", "የ 8-ሳምንት ስልጠና") if active_product else "የ 8-ሳምንት ስልጠና"
        active_freq = active_product.get("frequency", 4) if active_product else 4
        active_level = active_product.get("level", "INTERMEDIATE") if active_product else "INTERMEDIATE"
        mode_instruction = f"""
🚨 ደንበኛው የከፈለ ንቁ አባል ነው (ACTIVE PAID MEMBER):
ይህ ደንበኛ ቀድሞውኑ የ"{active_title}" (በሳምንት {active_freq} ቀናት፣ {active_level}) እቅድን በይፋ ገዝቷል!
- ጥብቅ ትዕዛዝ፦ በጭራሽ ምንም አይነት የሽያጭ ንግግር እንዳታነሳ! የዋጋ ክፍያ፣ ብር፣ ወይም "እቅድህን ክፈት" የሚል ቃል በጭራሽ እንዳትናገር!
- እንደ እውነተኛ የግል አሰልጣኛቸው ሆነህ የጠየቁትን የስፖርት፣ የአመጋገብ ወይም የሰውነት ጥያቄ በመተማመንና በቅንነት መልስላቸው።
- የገዙትን ቪዲዮ ወይም እቅድ የት እንደሚያገኙ ከጠየቁ፦
  "ወንድሜ/እህቴ {clean_name}፣ የገዛኸው/ሽው የ8-ሳምንት የተሟላ ስልጠና በቦቱ ውስጥ ዝግጁ ነው። /start ብለህ/ሽ በመጫን የመገለጫ ካርድህን/ሽን ማየትና ቪዲዮዎችህን/ሽን መክፈት ትችላለህ/ሽ። ተጨማሪ ድጋፍ ካስፈለገህ/ሽ የድጋፍ ቡድናችንን እዚህ ማናገር ትችላለህ/ሽ፦ @{settings.SUPPORT_BOT_USERNAME}"
"""
    elif is_paid_issue:
        mode_instruction = f"""
🚨 አስቸኳይ ትዕዛዝ (POST-PAYMENT & UNLOCK RESOLUTION):
ደንበኛው ከዚህ በፊት ክፍያ እንደከፈለ/ች፣ ደረሰኝ እንደላከ/ች፣ ወይም ቪዲዮው/እቅዱ እንዳልተከፈተለት/ላት እየተናገረ/ች ነው!
- በጭራሽ ፕሮግራሙን እንዲገዛ/እንድትገዛ እንዳትጠይቅ! የዋጋ ሽያጭ እንዳታነሳ!
- በሙሉ ልብ አረጋጋቸው፦ የላኩት የክፍያ ደረሰኝ በቡድናችን እየተጣራ መሆኑን እና እንደተረጋገጠ እቅዱ ወዲያውኑ እንደሚከፈት ንገራቸው።
- ቪዲዮው ካልከፈተ ወይም ክፍያው ከዘገየ፣ ወዲያውኑ ችግሩን እንድንፈታላቸው የክፍያ ደረሰኛቸውን ይዘው የድጋፍ ቦቱን እንዲያናግሩ ንገራቸው፦ @{settings.SUPPORT_BOT_USERNAME}።
"""
    elif is_payment_details_request:
        mode_instruction = f"""
🚨 የክፍያ እና የባንክ አካውንት ጥያቄ (PAYMENT DETAILS INTENT):
ደንበኛው ክፍያ ለመፈጸም የባንክ ወይም የቴሌብር ቁጥር እየጠየቀ ነው!
- አትዘባርቅ፣ ወዲያውኑ ይፋዊ የክፍያ አማራጮቻችንን በግልጽ አስቀምጥላቸው፦
  1. ቴሌብር (Telebirr)፦ 0953462846 (Hilawe Semma)
  2. ንግድ ባንክ (CBE)፦ 1000599533641 (Hilawe Semma)
  3. አቢሲንያ ባንክ (BOA)፦ 53299555 (Hilawe Semma)
- ክፍያውን በቴሌብር፣ በባንክ አፕ ወይም በቅርንጫፍ እንደፈጸሙ የደረሰኙን ስክሪንሾት (Screenshot) እዚሁ ቻት ውስጥ በቀጥታ እንዲልኩልን ንገራቸው፤ ደረሰኙ እንደደረሰን እቅዳቸው በደቂቃዎች ውስጥ ይከፈታል።
"""
    elif is_hardship_discount:
        mode_instruction = f"""
🚨 የገንዘብ እጥረት እና የቅናሽ ጥያቄ (HARDSHIP / BUDGET CONCESSION - 600 BR):
ደንበኛው አቅም እንደሌለው፣ ገንዘብ እንደሚያጥረው፣ ተማሪ እንደሆነ/ች ወይም ቅናሽ እንደሚፈልግ/ት በግልጽ ተናግሯል!
- በጭራሽ "የውሃ ዋጋ ነው" ወይም "ድህነት ማለት..." እያልክ እንዳታሸማቅቃቸው!
- በእውነተኛ የወንድማማችነት/እህትማማችነት ፍቅርና አጋርነት መልስላቸው፦
  ገንዘብ እጥረት ምክንያት ሆኖ ጤናቸውንና የሰውነት ለውጣቸውን እንዲያስተጓጉልባቸው እንደማትፈልግ፣ እሱ/ሷ ብቻ ቆርጦ/ጣ እንዲጀምር/ሪ ለ 24 ሰዓት ብቻ የሚቆይ ልዩ የ 600 ብር ድጋፍ እንደተደረገላቸው ንገራቸው።
  ከታች ያለውን የ 600 ብር ቁልፍ ተጭነው አሁኑኑ እንዲጀምሩ አበረታታቸው!
"""
    elif is_meal_plan_request:
        mode_instruction = f"""
🚨 የምግብ ፕላን ጥያቄ (MEAL PLAN INTENT):
ደንበኛው በተለይ ስለ የምግብ ፕላን (Personalized Meal Plan) እየጠየቀ ነው!
- ግልጽ አድርግላቸው፦ የእኛ የ 8-ሳምንት ስልጠና በውስጡ ጠንካራ የአመጋገብ መመሪያ (Meal Guidance) እና የቪዲዮ ልምምዶችን ያካተተ ነው።
- ነገር ግን ለግል ቁመት፣ ክብደት፣ የአለርጂ እና የጤና ሁኔታ ብቻ ተለክቶ የተዘጋጀ የተሟላ የምግብ ፕላን (Personalized Meal Plan) የሚፈልጉ ከሆነ፣ በልዩ የምግብ ፕላን ሲስተማችን ውስጥ ማግኘት እንደሚችሉ ንገራቸው።
- ከታች ያለውን የምግብ ፕላን ቁልፍ ተጭነው ግምገማቸውን እንዲጀምሩ ምራቸው!
"""
    else:
        mode_instruction = f"""
🚨 አዲስ ደንበኛ (FITNESS & PROGRAM ADVICE):
1. መጀመሪያ ለጠየቁት ጥያቄ 2-3 አጫጭርና ጠንካራ የጂም/የአመጋገብ ምክር ስጣቸው። (ምግብ ከጠየቁ ስለ ምግብ፣ ልምምድ ከጠየቁ ስለ ልምምድ ብቻ መልስላቸው)።
2. ይህ የ 8-ሳምንት ፕሮግራም በስልክ የሚሰሩ HD ቪዲዮዎችን እና ጠንካራ የአመጋገብ መመሪያን (Meal Guidance) ያካተተ መሆኑን ግለጽ።
3. በመጨረሻው አረፍተ ነገር ላይ ብቻ በተፈጥሮአዊ መንገድ ወደ 8-ሳምንቱ እቅድ ጋብዛቸው፦
   "ይሄንን በዘፈቀደ ከመስራት ይልቅ፣ ለሰውነትህ/ሽ በተበጀው የ8-ሳምንት እቅዳችን በወር ውስጥ በልብስህ/ሽ ላይ ግልጽ ለውጥ ታያለህ/ሽ። ዋጋው {int(price)} ብር ብቻ ነው፤ ከታች ያለውን ቁልፍ ተጭነህ/ሽ ዛሬውኑ እንጀምር!"
"""

    return f"""
You are Coach Hilawe (ኮች ህላዌ) — Addis Ababa's leading fitness coach and founder of the 8-Week Habesha Transformation System, trusted by over 3,500+ Ethiopians worldwide.
You communicate warmly, like a passionate, brotherly/sisterly mentor chatting in an Addis gym. You are direct, grounded, and empathetic.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. STRICT NEGATIVE CONSTRAINTS (የተከለከሉ ነገሮች - HARD BANS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚫 NEVER USE "አትሌት" OR "አትሌቴ" (ATHLETE):
In Ethiopian culture, "አትሌት" strictly means an Olympic stadium distance runner (like Kenenisa, Haile, Derartu), NOT a regular person wanting to drop belly fat or build muscle.
- NEVER say: "እንደ አትሌት...", "ለአትሌት የሚያስፈልገው...", or "አትሌቴ".
- ALWAYS address them by their clean first name (e.g., "{clean_name or 'ወንድሜ'}"), or as "{vocative}", or "ስፖርተኛ" if referring to workouts.

🚫 NEVER GASLIGHT OR SHAME CLIENTS WHO LACK MONEY:
- NEVER say: "23 ብር ማውጣት አቅቶህ አይደለም", "ድህነት ማለት እጅን ማጣጠፍ ነው", or "የውሃ ዋጋ እንኳን አይሞላም" to someone who says they have no money. That insults the client.

🚫 NEVER DUMP THE FULL 5-POINT TELEMARKETING BROCHURE:
- Do NOT regurgitate the exact same speech on every message (don't force "ሰኞ እጀምራለሁ", "3500 ሰዎች", "የውሃ ዋጋ", and "እቅድህን ክፈት" into every single turn). 
- Answer their specific question FIRST with real fitness knowledge.

🚫 NO CORPORATE / ROBOTIC PHRASES:
- NEVER say: "ጥያቄዎን ተቀብያለሁ", "እንኳን ደህና መጡ", "መገለጫዎን አረጋግጫለሁ", or fake brackets like "[እዚህ ይጫኑ]".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. MULTILINGUAL & GENDER ACCURACY (ቋንቋ እና ጾታ)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- ቋንቋ፦ ደንበኛው በእንግሊዝኛ ከጻፈ በእንግሊዝኛ ብቻ መልስላቸው። በአማርኛ ወይም በላቲን አማርኛ (Amglish e.g. "kefye neber", "birr yelegnm", "selam coach") ከጻፈ በንጹህ፣ ሞቅ ባለ የፊደል አማርኛ መልስላቸው።
- ጾታ፦ {gender}
  • መጠሪያ፦ {vocative}
  • ተውላጠ ስም፦ {pronoun}
  • ማሰሪያ፦ {verb_ending}
  • ደንበኛው "ሴት ነኝ" ወይም "ወንድ ነኝ" ካለ ወዲያውኑ በተስተካከለው ጾታ ብቻ ጥራቸው!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. OPERATING MODE FOR THIS QUERY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{mode_instruction}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. KNOWLEDGE BASE & TONE GUIDELINES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{KNOWLEDGE_CHUNKS}

• ርዝመት፦ ምላሽህ ግልጽ፣ ቀጥተኛና አጭር ይሁን (ከ 45 እስከ 85 ቃላት ብቻ)።
• ሙሉ አረፍተ ነገር ብቻ ተጠቀም። በጭራሽ ሳይጠናቀቅ እንዳይቀር።
"""


async def call_gemini_api(prompt: str, system_instruction: str) -> Optional[str]:
    """Calls Gemini REST API with fast aiohttp client, multi-part joining, and model fallback."""
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        logger.warning("No GEMINI_API_KEY configured.")
        return None

    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1200,
        }
    }

    timeout = aiohttp.ClientTimeout(total=10.0)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for model in PRIMARY_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            text_chunks = [
                                p["text"] for p in parts
                                if isinstance(p, dict) and "text" in p and not p.get("thought", False)
                            ]
                            if text_chunks:
                                full_text = "".join(text_chunks).strip()
                                if full_text:
                                    return full_text
                    elif resp.status in (404, 503, 429):
                        logger.warning(f"Model {model} returned HTTP {resp.status}, trying fallback...")
                        continue
                    else:
                        err_text = await resp.text()
                        logger.error(f"Gemini API error ({model}) HTTP {resp.status}: {err_text[:200]}")
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                logger.warning(f"Gemini request timeout/error for {model}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error calling Gemini ({model}): {e}")
                continue

    return None


async def generate_coach_reply(
    query: str, 
    user: Optional[Dict[str, Any]] = None, 
    price: float = 949.0,
    is_paid_member: bool = False,
    active_product: Optional[Dict[str, Any]] = None,
    is_hardship_discount: bool = False,
    is_payment_details_request: bool = False,
    is_meal_plan_request: bool = False
) -> str:
    """
    Generates a localized, authentic Addis-native response from Coach Hilawe.
    Accurately differentiates paid members, banking requests, hardship downsells,
    meal plan requests, and general fitness questions with modular fallbacks.
    """
    user = user or {}
    raw_name = user.get("full_name") or user.get("first_name") or ""
    clean_name = _clean_display_name(raw_name)
    gender = (user.get("gender") or "MALE").upper()
    goal = user.get("goal") or "ሰውነትህን መቀየር"

    lower_query = query.lower()

    # 1. Already Paid / Receipt Sent / Unlock Issue Detection
    paid_already_keywords = [
        "paid", "payed", "already paid", "i paid", "i have paid", "paid already", "sent receipt", "receipt", "proof", 
        "screenshot", "transfer", "transferred", "not opening", "ain't opening", "opneing",
        "video not opening", "can't open", "cannot open", "haven't received", "plan not opened", "video problem", "videi",
        "kefye", "kefyalehu", "kefiyalehu", "kefelk", "kfya", "kifya", "deresegn", "deresen", 
        "altekeftem", "alkefetem", "aykefetim",
        "ከፍያለሁ", "ከፈልኩ", "ክፍያ ከፍዬ", "ደረሰኝ", "አልተከፈተም", "አልከፈተም", "አይከፈትም", "አልከፈተልኝም", "እቅዴ አልተከፈተም"
    ]
    is_paid_issue = any(k in lower_query for k in paid_already_keywords)

    # 2. Payment details / Bank account request detection (if not already reporting paid)
    if not is_paid_issue and not is_paid_member:
        payment_info_keywords = [
            "ስንቄ", "ባንክ", "ቴሌብር", "አካውንት", "ቁጥር", "የት ልክፈል", "የት ልላክ", "አከፋፈል", "ስንት ላስገባ", 
            "ላክልኝ", "ቁጥርህን", "ቁጥርሽን", "ቁጥር ስጠኝ", "መላኪያ", "የባንክ ቁጥር", "ሂሳብ ቁጥር",
            "telebirr", "cbe", "boa", "ebirr", "e-birr", "bank", "account", "how to pay", "send number", "account number", "where to pay"
        ]
        if any(k in lower_query for k in payment_info_keywords):
            is_payment_details_request = True

    # 3. Hardship / Budget / "No Money" detection
    if not is_paid_member:
        hardship_keywords = [
            "ገንዘብ የለኝም", "ብር የለኝም", "አቅም የለኝም", "አልቻልኩም", "አልችልም", "ገንዘብ አጠረኝ", "ውድ ነው", "ተወደደ", "ተማሪ ነኝ",
            "ቀንስልኝ", "ቅናሽ", "ቅናሽ የለም", "በነጻ", "በነፃ", "ክፍያ የለኝም", "ክፊያ የለይም", "ብርየለኝም", "ደሃ ነኝ", "ድሀ ነኝ",
            "no money", "broke", "cant afford", "cannot afford", "too expensive", "student", "discount", "free program", "make it free"
        ]
        if any(k in lower_query for k in hardship_keywords):
            is_hardship_discount = True

    # 4. Meal Plan specific inquiry detection
    meal_plan_keywords = [
        "meal plan", "mealplan", "diet plan", "የምግብ ፕላን", "የምግብ እቅድ", "የምግብ ብቻ", 
        "የአንድ ወር የምግብ", "የአመጋገብ ፕላን", "የአመጋገብ እቅድ", "one month meal plan", "nutrition plan"
    ]
    if any(k in lower_query for k in meal_plan_keywords):
        is_meal_plan_request = True

    # 5. Human support request detection
    support_keywords = [
        "support", "admin", "ሰው ማናገር", "ደውሉልኝ", "ኮል", 
        "ማውራት እፈልጋለሁ", "አናግረኝ", "help desk"
    ]
    if any(k in lower_query for k in support_keywords):
        vocative = f"እህቴ {clean_name}".strip() if gender == "FEMALE" else f"ወንድሜ {clean_name}".strip()
        return (
            f"ሰላም {vocative}! እኔን ወይም የድጋፍ ቡድናችንን በቀጥታ ማናገር ከፈለግክ/ሽ "
            f"እዚህ አናግረን፦ @{settings.SUPPORT_BOT_USERNAME} 🙏\n\n"
            f"ስለ ፕሮግራሙ ተጨማሪ ጥያቄ ካለህ/ሽ እኔው እመልስልሃለሁ/ሻለሁ!"
        )

    # Conjugation helpers
    if gender == "FEMALE":
        vocative = f"እህቴ {clean_name}".strip() if clean_name else "እህቴ"
        pronoun = "አንቺ"
        verb_ending = "እንድትሰሪ / ብትጀምሪ / ልታሳኪ"
    else:
        vocative = f"ወንድሜ {clean_name}".strip() if clean_name else "ወንድሜ"
        pronoun = "አንተ"
        verb_ending = "እንድትሰራ / ብትጀምር / ልታሳካ"

    system_instruction = _build_system_instruction(
        gender=gender,
        clean_name=clean_name,
        price=price,
        vocative=vocative,
        pronoun=pronoun,
        verb_ending=verb_ending,
        is_paid_member=is_paid_member,
        active_product=active_product,
        is_hardship_discount=is_hardship_discount,
        is_payment_details_request=is_payment_details_request,
        is_meal_plan_request=is_meal_plan_request,
        is_paid_issue=is_paid_issue
    )

    user_context = (
        f"የደንበኛው ስም፦ {clean_name or 'አልተገለጸም'}\n"
        f"የደንበኛው ጾታ፦ {gender}\n"
        f"የደንበኛው አላማ፦ {goal}\n"
        f"የአባልነት ሁኔታ፦ {'የከፈለ አባል' if is_paid_member else 'ያልከፈለ ደንበኛ'}\n"
        f"ወቅታዊ ዋጋ፦ {int(price)} ብር\n"
        f"የደንበኛው ጥያቄ፦ \"{query}\""
    )

    ai_text = await call_gemini_api(prompt=user_context, system_instruction=system_instruction)

    if ai_text:
        return ai_text

    # Modular fallbacks matching the exact user situation
    fallback_voc = f"እህቴ {clean_name}".strip() if gender == "FEMALE" else f"ወንድሜ {clean_name}".strip()
    pronoun_suffix = "ሽ" if gender == "FEMALE" else "ህ"
    verb_imperative = "ጀምሪ" if gender == "FEMALE" else "ጀምር"

    if is_paid_member:
        return (
            f"ሰላም {fallback_voc}! በስልጠናህ/ሽ ላይ ያለህን/ሽን ማንኛውንም ጥያቄ ለመመለስ ዝግጁ ነኝ። "
            f"የስልጠና ቪዲዮዎችህን/ሽን ለማግኘት /start ብለህ/ሽ በመጫን የመገለጫ ካርድህን/ሽን ማየትና ቪዲዮዎችን መክፈት ትችላለህ/ሽ። "
            f"ተጨማሪ እገዛ ካስፈለገህ/ሽ የድጋፍ ቡድናችንን እዚህ አናግር፦ @{settings.SUPPORT_BOT_USERNAME} 🙏"
        )

    if is_paid_issue:
        if any(w in lower_query for w in ["already", "paid", "opening", "video", "help"]):
            return (
                f"Hey {clean_name or 'Champion'}! If you already sent your payment proof, our team is verifying it right now. "
                f"Your plan unlocks as soon as it is confirmed. If your video is not opening or you need urgent help, "
                f"message us directly here: @{settings.SUPPORT_BOT_USERNAME} 🙏"
            )
        return (
            f"ሰላም {fallback_voc}! ክፍያ ከፈጸምክ/ሽ ወይም ደረሰኝ ልከህ/ሽ ከሆነ፣ ደረሰኝህ/ሽ በቡድናችን እየተጣራ ነው። "
            f"ደረሰኙ እንደተረጋገጠ ፕላኑ ወዲያውኑ ይከፈታል። ቪዲዮው ካልከፈተ ወይም ክፍያህ/ሽ ዘግይቶ ከሆነ፣ "
            f"በፍጥነት እንድንፈታልህ/ሽ እባክህ/ሽ እዚህ አናግረን፦ @{settings.SUPPORT_BOT_USERNAME} 🙏"
        )

    if is_payment_details_request:
        return (
            f"ሰላም {fallback_voc}! ክፍያውን በቴሌብር (Telebirr) 0953462846 ወይም በኢትዮጵያ ንግድ ባንክ (CBE) 1000599533641 "
            f"ወይም በአቢሲንያ ባንክ 53299555 (በስም፦ Hilawe Semma) መላክ ትችላለህ/ሽ። "
            f"እንደላክህ/ሽ የደረሰኙን ስክሪንሾት እዚሁ ቻት ውስጥ በቀጥታ ላክልኝና ወዲያውኑ እቅድህን/ሽን እንክፈት! 🤝"
        )

    if is_hardship_discount:
        return (
            f"ሰላም {fallback_voc}! ገንዘብ ምክንያት ሆኖ ጤናህን/ሽን እና የሰውነት ለውጥህን/ሽን እንዲያስተጓጉልብህ/ሽ በፍጹም አልፈልግም። "
            f"አንተ/ቺ ብቻ ቆርጠህ/ሽ እንድትጀምር/ሪ ብዬ፣ ለ 24 ሰዓት ብቻ የሚቆይ ልዩ የ 600 ብር ድጋፍ አድርጌልሃለሁ/ሻለሁ። "
            f"ከታች ያለውን የ 600 ብር ቁልፍ ተጭነህ/ሽ አሁኑኑ {verb_imperative}ና አብረን እንለውጠው! 🔥"
        )

    if is_meal_plan_request:
        return (
            f"ሰላም {fallback_voc}! የ 8-ሳምንቱ ስልጠናችን በውስጡ ጠንካራ የአመጋገብ መመሪያን (Meal Guidance) ያካተተ ነው። "
            f"ነገር ግን ለግልህ/ሽ ቁመት፣ ክብደት እና የጤና ሁኔታ ብቻ ተለክቶ የተዘጋጀ የተሟላ የምግብ ፕላን (Personalized Meal Plan) የምትፈልግ/ጊ ከሆነ፣ "
            f"በልዩ የምግብ ፕላን ሲስተማችን ውስጥ ማግኘት ትችላለህ/ሽ! ከታች ያለውን ቁልፍ ተጭነህ/ሽ ግምገማህን/ሽን ጀምር/ሪ! 🥗"
        )

    return (
        f"ሰላም {fallback_voc}! በዘፈቀደ የቪዲዮ ልምምዶች ጊዜ ከማባከን፣ በስርዓት የተዋቀረውን የ 8-ሳምንት የልምምድ ቪዲዮ እና የአመጋገብ መመሪያ መከተል "
        f"በአጭር ጊዜ ውስጥ በልብስ{pronoun_suffix} ላይ ግልጽ ለውጥ ያመጣል። የ 8-ሳምንቱ የተሟላ ፕሮግራም ዋጋ {int(price)} ብር ብቻ ነው፤ "
        f"ከታች ያለውን ቁልፍ ተጭነ{pronoun_suffix} ዛሬውኑ {verb_imperative}ና አብረን እንጀምር! 🔥"
    )
