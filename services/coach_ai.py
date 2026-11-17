"""
Coach Hilawe Real-Time AI Sales & Advice Engine.
Directly grounded in real Addis Ababa client chats, local Ethiopian diet realities,
and psychological objection handling to maximize program conversion.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

import aiohttp

from config import settings

logger = logging.getLogger("COACH_AI")

# Fast, high-uptime models with fallback
PRIMARY_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
]

# Knowledge base grounded in actual Ethiopian client chats (from Chat_Export)
KNOWLEDGE_CHUNKS = """
1. የፆም ምግቦች እና ፕሮቲን (ETHIOPIAN FASTING / TSOM DIET):
- የምግብ እቅዱ የፆም ምግቦችን 100% ያካትታል።
- በፆም ወቅት ፕሮቲን እንዳይጎድል፦ ምስር፣ ሽንብራ፣ አኩሪ አተር (soya chunks)፣ አጃ (oats)፣ የኦቾሎኒ ቅቤ (peanut butter) እና አቮካዶ በመጠቀም ጡንቻ ሳይቀንስ ቅርጽን መጠበቅ ይቻላል።

2. አሁን ተመዝግቦ በኋላ መጀመር (REGISTER NOW, START LATER):
- አዎ ይቻላል! አሁን በቅናሽ ዋጋ ተመዝግቦ ፕላኑን መያዝ ይቻላል። ልምምዱን ደግሞ ደንበኛው በተመቸው ቀን (ከበዓል ወይም ከፈተና በኋላ) መጀመር ይችላል።

3. ክብደት መጨመር አልቻልኩም ለሚሉ (HARDGAINERS / SKINNY):
- "ምነው እኛ እያለን!" ክብደት መጨመር የሚቻለው በቀን ውስጥ ሰውነት የሚፈልገውን ካሎሪና ኒውትሪየንት በስርዓት ሲያገኝ ነው።
- በፕሮግራሙ ውስጥ በቀላሉ በአዲስ አበባ ገበያ በሚገኙ ምግቦች የሚዘጋጅ ከፍተኛ ካሎሪ ያለው የአመጋገብ እቅድ አለ። ከ600 በላይ ሰዎች ተጠቅመውበታል።

4. ቦርጭ ብቻ ማጥፋት (BELLY FAT / SPOT REDUCTION):
- ቦርጭን ብቻውን ነጥሎ ማጥፋት (spot reduction) በሳይንስም በተግባርም ውሸት ነው። ሆድ ላይ ክራንች በመስራት ብቻ ቦርጭ አይጠፋም።
- ቦርጭ የሚጠፋው ሙሉ ሰውነት ላይ ያለውን ስብ የሚያቀልጥ የተዋቀረ ልምምድ እና የካሎሪ ቁጥጥር ሲኖር ነው። ይህ ፕሮግራም ልክ ለግለሰቡ ቁመትና ክብደት ተበጅቶ የተሰራ ነው።

5. ለውጥ ለማየት የሚፈጀው ጊዜ (TIMELINE TO RESULTS):
- በመጀመሪያዎቹ 2 ሳምንታት፦ ጉልበት ይጨምራል፣ እንቅልፍ ይስተካከላል።
- በ4ኛው ሳምንት፦ ሆድና ልብስ ላይ የሚታይ ግልጽ ልዩነት ይታያል።
- በ8ኛው ሳምንት፦ ሰውነት ሙሉ በሙሉ ይቀየራል (ወጥነትና ዲሲፕሊን እስካለ ድረስ)።

6. ጂም ወይስ ቤት ውስጥ (GYM VS HOME WORKOUT):
- ጂም መሄድ ላልቻለ ሰው ምንም ችግር የለውም፤ ቤት ውስጥ ያለ ምንም እቃ ወይም ቀላል እቃዎችን (የውሃ ፕላስቲክ፣ ቦርሳ) በመጠቀም የሚሰራ የቤት ውስጥ (Home workout) አማራጭ አለው።

