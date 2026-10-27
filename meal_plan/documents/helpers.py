from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from meal_plan.generation.dataset import load_dataset


def safe_slug(value: str, fallback: str = "CLIENT") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value).strip()).strip("-")
    return (cleaned or fallback)[:48]


def artifact_basename(plan_public_id: str, client_name: str, version_number: int) -> str:
    plan = safe_slug(plan_public_id, "PLAN")
    client = safe_slug(client_name, "CLIENT")
    return f"{plan}-{client}-V{int(version_number)}"


def client_artifact_filename(
    client_name: str,
    duration_days: int,
    version_number: int,
    ext: str = "pdf",
    unique_id: str | None = None,
) -> str:
    cleaned_name = re.sub(r"[^\w]+", "_", str(client_name).strip()).strip("_")
    safe_name = cleaned_name or "Client"
    clean_ext = ext.lstrip(".")
    if unique_id:
        uid_slug = re.sub(r"[^\w]+", "", str(unique_id))[:8]
        return f"{safe_name}_የምግብ_እቅድ_{int(duration_days)}_Days_V{int(version_number)}_{uid_slug}.{clean_ext}"
    return f"{safe_name}_የምግብ_እቅድ_{int(duration_days)}_Days_V{int(version_number)}.{clean_ext}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_food_name(food_id: str, default_name: str, language: str) -> str:
    from meal_plan.glossary import get_food_name
    is_am = str(language).upper() == "AM"
    d_lower = str(default_name or "").lower()

    if food_id == "A011" and ("raw" in d_lower or d_lower == "eggs" or "ፍሬ" in d_lower):
        return "እንቁላል" if is_am else "Eggs"
    if food_id == "C010" and ("raw" in d_lower or "ጥሬ" in d_lower):
        return "ድንች (ጥሬ)" if is_am else "Potatoes (Raw)"
    if food_id in ("A001", "A002") and ("raw" in d_lower or "ጥሬ" in d_lower):
        return "የዶሮ ስጋ (ጥሬ)" if is_am else "Chicken breast (Raw)"
    if food_id in ("A003", "A004") and ("raw" in d_lower or "ጥሬ" in d_lower):
        return "የበሬ ስጋ (ጥሬ)" if is_am else "Lean beef (Raw)"
    if food_id == "A007" and ("raw" in d_lower or "ጥሬ" in d_lower):
        return "ጥሬ አሳ (የተጸዳ)" if is_am else "Tilapia fillet (Raw)"
    if food_id == "A015":
        return "ወተት (ዝቅተኛ ቅባት)" if is_am else "Milk, low-fat"

    name = get_food_name(food_id, default_name, language)
    if " ዝ" in name or name.startswith(" ዝ"):
        name = name.replace(" ዝ", "ሙዝ")
    elif name == "ዝ":
        name = "ሙዝ"
    if "ፋል" in name:
        name = name.replace("የጾም ፋል", "የጾም ፉል").replace("ፋል", "ፉል")
    name = name.replace("Coach Hilawe ", "").replace("የአሰልጣኝ ህላዌ ", "").replace("አሰልጣኝ ህላዌ ", "").strip()
    if ("dry" in d_lower or "ጥሬ" in d_lower) and not name.endswith("(ጥሬ)") and not name.endswith("(Dry)") and not name.endswith("(Raw)"):
        name = f"{name} (ጥሬ)" if is_am else f"{name} (Dry)"
    return name


def local_recipe_name(recipe_id: str, default_name: str, language: str) -> str:
    from meal_plan.glossary import get_recipe_name
    name = get_recipe_name(recipe_id, default_name, language)
    if "ፋል" in name:
        name = name.replace("የጾም ፋል", "የጾም ፉል").replace("ፋል", "ፉል")
    name = name.replace("Coach Hilawe ", "").replace("የአሰልጣኝ ህላዌ ", "").replace("አሰልጣኝ ህላዌ ", "").strip()
    return name


