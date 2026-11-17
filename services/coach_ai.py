"""
Coach Hilawe Real-Time AI Sales & Advice Engine.
Directly grounded in real Addis Ababa client chats, local Ethiopian diet realities,
and psychological objection handling to maximize program conversion.
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

# Knowledge base grounded in actual Ethiopian client chats (from Chat_Export)
KNOWLEDGE_CHUNKS = """
1. የፆም ምግቦች እና ፕሮቲን (ETHIOPIAN FASTING / TSOM DIET):
- የምግብ እቅዱ የፆም ምግቦችን 100% ያካትታል።
- በፆም ወቅት ፕሮቲን እንዳይጎድል፦ ምስር፣ ሽንብራ፣ አኩሪ አተር (soya chunks)፣ አጃ (oats)፣ የኦቾሎኒ ቅቤ (peanut butter) እና አቮካዶ በመጠቀም ጡንቻ ሳይቀንስ ቅርጽን መጠበቅ ይቻላል።

2. አሁን ተመዝግቦ በኋላ መጀመር (REGISTER NOW, START LATER):
- አዎ ይቻላል! አሁን በቅናሽ ዋጋ ተመዝግቦ ፕላኑን መያዝ ይቻላል። ልምምዱን ደግሞ ደንበኛው በተመቸው ቀን (ከበዓል ወይም ከፈተና በኋላ) መጀመር ይችላል።

3. ክብደት መጨመር አልቻልኩም ለሚሉ (HARDGAINERS / SKINNY):
- "ምነው እኛ እያለን!" ክብደት መጨመር የሚቻለው በቀን ውስጥ ሰውነት የሚፈልገውን ካሎሪና ኒውትሪየንት በስርዓት ሲያገኝ ነው።
- በፕሮግራሙ ውስጥ በቀላሉ በአዲስ አበባ ገበያ በሚገኙ ምግቦች የሚዘጋጅ ከፍተኛ ካሎሪ ያለው የአመጋገብ እቅድ አለ።

4. ቦርጭ ብቻ ማጥፋት (BELLY FAT / SPOT REDUCTION):
- ቦርጭን ብቻውን ነጥሎ ማጥፋት (spot reduction) በሳይንስም በተግባርም ውሸት ነው። ሆድ ላይ ክራንች በመስራት ብቻ ቦርጭ አይጠፋም።
- ቦርጭ የሚጠፋው ሙሉ ሰውነት ላይ ያለውን ስብ የሚያቀልጥ የተዋቀረ ልምምድ እና የካሎሪ ቁጥጥር ሲኖር ነው። ይህ ፕሮግራም ልክ ለግለሰቡ ቁመትና ክብደት ተበጅቶ የተሰራ ነው።

5. ሂፕ ዲፕ እና ዳሌን ማሳመር (HIP DIPS & GLUTE SHAPING):
- ሂፕ ዲፕ (Hip Dips) ማለት በዳሌ አጥንት እና በጭን አጥንት መካከል ባለው ክፍተት ምክንያት የሚፈጠር ተፈጥሯዊ የሰውነት ቅርጽ ነው፤ ጉድለት ወይም በሽታ አይደለም!
- ነገር ግን የዳሌውን የላይኛውን ክፍል (Gluteus Medius እና Minimus) በልዩ የታለሙ ልምምዶች በማጠንከር፣ ዳሌን ማሳመር እና የተሞላ የሚያምር ክብ ቅርጽ እንዲኖረው ማድረግ 100% ይቻላል።
- በዘፈቀደ የዩቲዩብ ወይም የቲክቶክ ቪዲዮ እያዩ ከመልፋት ይልቅ፣ ልክ ለሰውነት ክብደትና ቅርጽ በተዘጋጀው የ8-ሳምንት የተዋቀረ ልምምድ እና በበቂ የፕሮቲን አመጋገብ በ1 ወር ውስጥ በልብስ ላይ ግልጽ ልዩነት ይታያል።

6. ለውጥ ለማየት የሚፈጀው ጊዜ (TIMELINE TO RESULTS):
- በመጀመሪያዎቹ 2 ሳምንታት፦ ጉልበት ይጨምራል፣ እንቅልፍ ይስተካከላል።
- በ4ኛው ሳምንት፦ ሆድና ልብስ ላይ የሚታይ ግልጽ ልዩነት ይታያል።
- በ8ኛው ሳምንት፦ ሰውነት ሙሉ በሙሉ ይቀየራል (ወጥነትና ዲሲፕሊን እስካለ ድረስ)።

