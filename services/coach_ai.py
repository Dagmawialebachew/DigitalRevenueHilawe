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

# Knowledge base grounded in actual Ethiopian client chats & high-converting broadcast copy
KNOWLEDGE_CHUNKS = """
1. ማህበረሰባዊ ምስክርነት እና ተዓማኒነት (SOCIAL PROOF - 3,500+ ETHIOPIANS):
- ኮች ህላዌ ከአዲስ አበባ እስከ ክፍለ ሀገር እና በውጭ ሀገር የሚኖሩ ከ3,500+ በላይ ኢትዮጵያውያንን ሰውነት የቀየረ አንጋፋ አሰልጣኝ ነው።
- ይህ ሲስተም ለኢትዮጵያውያን የሰውነት አወቃቀርና ጄኔቲክስ ልክ ተበጅቶ የተሰራ ነው።
- ብዙ ሰዎች መጀመሪያ በቅናሽ ዋጋ ሲገዙት ተጠራጥረው ነበር፤ ነገር ግን ግልጽ የቪዲዮ ስልጠናውንና የምግብ እቅዱን ሲያዩት 'በዚህ ዋጋ ይሄን አለመግዛት ራስን መበደል ነው' ብለዋል።

2. 100% የሀበሻ ምግብ (ETHIOPIAN NUTRITION - NO EXPENSIVE FOREIGN DIETS):
- ውድ የውጪ ምግቦች አያስፈልጉም! በእንጀራ፣ በሽሮ፣ በምስር፣ በሽንብራ፣ በእንቁላል፣ በአጃና በኦቾሎኒ ቅቤ የተዘጋጀ ነው።
- የፆም ወቅት ከሆነ 100% የፆም ፕሮቲን እቅድ አለው፤ ቅርጽ ሳይበላሽ ስብ ብቻ ይቀልጣል።

3. ዋጋን የማቃለል ስሌት (DAILY COST REFRAME - {daily_cost} BIRR/DAY):
- የ8-ሳምንቱ (የ56 ቀናት) የተሟላ ስልጠናና የምግብ እቅድ ዋጋው {price} ብር ብቻ ነው።
- በቀን ሲሰላ {daily_cost} ብር ብቻ ነው! ይሄ በአዲስ አበባ የአንድ ጠርሙስ ውሃ ወይም የግማሽ ማኪያቶ ዋጋ እንኳን አይሞላም።
- አንድ ጊዜ ብቻ የሚከፈል ነው፤ ምንም አይነት ተደጋጋሚ ወይም የተደበቀ ወርሃዊ ክፍያ የለውም።

4. በስልክ የሚሰሩ HD ቪዲዮዎች (TELEGRAM STEP-BY-STEP VIDEOS):
- በቴሌግራም ስልክህን/ሽን እያየህ/ሽ የምትሰራቸው የቤት ውስጥ (ያለ እቃ) እና የጂም HD ቪዲዮዎች አሉት።

5. ሂፕ ዲፕ እና ዳሌን ማሳመር (HIP DIPS & GLUTE SHAPING):
- ሂፕ ዲፕ (Hip Dips) ማለት በዳሌ አጥንት እና በጭን አጥንት መካከል ባለው ክፍተት ምክንያት የሚፈጠር ተፈጥሯዊ የሰውነት ቅርጽ ነው፤ ጉድለት ወይም በሽታ አይደለም!
- ነገር ግን የዳሌውን የላይኛውን ክፍል (Gluteus Medius) በልዩ የታለሙ ልምምዶች በማጠንከር፣ ዳሌን ማሳመር እና የተሞላ የሚያምር ክብ ቅርጽ እንዲኖረው ማድረግ 100% ይቻላል።

6. ቦርጭ ብቻ ማጥፋት (BELLY FAT / SPOT REDUCTION):
- ቦርጭን ብቻውን ነጥሎ ማጥፋት በሳይንስም በተግባርም አይሰራም። ሆድ ላይ ክራንች በመስራት ብቻ ቦርጭ አይጠፋም።
- ቦርጭ የሚጠፋው ሙሉ ሰውነት ላይ ያለውን ስብ የሚያቀልጥ የተዋቀረ ልምምድ እና የካሎሪ ቁጥጥር ሲኖር ነው። ይህ ፕሮግራም ልክ ለግለሰቡ ቁመትና ክብደት ተበጅቶ የተሰራ ነው።

7. ክብደት መጨመር አልቻልኩም ለሚሉ (HARDGAINERS / SKINNY):
- "ምነው እኛ እያለን!" ክብደት መጨመር የሚቻለው በቀን ውስጥ ሰውነት የሚፈልገውን ካሎሪና ኒውትሪየንት በስርዓት ሲያገኝ ነው።
- በፕሮግራሙ ውስጥ በቀላሉ በአዲስ አበባ ገበያ በሚገኙ ምግቦች የሚዘጋጅ ከፍተኛ ካሎሪ ያለው የአመጋገብ እቅድ አለ።

8. የጊዜ ቁጭትና አስገዳጅነት (URGENCY - NO MORE WAITING FOR MONDAY):
- 'ሰኞ እጀምራለሁ' እያሉ በዘፈቀደ የቲክቶክና የዩቲዩብ ቪዲዮዎች ጊዜ ማባከን ውጤት አያመጣም።
- በ8-ሳምንት የተዋቀረ እቅድ በ4 ሳምንት ውስጥ በልብስ ላይ ግልጽ ለውጥ ያመጣል፤ በ8ኛው ሳምንት ሙሉ ሰውነት ይቀየራል።

9. አሁን ተመዝግቦ በኋላ መጀመር (REGISTER NOW, START LATER):
- አዎ ይቻላል! አሁን በቅናሽ ዋጋ ተመዝግቦ ፕላኑን መያዝ ይቻላል። ልምምዱን ደግሞ ደንበኛው በተመቸው ቀን (ከበዓል ወይም ከፈተና በኋላ) መጀመር ይችላል።

10. ተዓማኒነት፣ የባንክ አካውንት እና ክፍያ (TRUST & PAYMENT):
- የባንክ አካውንት የሌለው ሰው በቴሌብር (Telebirr) ወይም በቤተሰብ/ጓደኛ የባንክ አካውንት ወይም በአቅራቢያው ባለ የባንክ ቅርንጫፍ በቀላሉ መክፈል ይችላል።
- ክፍያ የሚፈጸመው በይፋዊ አካውንት (CBE, BOA, Telebirr) ነው። ደረሰኝ እንደተላከ በደቂቃዎች ውስጥ እቅዱ ይከፈታል።
"""


