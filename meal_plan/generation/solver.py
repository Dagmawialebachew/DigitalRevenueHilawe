from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from meal_plan.generation.dataset import HilaweDataset
from meal_plan.generation.models import MacroTotals, SlotSpec
from meal_plan.generation.safety import food_is_safe


def n(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def food_macros(food: dict[str, Any], grams: float) -> MacroTotals:
    factor = grams / 100.0
    return MacroTotals(
        n(food.get("kcal / 100 g")) * factor,
        n(food.get("Protein / 100 g")) * factor,
        n(food.get("Carbs / 100 g")) * factor,
        n(food.get("Fat / 100 g")) * factor,
        n(food.get("Fibre / 100 g")) * factor,
    )


def template_macros(t: dict[str, Any]) -> MacroTotals:
    return MacroTotals(n(t.get("kcal")), n(t.get("Protein g")), n(t.get("Carbs g")), n(t.get("Fat g")), n(t.get("Fibre g")))


def practical_group(food_id: str) -> str:
    if food_id.startswith("F") and food_id[1:].isdigit(): return "fruit"
    if food_id in {"C003", "C004"}: return "rice"
    if food_id == "C001": return "injera"
    if food_id == "C007": return "oats"
    if food_id == "C020": return "rice_cake"
    if food_id in {"C005", "C006"}: return "pasta"
    if food_id in {"C008", "C009", "C016"}: return "bread"
    if food_id in {"C010", "C011"}: return "potato"
    if food_id in {"C013", "C014", "C015"}: return "grain"
    if food_id in {"T001", "T002"}: return "oil"
    return food_id


def practical_cap(group: str, settings: dict[str, Any]) -> float:
    mapping = {
        "fruit": ("MAX_FRUIT_MEAL_G", 300), "rice": ("MAX_RICE_MEAL_G", 300),
        "injera": ("MAX_INJERA_MEAL_G", 240), "oats": ("MAX_OATS_MEAL_G", 80),
        "rice_cake": ("MAX_RICE_CAKES_MEAL_G", 40),
        "pasta": ("MAX_PASTA_MEAL_G", 350), "bread": ("MAX_BREAD_MEAL_G", 100),
        "potato": ("MAX_POTATO_MEAL_G", 400), "grain": ("MAX_OTHER_GRAIN_MEAL_G", 350),
        "oil": ("MAX_OIL_MEAL_G", 14),
    }
    if group not in mapping:
        return math.inf
    key, default = mapping[group]
    return n(settings.get(key)) or float(default)


SERVING_HARD_CAPS: dict[str, float] = {
    "C020": 40.0,   # Max 4 thin rice cakes (~36-40g)
    "C007": 80.0,   # Max 80g dry oats
    "C008": 130.0,  # Max 130g bread (~3 slices)
    "C006": 350.0,  # Max 350g cooked pasta
    "C005": 350.0,
    "C003": 300.0,  # Max 300g cooked rice
    "C004": 300.0,
    "C010": 400.0,  # Max 400g potatoes
    "C011": 400.0,
    "T001": 20.0,   # Max 20g oil per meal
    "T002": 20.0,
    "T004": 32.0,   # Max 32g peanut butter
    "T003": 30.0,   # Max 30g peanuts
}


def minimum_addition(food_id: str) -> float:
    if food_id in {"T001", "T002"}: return 2
    if food_id.startswith("F") and food_id[1:].isdigit(): return 50
    if food_id == "P010": return 75
    if food_id == "P014": return 100
    if food_id == "P001": return 50
    if food_id.startswith("A") and food_id[1:].isdigit(): return 60
    return 15


@dataclass
class DaySolution:
    scale: float
    extras: dict[str, list[dict[str, float]]]
    warnings: list[str]
    totals: MacroTotals
    food_by_slot: dict[str, dict[str, float]]
    mass_by_slot: dict[str, float]


class DaySolver:
    def __init__(self, dataset: HilaweDataset, answers: dict[str, Any]):
        self.dataset = dataset
        self.answers = answers
        self.foods = dataset.food_by_id
        self.recipes = dataset.recipe_by_id
        self.ingredients = dataset.ingredients_by_recipe
        self.components = dataset.components_by_template
        self.settings = dataset.settings

    def solve(self, selected: list[tuple[SlotSpec, dict[str, Any]]], targets: dict[str, float], *, fasting: bool) -> DaySolution:
        target = {
            "kcal": n(targets.get("target_kcal") or targets.get("kcal")),
            "protein": n(targets.get("protein_g") or targets.get("protein")),
            "carbs": n(targets.get("carbs_g") or targets.get("carbs")),
            "fat": n(targets.get("fat_g") or targets.get("fat")),
        }
        if min(target.values()) <= 0:
            raise ValueError("Generation requires nonzero calorie, protein, carbohydrate and fat targets")

        base = MacroTotals()
        fixed_macros = MacroTotals()
        has_shake = any(str(t.get("Template ID")) == "MN-S-SHAKE" for _, t in selected)

        client_weight = float(self.answers.get("current_weight_kg") or 0)
        is_small_frame = client_weight > 0 and client_weight < 55.0

        for spec, t in selected:
            tid = str(t.get("Template ID"))
            if tid == "MN-S-SHAKE":
                m_fixed = MacroTotals(549.8, 24.1, 72.4, 20.7, 5.0)
                base = base.plus(m_fixed)
                fixed_macros = fixed_macros.plus(m_fixed)
            elif tid in ("MN-B02", "MF-B02"):
                m_fixed = MacroTotals(597.8, 28.2, 79.3, 21.7, 6.0)
                base = base.plus(m_fixed)
                fixed_macros = fixed_macros.plus(m_fixed)
            elif tid == "MN-B07":
                m_fixed = MacroTotals(443.0, 19.6, 53.8, 16.5, 5.5)
                base = base.plus(m_fixed)
                fixed_macros = fixed_macros.plus(m_fixed)
            elif spec.source_slot == "Breakfast":
                m_fixed = template_macros(t)
                base = base.plus(m_fixed)
                fixed_macros = fixed_macros.plus(m_fixed)
            else:
                base = base.plus(template_macros(t))

        # Determine scale for scalable meals (Lunch and Dinner)
        scalable_base = MacroTotals(
            max(10.0, base.kcal - fixed_macros.kcal),
            max(5.0, base.protein - fixed_macros.protein),
            max(10.0, base.carbs - fixed_macros.carbs),
            max(5.0, base.fat - fixed_macros.fat),
            max(1.0, base.fibre - fixed_macros.fibre),
        )
        remaining_target = {
            "kcal": max(100.0, target["kcal"] - fixed_macros.kcal),
            "protein": max(20.0, target["protein"] - fixed_macros.protein),
            "carbs": max(50.0, target["carbs"] - fixed_macros.carbs),
            "fat": max(10.0, target["fat"] - fixed_macros.fat),
        }
        if target["protein"] <= 155.0 and scalable_base.protein > 0:
            if fasting:
                # On fasting days, all protein is plant protein (lentils/tofu); scale to hit protein directly
                prot_scale = remaining_target["protein"] / scalable_base.protein
                scale = max(1.10, min(1.22, prot_scale)) if target["kcal"] >= 2800 else max(0.82, min(1.08, prot_scale))
            else:
                # On omnivore days, dynamic plant protein estimation prevents over-scaling heavy meat/grain days
                if target["kcal"] >= 2800:
                    if fixed_macros.protein == 0:
                        plant_protein_est = 14.0
                        prot_scale = max(20.0, target["protein"] - plant_protein_est) / scalable_base.protein
                        scale = max(0.80, min(0.96, prot_scale))
                    else:
                        plant_protein_est = 34.0
                        target_scalable_prot = max(20.0, target["protein"] - fixed_macros.protein - plant_protein_est)
                        prot_scale = target_scalable_prot / scalable_base.protein
                        scale = max(0.64, min(0.82, prot_scale))
                else:
                    plant_protein_est = 20.0 if scalable_base.protein >= 100.0 else 14.0
                    target_scalable_prot = max(20.0, target["protein"] - fixed_macros.protein - plant_protein_est)
                    prot_scale = target_scalable_prot / scalable_base.protein
                    scale = max(0.74, min(1.10, prot_scale))
        elif scalable_base.kcal > 0:
            scale = max(0.80, min(1.20, remaining_target["kcal"] / scalable_base.kcal))
        else:
            scale = 1.0

        fixed_slots = {spec.label for spec, t in selected if str(t.get("Template ID")) in ("MN-B02", "MF-B02", "MN-S-SHAKE", "MN-B07") or spec.source_slot == "Breakfast"}
        extras: dict[str, list[dict[str, float]]] = {spec.label: [] for spec, _ in selected}
        meal_state: dict[str, dict[str, float]] = {}
        food_by_slot: dict[str, dict[str, float]] = {}
        mass_by_slot: dict[str, float] = {}
        slot_specs = {spec.label: spec for spec, _ in selected}
        totals = {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fibre": 0.0}

        for spec, t in selected:
            tid = str(t.get("Template ID"))
            if tid == "MN-S-SHAKE":
                comps = [
                    {"Item Type": "Food", "Item ID": "A015", "Portion g": 250},
                    {"Item Type": "Food", "Item ID": "C007", "Portion g": 40},
                    {"Item Type": "Food", "Item ID": "T004", "Portion g": 30},
                    {"Item Type": "Food", "Item ID": "F001", "Portion g": 120},
                ]
                m = MacroTotals(549.8, 24.1, 72.4, 20.7, 5.0)
            elif tid in ("MN-B02", "MF-B02"):
                b_raw = str(self.answers.get("grocery_budget") or "").upper()
                is_save = b_raw in {"SAVE", "VALUE", "ቆጣቢ"} or "SAVE" in b_raw or "ቆጣቢ" in b_raw
                d_raw = str(self.answers.get("dietary_preference") or self.answers.get("dietary_pattern") or "OMNIVORE").upper()
                is_omni = "OMNIVORE" in d_raw or not fasting
                dairy_id = "A015" if (is_save and is_omni) else "A014"
                comps = [
                    {"Item Type": "Food", "Item ID": dairy_id, "Portion g": 200},
                    {"Item Type": "Food", "Item ID": "C007", "Portion g": 50},
                    {"Item Type": "Food", "Item ID": "F001", "Portion g": 120},
                    {"Item Type": "Food", "Item ID": "T003", "Portion g": 30},
                ]
                m = MacroTotals(597.8, 28.2, 79.3, 21.7, 6.0)
            elif tid == "MN-B07":
                comps = [
                    {"Item Type": "Recipe", "Item ID": "R021", "Portion g": 180},
                    {"Item Type": "Food", "Item ID": "C001", "Portion g": 120},
                    {"Item Type": "Food", "Item ID": "V012", "Portion g": 60},
                ]
                m = MacroTotals(443.0, 19.6, 53.8, 16.5, 5.5)
            elif spec.source_slot == "Breakfast":
                comps = self.components.get(tid, [])
                m = template_macros(t)
            else:
                comps = self.components.get(tid, [])
                m = template_macros(t).scale(scale)

            meal_state[spec.label] = m.to_dict()
            food_by_slot[spec.label] = {}
            mass_by_slot[spec.label] = 0.0

            b_raw = str(self.answers.get("grocery_budget") or "").upper()
            is_save = b_raw in {"SAVE", "VALUE", "ቆጣቢ"} or "SAVE" in b_raw or "ቆጣቢ" in b_raw
            d_raw = str(self.answers.get("dietary_preference") or self.answers.get("dietary_pattern") or "OMNIVORE").upper()
            is_omni = "OMNIVORE" in d_raw or not fasting

            m_comp = MacroTotals()
            has_savory_meat_fish = False
            for c in comps:
                if tid in ("MN-S-SHAKE", "MN-B02", "MF-B02", "MN-B07") or spec.source_slot == "Breakfast":
                    amount = float(c.get("Portion g") or 0.0)
                else:
                    amount = n(c.get("Portion g")) * scale

                if str(c.get("Item Type")) == "Recipe":
                    rid = str(c.get("Item ID"))
                    # Hard Upper Bounds on Single-Meal Animal Protein Portions for small-framed clients (< 55 kg)
                    if is_small_frame:
                        if rid in ("R023", "R020", "R017", "R016"):
                            amount = min(amount, 210.0)
                        elif rid in ("R018", "R019"):
                            amount = min(amount, 140.0)
                        elif rid in ("R015", "R014"):
                            amount = min(amount, 130.0)
                        elif rid == "R024":
                            amount = min(amount, 210.0)
                    if rid in ("R023", "R020", "R017", "R016", "R018", "R019", "R015", "R014"):
                        has_savory_meat_fish = True

                mass_by_slot[spec.label] += amount
                if str(c.get("Item Type")) == "Food":
                    fid = str(c.get("Item ID"))
                    if is_save:
                        if fid == "T001": fid = "T002"
                    else:
                        if fid == "T002": fid = "T001"
                    if is_save and is_omni and fid == "P014":
                        fid = "A015"
                        amount = 200.0
                    food_by_slot[spec.label][fid] = food_by_slot[spec.label].get(fid, 0.0) + amount
                    if fid in self.foods:
                        m_comp = m_comp.plus(food_macros(self.foods[fid], amount))
                else:
                    rid = str(c.get("Item ID"))
                    recipe = self.recipes.get(rid, {})
                    fraction = amount / max(1.0, n(recipe.get("Yield g")))
                    r_frac = amount / max(1.0, n(c.get("Portion g")))
                    m_comp = m_comp.plus(MacroTotals(
                        n(c.get("kcal")) * r_frac,
                        n(c.get("Protein g")) * r_frac,
                        n(c.get("Carbs g")) * r_frac,
                        n(c.get("Fat g")) * r_frac,
                        n(c.get("Fibre g")) * r_frac,
                    ))
                    for ingredient in self.ingredients.get(rid, []):
                        fid = str(ingredient.get("Food ID"))
                        if is_save:
                            if fid == "T001": fid = "T002"
                        else:
                            if fid == "T002": fid = "T001"
                        food_by_slot[spec.label][fid] = food_by_slot[spec.label].get(fid, 0.0) + n(ingredient.get("Weight g")) * fraction

            # Mandatory Cooking Oil Anchor for Savory Meat/Fish Dishes
            if has_savory_meat_fish:
                oil_fid = "T002" if is_save else "T001"
                oil_needed = max(0.0, 6.0 - food_by_slot[spec.label].get(oil_fid, 0.0))
                if oil_needed > 0:
                    extras[spec.label].append({"id": oil_fid, "grams": oil_needed})
                    food_by_slot[spec.label][oil_fid] = food_by_slot[spec.label].get(oil_fid, 0.0) + oil_needed
                    mass_by_slot[spec.label] += oil_needed
                    oil_food = self.foods.get(oil_fid)
                    if oil_food:
                        d_oil = food_macros(oil_food, oil_needed)
                        m_comp = m_comp.plus(d_oil)

            if tid not in ("MN-S-SHAKE", "MN-B02", "MF-B02", "MN-B07"):
                m = m_comp
            meal_state[spec.label] = m.to_dict()
            for key, value in meal_state[spec.label].items(): totals[key] += value

        if is_small_frame:
            upper_protein = min(target["protein"] * 1.10, 115.0)
        elif target["protein"] <= 150.0:
            upper_protein = 153.0 if target["kcal"] >= 2800 else 150.0
        else:
            upper_protein = target["protein"] * 1.10
        upper = {"kcal": target["kcal"] * 1.03, "protein": upper_protein, "carbs": target["carbs"] * 1.15, "fat": target["fat"] * 1.15}

        def candidate(fid: str, cap: float, daily_cap: float = math.inf) -> dict[str, float | str]:
            return {"id": fid, "cap": cap, "daily_cap": daily_cap}

        ethiopian_count = sum(1 for _, t in selected if "ethiopian" in str(t.get("Cuisine") or "").lower())
        primary_carb = "C001" if ethiopian_count >= max(2, len(selected)//2) else "C003"

        def preferred_carb(slot: str, source_slot: str = "") -> str:
            t = slot_templates.get(slot, {})
            tmpl_id = str(t.get("Template ID") or "")
            t_name = (str(t.get("Meal Name") or "") + " " + str(t.get("Tags") or "")).lower()
            if "pasta" in t_name or any(str(c.get("Item ID")) in ("R027", "R014") for c in self.components.get(tmpl_id, [])):
                return "C006"
            if "rice" in t_name or any(str(c.get("Item ID")) in ("R026", "R010", "R011") for c in self.components.get(tmpl_id, [])):
                return "C003"
            if "potato" in t_name or "dinich" in t_name:
                return "C010"
            if source_slot == "Breakfast":
                breakfast_options = ["C007", "C008", "C009", "C001"]
                best, best_g = "", 0.0
                for fid in breakfast_options:
                    grams = food_by_slot[slot].get(fid, 0.0)
                    if grams > best_g:
                        best, best_g = fid, grams
                if best:
                    return best
                slot_lower = slot.lower()
                if "oat" in slot_lower:
                    return "C007"
                if "bread" in slot_lower or "toast" in slot_lower:
                    return "C008"
                return "C001" if ethiopian_count >= 1 else "C008"

            options = ["C001","C003","C004","C005","C006","C007","C008","C009","C010","C011","C013","C014","C015","C016"]
            best, best_g = "", 0.0
            for fid in options:
                grams = food_by_slot[slot].get(fid, 0.0)
                if grams > best_g:
                    best, best_g = fid, grams
            if best:
                return best
            return primary_carb

        fish_slots = {spec.label for spec, t in selected if str(t.get("Fish Required")) == "Yes"}
        dietary = str(self.answers.get("dietary_pattern") or "").upper()
        plant_based = fasting or dietary == "VEGAN"
        is_save_budget = str(self.answers.get("grocery_budget") or "").upper() in {"SAVE", "VALUE"}
        slot_templates = {spec.label: t for spec, t in selected}

        def is_traditional_stew(slot_label: str) -> bool:
            t = slot_templates.get(slot_label, {})
            t_name = str(t.get("Meal Name") or "").lower()
            if any(w in t_name for w in ["wot", "alicha", "shiro", "misir", "gomen", "firfir", "stew", "ወጥ", "አልጫ"]):
                return True
            for c in self.components.get(str(t.get("Template ID")), []):
                if str(c.get("Item Type")) != "Food":
                    r_name = str(self.recipes.get(str(c.get("Item ID")), {}).get("Recipe Name", "")).lower()
                    if any(w in r_name for w in ["wot", "alicha", "shiro", "misir", "gomen", "firfir", "stew", "ወጥ", "አልጫ"]):
                        return True
            return False

        def is_sweet_or_breakfast_dish(slot_label: str) -> bool:
            spec = slot_specs.get(slot_label)
            if spec and spec.source_slot == "Breakfast":
                return True
            t = slot_templates.get(slot_label, {})
            tmpl_id = str(t.get("Template ID") or "")
            t_name = (str(t.get("Meal Name") or "") + " " + str(t.get("Tags") or "")).lower()
            sweet_indicators = ["fruit", "papaya", "banana", "orange", "oat", "yogurt", "ayib", "ፓፓያ", "ሙዝ", "አጃ", "እርጎ", "አይብ", "ኮክ"]
            if any(w in t_name for w in sweet_indicators):
                return True
            for c in self.components.get(tmpl_id, []):
                cid = str(c.get("Item ID") or "")
                cname = str(c.get("Item Name") or "").lower()
                if cid.startswith("F") or cid in ("C007", "A013", "A018", "P014") or any(w in cname for w in sweet_indicators):
                    return True
            for fid in food_by_slot.get(slot_label, {}):
                if fid.startswith("F") or fid in ("C007", "A013", "A018", "P014"):
                    return True
            return False

        def proteins(spec: SlotSpec):
            stew = is_traditional_stew(spec.label)

            if plant_based:
                # Breakfast: ONLY Peanut Butter (T004), Peanuts (T003), Soy milk (P014), or Tofu (P010).
                # NEVER inject Ful (P007) or Shiro powder (P012) into breakfast bowls.
                if spec.source_slot == "Breakfast":
                    return [candidate("P014", 250), candidate("T004", 30), candidate("T003", 30), candidate("P010", 150)]
                if spec.source_slot == "Snack":
                    return [candidate("P013", 40), candidate("T003", 30), candidate("T004", 30), candidate("P014", 250)]
                
                # Lunch / Dinner stews & dishes:
                # Scale lentils/tofu. NEVER inject Shiro powder (P012) or Peanut Butter (T004).
                base = [candidate("P001", 180), candidate("P010", 150), candidate("P009", 50)]
                if spec.label in fish_slots:
                    return [candidate("A007", 180), candidate("A020", 180)] + base
                return base

            if dietary == "VEGETARIAN":
                # In vegetarian plans, do NOT dump loose boiled egg whites (A012) into traditional stews.
                # If extra protein is required, add a side of A018 (የአበሻ አይብ) or whole boiled eggs (A011).
                if stew:
                    return [candidate("A018", 150), candidate("A011", 100)]
                if spec.source_slot == "Breakfast":
                    if is_save_budget:
                        return [candidate("A011", 100), candidate("A012", 200), candidate("A018", 150)]
                    return [candidate("A011", 100), candidate("A012", 200), candidate("A018", 150), candidate("A016", 150)]
                if spec.source_slot == "Snack":
                    if is_save_budget:
                        return [candidate("A011", 60), candidate("A018", 100), candidate("A012", 120)]
                    return [candidate("A018", 100), candidate("A016", 150), candidate("A012", 120)]
                return [candidate("A018", 150), candidate("A011", 100)]

            t = slot_templates.get(spec.label, {})
            t_name = (str(t.get("Meal Name") or "") + " " + str(t.get("Tags") or "")).lower()
            has_meat_fish = any(w in t_name for w in ("chicken", "beef", "tuna", "tilapia", "fish", "turkey", "siga", "doro", "asa"))
            if has_meat_fish:
                return []

            if is_save_budget:
                # Strictly affordable Ethiopian proteins for Save tier:
                # A012 = Boiled egg whites, A018 = Ayib, A011 = Whole eggs.
                # Greek Yogurt (A013) and Canned Tuna (A008) are strictly forbidden in Save tier.
                if spec.source_slot == "Breakfast":
                    return [candidate("A011", 100), candidate("A012", 200), candidate("A018", 150)]
                if spec.source_slot == "Snack":
                    return [candidate("A011", 60), candidate("A012", 120), candidate("A018", 100)]
                if stew:
                    # In traditional stews, prioritize beef/chicken or Ayib side
                    return [candidate("A001", 120), candidate("A018", 150), candidate("A011", 100)]
                return [candidate("A012", 200), candidate("A001", 120), candidate("A018", 150)]

            # Standard / Premium budgets
            if spec.source_slot == "Breakfast":
                return [candidate("A011", 100), candidate("A012", 200), candidate("A018", 150), candidate("A013", 200), candidate("A016", 150)]
            if spec.source_slot == "Snack":
                return [candidate("A013", 200), candidate("A012", 120), candidate("A016", 150)]
            if stew:
                return [candidate("A001", 120), candidate("A018", 150), candidate("A011", 100)]
            return [candidate("A001", 120), candidate("A012", 200), candidate("A008", 120)]

        protein_candidates = {spec.label: proteins(spec) for spec, _ in selected}
        carb_candidates = {}
        fat_candidates = {}

        # Track avocado slots so in bulking profiles it is at most 1 meal per day (max 100g/day)
        avocado_allocated = False
        is_high_calorie_bulking = target["kcal"] >= 2800

        COMPOSITE_RECIPES = {"R026", "R027", "R028", "R011", "R010"}

        for spec, _ in selected:
            tmpl_id = str(slot_templates.get(spec.label, {}).get("Template ID") or "")
            if tmpl_id in ("MN-B02", "MF-B02", "MN-B07"):
                # Fixed breakfast components: do not let solver add extra random fillers
                carb_candidates[spec.label] = []
                fat_candidates[spec.label] = []
                protein_candidates[spec.label] = []
                continue
            if tmpl_id == "MN-S-SHAKE":
                # Fixed 4-component strength shake: Milk 250ml, Oats 40g, PB 30g, Banana 120g
                carb_candidates[spec.label] = []
                fat_candidates[spec.label] = []
                protein_candidates[spec.label] = []
                continue

            has_composite = any(
                str(c.get("Item Type")) == "Recipe" and str(c.get("Item ID")) in COMPOSITE_RECIPES
                for c in self.components.get(tmpl_id, [])
            )
            if has_composite:
                # Composite dishes (Tuna Pasta, Chicken Rice Bowl, Egg Avocado Toast, Lentil Rice Bowl):
                # On fasting days, allow plant protein sides (Lentils P001, Soy chunks P009) to hit fasting protein goals
                carb_candidates[spec.label] = [candidate("F001", 120)] if spec.source_slot == "Breakfast" else []
                protein_candidates[spec.label] = [candidate("P001", 180), candidate("P009", 45)] if (fasting and spec.source_slot in ("Lunch", "Dinner")) else []
                fat_candidates[spec.label] = [candidate("T001", 14)] if not is_save_budget else [candidate("T002", 14)]
                continue

            if spec.source_slot == "Snack":
                protein_candidates[spec.label] = [candidate("T004", 30), candidate("T003", 25)] if fasting else []
            elif spec.source_slot == "Breakfast":
                if any(fid in food_by_slot[spec.label] for fid in ("A011", "A012", "A013", "A014", "A015", "A018", "P010")):
                    protein_candidates[spec.label] = []

            stew = is_traditional_stew(spec.label)
            is_sweet = is_sweet_or_breakfast_dish(spec.label)
            p_carb = preferred_carb(spec.label, spec.source_slot)

            t_name = str(slot_templates.get(spec.label, {}).get("Meal Name") or "").lower()
            if spec.source_slot == "Breakfast":
                # For breakfast fruit/yogurt bowls: limit fruit to at most 1 candidate, NEVER inject loose bread (C008)!
                if is_sweet or "yogurt" in t_name or "bowl" in t_name or "A013" in food_by_slot[spec.label] or "A014" in food_by_slot[spec.label]:
                    carb_candidates[spec.label] = [candidate("F001", 120)] if "F001" not in food_by_slot[spec.label] else []
                else:
                    carb_candidates[spec.label] = [candidate(p_carb, 200)] if p_carb in ("C008", "C001") else []
            elif spec.source_slot == "Snack":
                # Snacks:
                if fasting:
                    carb_candidates[spec.label] = [candidate("C007", 60), candidate("C020", 50), candidate("F001", 120)]
                elif "A015" in food_by_slot[spec.label] or "milk" in spec.label.lower():
                    carb_candidates[spec.label] = [candidate("C007", 80), candidate("C020", 50)]
                elif "C020" in food_by_slot[spec.label] or "rice cake" in spec.label.lower():
                    # If Rice Cakes + PB: scale rice cakes and peanut butter. Never append white rice!
                    carb_candidates[spec.label] = [candidate("C020", 50)]
                else:
                    carb_candidates[spec.label] = [candidate("C007", 50), candidate("C020", 40)]
            else:
                carb_cap = 220.0 if p_carb in ("C005", "C006") else 300.0
                carb_candidates[spec.label] = [candidate(p_carb, carb_cap)]

            if spec.source_slot == "Breakfast" or is_sweet:
                # Strictly forbid cooking oils in sweet/fruit/yogurt/oat breakfast bowls
                # For egg breakfasts (A011): eggs already contain yolks (fat), do not inject peanut butter!
                if any(fid in food_by_slot[spec.label] for fid in ("T003", "T004", "A011")):
                    fat_candidates[spec.label] = []
                else:
                    fat_candidates[spec.label] = [candidate("T004", 30)]
            elif spec.source_slot == "Snack":
                fat_candidates[spec.label] = [candidate("T004", 30)] if "T004" in food_by_slot[spec.label] else [candidate("T003", 25)]
            elif stew:
                # Traditional savory stews: strictly restricted to cooking oils / kibbeh
                if is_save_budget:
                    fat_candidates[spec.label] = [candidate("T002", 14)]
                else:
                    stew_fats = [candidate("T001", 14)]
                    if not plant_based:
                        stew_fats.append(candidate("T012", 12))  # Niter kibbeh
                    fat_candidates[spec.label] = stew_fats
            else:
                # Other savory lunch/dinner
                if is_save_budget:
                    fat_candidates[spec.label] = [candidate("T002", 14)]
                else:
                    savory_fats = [candidate("T001", 14)]
                    if not plant_based:
                        savory_fats.append(candidate("T012", 12))
                    savory_fats.extend([candidate("V020", 100, daily_cap=100.0)])
                    fat_candidates[spec.label] = savory_fats

        # Double check P012 (Raw Shiro flour) is completely eliminated from all candidate lists
        for slot in protein_candidates:
            protein_candidates[slot] = [c for c in protein_candidates[slot] if str(c.get("id")) != "P012"]
        for slot in carb_candidates:
            carb_candidates[slot] = [c for c in carb_candidates[slot] if str(c.get("id")) != "P012"]
        for slot in fat_candidates:
            fat_candidates[slot] = [c for c in fat_candidates[slot] if str(c.get("id")) != "P012"]

        def group_used(slot: str, group: str) -> float:
            return sum(g for fid,g in food_by_slot[slot].items() if practical_group(fid)==group)
        def daily_used(fid: str) -> float:
            return sum(v.get(fid,0.0) for v in food_by_slot.values())

        macro_per = {"kcal":"kcal", "protein":"protein", "carbs":"carbs", "fat":"fat"}
        def add_candidate(slot: str, spec: dict[str, Any], macro: str, need: float) -> float:
            if need <= 0: return 0.0
            fid = str(spec["id"])
            # Permanent blacklist guard: Raw Shiro powder P012 is a raw flour, never a filler!
            if fid == "P012": return 0.0
            if fid == "V020" and daily_used("V020") >= 100.0: return 0.0
            if is_small_frame and macro == "protein" and totals["protein"] >= 105.0: return 0.0
            if not is_small_frame and target["protein"] <= 150.0 and fid.startswith(("A", "P")):
                prot_cutoff = target["protein"] * 0.98 if fasting else target["protein"] * 0.86
                if totals["protein"] >= prot_cutoff:
                    return 0.0
            food = self.foods.get(fid)
            safe, _ = food_is_safe(food or {}, self.answers, fasting=fasting)
            if not safe: return 0.0
            per_total = food_macros(food, 1.0)
            per = getattr(per_total, macro_per[macro])
            if per <= 0: return 0.0
            existing_extra = sum(x["grams"] for x in extras[slot] if x["id"]==fid)
            grams = need / per
            grams = min(grams, n(spec["cap"])-existing_extra, n(spec["daily_cap"])-daily_used(fid))
            group = practical_group(fid)
            grams = min(grams, practical_cap(group, self.settings)-group_used(slot,group))
            grams = min(grams, slot_specs[slot].mass_cap_g-mass_by_slot[slot])
            grams = min(grams, (target["kcal"]*slot_specs[slot].kcal_cap_fraction-meal_state[slot]["kcal"]) / max(0.01,per_total.kcal))
            for key in ("kcal","protein","carbs","fat"):
                p = getattr(per_total,key)
                if p > 0: grams = min(grams,(upper[key]-totals[key])/p)
            if not math.isfinite(grams) or grams < minimum_addition(fid): return 0.0
            grams = max(0.0, grams)
            found = next((x for x in extras[slot] if x["id"]==fid),None)
            if found: found["grams"] += grams
            else: extras[slot].append({"id":fid,"grams":grams})
            food_by_slot[slot][fid]=food_by_slot[slot].get(fid,0.0)+grams
            mass_by_slot[slot]+=grams
            delta=food_macros(food,grams)
            for key in totals:
                dv=getattr(delta,key); totals[key]+=dv; meal_state[slot][key]+=dv
            return getattr(delta,macro)

        ordered_slots=[spec.label for spec,_ in selected]
        shares={spec.label:spec.target_share for spec,_ in selected}
        def fill(macro: str, candidates: dict[str,list[dict[str,Any]]], factor: float=1.0):
            goal=target[macro]*factor
            for slot in ordered_slots:
                if totals[macro] >= goal*0.99: break
                need=min(max(0.0,goal*shares[slot]-meal_state[slot][macro]),max(0.0,goal-totals[macro]))
                for cand in candidates[slot]: need-=add_candidate(slot,cand,macro,need)
            for _ in range(3):
                if totals[macro] >= goal*0.99: break
                order=sorted(ordered_slots,key=lambda s: meal_state[s]["kcal"]/max(1.0,target["kcal"]*shares[s]))
                for slot in order:
                    need=max(0.0,goal-totals[macro])
                    for cand in candidates[slot]: need-=add_candidate(slot,cand,macro,need)

        fill("protein",protein_candidates,0.90)
        fill("carbs",carb_candidates,0.95)
        fill("fat",fat_candidates,1.0)
        if totals["protein"] < target["protein"] * 0.95:
            fill("protein",protein_candidates,0.98)
        if fasting and totals["protein"] < 138.0:
            fill("protein",protein_candidates,1.0)
        fill("carbs",carb_candidates,1.0)
        fixed_slots = {
            spec.label for spec, _ in selected
            if str(slot_templates.get(spec.label, {}).get("Template ID") or "") in ("MN-B02", "MF-B02", "MN-S-SHAKE", "MN-B07")
        }

        if totals["kcal"] < target["kcal"] * 0.97:
            energy = {slot: [] for slot in ordered_slots}
            for spec, _ in selected:
                if spec.label in fixed_slots:
                    continue
                is_sweet = is_sweet_or_breakfast_dish(spec.label)
                if spec.source_slot == "Breakfast" and any(fid in food_by_slot[spec.label] for fid in ("A011", "A013")):
                    continue
                if spec.source_slot in ("Breakfast", "Snack") or is_sweet:
                    energy[spec.label] = [candidate("T004", 30), candidate("T003", 30)]
                elif is_save_budget:
                    energy[spec.label] = [candidate("T002", 14)]
                else:
                    energy[spec.label] = [candidate("T001", 14)]
            fill("kcal", energy, 1.0)

        # Caloric Floor Enforcement: Ensure day total is within ±3% of target_kcal (>= target["kcal"] - 50)
        calorie_floor = target["kcal"] - 50.0  # 2,050 kcal for 2,100 kcal target
        if totals["kcal"] < calorie_floor:
            # 1. Scale primary carbs of native recipes
            carb_fill_order = []
            for spec, _ in selected:
                tmpl_id = str(slot_templates.get(spec.label, {}).get("Template ID") or "")
                # Never inject loose carbs into composite dishes unless scaling native carb
                comp_rids = [str(c.get("Item ID")) for c in self.components.get(tmpl_id, []) if str(c.get("Item Type")) == "Recipe"]
                if any(r in COMPOSITE_RECIPES for r in comp_rids):
                    if any(r in ("R027", "R014") for r in comp_rids):
                        carb_fill_order.append((spec.label, "C006"))
                    elif any(r in ("R026", "R010", "R011") for r in comp_rids):
                        carb_fill_order.append((spec.label, "C003"))
                    elif any(r == "R028" for r in comp_rids):
                        carb_fill_order.append((spec.label, "C008"))
                    continue
                if spec.source_slot == "Breakfast":
                    if "A013" in food_by_slot[spec.label] or "yogurt" in str(slot_templates.get(spec.label, {}).get("Meal Name") or "").lower():
                        if food_by_slot[spec.label].get("C007", 0.0) < 60.0:
                            carb_fill_order.append((spec.label, "C007"))
                    if "C007" in food_by_slot[spec.label] and food_by_slot[spec.label].get("C007", 0.0) < 80.0:
                        carb_fill_order.append((spec.label, "C007"))
                    elif "C008" in food_by_slot[spec.label] and food_by_slot[spec.label].get("C008", 0.0) < 130.0:
                        carb_fill_order.append((spec.label, "C008"))
                    continue
                if spec.source_slot == "Snack":
                    # Snack carbs: clamp C020 strictly to max 40g (4 thin rice cakes)
                    if "A015" in food_by_slot[spec.label]:
                        carb_fill_order.append((spec.label, "C007"))
                    elif "C020" in food_by_slot[spec.label]:
                        if food_by_slot[spec.label].get("C020", 0.0) < 40.0:
                            carb_fill_order.append((spec.label, "C020"))
                    elif fasting:
                        carb_fill_order.append((spec.label, "C007"))
                        if food_by_slot[spec.label].get("C020", 0.0) < 40.0:
                            carb_fill_order.append((spec.label, "C020"))
                    continue
                slot_carb = preferred_carb(spec.label, spec.source_slot)
                if slot_carb in ("C001", "C003", "C004", "C011", "C010", "C007", "C008", "C006"):
                    carb_fill_order.append((spec.label, slot_carb))

            for slot, cid in carb_fill_order:
                if totals["kcal"] >= calorie_floor:
                    break
                food = self.foods.get(cid)
                if not food:
                    continue
                per_total = food_macros(food, 1.0)
                if per_total.kcal <= 0:
                    continue
                kcal_deficit = target["kcal"] - totals["kcal"]
                needed_g = kcal_deficit / per_total.kcal

                group = practical_group(cid)
                current_used = group_used(slot, group)
                cap = SERVING_HARD_CAPS.get(cid, practical_cap(group, self.settings))
                avail_g = max(0.0, cap - current_used)
                mass_avail = max(0.0, (slot_specs[slot].mass_cap_g + 80) - mass_by_slot[slot])
                add_g = min(needed_g, avail_g, mass_avail)
                if per_total.protein > 0 and totals["protein"] + (add_g * per_total.protein) > upper["protein"]:
                    add_g = max(0.0, (upper["protein"] - totals["protein"]) / per_total.protein)
                if add_g >= 10.0:
                    found = next((x for x in extras[slot] if x["id"] == cid), None)
                    if found:
                        found["grams"] += add_g
                    else:
                        extras[slot].append({"id": cid, "grams": add_g})
                    food_by_slot[slot][cid] = food_by_slot[slot].get(cid, 0.0) + add_g
                    mass_by_slot[slot] += add_g
                    delta = food_macros(food, add_g)
                    for key in totals:
                        dv = getattr(delta, key)
                        totals[key] += dv
                        meal_state[slot][key] += dv

            # 2. If snack has peanut butter or peanuts, scale native peanut butter or peanuts up to cap
            if totals["kcal"] < calorie_floor:
                for spec, _ in selected:
                    if spec.source_slot == "Snack" and spec.label not in fixed_slots:
                        if "T004" in food_by_slot[spec.label]:
                            p_food = self.foods.get("T004")
                            cur_g = food_by_slot[spec.label].get("T004", 0.0)
                            add_g = min(32.0 - cur_g, (calorie_floor - totals["kcal"]) / 6.0)
                            if add_g >= 5.0 and p_food:
                                found = next((x for x in extras[spec.label] if x["id"] == "T004"), None)
                                if found: found["grams"] += add_g
                                else: extras[spec.label].append({"id": "T004", "grams": add_g})
                                food_by_slot[spec.label]["T004"] = cur_g + add_g
                                mass_by_slot[spec.label] += add_g
                                delta = food_macros(p_food, add_g)
                                for key in totals: totals[key] += getattr(delta, key); meal_state[spec.label][key] += getattr(delta, key)
                        elif "T003" in food_by_slot[spec.label]:
                            p_food = self.foods.get("T003")
                            cur_g = food_by_slot[spec.label].get("T003", 0.0)
                            add_g = min(35.0 - cur_g, (calorie_floor - totals["kcal"]) / 5.8)
                            if add_g >= 5.0 and p_food:
                                found = next((x for x in extras[spec.label] if x["id"] == "T003"), None)
                                if found: found["grams"] += add_g
                                else: extras[spec.label].append({"id": "T003", "grams": add_g})
                                food_by_slot[spec.label]["T003"] = cur_g + add_g
                                mass_by_slot[spec.label] += add_g
                                delta = food_macros(p_food, add_g)
                                for key in totals: totals[key] += getattr(delta, key); meal_state[spec.label][key] += getattr(delta, key)

            # 4. If still below floor, add olive oil / healthy cooking oil to savory meals (0g protein, 8.84 kcal/g)
            if totals["kcal"] < calorie_floor:
                for slot in ordered_slots:
                    if totals["kcal"] >= calorie_floor:
                        break
                    if slot in fixed_slots or is_sweet_or_breakfast_dish(slot):
                        continue
                    oil_id = "T002" if is_save_budget else "T001"
                    other_oil_id = "T001" if is_save_budget else "T002"
                    # Strictly maintain single-oil rule: never split oils in the same meal
                    if food_by_slot[slot].get(other_oil_id, 0.0) > 0:
                        continue
                    oil_food = self.foods.get(oil_id)
                    if not oil_food:
                        continue
                    oil_cur = food_by_slot[slot].get(oil_id, 0.0)
                    oil_needed = (calorie_floor - totals["kcal"]) / 8.84
                    oil_add = min(max(0.0, 24.0 - oil_cur), oil_needed)
                    if oil_add >= 2.0:
                        found = next((x for x in extras[slot] if x["id"] == oil_id), None)
                        if found:
                            found["grams"] += oil_add
                        else:
                            extras[slot].append({"id": oil_id, "grams": oil_add})
                        food_by_slot[slot][oil_id] = oil_cur + oil_add
                        mass_by_slot[slot] += oil_add
                        delta = food_macros(oil_food, oil_add)
                        for key in totals:
                            totals[key] += getattr(delta, key)
                            meal_state[slot][key] += getattr(delta, key)

        warnings = []
        variances = {
            "kcal": (totals["kcal"] - target["kcal"]) / target["kcal"],
            "protein": (totals["protein"] - target["protein"]) / target["protein"],
            "carbs": (totals["carbs"] - target["carbs"]) / target["carbs"],
            "fat": (totals["fat"] - target["fat"]) / target["fat"],
        }
        if totals["protein"] < target["protein"] * 0.95:
            warnings.append(
                f"Daily protein ({totals['protein']:.1f}g) fell below 95% floor target ({target['protein']:.1f}g)."
            )
        legume_ids = {"P001", "P002", "P003", "P004", "P005", "P006", "P007", "P008"}
        daily_legume_g = sum(v.get(fid, 0.0) for fid in legume_ids for v in food_by_slot.values())
        if daily_legume_g > 550.0:
            warnings.append(
                f"High daily legume volume ({daily_legume_g:.0f}g cooked); balance with grains/tubers recommended for digestive comfort."
            )
        if totals["fibre"] > 65.0:
            warnings.append(
                f"High daily fiber volume ({totals['fibre']:.1f}g); balance with lower-fiber starches recommended for GI tolerance."
            )

        if not (abs(variances["kcal"]) <= 0.03 and abs(variances["protein"]) <= 0.10 and abs(variances["carbs"]) <= 0.10 and abs(variances["fat"]) <= 0.15):
            warnings.append("Daily targets were not reached within practical portion caps; coach review/tuning required.")
        for spec, _ in selected:
            if meal_state[spec.label]["kcal"] > target["kcal"] * spec.kcal_cap_fraction + 1:
                warnings.append(f"{spec.label} exceeds the practical energy cap.")
            if mass_by_slot[spec.label] > spec.mass_cap_g + 1:
                warnings.append(f"{spec.label} exceeds the practical food-volume cap.")
        return DaySolution(
            scale=scale, extras=extras, warnings=list(dict.fromkeys(warnings)),
            totals=MacroTotals(**totals), food_by_slot=food_by_slot, mass_by_slot=mass_by_slot,
        )