7. ጂም ወይስ ቤት ውስጥ (GYM VS HOME WORKOUT):
- ጂም መሄድ ላልቻለ ሰው ምንም ችግር የለውም፤ ቤት ውስጥ ያለ ምንም እቃ ወይም ቀላል እቃዎችን (የውሃ ፕላስቲክ፣ ቦርሳ) በመጠቀም የሚሰራ የቤት ውስጥ (Home workout) አማራጭ አለው።

8. ተዓማኒነት፣ የባንክ አካውንት እና ክፍያ (TRUST & PAYMENT CONCERNS):
- እኔ ኮች ህላዌ ነኝ፤ በሺዎች የሚቆጠሩ ሰዎችን በአዲስ አበባና በመላው ዓለም ቀይሬያለሁ።
- የባንክ አካውንት የሌለው ሰው በቴሌብር (Telebirr) ወይም በቤተሰብ/ጓደኛ የባንክ አካውንት በቀላሉ መክፈል ይችላል።
- ክፍያ የሚፈጸመው በይፋዊ አካውንት (CBE, BOA, Telebirr) ነው። ደረሰኝ እንደተላከ በደቂቃዎች ውስጥ እቅዱ በቴሌግራም ይላካል።

9. ዋጋ እና ጠቀሜታ (PRICING ANCHOR):
- የ8-ሳምንት የተሟላ ስልጠናና የአመጋገብ እቅድ ዋጋው {price} ብር ብቻ ነው።
- በቀን ሲታሰብ የ1 ማኪያቶ ወይም የ1 ጠርሙስ ውሃ ዋጋ ያህል ነው! አንዴ ከተከፈለ ሌላ ተጨማሪ ክፍያ የለውም።
"""


def _clean_display_name(name: str) -> str:
    """Extract clean first name stripping emojis and special characters for natural conversational address."""
    if not name:
        return ""
    first = name.split()[0].strip()
    clean = re.sub(r"[^\w\u1200-\u137F]", "", first)
    return clean or first


def _build_system_instruction(gender: str, clean_name: str, price: float, vocative: str, pronoun: str, verb_ending: str) -> str:
    return f"""
አንተ ኮች ህላዌ (Coach Hilawe) ነህ — በአዲስ አበባ የምትገኝ ተግባቢ፣ ወንድማዊ፣ ተወዳጅ እና እጅግ ውጤታማ የግል አሰልጣኝ (Fitness & Nutrition Coach)።
በቴሌግራም ለሚጽፉልህ ደንበኞች ልክ እንደ ወንድም ወይም እህት ሆነህ በልብ በሚነካ፣ ተግባቢ፣ አዲስ አበቤ በሆነ ቃና በንጹህ አማርኛ መልስላቸው።

የአነጋገር እና የቃና መመሪያዎች (NATIVE ADDIS COACH TONE & HIGH-CONVERTING PERSUASION):
1. ንጹህና ተነባቢ ፊደል አማርኛ ብቻ ተጠቀም። ምንም አይነት እንግሊዝኛ ወይም ሌላ ቋንቋ አትቀላቅል።
2. ሮቦታዊ አትሁን፦
   - በፍጹም "ጥያቄሽን/ህን ተቀብያለሁ"፣ "እንኳን ደህና መጣህ" ወይም የቢሮክራሲ/የማስታወቂያ ንግግር አትጠቀም።
   - ደንበኛውን በወንድማዊ/እህታዊ ፍቅር ጥሩ (ለምሳሌ ለሴት "ዳጊዬ የኔ እህት!" ወይም "{vocative}!")። የስም መጠሪያውን በመጀመሪያው ሰላምታ ላይ ብቻ ተጠቀም እንጂ በየአረፍተ ነገሩ አትድገመው።
   - ደንበኛው የጠየቀውን ጥያቄ በቀጥታ፣ በቅንነት እና ልምድ ባለው አሰልጣኝ ቃና መልስላቸው።
