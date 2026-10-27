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
    base = re.sub(r"\(?\s*cooked\s*\)?", "", str(name or ""), flags=re.I)
    base = re.sub(r"\(\s*\)", "", base).strip(" ,")
    if not base:
        return str(name or "")
    if "(ጥሬ)" in base or "(Raw)" in base or "dry" in base.lower():
        return base
    return f"{base} (Dry)"

CATEGORY_ORDER: dict[str, int] = {
    "Lean animal protein": 1,
    "Fish & seafood": 2,
    "Eggs": 3,
    "Dairy products": 4,
    "Dairy protein": 4,
    "Plant-based milk": 5,
    "Plant protein & soy": 6,
    "Plant protein": 6,
    "Legumes & plant protein": 7,
    "Grains & starches": 8,
    "Root vegetables & tubers": 9,
    "Tuber / starch": 9,
    "Vegetables": 10,
    "Fresh fruits": 11,
    "Dried fruits": 12,
    "Fruit / dried": 12,
    "Healthy fat fruits": 13,
    "Fruit / fat": 13,
    "Nuts & nut butters": 14,
    "Nuts / fat": 14,
    "Added fat & oils": 15,
    "Added fat": 15,
    "Aromatics & seasonings": 16,
    "Vegetable / seasoning": 16,
    "Condiments & sauces": 17,
    "Condiment": 17,
}


def _standard_category(cat: str) -> str:
    c_lower = str(cat or "").lower()
    if "oil" in c_lower or "fat" in c_lower and "fruit" not in c_lower and "nut" not in c_lower:
        return "Added fat & oils"
    if "dairy" in c_lower or "milk" in c_lower and "soy" not in c_lower:
        return "Dairy products"
    if "plant" in c_lower and "milk" in c_lower or "beverage" in c_lower:
        return "Plant-based milk"
    if "egg" in c_lower:
        return "Eggs"
    if "fish" in c_lower or "seafood" in c_lower or "tuna" in c_lower or "tilapia" in c_lower:
        return "Fish & seafood"
    if "meat" in c_lower or "poultry" in c_lower or "chicken" in c_lower or "beef" in c_lower or "turkey" in c_lower:
        return "Lean animal protein"
    if "legume" in c_lower or "lentil" in c_lower or "bean" in c_lower or "chickpea" in c_lower:
        return "Legumes & plant protein"
    if "soy" in c_lower or "tofu" in c_lower:
        return "Plant protein & soy"
    if "grain" in c_lower or "starch" in c_lower or "rice" in c_lower or "oat" in c_lower or "pasta" in c_lower or "bread" in c_lower:
        return "Grains & starches"
    if "tuber" in c_lower or "potato" in c_lower:
        return "Root vegetables & tubers"
    if "fruit" in c_lower and "fat" in c_lower or "avocado" in c_lower:
        return "Healthy fat fruits"
    if "fruit" in c_lower and "dried" in c_lower:
        return "Dried fruits"
    if "fruit" in c_lower:
        return "Fresh fruits"
    if "nut" in c_lower or "peanut" in c_lower:
        return "Nuts & nut butters"
    if "seasoning" in c_lower or "aromatic" in c_lower or "garlic" in c_lower:
        return "Aromatics & seasonings"
    if "condiment" in c_lower or "sauce" in c_lower or "lemon" in c_lower:
        return "Condiments & sauces"
    if "vegetable" in c_lower:
        return "Vegetables"
    return cat or "General"