def local_template_name(template_id: str, default_name: str, language: str) -> str:
    if template_id == "MN-B04":
        return "Boiled eggs, bread and orange" if str(language).upper().startswith("EN") else "የተቀቀለ እንቁላል ከዳቦ እና ብርቱካን ጋር"
    from meal_plan.glossary import get_template_name
    name = get_template_name(template_id, default_name, language)
    if "ፋል" in name:
        name = name.replace("የጾም ፋል", "የጾም ፉል").replace("ፋል", "ፉል")
    name = name.replace("Coach Hilawe ", "").replace("የአሰልጣኝ ህላዌ ", "").replace("አሰልጣኝ ህላዌ ", "").strip()
    d_lower = str(default_name or "").lower()
    if "soy" not in d_lower and "አኩሪ" not in d_lower and ("milk" in d_lower or "ወተት" in d_lower):
        if "የአኩሪ አተር ወተት" in name:
            name = name.replace("የአኩሪ አተር ወተት", "ወተት")
        if "soy milk" in name.lower():
            name = re.sub(r"soy milk", "milk", name, flags=re.I)
    return name


def local_category_name(category: str, language: str) -> str:
    from meal_plan.glossary import get_category_name
    return get_category_name(category, language)


def sanitize_display_text(text: str) -> str:
    res = str(text or "")
    # Strict boundary fraction replacements: NEVER match integers like 125, 250, etc.
    res = re.sub(r'(?<!\d)1\s*¼(?!\d)', '1.25', res)
    res = re.sub(r'(?<!\d)1\s*½(?!\d)', '1.5', res)
    res = re.sub(r'(?<!\d)1\s*¾(?!\d)', '1.75', res)
    res = re.sub(r'(?<!\d)2\s*½(?!\d)', '2.5', res)
    res = re.sub(r'(?<!\d)3\s*½(?!\d)', '3.5', res)
    res = re.sub(r'(?<!\d)¼(?!\d)', '0.25', res)
    res = re.sub(r'(?<!\d)½(?!\d)', '0.5', res)
    res = re.sub(r'(?<!\d)¾(?!\d)', '0.75', res)
    res = re.sub(r'(?<!\d)⅓(?!\d)', '0.33', res)
    res = re.sub(r'(?<!\d)⅔(?!\d)', '0.67', res)
    res = re.sub(r'(?<!\d)1\s+1/4(?!\d)', '1.25', res)
    res = re.sub(r'(?<!\d)1\s+1/2(?!\d)', '1.5', res)
    res = re.sub(r'(?<!\d)1\s+3/4(?!\d)', '1.75', res)
    res = re.sub(r'(?<!\d)114/2(?!\d)', '0.5', res)
    res = re.sub(r'(?<!\d)4/2(?!\d)', '2', res)
    res = re.sub(r'\b14\.5\s+cups?\b', '1.5 cups', res, flags=re.I)
    # Fix /2 large avocado string glitch
    res = re.sub(r'/2\s+large\s+avocado', 'large avocado', res, flags=re.I)
    res = res.replace("Yoharmes", "Yohannes")
    # Fix typographical/ligature anomalies
    res = re.sub(r'\bDimer\b', 'Dinner', res)
    res = re.sub(r'\bdimer\b', 'dinner', res)
    res = re.sub(r'\bgig\s*ke?al\b', '919 kcal', res, flags=re.I)
    res = re.sub(r'\babout\s+[1I]\s+approx\.?\s*', 'about ', res, flags=re.I)
    res = re.sub(r'\babout\s+approx\.?\s*', 'about ', res, flags=re.I)
    return res