7. ተዓማኒነት እና ማጭበርበር ስጋት (TRUST & SECURITY):
- እኔ ኮች ህላዌ ነኝ፤ በሺዎች የሚቆጠሩ ሰዎችን በአዲስ አበባና በመላው ዓለም ቀይሬያለሁ።
- ክፍያ የሚፈጸመው በይፋዊ የባንክ አካውንት (CBE, BOA, Telebirr) ነው።
- ደረሰኝ በተላከ በደቂቃዎች ውስጥ የተዘጋጀው እቅድ በቴሌግራም ይላካል።

8. ዋጋ እና ጠቀሜታ (PRICING ANCHOR):
- የ8-ሳምንት የተሟላ ስልጠናና የአመጋገብ እቅድ ዋጋው {price} ብር ብቻ ነው።
- በቀን ሲታሰብ የ1 ማኪያቶ ወይም የ1 ጠርሙስ ውሃ ዋጋ ያህል ነው! አንዴ ከተከፈለ ሌላ ተጨማሪ ክፍያ የለውም።
"""


def _build_system_instruction(gender: str, first_name: str, price: float, vocative: str, pronoun: str, verb_ending: str) -> str:
    return f"""
አንተ ኮች ህላዌ (Coach Hilawe) ነህ — በአዲስ አበባ ታዋቂና ተወዳጅ የግል አሰልጣኝ።
የምትመልሰው በቴሌግራም ለሚጽፉልህ ደንበኞች ነው።

ቋንቋ እና ቃና (STRICT VOICE RULES):
1. 100% ንጹህና ተነባቢ ፊደል አማርኛ ብቻ ተጠቀም። ምንም አይነት እንግሊዝኛ ወይም ሌላ ቋንቋ አትቀላቅል።
2. የአዲስ አበባ ወንድማዊ/እህታዊ፣ የቀረበ፣ ቅን፣ ጉልበት ያለው እና የሚያበረታታ ቃና ይኑርህ።
3. ፍፁም የሆነ የጾታ ሰዋሰው ጠብቅ፦
   - የደንበኛው ጾታ፦ {gender}
   - የምትጠራበት መጠሪያ፦ "{vocative}"
   - ተውላጠ ስም፦ "{pronoun}"
   - የግስ ማሰሪያ፦ "{verb_ending}" (ለምሳሌ፦ {vocative} ብትጀምር/ብትጀምሪ፣ እንድትሰራ/እንድትሰሪ)
4. ምንም አይነት ሰው ሰራሽ (robotic) ወይም የቢሮክራሲ ቋንቋ አትጠቀም። ልክ ጂም ውስጥ ፊት ለፊት እንደምታወራው ሰው ሁን።

የሽያጭ ቀመር (CONVERSION BLUEPRINT):
- አንቀጽ 1፦ የጠየቁትን ጥያቄ በቀጥታ በአጭሩና በሙያዊ ብቃት መልስላቸው (1-2 አረፍተ ነገር)።
- አንቀጽ 2፦ ያለ እቅድ በዘፈቀደ መስራት ለውጥ እንደማያመጣ እና የ8-ሳምንት የተዋቀረ እቅድ ለምን እንደሚያስፈልጋቸው አስረዳ።
- አንቀጽ 3፦ አሁኑኑ እንዲጀምሩ አነሳሳቸው (ዋጋው {int(price)} ብር መሆኑንና ከታች ያለውን ቁልፍ ተጭነው መክፈት እንደሚችሉ ንገራቸው)።
- ርዝመት፦ በጣም አጭር ይሁን (ከ 80 እስከ 110 ቃላት ብቻ)።