def build_grocery(weekly_food_grams: dict[str, float], dataset: HilaweDataset) -> list[dict[str, Any]]:
    foods = dataset.food_by_id
    rows = []
    for fid, planned in sorted(weekly_food_grams.items()):
        food = foods.get(fid)
        if not food or planned <= 0:
            continue

        cat = _standard_category(str(food.get("Category") or ""))
        planned_rounded = math.ceil(planned / 10) * 10

        # 1. Eggs: Standard retail carton procurement
        if fid == "A011" or "egg" in str(food.get("Food Name", "")).lower():
            egg_count = max(1, int(round(planned / 50.0)))
            planned_g = float(egg_count * 50)
            purchase_qty_en = "1 carton (10–12 eggs)" if egg_count <= 12 else f"1–2 cartons ({egg_count} eggs)"
            purchase_qty_am = "1 ካርቶን (10–12 ፍሬ)" if egg_count <= 12 else f"1–2 ካርቶን ({egg_count} ፍሬ)"
            rows.append({
                "food_id": fid,
                "buy_item": "Fresh whole eggs",
                "category": "Eggs",
                "planned_grams": planned_g,
                "buy_weight_g": float(max(12, egg_count) * 50),
                "planned_display": f"{egg_count} eggs",
                "buy_display": purchase_qty_en,
                "planned_display_en": f"{egg_count} eggs",
                "buy_display_en": purchase_qty_en,
                "planned_display_am": f"{egg_count} ፍሬ",
                "buy_display_am": purchase_qty_am,
                "purchase_quantity": purchase_qty_en,
                "purchase_quantity_en": purchase_qty_en,
                "purchase_quantity_am": purchase_qty_am,
                "plan_yield_guide": f"Plan uses {egg_count} eggs (~50g per egg)",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Fresh whole eggs purchased in standard retail carton.",
            })
            continue

        # 2. Specific Retail Commodity Calibrations:
        if fid in ("T001", "T002"):
            name = "Extra virgin olive oil" if fid == "T001" else "Sunflower oil"
            rows.append({
                "food_id": fid,
                "buy_item": name,
                "category": "Added fat & oils",
                "planned_grams": float(planned_rounded),
                "buy_weight_g": 500.0,
                "purchase_quantity": "1 bottle (500 ml)",
                "purchase_quantity_en": "1 bottle (500 ml)",
                "purchase_quantity_am": "1 ጠርሙስ (500 ሚ.ሊ)",
                "plan_yield_guide": f"Plan uses ~{planned_rounded:.0f} g for cooking & dressing",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Standard retail bottle covers weekly cooking and salad dressing.",
            })
            continue

        if fid == "A015":
            rows.append({
                "food_id": fid,
                "buy_item": "Low-fat fresh milk",
                "category": "Dairy products",
                "planned_grams": float(planned_rounded),
                "buy_weight_g": 1000.0 if planned_rounded <= 1000 else 2000.0,
                "purchase_quantity": "1 carton (1.0 L)" if planned_rounded <= 1000 else "1–2 cartons (1.0–2.0 L)",
                "purchase_quantity_en": "1 carton (1.0 L)" if planned_rounded <= 1000 else "1–2 cartons (1.0–2.0 L)",
                "purchase_quantity_am": "1 ካርቶን (1.0 ሊ)" if planned_rounded <= 1000 else "1–2 ካርቶን (1.0–2.0 ሊ)",
                "plan_yield_guide": f"Plan uses ~{planned_rounded:.0f} ml in shakes & bowls",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Fresh refrigerated milk.",
            })
            continue

        if fid == "P014":
            rows.append({
                "food_id": fid,
                "buy_item": "Fortified soy milk (unsweetened)",
                "category": "Plant-based milk",
                "planned_grams": float(planned_rounded),
                "buy_weight_g": 1000.0,
                "purchase_quantity": "1 carton (1.0 L)",
                "purchase_quantity_en": "1 carton (1.0 L)",
                "purchase_quantity_am": "1 ካርቶን (1.0 ሊ)",
                "plan_yield_guide": f"Plan uses ~{planned_rounded:.0f} ml on fasting days",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Calcium- and B12-fortified unsweetened soy milk carton.",
            })
            continue

        if fid == "C008":
            rows.append({
                "food_id": fid,
                "buy_item": "Whole-wheat / sourdough bread",
                "category": "Grains & starches",
                "planned_grams": float(planned_rounded),
                "buy_weight_g": 500.0,
                "purchase_quantity": "1 fresh loaf (~500 g)",
                "purchase_quantity_en": "1 fresh loaf (~500 g)",
                "purchase_quantity_am": "1 ትኩስ ዳቦ (~500 ግ)",
                "plan_yield_guide": f"Plan uses ~{planned_rounded:.0f} g (approx. 8–10 slices)",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Fresh bakery whole-grain or sourdough loaf.",
            })
            continue

        if fid in ("A013", "A014"):
            name = "Greek yogurt (non-fat)" if fid == "A013" else "Low-fat yogurt"
            rows.append({
                "food_id": fid,
                "buy_item": name,
                "category": "Dairy products",
                "planned_grams": float(planned_rounded),
                "buy_weight_g": 500.0,
                "purchase_quantity": "1 tub (500 g)",
                "purchase_quantity_en": "1 tub (500 g)",
                "purchase_quantity_am": "1 እቃ (500 ግ)",
                "plan_yield_guide": f"Plan uses ~{planned_rounded:.0f} g",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Standard retail refrigerated tub.",
            })
            continue

        if fid == "T004":
            rows.append({
                "food_id": fid,
                "buy_item": "Pure peanut butter",
                "category": "Nuts & nut butters",
                "planned_grams": float(planned_rounded),
                "buy_weight_g": 350.0,
                "purchase_quantity": "1 jar (350–500 g)",
                "purchase_quantity_en": "1 jar (350–500 g)",
                "purchase_quantity_am": "1 ጆግ (350–500 ግ)",
                "plan_yield_guide": f"Plan uses ~{planned_rounded:.0f} g",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Natural 100% roasted peanut butter with no added sugar or palm oil.",
            })
            continue

        if fid == "T003":
            rows.append({
                "food_id": fid,
                "buy_item": "Roasted peanuts",
                "category": "Nuts & nut butters",
                "planned_grams": float(planned_rounded),
                "buy_weight_g": 200.0,
                "purchase_quantity": "1 bag (~200 g)",
                "purchase_quantity_en": "1 bag (~200 g)",
                "purchase_quantity_am": "1 ከረጢት (~200 ግ)",
                "plan_yield_guide": f"Plan uses ~{planned_rounded:.0f} g",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Dry roasted unsalted peanuts.",
            })
            continue

        if fid == "P010":
            rows.append({
                "food_id": fid,
                "buy_item": "Firm tofu",
                "category": "Plant protein & soy",
                "planned_grams": float(planned_rounded),
                "buy_weight_g": 500.0,
                "purchase_quantity": "1–2 blocks (400–500 g)",
                "purchase_quantity_en": "1–2 blocks (400–500 g)",
                "purchase_quantity_am": "1–2 ፓኬት (400–500 ግ)",
                "plan_yield_guide": f"Plan uses ~{planned_rounded:.0f} g for Tofu Tibs",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Vacuum-sealed firm or extra-firm tofu.",
            })
            continue

        if fid == "A008":
            rows.append({
                "food_id": fid,
                "buy_item": "Canned tuna in water",
                "category": "Fish & seafood",
                "planned_grams": float(planned_rounded),
                "buy_weight_g": 555.0,
                "purchase_quantity": "3–4 cans (185g each)",
                "purchase_quantity_en": "3–4 cans (185g each)",
                "purchase_quantity_am": "3–4 ቆርቆሮ (185ግ)",
                "plan_yield_guide": f"Plan uses ~{planned_rounded:.0f} g drained weight",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Skipjack or light tuna canned in spring water.",
            })
            continue

        if fid == "V003":
            rows.append({
                "food_id": fid,
                "buy_item": "Fresh garlic",
                "category": "Aromatics & seasonings",
                "planned_grams": float(planned_rounded),
                "buy_weight_g": 60.0,
                "purchase_quantity": "1 head / bulb",
                "purchase_quantity_en": "1 head / bulb",
                "purchase_quantity_am": "1 ራስ ነጭ ሽንኩርት",
                "plan_yield_guide": f"Plan uses ~{planned_rounded:.0f} g for recipe seasoning",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Whole fresh garlic bulb.",
            })
            continue

        if fid == "V001":
            rows.append({
                "food_id": fid,
                "buy_item": "Fresh red/yellow onions",
                "category": "Vegetables",
                "planned_grams": float(planned_rounded),
                "buy_weight_g": 500.0,
                "purchase_quantity": "1 net bag (~500 g)",
                "purchase_quantity_en": "1 net bag (~500 g)",
                "purchase_quantity_am": "1 መረብ ሽንኩርት (~500 ግ)",
                "plan_yield_guide": f"Plan uses ~{planned_rounded:.0f} g",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Fresh cooking onions.",
            })
            continue

        if fid == "V002":
            rows.append({
                "food_id": fid,
                "buy_item": "Fresh tomatoes",
                "category": "Vegetables",
                "planned_grams": float(planned_rounded),
                "buy_weight_g": 1000.0,
                "purchase_quantity": "~1.0 kg fresh",
                "purchase_quantity_en": "~1.0 kg fresh",
                "purchase_quantity_am": "~1.0 ኪ.ግ ትኩስ",
                "plan_yield_guide": f"Plan uses ~{planned_rounded:.0f} g",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Fresh ripe salad and cooking tomatoes.",
            })
            continue

        if fid == "C010":
            buy_kg = planned_rounded / 1000.0
            qty_am = f"~{buy_kg:.1f} ኪ.ግ" if buy_kg >= 1.0 else f"~{planned_rounded} ግ"
            qty_en = f"~{buy_kg:.1f} kg" if buy_kg >= 1.0 else f"~{planned_rounded} g"
            rows.append({
                "food_id": fid,
                "buy_item": "Potatoes (Raw)",
                "category": "Root vegetables & tubers",
                "planned_grams": float(planned_rounded),
                "buy_weight_g": float(planned_rounded),
                "purchase_quantity": qty_en,
                "purchase_quantity_en": qty_en,
                "purchase_quantity_am": qty_am,
                "plan_yield_guide": f"Plan uses ~{planned_rounded/1000:.1f} kg cooked",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Fresh raw boiling potatoes.",
            })
            continue

        # 3. Meat shrinkage factor: 100g cooked meat requires ~140g raw meat (buy = round(planned * 1.38))
        is_meat = fid in MEAT_FOOD_IDS or any(k in cat.lower() for k in ("meat", "poultry", "fish", "beef", "chicken", "tilapia", "turkey")) or any(k in str(food.get("Food Name") or "").lower() for k in ("chicken", "beef", "turkey", "tilapia", "fish"))
        if is_meat:
            buy = math.ceil((planned_rounded * 1.38) / 10) * 10
            buy_kg = buy / 1000.0
            qty_am = f"~{buy_kg:.1f} ኪ.ግ ጥሬ" if buy_kg >= 1.0 else f"~{round(buy)} ግ ጥሬ"
            qty_en = f"~{buy_kg:.1f} kg (raw cut)" if buy_kg >= 1.0 else f"~{round(buy)} g (raw cut)"
            name = str(food.get("Food Name") or "")
            if "cooked" in name.lower():
                import re
                name = re.sub(r"\(?\s*cooked\s*\)?", "", name, flags=re.I)
                name = re.sub(r"\(\s*\)", "", name).strip(" ,") + " (Raw)"
            elif not name.endswith("(Raw)") and not name.endswith("(ጥሬ)"):
                name = f"{name} (Raw)"
            rows.append({
                "food_id": fid,
                "buy_item": name,
                "category": cat,
                "planned_grams": float(planned_rounded),
                "buy_weight_g": float(buy),
                "purchase_quantity": qty_en,
                "purchase_quantity_en": qty_en,
                "purchase_quantity_am": qty_am,
                "plan_yield_guide": f"Plan uses ~{planned_rounded} g cooked • accounts for 0.72× cooking shrinkage",
                "budget": food.get("Budget Level"),
                "fasting_allowed": food.get("Fasting Allowed"),
                "data_quality": food.get("Data Quality"),
                "note": "Purchase raw butcher cut allowing for cooking moisture loss.",
            })
            continue

        # 4. Standard dry grain yield / general items
        factor = _n(food.get("Yield Conversion")) or DEFAULT_YIELD.get(fid, 1.0)
        buy = math.ceil((planned / max(0.01, factor)) / 10) * 10

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
            "category": cat,
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

    rows.sort(key=lambda r: (CATEGORY_ORDER.get(str(r["category"]), 99), str(r["buy_item"])))
    return rows
