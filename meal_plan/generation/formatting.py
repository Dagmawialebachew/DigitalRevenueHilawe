from __future__ import annotations

import math
import re
from typing import Any


def n(value: Any) -> float:
    try: return float(value or 0)
    except (TypeError, ValueError): return 0.0


def quarter_text(value: float) -> str:
    rounded=max(0.25,round(float(value)*4)/4)
    whole=int(math.floor(rounded+1e-8))
    frac=round((rounded-whole)*4)
    glyph={1:"¼",2:"½",3:"¾"}.get(frac,"")
    if whole and glyph: return f"{whole} {glyph}"
    if whole: return str(whole)
    return glyph or "¼"


def _fraction_num(text: str) -> float:
    if "/" in text:
        a,b=text.split("/",1)
        try:return float(a)/float(b)
        except (ValueError,ZeroDivisionError):return 0
    try:return float(text)
    except ValueError:return 0


MEASURE_DICT_AM: dict[str, str] = {
    "large bowl": "ትልቅ ጎድጓዳ ሳህን",
    "medium bowl": "መካከለኛ ጎድጓዳ ሳህን",
    "bowl": "ጎድጓዳ ሳህን",
    "large glass": "ትልቅ ብርጭቆ",
    "glass": "ብርጭቆ",
    "large cup": "ትልቅ ሲኒ",
    "cup cooked": "ሲኒ የበሰለ",
    "cups rehydrated": "ሲኒ የበሰለ/የረጠበ",
    "cup dry": "ሲኒ ጥሬ",
    "cup flour": "ሲኒ ዱቄት",
    "cup powder": "ሲኒ ዱቄት",
    "cup pieces": "ሲኒ የተከተፈ",
    "cups pieces": "ሲኒ የተከተፈ",
    "cups shredded": "ሲኒ የተፈጨ/የተከተፈ",
    "cups": "ሲኒ",
    "cup": "ሲኒ",
    "level tablespoons": "የተስተካከለ የሾርባ ማንኪያ",
    "level tablespoon": "የተስተካከለ የሾርባ ማንኪያ",
    "tablespoons": "የሾርባ ማንኪያ",
    "tablespoon": "የሾርባ ማንኪያ",
    "level teaspoon": "የተስተካከለ የሻይ ማንኪያ",
    "teaspoon": "የሻይ ማንኪያ",
    "just under 1 teaspoon": "ከ1 የሻይ ማንኪያ በትንሹ ያነሰ",
    "large slice": "ትልቅ ቁራጭ",
    "medium slice": "መካከለኛ ቁራጭ",
    "slice": "ቁራጭ",
    "slices": "ቁራጭ",
    "medium rolled piece": "መካከለኛ የተጠቀለለ እንጀራ",
    "large piece": "ትልቅ ቁራጭ",
    "medium piece": "መካከለኛ ቁራጭ",
    "piece": "ቁራጭ",
    "pieces": "ቁራጭ",
    "large fillet": "ትልቅ ቁራጭ (ፊሌ)",
    "medium fillet": "መካከለኛ ቁራጭ (ፊሌ)",
    "fillet": "ቁራጭ (ፊሌ)",
    "large thigh portion": "ትልቅ የጭን ስጋ ቁራጭ",
    "large eggs": "ትላልቅ እንቁላል",
    "large egg whites": "ትላልቅ የእንቁላል ነጭ ክፍል",
    "small drained can": "አነስተኛ የታሸገ (የተጣራ) ቆርቆሮ",
    "small can": "አነስተኛ ቆርቆሮ",
    "can": "ቆርቆሮ",
    "scoop": "ጭልፋ (ስኩፕ)",
    "small handful": "አነስተኛ ጭብጥ / እፍኝ",
    "thin cakes": "ቀጭን የሩዝ ኬክ (ክራከር)",
    "standard block": "መደበኛ የቶፉ ቁራጭ",
    "large carrot": "ትልቅ ካሮት",
    "large clove": "ትልቅ የነጭ ሽንኩርት ፍንካች",
    "large orange": "ትልቅ ብርቱካን",
    "large peach": "ትልቅ ኮክ",
    "large pepper": "ትልቅ ቃሪያ",
    "large tomato": "ትልቅ ቲማቲም",
    "medium apple": "መካከለኛ ፖም (አፕል)",
    "medium banana": "መካከለኛ ሙዝ",
    "medium bottle": "መካከለኛ ጠርሙስ",
    "medium cob": "መካከለኛ የበቆሎ ዛላ",
    "medium onion": "መካከለኛ ቀይ ሽንኩርት",
    "medium pear": "መካከለኛ ፒር (አንኮይ)",
    "medium wrap": "መካከለኛ ጥቅል ቶርቲላ",
    "medium cucumber": "መካከለኛ ኪያር",
    "large avocado": "ትልቅ አቮካዶ",
    "medium guavas": "መካከለኛ ዘይቱን",
    "medium potatoes": "መካከለኛ ድንች",
    "large dates": "ትላልቅ ቴምር",
    "palm-and-a-half": "የእጅ መዳፍ",
    "palms": "የእጅ መዳፍ",
    "palm": "የእጅ መዳፍ",
    "palm portion": "የእጅ መዳፍ የሚያህል",
    "palm size": "የእጅ መዳፍ የሚያህል",
    "medium ladle": "መካከለኛ ጭልፋ",
    "ladle": "ጭልፋ",
    "small bowl": "አነስተኛ ሳህን",
    "medium bowl": "መካከለኛ ሳህን",
    "medium tuber": "መካከለኛ ፍሬ",
    "standard portion": "መካከለኛ ጭልፋ",
    "medium serving": "መካከለኛ ጭልፋ",
    "egg whites": "የተቀቀለ የእንቁላል ነጭ",
    "egg white": "የተቀቀለ የእንቁላል ነጭ",
    "medium injera": "መካከለኛ እንጀራ",
    "injera": "እንጀራ",
    "1/3 medium injera": "ሲሶ (1/3) መካከለኛ እንጀራ",
    "1/3-1/2 block": "ግማሽ የቶፉ ቁራጭ",
    "1/3--1/2 block": "ግማሽ የቶፉ ቁራጭ",
    "block": "የቶፉ ቁራጭ",
}


