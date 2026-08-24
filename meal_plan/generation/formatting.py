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


def familiar_portion(multiplier: float, familiar_measure: str | None) -> str:
    clean=re.sub(r"^about\s+","",str(familiar_measure or "standard portion").strip(),flags=re.I)
    m=re.match(r"^(\d+(?:\.\d+)?|\d+/\d+)\s+(.+)$",clean)
    if not m:
        return f"about {quarter_text(multiplier)} of {clean}"
    qty=max(0.25,round(_fraction_num(m.group(1))*multiplier*4)/4)
    return f"about {quarter_text(qty)} {m.group(2)}"


def grams_text(grams: float) -> str:
    return f"{round(grams):,} g"