def local_purchase_quantity(quantity: str, language: str) -> str:
    raw = str(quantity or "").strip()
    if str(language).upper() != "AM":
        res = raw.replace("ኪ.ግ", "kg").replace("ግ", "g")
        return sanitize_display_text(res)
    res = re.sub(r"\bkg\s+dry\b", "ኪ.ግ ጥሬ", raw, flags=re.I)
    res = re.sub(r"\bg\s+dry\b", "ግ ጥሬ", res, flags=re.I)
    res = re.sub(r"\bkg\b", "ኪ.ግ", res, flags=re.I)
    res = re.sub(r"\bg\b", "ግ", res, flags=re.I)
    return res


def local_portion(multiplier: float, familiar: str, language: str) -> str:
    from meal_plan.generation.formatting import familiar_portion
    return familiar_portion(multiplier, familiar, language)



def rounded(value: Any, digits: int = 0) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if digits == 0:
        return f"{number:,.0f}"
    return f"{number:,.{digits}f}"


def build_manifest(plan: dict[str, Any], context: Any, artifacts: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "plan_public_id": context.plan_public_id,
        "version_number": context.version_number,
        "language": context.normalized_language,
        "status": context.status,
        "engine_version": plan.get("engine_version"),
        "dataset_version": plan.get("dataset_version"),
        "settings_version": plan.get("settings_version"),
        "artifacts": artifacts,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def local_warning(warning_text: str, language: str = "EN") -> str:
    if str(language).upper() != "AM":
        return warning_text
    text = str(warning_text).strip()
    m_calib = re.match(r"^Recipe calibration required before final approval:\s*(.+)$", text, re.IGNORECASE)
    if m_calib:
        name = m_calib.group(1).strip()
        from meal_plan.glossary import get_recipe_name
        am_name = get_recipe_name("", name, "AM")
        return f"የምግብ አሰራር ምርመራ ያስፈልጋል፦ {am_name}"

    m_fiber = re.search(r"High daily fiber volume\s*\(([^)]+)\);\s*balance with lower-fiber starches recommended for GI tolerance\.?", text, re.IGNORECASE)
    if m_fiber:
        qty = m_fiber.group(1).replace("g", "ግ").replace("G", "ግ")
        return f"ከፍተኛ የቀን የፋይበር መጠን ({qty})፤ ለሆድ ምቾት ከዝቅተኛ ፋይበር ካርቦሃይድሬት ጋር ሚዛን እንዲጠበቅ ይመከራል።"

    return text


def review_warning_lines(plan: dict[str, Any], language: str = "EN") -> list[str]:
    review = plan.get("review") or {}
    candidates: list[str] = []
    for warning in review.get("practical_warnings") or []:
        text = str(warning).strip()
        if text:
            candidates.append(text)
    for recipe in review.get("uncalibrated_recipes") or []:
        if isinstance(recipe, dict):
            name = str(recipe.get("recipe_name") or recipe.get("name") or recipe.get("recipe_id") or "recipe").strip()
        else:
            name = str(recipe).strip()
        if name:
            candidates.append(f"Recipe calibration required before final approval: {name}")
    seen: set[str] = set()
    output: list[str] = []
    for text in candidates:
        loc = local_warning(text, language)
        normalized = " ".join(loc.split())
        if normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        output.append(normalized)
    return output


def find_coach_image_path(explicit_path: str | Path | None = None) -> Path | None:
    """Resolve path to Coach Hilawe's photo asset across miniapp or documents folders."""
    if explicit_path:
        p = Path(explicit_path).expanduser()
        if p.exists():
            return p
    candidates = [
        Path(__file__).resolve().parent / "coach-hilawe.webp",
        Path(__file__).resolve().parent.parent.parent / "meal_plan_miniapp" / "public" / "coach-hilawe.webp",
        Path("d:/The hobby 2/DigitalRevenueHilawe/meal_plan_miniapp/public/coach-hilawe.webp"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def format_swap_text(meal: Any, swap_item: dict[str, Any], is_am: bool = True) -> str:
    category = swap_item.get("category", "")
    fid = str(swap_item.get("food_id") or "")
    swap_name = swap_item.get("food_name_am" if is_am else "food_name", "")
    if not swap_name:
        swap_name = swap_item.get("food_name", "")

    # Budget guardrail: Replace imported cottage cheese (A016) with affordable boiled eggs (A011)
    if fid == "A016" or "cottage" in str(swap_name).lower() or "ኮቴጅ" in str(swap_name):
        swap_name = "የተቀቀለ እንቁላል" if is_am else "Boiled eggs"
        grams_val = 100
        familiar = "2 ፍሬ" if is_am else "2 large eggs"
    else:
        grams_val = swap_item.get("grams") or swap_item.get("exchange_weight_g") or 0
        if is_am and swap_item.get("familiar_am"):
            familiar = str(swap_item.get("familiar_am")).strip()
        elif not is_am and swap_item.get("familiar"):
            familiar = str(swap_item.get("familiar")).strip()
        else:
            familiar = str(swap_item.get("familiar_guidance") or swap_item.get("familiar") or "").strip()

    g_unit = "ግ" if is_am else "g"
    swap_qty = f"{round(float(grams_val))} {g_unit}"

    if familiar:
        if is_am and any('\u1200' <= ch <= '\u137f' for ch in familiar):
            fam_text = familiar
        else:
            from meal_plan.generation.formatting import familiar_portion
            clean_fam = re.sub(r"^(about|approx\.?|በግምት)\s*", "", familiar, flags=re.I).strip()
            fam_text = familiar_portion(1.0, clean_fam, language="AM" if is_am else "EN")
            fam_text = re.sub(r"\babout\s+[1I]\s+approx\.?\s*", "about ", fam_text, flags=re.I)
            fam_text = re.sub(r"\babout\s+approx\.?\s*", "about ", fam_text, flags=re.I)
        detail = f"{swap_name} ({swap_qty} — {fam_text})"
    else:
        detail = f"{swap_name} ({swap_qty})"

    # Clean double em-dashes
    detail = re.sub(r"—{2,}", " — ", detail)
    detail = re.sub(r"—\s*—", " — ", detail)
    detail = re.sub(r"--+", " — ", detail)
    detail = re.sub(r"\s+—\s+", " — ", detail)
    detail = sanitize_display_text(detail)

    for_fid = str(swap_item.get("for_food_id") or "")
    s_type = swap_item.get("swap_type") or ""
    cat_lower = str(category).lower()

    if for_fid == "C001":
        prefix = "🔄 የእንጀራ ተቀያሪ፦ " if is_am else "🔄 Injera Swap: "
    elif for_fid == "C010":
        prefix = "🔄 የድንች ተቀያሪ፦ " if is_am else "🔄 Potato Swap: "
    elif for_fid == "A018":
        prefix = "🔄 የአይብ ተቀያሪ፦ " if is_am else "🔄 Ayib Swap: "
    elif for_fid == "A011":
        prefix = "🔄 የእንቁላል ተቀያሪ፦ " if is_am else "🔄 Egg Swap: "
    elif s_type == "carb" or any(k in cat_lower for k in ("grain", "starch", "tuber")):
        prefix = "🔄 የእህል / የካርቦሃይድሬት ተቀያሪ፦ " if is_am else "🔄 Grain/Carb Swap: "
    elif s_type == "protein" or "protein" in cat_lower or "meat" in cat_lower or "egg" in cat_lower:
        prefix = "🔄 የፕሮቲን ተቀያሪ፦ " if is_am else "🔄 Protein Swap: "
    elif s_type == "fat" or "fat" in cat_lower or "oil" in cat_lower:
        prefix = "🔄 የቅባት ተቀያሪ፦ " if is_am else "🔄 Fat Swap: "
    else:
        prefix = "🔄 ተቀያሪ አማራጭ፦ " if is_am else "🔄 Alternative: "

    return f"{prefix}{detail}"