def _translate_measure_phrase_am(phrase: str) -> str:
    cleaned = phrase.strip().lower()
    if cleaned in MEASURE_DICT_AM:
        return MEASURE_DICT_AM[cleaned]
    for k in sorted(MEASURE_DICT_AM.keys(), key=len, reverse=True):
        if k in cleaned:
            return MEASURE_DICT_AM[k]
    return cleaned


def quarter_text_am(value: float) -> str:
    rounded = max(0.25, round(float(value) * 4) / 4)
    whole = int(math.floor(rounded + 1e-8))
    frac = round((rounded - whole) * 4)
    if frac == 0:
        return str(whole) if whole else "1"
    if whole == 0:
        return {1: "ሩብ", 2: "ግማሽ", 3: "ሶስት አራተኛ"}.get(frac, "ግማሽ")
    return {1: f"{whole} ከሩብ", 2: f"{whole} ከግማሽ", 3: f"{whole} ከሶስት አራተኛ"}.get(frac, str(whole))


_GLYPH_VALS = {"¼": 0.25, "½": 0.5, "¾": 0.75}


def _parse_portion_string(text: str) -> tuple[float, str]:
    clean = re.sub(r"^(about|በግምት)\s+", "", text, flags=re.I).strip()
    if "palm-and-a-half" in clean.lower():
        return 1.5, "palm"
    m = re.match(r"^(\d+)?\s*([¼½¾]|\d+/\d+)?\s*(.+)$", clean)
    if m:
        whole = float(m.group(1)) if m.group(1) else 0.0
        frac_str = m.group(2)
        frac = 0.0
        if frac_str:
            if frac_str in _GLYPH_VALS:
                frac = _GLYPH_VALS[frac_str]
            elif "/" in frac_str:
                a, b = frac_str.split("/", 1)
                try:
                    frac = float(a) / float(b)
                except (ValueError, ZeroDivisionError):
                    frac = 0.0
        val = whole + frac if (whole or frac) else 1.0
        unit = m.group(3).strip()
        return val, unit
    return 1.0, clean


def familiar_portion(multiplier: float, familiar_measure: str | None, language: str = "EN") -> str:
    raw = str(familiar_measure or "medium ladle").strip()
    is_am = str(language).upper() == "AM"
    if is_am:
        # Pre-process known quirky strings and ranges directly
        if re.search(r"1\s*/\s*3\s*-+\s*1\s*/\s*2\s*block", raw, flags=re.I):
            return "በግምት ግማሽ የቶፉ ቁራጭ"
        if re.search(r"1\s*/\s*3\s*medium\s*injera", raw, flags=re.I):
            return "በግምት ሲሶ (1/3) መካከለኛ እንጀራ"
        if raw.startswith("በግምት "):
            raw = raw[len("በግምት "):].strip()
    elif raw.startswith("about "):
        raw = raw[len("about "):].strip()

    base_qty, unit = _parse_portion_string(raw)
    total_qty = max(0.25, round(base_qty * multiplier * 4) / 4)
    if is_am:
        trans_unit = _translate_measure_phrase_am(unit)
        qty_text = quarter_text_am(total_qty)
        if trans_unit.startswith(qty_text):
            trans_unit = trans_unit[len(qty_text):].strip()
        res = f"በግምት {qty_text} {trans_unit}".strip()
        # Clean up any duplicated phrases like '1 ከግማሽ 1 ከግማሽ'
        res = re.sub(r"\b(1 ከግማሽ|ግማሽ|ሩብ|ሲሶ)\s+\1\b", r"\1", res)
        if " ዝ" in res:
            res = res.replace(" ዝ", " ሙዝ")
        return res
    return f"about {quarter_text(total_qty)} {unit}"


def grams_text(grams: float, language: str = "EN") -> str:
    val = f"{round(grams):,}"
    if str(language).upper() == "AM":
        return f"{val} ግ"
    return f"{val} g"

