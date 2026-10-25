from __future__ import annotations

import math
from typing import Any

from meal_plan.generation.dataset import HilaweDataset
from meal_plan.generation.formatting import familiar_portion


DEFAULT_YIELD = {
    "C003": 3.0, "C004": 3.0, "C005": 2.4, "C006": 2.4, "C013": 3.0, "C014": 2.5, "C015": 3.0,
    "P001": 2.5, "P002": 2.4, "P003": 2.5, "P004": 2.5, "P005": 2.5, "P006": 2.5, "P007": 2.5,
}

# Meat and poultry cooking shrinkage factor: 100g cooked meat requires ~140g raw meat (shrinkage = 0.72)
MEAT_SHRINKAGE_FACTOR = 0.72
MEAT_FOOD_IDS = {"A001", "A002", "A003", "A004", "A005", "A006", "A007", "A019", "A020"}


def _n(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _dry_name(name: str) -> str:
    import re
    base = re.sub(r",?\s*cooked\b", "", str(name or ""), flags=re.I).strip(" ,")
    return base + ", dry"


def build_grocery(weekly_food_grams: dict[str, float], dataset: HilaweDataset) -> list[dict[str, Any]]:
    foods = dataset.food_by_id
    rows = []
    for fid, planned in sorted(weekly_food_grams.items()):
        food = foods.get(fid)
        if not food or planned <= 0:
            continue

        cat = str(food.get("Category") or "").lower()

        # 1. Eggs: Standardize to clean whole integer counts (1 whole egg = 50g)
        if fid == "A011" or "egg" in str(food.get("Food Name", "")).lower():
            egg_count = max(1, int(round(planned / 50.0)))
            buy_count = int(math.ceil(egg_count / 2.0) * 2)  # round up to even count (e.g. 8, 10, 14)
            planned_g = float(egg_count * 50)
            buy_g = float(buy_count * 50)
            purchase_qty = f"{buy_count} ፍሬ"
            purchase_qty_en = f"{buy_count} eggs"
            rows.append({
                "food_id": fid,
                "buy_item": "Eggs",
                "category": food.get("Category") or "Egg",
                "planned_grams": planned_g,
                "buy_weight_g": buy_g,
                "planned_display": f"{egg_count} ፍሬ",
                "buy_display": f"{buy_count} ፍሬ",
                "purchase_quantity": purchase_qty,
                "purchase_quantity_en": purchase_qty_en,
                "plan_yield_guide": f"{egg_count} ፍሬ እንቁላል",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Fresh whole eggs purchased by count (approx. 50g per egg).",
            })
            continue

        # 2. Potatoes: Display as raw produce with buying weight in kg
        if fid == "C010":
            planned_rounded = math.ceil(planned / 10) * 10
            buy_kg = planned_rounded / 1000.0
            qty_am = f"~{buy_kg:.1f} ኪ.ግ" if buy_kg >= 1.0 else f"~{planned_rounded} ግ"
            qty_en = f"~{buy_kg:.1f} kg" if buy_kg >= 1.0 else f"~{planned_rounded} g"
            rows.append({
                "food_id": fid,
                "buy_item": "Potatoes (Raw)",
                "category": food.get("Category") or "Tuber",
                "planned_grams": float(planned_rounded),
                "buy_weight_g": float(planned_rounded),
                "purchase_quantity": qty_en,
                "purchase_quantity_en": qty_en,
                "purchase_quantity_am": qty_am,
                "plan_yield_guide": f"Plan uses ~{planned_rounded/1000:.1f} kg cooked" if planned_rounded >= 1000 else f"Plan uses ~{planned_rounded} g cooked",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Fresh raw potatoes.",
            })
            continue

        # 3. Meat shrinkage factor: 100g cooked meat requires ~140g raw meat (buy = planned / 0.72)
        is_meat = fid in MEAT_FOOD_IDS or any(k in cat for k in ("meat", "poultry", "fish", "beef", "chicken"))
        if is_meat:
            factor = MEAT_SHRINKAGE_FACTOR
            planned_rounded = math.ceil(planned / 10) * 10
            buy = math.ceil((planned / factor) / 10) * 10
            buy_kg = buy / 1000.0
            qty_am = f"~{buy_kg:.1f} ኪ.ግ" if buy_kg >= 1.0 else f"~{round(buy)} ግ"
            qty_en = f"~{buy_kg:.1f} kg" if buy_kg >= 1.0 else f"~{round(buy)} g"
            name = str(food.get("Food Name") or "")
            if "cooked" in name.lower():
                import re
                name = re.sub(r",?\s*cooked\b", "", name, flags=re.I).strip(" ,") + " (Raw)"
            elif not name.endswith("(Raw)") and not name.endswith("(ጥሬ)"):
                name = f"{name} (Raw)"
            rows.append({
                "food_id": fid,
                "buy_item": name,
                "category": food.get("Category"),
                "planned_grams": float(planned_rounded),
                "buy_weight_g": float(buy),
                "purchase_quantity": qty_en,
                "purchase_quantity_en": qty_en,
                "purchase_quantity_am": qty_am,
                "plan_yield_guide": f"Plan uses ~{planned_rounded} g cooked • accounts for 0.72× cooking shrinkage",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Purchase raw meat allowing for cooking moisture loss.",
            })
            continue

        # 4. Standard dry grain yield / general items
        factor = _n(food.get("Yield Conversion")) or DEFAULT_YIELD.get(fid, 1.0)
        planned_rounded = math.ceil(planned / 10) * 10
        buy = math.ceil((planned / max(0.01, factor)) / 10) * 10

        # Fix typo for peanuts (ensure clean multiple of 10g, e.g. 190g)
        if fid == "T003":
            planned_rounded = math.ceil(planned / 10) * 10
            buy = planned_rounded

        if factor > 1:
            name = _dry_name(str(food.get("Food Name") or ""))
            qty_en = f"~{buy/1000:.1f} kg dry" if buy >= 1000 else f"~{round(buy)} g dry"
            qty_am = f"~{buy/1000:.1f} ኪ.ግ ጥሬ" if buy >= 1000 else f"~{round(buy)} ግ ጥሬ"
            guide = (f"Plan uses ~{planned_rounded/1000:.1f} kg cooked" if planned_rounded >= 1000 else f"Plan uses ~{round(planned_rounded)} g cooked") + f" • estimated {factor:.1f}× cooking yield"
            note = "Dry purchase estimate. Cooking water, product, batch method, package size and waste can change purchase need."
        else:
            name = str(food.get("Food Name") or "")
            qty_en = f"{buy/1000:.1f} kg" if buy >= 1000 else f"{round(buy)} g"
            qty_am = f"{buy/1000:.1f} ኪ.ግ" if buy >= 1000 else f"{round(buy)} ግ"
            guide = familiar_portion(planned_rounded / max(1.0, _n(food.get('Standard Portion g'))), str(food.get('Familiar Measure') or 'standard portion'))
            note = "Adjust for household waste, package size and client preference."

        rows.append({
            "food_id": fid,
            "buy_item": name,
            "category": food.get("Category"),
            "planned_grams": float(planned_rounded),
            "buy_weight_g": float(buy),
            "purchase_quantity": qty_en,
            "purchase_quantity_en": qty_en,
            "purchase_quantity_am": qty_am,
            "plan_yield_guide": guide,
            "budget": food.get("Budget Level"),
            "fasting_allowed": food.get("Fasting Allowed"),
            "data_quality": food.get("Data Quality"),
            "note": note,
        })

    rows.sort(key=lambda r: (str(r["category"] or ""), str(r["buy_item"])))
    return rows