የእውቀት መሰረት (KNOWLEDGE BASE):
{KNOWLEDGE_CHUNKS}
"""


async def call_gemini_api(prompt: str, system_instruction: str) -> Optional[str]:
    """Calls Gemini REST API with fast aiohttp client and model fallback."""
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
            "maxOutputTokens": 300,
        }
    }

    timeout = aiohttp.ClientTimeout(total=4.5)

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
                            if parts and "text" in parts[0]:
                                text = parts[0]["text"].strip()
                                return text
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


async def generate_coach_reply(query: str, user: Optional[Dict[str, Any]] = None, price: float = 949.0) -> str:
    """
    Generates a localized, high-converting Addis-native response from Coach Hilawe.
    Falls back gracefully to Support Bot on errors.
    """
    user = user or {}
    first_name = user.get("full_name") or user.get("first_name") or ""
    gender = (user.get("gender") or "MALE").upper()
    goal = user.get("goal") or "ሰውነትህን መቀየር"

    # Human support request detection
    lower_query = query.lower()
    support_keywords = [
        "support", "admin", "ስልክ", "ሰው ማናገር", "ደውሉልኝ", "ኮል", 
        "ማውራት እፈልጋለሁ", "አናግረኝ", "help desk", "ስልክ ቁጥር"
    ]
    if any(k in lower_query for k in support_keywords):
        vocative = "እህቴ" if gender == "FEMALE" else "ወንድሜ"
        return (
            f"ሠላም {vocative}! እኔን ወይም የድጋፍ ቡድናችንን በቀጥታ ማናገር ከፈለግክ/ሽ "
            f"እዚህ አናግረን፦ @{settings.SUPPORT_BOT_USERNAME} 🙏\n\n"
            f"ስለ ፕሮግራሙ ተጨማሪ ጥያቄ ካለህ/ሽ እኔው እመልስልሃለሁ/ሻለሁ!"
        )

    # Conjugation helpers
    if gender == "FEMALE":
        vocative = f"እህቴ {first_name}".strip() if first_name else "እህቴ"
        pronoun = "አንቺ"
        verb_ending = "እንድትሰሪ / ብትጀምሪ / ልታሳኪ"
    else:
        vocative = f"ወንድሜ {first_name}".strip() if first_name else "ወንድሜ"
        pronoun = "አንተ"
        verb_ending = "እንድትሰራ / ብትጀምር / ልታሳካ"

    system_instruction = _build_system_instruction(
        gender=gender,
        first_name=first_name,
        price=price,
        vocative=vocative,
        pronoun=pronoun,
        verb_ending=verb_ending
    )

    user_context = (
        f"የደንበኛው ስም፦ {first_name or 'አልተገለጸም'}\n"
        f"ዋና አላማው፦ {goal}\n"
        f"ወቅታዊ ዋጋ፦ {int(price)} ብር\n"
        f"የደንበኛው ጥያቄ፦ \"{query}\""
    )

    ai_text = await call_gemini_api(prompt=user_context, system_instruction=system_instruction)

    if ai_text:
        return ai_text

    # Resilient fallback if AI is down or network blip
    fallback_voc = "እህቴ" if gender == "FEMALE" else "ወንድሜ"
    return (
        f"ሠላም {fallback_voc}! ጥያቄህ/ሽ ደርሶኛል።\n\n"
        f"ሰውነትህን/ሽን ለመቀየር የወሰንከው/ሽው ውሳኔ ትክክለኛ ነው፤ "
        f"የ8-ሳምንት የተሟላ ስልጠናና የምግብ እቅድህን/ሽን አዘጋጅቼ ጨርሻለሁ። "
        f"አሁን ከታች ያለውን ቁልፍ ተጭነህ/ሽ ፕሮግራምህን/ሽን ክፈትና ዛሬውኑ እንጀምር! 🔥\n\n"
        f"ተጨማሪ አስቸኳይ ጥያቄ ካለህ/ሽ በቀጥታ እዚህ አናግረኝ፦ @{settings.SUPPORT_BOT_USERNAME}"
    )
