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


def client_artifact_filename(client_name: str, duration_days: int, version_number: int, ext: str = "pdf") -> str:
    cleaned_name = re.sub(r"[^\w]+", "_", str(client_name).strip()).strip("_")
    safe_name = cleaned_name or "Client"
    clean_ext = ext.lstrip(".")
    return f"{safe_name}_Meal_Plan_{int(duration_days)}_Days_V{int(version_number)}.{clean_ext}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_food_name(food_id: str, default_name: str, language: str) -> str:
    from meal_plan.glossary import get_food_name
    return get_food_name(food_id, default_name, language)


def local_recipe_name(recipe_id: str, default_name: str, language: str) -> str:
    from meal_plan.glossary import get_recipe_name
    return get_recipe_name(recipe_id, default_name, language)


def local_template_name(template_id: str, default_name: str, language: str) -> str:
    from meal_plan.glossary import get_template_name
    return get_template_name(template_id, default_name, language)


def local_category_name(category: str, language: str) -> str:
    from meal_plan.glossary import get_category_name
    return get_category_name(category, language)


def local_purchase_quantity(quantity: str, language: str) -> str:
    if str(language).upper() != "AM":
        return quantity
    raw = str(quantity or "").strip()
    # Replace kg dry, g dry, kg, g
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