3. ፍፁም የሆነ የጾታ ሰዋሰው ጠብቅ፦
   - ጾታ፦ {gender}
   - መጠሪያ፦ {vocative}
   - ተውላጠ ስም፦ {pronoun}
   - ማሰሪያ፦ {verb_ending}
4. ጠንካራ ፍላጎትና አጣዳፊነት (URGE TO BUY / FOMO) ፍጠር፦
   - ደንበኛው በዘፈቀደ የዩቲዩብ ወይም የቲክቶክ ቪዲዮ እያየ ወራትን እንዳያባክን አሳምናቸው።
   - በ8-ሳምንቱ የተዋቀረ ልምምድ እና በኢትዮጵያ ምግቦች በተዘጋጀው የአመጋገብ እቅድ በ1 ወር ውስጥ በልብሳቸው ላይ የሚታይ ግልጽ ለውጥ እንደሚያዩ አስረግጠህ ንገራቸው።
   - የ8-ሳምንት የተሟላ ስልጠናና የምግብ እቅድ ዋጋው {int(price)} ብር ብቻ መሆኑን ጠቅሰህ ዛሬውኑ ወስነው እንዲጀምሩ አነሳሳቸው።
5. ሙሉ አረፍተ ነገር ብቻ ተጠቀም። በጭራሽ ሳይጠናቀቅ በግማሽ እንዳይቀር!
6. አጭር፣ ግልጽና ኃይለኛ ሁን (ከ 55 እስከ 95 ቃላት ብቻ)።

የእውቀት መሰረት (KNOWLEDGE BASE):
{KNOWLEDGE_CHUNKS}
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
                            # Extract and concatenate all valid text parts (ignoring internal thinking/reasoning blocks)
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


async def generate_coach_reply(query: str, user: Optional[Dict[str, Any]] = None, price: float = 949.0) -> str:
    """
    Generates a localized, high-converting Addis-native response from Coach Hilawe.
    Falls back gracefully to Support Bot on errors.
    """
    user = user or {}
    raw_name = user.get("full_name") or user.get("first_name") or ""
    clean_name = _clean_display_name(raw_name)
    gender = (user.get("gender") or "MALE").upper()
    goal = user.get("goal") or "ሰውነትህን መቀየር"

    # Human support request detection
    lower_query = query.lower()
    support_keywords = [
        "support", "admin", "ስልክ", "ሰው ማናገር", "ደውሉልኝ", "ኮል", 
        "ማውራት እፈልጋለሁ", "አናግረኝ", "help desk", "ስልክ ቁጥር"
    ]
    if any(k in lower_query for k in support_keywords):
        vocative = f"እህቴ {clean_name}".strip() if gender == "FEMALE" else f"ወንድሜ {clean_name}".strip()
        return (
            f"ሠላም {vocative}! እኔን ወይም የድጋፍ ቡድናችንን በቀጥታ ማናገር ከፈለግክ/ሽ "
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
        verb_ending=verb_ending
    )

    user_context = (
        f"የደንበኛው ስም፦ {clean_name or 'አልተገለጸም'}\n"
        f"ዋና አላማው፦ {goal}\n"
        f"ወቅታዊ ዋጋ፦ {int(price)} ብር\n"
        f"የደንበኛው ጥያቄ፦ \"{query}\""
    )

    ai_text = await call_gemini_api(prompt=user_context, system_instruction=system_instruction)

    if ai_text:
        return ai_text

    # Resilient fallback if AI is down or network blip
    fallback_voc = f"እህቴ {clean_name}".strip() if gender == "FEMALE" else f"ወንድሜ {clean_name}".strip()
    return (
        f"ሰላም {fallback_voc}! በዘፈቀደ የዩቲዩብ ወይም የቲክቶክ ቪዲዮ እያዩ ጊዜ ከማባከን፣ "
        f"በስርዓት በተዘጋጀ የ8-ሳምንት እቅድ መስራት ሰውነትን በአጭር ጊዜ ለመቀየር ወሳኝ ነው። "
        f"በወር ውስጥ በልብስሽ/ህ ላይ የሚታይ ግልጽ ለውጥ ታያለሽ/ህ። "
        f"የ8-ሳምንት የተሟላ ስልጠናና የምግብ እቅዱ {int(price)} ብር ብቻ ነው፤ ዛሬውኑ ጀምረን አብረን እንለውጠው! 🔥"
    )