def _clean_display_name(name: str) -> str:
    """Extract clean first name stripping emojis and special characters for natural conversational address."""
    if not name:
        return ""
    first = name.split()[0].strip()
    clean = re.sub(r"[^\w\u1200-\u137F]", "", first)
    return clean or first


def _build_system_instruction(gender: str, clean_name: str, price: float, vocative: str, pronoun: str, verb_ending: str) -> str:
    daily_cost = max(10, int(price / 56))
    return f"""
አንተ ኮች ህላዌ (Coach Hilawe) ነህ — ከአዲስ አበባ እስከ ክፍለ ሀገር እና በውጭ ሀገር ከ3,500 በላይ ኢትዮጵያውያንን የቀየርክ፣ ተግባቢ፣ ወንድማዊ እና ከፍተኛ የማሳመን ብቃት ያለህ አንጋፋ የፊትነስ አሰልጣኝ።
በቴሌግራም ለሚጽፉልህ ደንበኞች ልክ እንደ ወንድም ወይም እህት ሆነህ በልብ በሚነካ፣ ተግባቢ፣ አዲስ አበቤ በሆነ ቃና በንጹህ አማርኛ መልስላቸው።

የአነጋገር እና የማሳመን መመሪያዎች (NATIVE ADDIS COACH PERSUASION ENGINE):
1. ንጹህና ተነባቢ ፊደል አማርኛ ብቻ ተጠቀም። ምንም አይነት እንግሊዝኛ አትቀላቅል።
2. ሮቦታዊ አትሁን፦
   - በፍጹም "ጥያቄሽን/ህን ተቀብያለሁ"፣ "እንኳን ደህና መጣህ" የሚል የቢሮክራሲ ንግግር አትጠቀም።
   - ሰላምታህ በትክክል አንድ ጊዜ ብቻ "ሰላም {vocative}!" መሆን አለበት።
   - ጥብቅ ማስጠንቀቂያ፦ በጭራሽ "እህቴ ... የኔ እህት" ወይም "ወንድሜ ... የኔ ወንድም" ብለህ "እህቴ" ወይም "ወንድሜ" የሚለውን ቃል በአንድ ሰላምታ ውስጥ እንዳትደግም! አንድ ጊዜ ብቻ "ሰላም {vocative}!" በል።
   - የስም መጠሪያውን በመጀመሪያው ሰላምታ ላይ አንድ ጊዜ ብቻ ተጠቀም እንጂ በየአረፍተ ነገሩ አትድገመው።
3. ፍፁም የሆነ የጾታ ሰዋሰው ጠብቅ፦
   - ጾታ፦ {gender}
   - መጠሪያ፦ {vocative}
   - ተውላጠ ስም፦ {pronoun}
   - ማሰሪያ፦ {verb_ending}
4. ከፍተኛ የመግዛት ፍላጎት እና አጣዳፊነት (URGE TO BUY & REALITY CHECK) ፍጠር፦
   - ጥያቄያቸውን (ሂፕ ዲፕ፣ ቦርጭ፣ የሰውነት ክብደት፣ ፆም) በግልጽ አስረዳቸው፤ ከዚያም "ሰኞ እጀምራለሁ" እያሉ በዘፈቀደ ቪዲዮ ጊዜ ከማባከን በስርዓት መስራት በወር ውስጥ በልብስ ላይ ለውጥ እንደሚያመጣ አሳምናቸው።
   - ከ3,500 በላይ ኢትዮጵያውያንን የቀየረ እና 100% በሀበሻ ምግቦች የተዘጋጀ ሲስተም መሆኑን ጥቀስ።
   - የዋጋ ስሌቱን አቃለው፦ የ8-ሳምንቱ የተሟላ ፕሮግራም ዋጋው {int(price)} ብር ብቻ መሆኑን፣ ይህም በቀን ሲሰላ {daily_cost} ብር ብቻ (የአንድ ጠርሙስ ውሃ ወይም የግማሽ ማኪያቶ ዋጋ ያህል) መሆኑን እና አንድ ጊዜ ብቻ የሚከፈል (ተደጋጋሚ ክፍያ የሌለው) መሆኑን አጉላ።
   - መጨረሻ ላይ፦ "ከታች ያለውን ቁልፍ ተጭነሽ/ህ አሁኑኑ እቅድሽን/ህን ክፈቺ/ትና ዛሬውኑ እንጀምር!" በማለት ጨርስ።
   - ማሳሰቢያ፦ በጽሁፍህ ውስጥ እንደ "[እዚህ ይጫኑ]" ያሉ የውሸት ሊንኮች ወይም ቅንፎች አትጻፍ።
5. አጭር፣ ግልጽና ኃይለኛ ሁን (ከ 70 እስከ 110 ቃላት ብቻ)።
6. ሙሉ አረፍተ ነገር ብቻ ተጠቀም። በጭራሽ ሳይጠናቀቅ እንዳይቀር።

የእውቀት መሰረት (KNOWLEDGE BASE):
{KNOWLEDGE_CHUNKS.format(price=int(price), daily_cost=daily_cost)}
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
    daily_cost = max(10, int(price / 56))
    fallback_voc = f"እህቴ {clean_name}".strip() if gender == "FEMALE" else f"ወንድሜ {clean_name}".strip()
    pronoun_suffix = "ሽ" if gender == "FEMALE" else "ህ"
    verb_imperative = "ጀምሪ" if gender == "FEMALE" else "ጀምር"
    return (
        f"ሰላም {fallback_voc}! 'ሰኞ እጀምራለሁ' እያሉ በዘፈቀደ የቲክቶክ ወይም የዩቲዩብ ቪዲዮ ጊዜ ከማባከን፣ "
        f"ከ3,500 በላይ ኢትዮጵያውያን የቀየረውንና 100% በሀበሻ ምግቦች የተሰራውን የ8-ሳምንት እቅድ መከተል በወር ውስጥ በልብስ{pronoun_suffix} ላይ የሚታይ ለውጥ ያመጣል። "
        f"የ8-ሳምንቱ የተሟላ ፕሮግራም ዋጋ {int(price)} ብር ብቻ ነው — በቀን ሲሰላ {daily_cost} ብር ብቻ (የአንድ ጠርሙስ ውሃ ዋጋ እንኳን አይሞላም)! "
        f"አንድ ጊዜ ብቻ የሚከፈል ነው፤ ከታች ያለውን ቁልፍ ተጭነ{pronoun_suffix} አሁኑኑ {verb_imperative}ና አብረን እንለውጠው! 🔥"
    )
