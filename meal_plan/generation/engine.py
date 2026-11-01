from __future__ import annotations

import math
import re
from datetime import date, timedelta
from typing import Any

from meal_plan.generation.dataset import HilaweDataset, load_dataset
from meal_plan.generation.fasting import fasting_days_for_period
from meal_plan.generation.formatting import familiar_portion
from meal_plan.generation.grocery import build_grocery
from meal_plan.generation.meal_structure import meal_structure
from meal_plan.generation.models import GeneratedDay, GeneratedMeal, MacroTotals, MealItem, SlotSpec
from meal_plan.generation.selection import TemplateSelector
from meal_plan.generation.solver import DaySolver, food_macros, n, template_macros, recipe_macros
from meal_plan.generation.swaps import build_exchange_options


ENGINE_VERSION = "HILAWE_PY_ENGINE_V1.0_PHASE6"
SETTINGS_VERSION = "HILAWE_V1.3_PLUS_MEALCOUNT_EXTENSION_V1"


class GenerationError(ValueError):
    pass


def _target_dict(profile: dict[str, Any]) -> dict[str, float]:
    result = {
        "target_kcal": n(profile.get("target_kcal")),
        "protein_g": n(profile.get("protein_g")),
        "carbs_g": n(profile.get("carbs_g")),
        "fat_g": n(profile.get("fat_g")),
    }
    if min(result.values()) <= 0:
        raise GenerationError("Nutrition profile is missing approved macro targets")
    return result


def _ingredient_food_grams(dataset: HilaweDataset, recipe_id: str, prepared_grams: float) -> dict[str, float]:
    recipe = dataset.recipe_by_id.get(recipe_id) or {}
    yield_g = max(1.0, n(recipe.get("Yield g")))
    fraction = prepared_grams / yield_g
    out: dict[str, float] = {}
    for row in dataset.ingredients_by_recipe.get(recipe_id, []):
        fid = str(row.get("Food ID") or "")
        if fid:
            out[fid] = out.get(fid, 0.0) + n(row.get("Weight g")) * fraction
    return out


def _recipe_familiar_measure(rid: str, rname: str) -> str:
    r_lower = (rname or "").lower()
    if "avocado toast" in r_lower or rid == "R028":
        return "2 slices"
    if "tofu tibs" in r_lower or (rid == "R024" and "tofu" in r_lower):
        return "1 large bowl"
    if any(w in r_lower for w in ("wot", "alicha", "minchet", "shiro", "misir", "dinich")):
        return "1 medium ladle"
    if any(w in r_lower for w in ("tibs", "kitfo", "steak", "fillet")):
        return "1 palm portion"
    if any(w in r_lower for w in ("firfir", "ful", "salad", "bowl", "gomen", "fosolia")):
        return "1 small bowl"
    if "toast" in r_lower:
        return "2 slices"
    return "1 medium ladle"


def _build_meal(
    dataset: HilaweDataset,
    answers: dict[str, Any],
    spec: SlotSpec,
    template: dict[str, Any],
    scale: float,
    extras: list[dict[str, float]],
    *,
    day_fasting: bool,
    restriction_fasting: bool,
) -> GeneratedMeal:
    foods = dataset.food_by_id
    recipes = dataset.recipe_by_id
    items: list[MealItem] = []
    direct: dict[str, float] = {}
    recipe_ids: list[str] = []
    warnings: list[str] = []
    effective_scale = 1.0 if spec.source_slot == "Breakfast" else scale
    meal_macros = template_macros(template).scale(effective_scale)

    budget_raw = str(answers.get("grocery_budget") or "").upper()
    is_save_budget = budget_raw in {"SAVE", "VALUE", "ቆጣቢ"} or "SAVE" in budget_raw or "ቆጣቢ" in budget_raw
    dietary_raw = str(answers.get("dietary_preference") or answers.get("dietary_pattern") or "OMNIVORE").upper()
    is_omnivore = "OMNIVORE" in dietary_raw or not day_fasting

    tmpl_id = str(template.get("Template ID") or "")
    if tmpl_id == "MN-S-SHAKE":
        # High-calorie compact strength shake for hardgainer: Low-fat milk 250ml, Oats 40g, Peanut butter 30g, Banana 120g
        direct["A015"] = 250.0
        direct["C007"] = 40.0
        direct["T004"] = 30.0
        direct["F001"] = 120.0
        meal_macros = MacroTotals(450.0, 22.0, 65.0, 18.0, 5.0)
    elif tmpl_id == "MN-B07":
        # Fixed 3-component Egg Firfir breakfast: 180g Egg Firfir, 120g Injera, 60g Cucumber
        firfir_g = 180.0
        items.append(MealItem(
            food_id="",
            food_name="የእንቁላል ፍርፍር" if is_save_budget else str(recipes.get("R021", {}).get("Recipe Name") or "Egg Firfir"),
            grams=firfir_g,
            source="recipe",
            familiar="በግምት 1 አነስተኛ ሳህን",
            exchange_group=None,
            recipe_id="R021",
            recipe_name=str(recipes.get("R021", {}).get("Recipe Name") or "Egg Firfir"),
            prepared_grams=firfir_g,
            macros=MacroTotals(218.0, 13.0, 7.2, 15.1, 1.7),
        ))
        direct["C001"] = 120.0
        direct["V012"] = 60.0
        recipe_ids.append("R021")
        meal_macros = MacroTotals(443.0, 19.6, 53.8, 16.5, 5.5)
    else:
        for component in dataset.components_by_template.get(tmpl_id, []):
            grams = n(component.get("Portion g")) * effective_scale
            if str(component.get("Item Type")) == "Food":
                fid = str(component.get("Item ID") or "")
                if fid:
                    if fid == "A008":
                        # Canned tuna anchor: maintain at least 130g drained weight for sports nutrition
                        grams = max(130.0, grams)
                    elif fid in ("A001", "A002"):
                        grams = max(130.0, grams)
                    elif fid == "A011" and spec.source_slot == "Breakfast" and float(answers.get("current_weight_kg") or 0) >= 55.0:
                        grams = max(150.0, grams)
                    if is_save_budget:
                        if fid == "T001": fid = "T002"
                    else:
                        if fid == "T002": fid = "T001"
                    if is_save_budget and is_omnivore and fid == "P014":
                        fid = "A015"
                        grams = 200.0
                    direct[fid] = direct.get(fid, 0.0) + grams
            else:
                rid = str(component.get("Item ID") or "")
                # Deconstruct composite oatmeal bowl (R025 / MN-B02 / MF-B02) into discrete kitchen ingredients
                if rid == "R025" or tmpl_id in ("MN-B02", "MF-B02"):
                    if is_save_budget and is_omnivore:
                        direct["A015"] = 200.0  # Milk, low-fat (ወተት (ዝቅተኛ ቅባት))
                    else:
                        direct["A014"] = 200.0  # Yogurt, low-fat (እርጎ (ዝቅተኛ ቅባት))
                    direct["C007"] = 50.0   # Oats, dry (አጃ / ኦትስ (ጥሬ))
                    direct["F001"] = 120.0  # Banana (ሙዝ)
                    direct["T003"] = 30.0   # Peanuts (የተቆላ ለውዝ)
                    continue

                recipe = recipes.get(rid) or {}
                recipe_ids.append(rid)
                calibration = str(recipe.get("Calibration Status") or "")
                if "required" in calibration.lower():
                    warnings.append(f"Recipe calibration required before final approval: {recipe.get('Recipe Name') or rid}")
                r_name = str(recipe.get("Recipe Name") or component.get("Item Name") or rid)

                # Round stews (Key Wot, Minchet Abish, Doro Wot, Shiro, Misir) to clean multiples of 25g
                is_stew = any(w in r_name.lower() for w in ("wot", "alicha", "minchet", "shiro", "misir", "stew", "ወጥ", "አልጫ")) or rid in ("R001", "R002", "R003", "R004", "R005", "R006", "R007", "R008", "R014", "R015", "R016", "R017")
                if is_stew:
                    grams = max(25.0, round(grams / 25.0) * 25.0)
                else:
                    if grams >= 100.0:
                        grams = float(round(grams / 10.0) * 10.0)
                    else:
                        grams = float(round(grams / 5.0) * 5.0)

                # Hard Upper Bounds on Single-Meal Animal Protein Portions for small-framed clients (< 55 kg)
                is_small_frame = float(answers.get("current_weight_kg") or 0) < 55.0
                if is_small_frame:
                    if rid in ("R023", "R020", "R017", "R016"):
                        grams = min(grams, 210.0)
                    elif rid in ("R018", "R019"):
                        grams = min(grams, 140.0)
                    elif rid in ("R015", "R014"):
                        grams = min(grams, 130.0)
                    elif rid == "R024":
                        grams = min(grams, 210.0)

                r_frac = grams / max(1.0, n(component.get("Portion g")))
                if "avocado toast" in r_name.lower() or rid == "R028":
                    fam_str = "about 2 slices"
                elif "tofu" in r_name.lower() and rid == "R024":
                    fam_str = "about 1 large bowl"
                else:
                    fam_str = familiar_portion(n(component.get("Servings"))*r_frac, _recipe_familiar_measure(rid, r_name))
                items.append(MealItem(
                    food_id="",
                    food_name=r_name,
                    grams=grams,
                    source="recipe",
                    familiar=fam_str,
                    exchange_group=str(component.get("Exchange Note") or "") or None,
                    recipe_id=rid,
                    recipe_name=r_name,
                    prepared_grams=grams,
                    macros=MacroTotals(
                        n(component.get("kcal"))*r_frac,
                        n(component.get("Protein g"))*r_frac,
                        n(component.get("Carbs g"))*r_frac,
                        n(component.get("Fat g"))*r_frac,
                        n(component.get("Fibre g"))*r_frac,
                    ),
                ))

        # Deduplication guard: if a recipe in this meal already contains this carb/protein,
        # do not append a duplicate loose line from solver extras;
        # instead, scale up the recipe item so calories and macros are fully preserved!
        recipe_ingredient_fids = {}
        for rid in recipe_ids:
            for ing in dataset.ingredients_by_recipe.get(rid, []):
                recipe_ingredient_fids[str(ing.get("Food ID") or "")] = rid

        for extra in extras:
            fid = str(extra["id"])
            target_rid = recipe_ingredient_fids.get(fid)
            # Absorb loose rice/pasta into composite bowls (R026 Chicken Rice Bowl, R027 Tuna Pasta)
            if not target_rid and fid in ("C003", "C004") and "R026" in recipe_ids:
                target_rid = "R026"
            elif not target_rid and fid in ("C005", "C006") and "R027" in recipe_ids:
                target_rid = "R027"

            if target_rid and (fid.startswith(("C", "P")) or fid in ("A001", "A002", "A008", "A011")):
                recipe_item = next((it for it in items if it.recipe_id == target_rid), None)
                if recipe_item and recipe_item.grams > 0:
                    extra_macros = food_macros(foods[fid], float(extra["grams"]))
                    rec = dataset.recipe_by_id.get(target_rid, {})
                    base_kcal = n(rec.get("kcal / Serving") or rec.get("kcal per serving") or rec.get("kcal"))
                    base_serv_g = n(rec.get("Serving g") or rec.get("serving_g") or 400.0)
                    kcal_per_g = base_kcal / max(1.0, base_serv_g)
                    extra_g = float(extra["grams"])
                    recipe_item.grams += extra_g
                    recipe_item.macros = recipe_item.macros.plus(extra_macros)
                    servings = recipe_item.grams / max(1.0, base_serv_g)
                    if "toast" in recipe_item.food_name.lower() or target_rid == "R028":
                        recipe_item.familiar = "about 2 slices"
                    elif "tofu" in recipe_item.food_name.lower() and target_rid == "R024":
                        recipe_item.familiar = "about 1 large bowl"
                    elif "chicken rice bowl" in recipe_item.food_name.lower() or target_rid == "R026":
                        recipe_item.familiar = "150g cooked chicken breast + 300g cooked rice"
                    elif "lentil rice bowl" in recipe_item.food_name.lower() or target_rid == "R025":
                        recipe_item.familiar = "250g cooked lentils + 350g cooked brown rice"
                    elif "tuna pasta" in recipe_item.food_name.lower() or target_rid == "R027":
                        recipe_item.familiar = "130g canned tuna + 350g cooked whole-wheat pasta"
                    else:
                        q_serv = max(1.0, round(servings * 4) / 4)
                        recipe_item.familiar = f"about {q_serv:g} standard serving"
                    continue
            direct[fid] = direct.get(fid, 0.0) + float(extra["grams"])
            meal_macros = meal_macros.plus(food_macros(foods[fid], float(extra["grams"])))

        # 1. Single rice variety per meal: never boil two separate pots of rice (white + brown)
        if "C003" in direct and "C004" in direct:
            is_brown_primary = "brown" in str(template.get("Meal Name") or "").lower() or "C004" in [str(c.get("Item ID")) for c in dataset.components_by_template.get(tmpl_id, [])]
            if is_brown_primary:
                direct["C004"] = min(300.0, direct["C004"] + direct.pop("C003"))
            else:
                direct["C003"] = min(300.0, direct["C003"] + direct.pop("C004"))

        # 2. Single potato variety per meal: never mix boiled potato (C010) and sweet potato (C011)
        if "C010" in direct and "C011" in direct:
            is_sweet_primary = "sweet potato" in str(template.get("Meal Name") or "").lower() or "C011" in [str(c.get("Item ID")) for c in dataset.components_by_template.get(tmpl_id, [])]
            if is_sweet_primary:
                direct["C011"] = min(400.0, direct["C011"] + direct.pop("C010"))
            else:
                direct["C010"] = min(400.0, direct["C010"] + direct.pop("C011"))

        # 3. Single carb in snacks: never stack dry raw oats on top of rice cakes
        if spec.source_slot == "Snack":
            if "C020" in direct and "C007" in direct:
                oat_g = direct.pop("C007")
                if "T004" in direct:
                    direct["T004"] = min(45.0, direct["T004"] + (oat_g * 0.5))
                elif "F001" in direct:
                    direct["F001"] = min(150.0, direct["F001"] + (oat_g * 1.5))
            if "C007" in direct and "A015" not in direct and "A014" not in direct and "P014" not in direct:
                # Dates and peanuts snack: avoid dry raw oats without milk/yogurt
                oat_g = direct.pop("C007")
                if "F012" in direct:
                    direct["F012"] = min(80.0, direct["F012"] + (oat_g * 1.0))
                if "T003" in direct:
                    direct["T003"] = min(40.0, direct["T003"] + (oat_g * 0.4))

        # Day 5 / Fasting Breakfast: Peanut banana oats (MF-B07)
        # Cap Peanut Butter (T004) to 15g, and provide Soy Milk (P014) 250g as liquid base
        if tmpl_id == "MF-B07" and day_fasting:
            if "T004" in direct:
                pb_diff = direct["T004"] - 15.0
                direct["T004"] = 15.0
                if pb_diff > 0:
                    meal_macros = meal_macros.minus(food_macros(foods["T004"], pb_diff))
            if "P014" not in direct and "P014" in foods:
                direct["P014"] = 250.0
                meal_macros = meal_macros.plus(food_macros(foods["P014"], 250.0))

        # Single cooking oil binary rule for ALL meals: never split T001 and T002 in the same meal
        oil_fid = "T002" if is_save_budget else "T001"
        other_oil_fid = "T001" if is_save_budget else "T002"
        if other_oil_fid in direct:
            direct[oil_fid] = direct.get(oil_fid, 0.0) + direct.pop(other_oil_fid)

        # Mandatory Cooking Oil Anchor for Dry Pan-Seared Savory Meat/Fish Dishes
        # NEVER apply to stews (Key Wot R023, Minchet Abish R020, Doro Wot R016, Siga Wot R017, Shiro R001, Misir R002, etc.)
        # which already have oil/kibe in their composite recipe ingredients!
        WOT_RECIPES_WITH_BUILT_IN_FAT = {
            "R001", "R002", "R003", "R004", "R005", "R006", "R007", "R008",
            "R014", "R016", "R017", "R020", "R023"
        }
        has_wot_stew = any(r in WOT_RECIPES_WITH_BUILT_IN_FAT for r in recipe_ids)
        has_dry_meat_fish = (
            any(r in ("R018", "R019", "R015") for r in recipe_ids)
            or any(fid in ("A001", "A002", "A003", "A004", "A005", "A006", "A007", "A019", "A020") for fid in direct)
        ) and not has_wot_stew

        primary_goal = str(answers.get("primary_goal") or "").upper()
        is_weight_loss = "LOSS" in primary_goal or "CUT" in primary_goal
        target_oil_g = 5.0 if is_weight_loss else 8.0

        if has_dry_meat_fish:
            if direct.get(oil_fid, 0.0) < target_oil_g:
                oil_needed = target_oil_g - direct.get(oil_fid, 0.0)
                direct[oil_fid] = target_oil_g
                meal_macros = meal_macros.plus(food_macros(foods[oil_fid], oil_needed))
        elif has_wot_stew:
            # If a rich stew is present, eliminate any loose oil injection
            if oil_fid in direct:
                oil_removed = direct.pop(oil_fid)
                meal_macros = meal_macros.minus(food_macros(foods[oil_fid], oil_removed))

        # Eliminate negligible micro-doses of cooking oil (< 4g) across all meals
        if direct.get(oil_fid, 0.0) > 0 and direct[oil_fid] < 4.0:
            oil_removed = direct.pop(oil_fid)
            meal_macros = meal_macros.minus(food_macros(foods[oil_fid], oil_removed))

    meal_food_ids = set(direct.keys())
    exchange_options: list[dict[str, Any]] = []
    for fid, grams in sorted(direct.items()):
        food = foods.get(fid)
        if not food:
            continue
        if fid == "A011":
            # Boiled Whole Eggs constrained to clean multiples of 50g (1 egg = 50g, 2 eggs = 100g, 3 eggs = 150g)
            grams = max(50.0, round(grams / 50.0) * 50.0)
            cnt = int(grams / 50.0)
            fam = f"{cnt} large eggs"
        elif fid in ("T001", "T002", "T012"):
            if grams < 4.0:
                continue
            grams = float(round(grams / 5.0) * 5.0)
            fam = familiar_portion(grams/max(1.0,n(food.get("Standard Portion g"))), str(food.get("Familiar Measure") or "standard portion"))
        elif fid == "A015":
            grams = float(round(grams / 10.0) * 10.0)
            if round(grams) == 200:
                fam = "በግምት ሶስት አራተኛ ትልቅ ብርጭቆ"
            elif round(grams) == 250:
                fam = "1 large glass"
            else:
                fam = familiar_portion(grams/max(1.0,n(food.get("Standard Portion g"))), str(food.get("Familiar Measure") or "standard portion"))
        elif fid == "C001":
            # Standardize Injera: 1 medium rolled Injera = 120g (strict 60g increments)
            grams = max(60.0, round(grams / 60.0) * 60.0)
            inj_rolls = grams / 120.0
            if inj_rolls == 1.0: fam = "1 medium rolled piece"
            elif inj_rolls == 1.5: fam = "1 ½ medium rolled piece"
            elif inj_rolls == 2.0: fam = "2 medium rolled piece"
            elif inj_rolls == 0.5: fam = "½ medium rolled piece"
            else: fam = f"{inj_rolls:.1f} medium rolled piece"
        elif fid in ("C010", "C011"):
            # Round potato / sweet potato to clean multiples of 50g
            grams = max(100.0, round(grams / 50.0) * 50.0)
            fam = familiar_portion(grams/max(1.0,n(food.get("Standard Portion g"))), str(food.get("Familiar Measure") or "standard portion"))
        else:
            # Clean kitchen rounding for all vegetables, meats, legumes, fruits (10g for >=100g, 5g for <100g)
            if grams >= 100.0:
                grams = float(round(grams / 10.0) * 10.0)
            else:
                grams = float(round(grams / 5.0) * 5.0)
            fam = familiar_portion(grams/max(1.0,n(food.get("Standard Portion g"))), str(food.get("Familiar Measure") or "standard portion"))

        item = MealItem(
            food_id=fid,
            food_name=str(food.get("Food Name") or fid),
            grams=grams,
            source="food",
            familiar=fam,
            exchange_group=str(food.get("Exchange Group") or "") or None,
            macros=food_macros(food, grams),
        )
        items.append(item)
        options = build_exchange_options(
            fid, dataset, answers,
            fasting=restriction_fasting,
            base_grams=grams,
            meal_food_ids=meal_food_ids,
            source_slot=spec.source_slot,
        )
        if options:
            swap_type = options[0].get("swap_type") or ("carb" if fid.startswith("C") else ("protein" if fid.startswith(("A", "P")) else "other"))
            exchange_options.append({"for_food_id": fid, "for_food_name": item.food_name, "swap_type": swap_type, "options": options})

    def _swap_prio(ex: dict[str, Any]) -> int:
        ffid = ex.get("for_food_id", "")
        if ffid in ("C001", "C010", "C011", "C003", "C007", "C005", "C008"): return 1
        if ffid in ("A018", "A011", "A001", "A002", "A007", "P010", "P001"): return 2
        return 3
    exchange_options.sort(key=_swap_prio)

    # Recalculate meal_macros strictly from the discrete kitchen items
    meal_macros = MacroTotals()
    for item in items:
        meal_macros = meal_macros.plus(item.macros)

    m_name = str(template.get("Meal Name"))
    if tmpl_id == "MN-B04":
        m_name = "Boiled eggs, bread and orange"
    if "A015" in meal_food_ids and "P014" not in meal_food_ids:
        if "soy milk" in m_name.lower():
            m_name = re.sub(r"soy milk", "milk", m_name, flags=re.I)
    if "A015" in meal_food_ids and "A014" not in meal_food_ids:
        if tmpl_id in ("MN-B02", "MF-B02", "MF-B07", "R025") or "yogurt" in m_name.lower() or "እርጎ" in m_name:
            m_name = "Oatmeal with milk, banana and peanuts"

    return GeneratedMeal(
        slot=spec.label,
        source_slot=spec.source_slot,
        template_id=str(template.get("Template ID")),
        meal_name=m_name,
        fasting=day_fasting,
        items=items,
        macros=meal_macros,
        exchange_options=exchange_options,
        warnings=list(dict.fromkeys(warnings)),
        recipe_ids=list(dict.fromkeys(recipe_ids)),
    )


def _rotation(
    duration_days: int,
    start_date: date,
    fasting_days: tuple[bool, ...] | None = None,
    fasting_core_days: tuple[bool, ...] | None = None,
) -> list[dict[str, Any]]:
    output=[]
    for offset in range(duration_days):
        week=offset//7+1
        core_day=offset%7
        # Agreed product model: week 1 primary, week 2 swaps, week 3 primary,
        # week 4 swaps; days 29-30 continue into the next primary cycle.
        mode="SWAP_ROTATION" if week in {2,4} else "PRIMARY"
        output.append({
            "day_number":offset+1,
            "date":(start_date+timedelta(days=offset)).isoformat(),
            "week":week,
            "core_day_index":core_day,
            "mode":mode,
            "fasting": bool(fasting_days and fasting_days[offset]),
            "core_source": "FASTING" if fasting_core_days and fasting_core_days[offset] else "REGULAR",
        })
    return output


def _generate_core_week(
    *,
    dataset: HilaweDataset,
    answers: dict[str, Any],
    slots: tuple[SlotSpec, ...] | list[SlotSpec],
    targets: dict[str, float],
    start_date: date,
    fasting_days: tuple[bool, ...],
    region: str,
    country_name: str | None,
) -> tuple[list[GeneratedDay], dict[str, float], list[str]]:
    selector = TemplateSelector(dataset, answers, region=region, country_name=country_name)
    solver = DaySolver(dataset, answers)
    days: list[GeneratedDay] = []
    weekly_food_grams: dict[str, float] = {}
    all_warnings: list[str] = []
    fasting_ordinal = 0
    dietary = str(answers.get("dietary_pattern") or "").upper()

    for d in range(7):
        current = start_date + timedelta(days=d)
        fasting = fasting_days[d]
        template_fasting_mode = fasting or dietary == "VEGAN"
        orthodox_mode = str(answers.get("orthodox_fasting") or "").upper() in ("WED_FRI", "LENT", "ALL_FASTS", "YES")
        fish_permitted = fasting and dietary == "OMNIVORE" and bool(answers.get("fish_during_fast")) and not orthodox_mode
        fish_slot = "Lunch" if fish_permitted and fasting_ordinal % 2 == 0 else ("Dinner" if fish_permitted else "")
        selected: list[tuple[SlotSpec, dict[str, Any]]] = []
        used_today: set[str] = set()
        used_recipes_today: set[str] = set()
        for spec in slots:
            prefer_fish = spec.source_slot == fish_slot
            avoid_fish = fish_permitted and spec.source_slot in {"Lunch", "Dinner"} and spec.source_slot != fish_slot
            template = selector.choose(
                fasting=template_fasting_mode, source_slot=spec.source_slot, day_index=d,
                exclude_today=used_today, exclude_recipes=used_recipes_today,
                prefer_fish=prefer_fish, avoid_fish=avoid_fish, whole_food_first=fasting,
            )
            tid = str(template.get("Template ID"))
            used_today.add(tid)
            for comp in dataset.components_by_template.get(tid, []):
                if str(comp.get("Item Type")) == "Recipe":
                    used_recipes_today.add(str(comp.get("Item ID")))
            selected.append((spec, template))
        if fasting:
            fasting_ordinal += 1

        solution = solver.solve(selected, targets, fasting=template_fasting_mode)
        meals=[]
        day_warnings=list(solution.warnings)
        for spec, template in selected:
            meal=_build_meal(
                dataset, answers, spec, template, solution.scale, solution.extras.get(spec.label, []),
                day_fasting=fasting, restriction_fasting=template_fasting_mode,
            )
            meals.append(meal)
            day_warnings.extend(meal.warnings)
            for item in meal.items:
                if item.food_id:
                    weekly_food_grams[item.food_id] = weekly_food_grams.get(item.food_id, 0.0) + item.grams
                elif item.recipe_id:
                    # Recursive grocery unpacking: tally raw foods from composite recipe
                    recipe_raw = _ingredient_food_grams(dataset, item.recipe_id, item.grams)
                    for r_fid, r_grams in recipe_raw.items():
                        if r_fid:
                            weekly_food_grams[r_fid] = weekly_food_grams.get(r_fid, 0.0) + r_grams

        # Day 3 (Fasting Wednesday) Lunch & Snack balance:
        # Move excess white rice out of heavy 4-carb Lunch into Afternoon Snack
        if fasting:
            lunch_meal = next((m for m in meals if m.source_slot == "Lunch"), None)
            snack_meal = next((m for m in meals if m.source_slot == "Snack"), None)
            if lunch_meal and snack_meal and lunch_meal.macros.kcal > 1100.0:
                rice_item = next((it for it in lunch_meal.items if it.food_id == "C003"), None)
                if rice_item:
                    lunch_meal.items.remove(rice_item)
                    removed_macros = rice_item.macros
                    lunch_meal.macros = MacroTotals(
                        lunch_meal.macros.kcal - removed_macros.kcal,
                        lunch_meal.macros.protein - removed_macros.protein,
                        lunch_meal.macros.carbs - removed_macros.carbs,
                        lunch_meal.macros.fat - removed_macros.fat,
                        lunch_meal.macros.fibre - removed_macros.fibre,
                    )
                    weekly_food_grams["C003"] = max(0.0, weekly_food_grams.get("C003", 0.0) - rice_item.grams)
                    oats_food = dataset.food_by_id.get("C007")
                    if oats_food:
                        add_oats_g = 50.0
                        oats_macros = food_macros(oats_food, add_oats_g)
                        existing_oats = next((it for it in snack_meal.items if it.food_id == "C007"), None)
                        if existing_oats:
                            existing_oats.grams += add_oats_g
                            existing_oats.macros = existing_oats.macros.plus(oats_macros)
                            existing_oats.familiar = "about 1 cup dry"
                        else:
                            snack_meal.items.append(MealItem(
                                food_id="C007",
                                food_name="Oats (Dry)",
                                grams=add_oats_g,
                                source="food",
                                familiar="about 1 cup dry",
                                exchange_group="Grain / starch",
                                macros=oats_macros,
                            ))
                        snack_meal.macros = snack_meal.macros.plus(oats_macros)
                        weekly_food_grams["C007"] = weekly_food_grams.get("C007", 0.0) + add_oats_g
                    pb_food = dataset.food_by_id.get("T004")
                    if pb_food:
                        add_pb_g = 12.0
                        pb_macros = food_macros(pb_food, add_pb_g)
                        snack_meal.items.append(MealItem(
                            food_id="T004",
                            food_name="Peanut butter",
                            grams=add_pb_g,
                            source="food",
                            familiar="1 tablespoon",
                            exchange_group="Nuts / fat",
                            macros=pb_macros,
                        ))
                        snack_meal.macros = snack_meal.macros.plus(pb_macros)
                        weekly_food_grams["T004"] = weekly_food_grams.get("T004", 0.0) + add_pb_g

        totals = MacroTotals()
        for m in meals:
            totals = totals.plus(m.macros)

        # General Declarative Fasting Calibration (Pillar 1 Architecture)
        if fasting:
            target_p = float(targets.get("protein") or targets.get("protein_g") or 140.0)
            target_kcal_val = float(targets.get("target_kcal") or targets.get("kcal") or 0.0)
            if target_kcal_val >= 2800.0:
                protein_floor = max(target_p * 0.95, 138.0)
            else:
                protein_floor = max(target_p * 0.78, min(target_p * 0.82, 112.0))
            allergies = [str(a).upper() for a in answers.get("food_allergies", [])]
            soya_allowed = "SOY" not in allergies
            soya_food = dataset.food_by_id.get("P009") if soya_allowed else None
            soymilk_food = dataset.food_by_id.get("P014") if soya_allowed else None

            breakfast_m = next((m for m in meals if m.source_slot == "Breakfast"), None)
            lunch_m = next((m for m in meals if m.source_slot == "Lunch"), None)
            dinner_m = next((m for m in meals if m.source_slot == "Dinner"), None)
            savory_meals = [m for m in meals if m.source_slot in ("Lunch", "Dinner")]

            # 1. Breakfast liquid balance (dynamic soy milk if oats + heavy PB)
            if breakfast_m:
                oat_it = next((it for it in breakfast_m.items if it.food_id == "C007"), None)
                pb_it = next((it for it in breakfast_m.items if it.food_id == "T004"), None)
                has_milk = any(it.food_id in ("P014", "A015") for it in breakfast_m.items)
                target_pb = 12.0 if target_kcal_val < 1650.0 else 15.0
                target_oat = 40.0 if target_kcal_val < 1650.0 else 50.0
                target_sm = 200.0 if target_kcal_val < 1650.0 else 250.0
                sm_fam = "about ¾ large glass" if target_sm == 200.0 else "about 1 large glass"

                if oat_it and pb_it:
                    if pb_it.grams > target_pb:
                        diff_pb = pb_it.grams - target_pb
                        pb_it.grams = target_pb
                        weekly_food_grams["T004"] = max(0.0, weekly_food_grams.get("T004", 0.0) - diff_pb)
                    if not has_milk and soymilk_food:
                        sm_m = food_macros(soymilk_food, target_sm)
                        breakfast_m.items.append(MealItem(
                            food_id="P014",
                            food_name="Soy milk (unsweetened)",
                            grams=target_sm,
                            source="food",
                            familiar=sm_fam,
                            exchange_group="Plant milk",
                            macros=sm_m,
                        ))
                        weekly_food_grams["P014"] = weekly_food_grams.get("P014", 0.0) + target_sm
                    oat_it.grams = target_oat
                    oat_it.familiar = "about 0.5 cup dry" if target_oat == 50.0 else "about 0.4 cup dry"

            # 2. Traditional stew portion standardization & legume stacking cleanup
            for m in savory_meals:
                has_legume_stew = any(it.recipe_id in ("R001", "R002", "R003") for it in m.items)
                if has_legume_stew:
                    stacked = [it for it in m.items if it.food_id in ("P001", "P007")]
                    for st in stacked:
                        m.items.remove(st)
                        weekly_food_grams[st.food_id] = max(0.0, weekly_food_grams.get(st.food_id, 0.0) - st.grams)

                atkilt_it = next((it for it in m.items if it.recipe_id == "R004"), None)
                if atkilt_it:
                    atkilt_it.grams = 80.0
                    atkilt_it.familiar = "ሲሶ / 1/3 መካከለኛ ጭልፋ"

                misir_it = next((it for it in m.items if it.recipe_id == "R002"), None)
                if misir_it:
                    misir_it.grams = 200.0
                    misir_it.familiar = "1 መካከለኛ ጭልፋ"

                ful_it = next((it for it in m.items if it.recipe_id in ("R018", "R025") or "ful" in str(it.food_name).lower()), None)
                if ful_it:
                    ful_it.grams = 220.0
                    ful_it.familiar = "1 መካከለኛ ሳህን"

            # 3. Recalculate intermediate macros across meals
            for m in meals:
                m_tot = MacroTotals()
                for it in m.items:
                    f_obj = dataset.food_by_id.get(it.food_id) if it.food_id else None
                    r_obj = dataset.recipe_by_id.get(it.recipe_id) if it.recipe_id else None
                    if f_obj:
                        it.macros = food_macros(f_obj, it.grams)
                        m_tot = m_tot.plus(it.macros)
                    elif r_obj:
                        it.macros = recipe_macros(r_obj, it.grams)
                        m_tot = m_tot.plus(it.macros)
                    elif it.macros:
                        m_tot = m_tot.plus(it.macros)
                m.macros = m_tot

            # 4. Dynamic Fasting Protein Booster
            day_p = sum(m.macros.protein for m in meals)
            if day_p < protein_floor and soya_food and savory_meals:
                diff_p = protein_floor - day_p
                needed_g = float(math.ceil((diff_p / 0.52) / 5.0) * 5.0)
                
                lunch_soya = next((it for it in lunch_m.items if it.food_id == "P009"), None) if lunch_m else None
                dinner_soya = next((it for it in dinner_m.items if it.food_id == "P009"), None) if dinner_m else None

                if needed_g > 30.0 and lunch_m and dinner_m:
                    g_lunch = float(math.ceil((needed_g / 2.0) / 5.0) * 5.0)
                    g_din = needed_g - g_lunch
                    if lunch_soya:
                        lunch_soya.grams += g_lunch
                        lunch_soya.familiar = "በግምት 1 ከግማሽ ሲኒ የተዘፈቀ"
                    else:
                        sm_l = food_macros(soya_food, g_lunch)
                        lunch_m.items.append(MealItem(
                            food_id="P009", food_name="Dry soy chunks", grams=g_lunch,
                            source="food", familiar="በግምት 1 ከግማሽ ሲኒ የተዘፈቀ",
                            exchange_group="Fasting protein", macros=sm_l
                        ))
                    weekly_food_grams["P009"] = weekly_food_grams.get("P009", 0.0) + g_lunch

                    if dinner_soya:
                        dinner_soya.grams += g_din
                        dinner_soya.familiar = "በግምት 1 ከግማሽ ሲኒ የተዘፈቀ"
                    else:
                        sm_d = food_macros(soya_food, g_din)
                        dinner_m.items.append(MealItem(
                            food_id="P009", food_name="Dry soy chunks", grams=g_din,
                            source="food", familiar="በግምት 1 ከግማሽ ሲኒ የተዘፈቀ",
                            exchange_group="Fasting protein", macros=sm_d
                        ))
                    weekly_food_grams["P009"] = weekly_food_grams.get("P009", 0.0) + g_din
                else:
                    target_m = dinner_m or lunch_m or savory_meals[0]
                    t_soya = dinner_soya or lunch_soya
                    if t_soya:
                        t_soya.grams += needed_g
                        t_soya.familiar = "በግምት 1 ከግማሽ ሲኒ የተዘፈቀ"
                    else:
                        sm_t = food_macros(soya_food, needed_g)
                        target_m.items.append(MealItem(
                            food_id="P009", food_name="Dry soy chunks", grams=needed_g,
                            source="food", familiar="በግምት 1 ከግማሽ ሲኒ የተዘፈቀ",
                            exchange_group="Fasting protein", macros=sm_t
                        ))
                    weekly_food_grams["P009"] = weekly_food_grams.get("P009", 0.0) + needed_g

            # Final Day Totals
            totals = MacroTotals()
            for m in meals:
                m_tot = MacroTotals()
                for it in m.items:
                    f_obj = dataset.food_by_id.get(it.food_id) if it.food_id else None
                    r_obj = dataset.recipe_by_id.get(it.recipe_id) if it.recipe_id else None
                    if f_obj:
                        it.macros = food_macros(f_obj, it.grams)
                        m_tot = m_tot.plus(it.macros)
                    elif r_obj:
                        it.macros = recipe_macros(r_obj, it.grams)
                        m_tot = m_tot.plus(it.macros)
                    elif it.macros:
                        m_tot = m_tot.plus(it.macros)
                m.macros = m_tot
                totals = totals.plus(m.macros)

        # Caloric floor adjustment for hardgainer plans: ensure day lands in [2,980, 3,075] kcal
        target_kcal_floor = targets.get("target_kcal") or targets.get("kcal") or 0.0
        if target_kcal_floor >= 2800.0 and totals.kcal < 2980.0:
            diff_kcal = 3025.0 - totals.kcal
            # Pass 1: Cooking oil in savory meals (up to 24g single oil) - do not drown breakfast toast in oil
            for m in meals:
                if totals.kcal >= 3020.0:
                    break
                if m.slot == "Breakfast" or m.source_slot == "Breakfast":
                    continue
                for it in m.items:
                    if it.food_id in ("T001", "T002") and it.grams < 24.0:
                        add_g = min(24.0 - it.grams, round(diff_kcal / 8.84, 1))
                        if add_g >= 1.0:
                            it.grams += add_g
                            tbsp = max(0.25, round((it.grams / 14.0) * 4) / 4)
                            it.familiar = f"about {tbsp:g} level tablespoon" + ("s" if tbsp > 1 else "")
                            delta_m = food_macros(dataset.food_by_id[it.food_id], add_g)
                            it.macros = it.macros.plus(delta_m)
                            m.macros = m.macros.plus(delta_m)
                            totals = totals.plus(delta_m)
                            weekly_food_grams[it.food_id] = weekly_food_grams.get(it.food_id, 0.0) + add_g
                            diff_kcal -= delta_m.kcal

            # Pass 2: Snack energy density (Dates F012, Peanuts T003, Milk A015, Peanut butter T004)
            if totals.kcal < 2980.0:
                diff_kcal = 3025.0 - totals.kcal
                for m in meals:
                    if totals.kcal >= 3020.0:
                        break
                    if m.source_slot == "Snack":
                        for it in m.items:
                            if it.food_id == "F012" and it.grams < 80.0:
                                add_g = min(80.0 - it.grams, round(diff_kcal / 2.82, 1))
                                if add_g >= 5.0:
                                    it.grams += add_g
                                    it.familiar = "about 5–6 large dates"
                                    delta_m = food_macros(dataset.food_by_id["F012"], add_g)
                                    it.macros = it.macros.plus(delta_m)
                                    m.macros = m.macros.plus(delta_m)
                                    totals = totals.plus(delta_m)
                                    weekly_food_grams["F012"] = weekly_food_grams.get("F012", 0.0) + add_g
                                    diff_kcal -= delta_m.kcal
                            elif it.food_id == "T003" and it.grams < 40.0:
                                add_g = min(40.0 - it.grams, round(diff_kcal / 5.85, 1))
                                if add_g >= 5.0:
                                    it.grams += add_g
                                    it.familiar = "about 1.5 small handfuls"
                                    delta_m = food_macros(dataset.food_by_id["T003"], add_g)
                                    it.macros = it.macros.plus(delta_m)
                                    m.macros = m.macros.plus(delta_m)
                                    totals = totals.plus(delta_m)
                                    weekly_food_grams["T003"] = weekly_food_grams.get("T003", 0.0) + add_g
                                    diff_kcal -= delta_m.kcal
                            elif it.food_id == "A015" and it.grams < 250.0:
                                add_g = min(250.0 - it.grams, round(diff_kcal / 0.50, 1))
                                if add_g >= 20.0:
                                    it.grams += add_g
                                    it.familiar = "1 large glass" if round(it.grams) == 250 else "about ¾ large glass"
                                    delta_m = food_macros(dataset.food_by_id["A015"], add_g)
                                    it.macros = it.macros.plus(delta_m)
                                    m.macros = m.macros.plus(delta_m)
                                    totals = totals.plus(delta_m)
                                    weekly_food_grams["A015"] = weekly_food_grams.get("A015", 0.0) + add_g
                                    diff_kcal -= delta_m.kcal

            # Pass 3: Composite dishes (Chicken Rice Bowl R026)
            if totals.kcal < 2980.0:
                diff_kcal = 3025.0 - totals.kcal
                for m in meals:
                    if totals.kcal >= 3020.0:
                        break
                    for it in m.items:
                        if it.recipe_id == "R026":
                            rec_food = dataset.recipe_by_id.get("R026", {})
                            base_serv = n(rec_food.get("Serving g") or 400.0)
                            add_g = min(150.0, round(diff_kcal / 1.3, 1))
                            if add_g >= 20.0:
                                it.grams += add_g
                                delta_m = MacroTotals(add_g * 1.3, add_g * 0.08, add_g * 0.16, add_g * 0.03, add_g * 0.01)
                                it.macros = it.macros.plus(delta_m)
                                m.macros = m.macros.plus(delta_m)
                                totals = totals.plus(delta_m)
                                it.familiar = "150g cooked chicken breast + 300g cooked rice"
                                diff_kcal -= delta_m.kcal

        if target_kcal_floor >= 2000.0 and totals.kcal < 2050.0:
            for m in meals:
                if totals.kcal >= 2050.0:
                    break
                for it in m.items:
                    if it.food_id == "C001" and it.grams < 240.0:
                        diff = 240.0 - it.grams
                        it.grams = 240.0
                        it.familiar = "2 medium rolled piece"
                        delta_m = food_macros(dataset.food_by_id["C001"], diff)
                        it.macros = it.macros.plus(delta_m)
                        m.macros = m.macros.plus(delta_m)
                        totals = totals.plus(delta_m)
                        weekly_food_grams["C001"] = weekly_food_grams.get("C001", 0.0) + diff
                        # Rebuild exchange options with updated 240g base
                        options = build_exchange_options(
                            "C001", dataset, answers,
                            fasting=template_fasting_mode,
                            base_grams=240.0,
                            meal_food_ids=set(m.food_ids if hasattr(m, 'food_ids') else [x.food_id for x in m.items]),
                            source_slot="Lunch",
                        )
                        for ex in m.exchange_options:
                            if ex.get("for_food_id") == "C001":
                                ex["options"] = options
                        break

        # Omnivore High-Protein Floor Booster (for profiles targeting >= 140g P)
        if not fasting:
            target_p = float(targets.get("protein") or targets.get("protein_g") or 0.0)
            day_p = sum(m.macros.protein for m in meals)
            if target_p >= 140.0 and day_p < target_p * 0.85:
                diff_p = (target_p * 0.88) - day_p
                needed_chicken_g = float(math.ceil((diff_p / 0.31) / 5.0) * 5.0)
                chicken_food = dataset.food_by_id.get("A001")
                savory_m = next((m for m in meals if m.source_slot in ("Lunch", "Dinner")), None)
                if chicken_food and savory_m:
                    existing_chick = next((it for it in savory_m.items if it.food_id == "A001"), None)
                    if existing_chick:
                        existing_chick.grams += needed_chicken_g
                        delta_m = food_macros(chicken_food, needed_chicken_g)
                        existing_chick.macros = existing_chick.macros.plus(delta_m)
                        savory_m.macros = savory_m.macros.plus(delta_m)
                        totals = totals.plus(delta_m)
                        weekly_food_grams["A001"] = weekly_food_grams.get("A001", 0.0) + needed_chicken_g
                    else:
                        m_chick = food_macros(chicken_food, needed_chicken_g)
                        savory_m.items.append(MealItem(
                            food_id="A001",
                            food_name="Cooked chicken breast",
                            grams=needed_chicken_g,
                            source="food",
                            familiar=f"about {needed_chicken_g:.0f}g portion",
                            exchange_group="Lean animal protein",
                            macros=m_chick,
                        ))
                        savory_m.macros = savory_m.macros.plus(m_chick)
                        totals = totals.plus(m_chick)
                        weekly_food_grams["A001"] = weekly_food_grams.get("A001", 0.0) + needed_chicken_g

        # Deficit / Fat Loss Caloric Ceiling Trimming Pass
        target_kcal_val = float(targets.get("target_kcal") or targets.get("kcal") or 0.0)
        primary_goal = str(answers.get("primary_goal") or "").upper()
        is_cut = "LOSS" in primary_goal or "CUT" in primary_goal or target_kcal_val < 2000.0

        if is_cut and totals.kcal > target_kcal_val * 1.03:
            excess_kcal = totals.kcal - (target_kcal_val * 1.01)
            # Pass 1: Trim cooking oil in savory meals if > 8g
            for m in meals:
                if totals.kcal <= target_kcal_val * 1.02:
                    break
                for it in m.items:
                    if it.food_id in ("T001", "T002") and it.grams > 8.0:
                        trim_oil = min(it.grams - 5.0, 5.0)
                        if trim_oil >= 2.0:
                            it.grams -= trim_oil
                            tbsp = max(0.25, round((it.grams / 14.0) * 4) / 4)
                            it.familiar = f"about {tbsp:g} level tablespoon" + ("s" if tbsp > 1 else "")
                            delta_m = food_macros(dataset.food_by_id[it.food_id], -trim_oil)
                            it.macros = it.macros.plus(delta_m)
                            m.macros = m.macros.plus(delta_m)
                            totals = totals.plus(delta_m)
                            weekly_food_grams[it.food_id] = max(0.0, weekly_food_grams.get(it.food_id, 0.0) - trim_oil)
                            excess_kcal -= abs(delta_m.kcal)

            # Pass 2: Trim heavy starchy tubers (sweet potato C011, potato C010) if > 120g
            if totals.kcal > target_kcal_val * 1.03:
                excess_kcal = totals.kcal - (target_kcal_val * 1.01)
                for m in meals:
                    if totals.kcal <= target_kcal_val * 1.02:
                        break
                    for it in m.items:
                        if it.food_id in ("C010", "C011") and it.grams > 120.0:
                            trim_g = min(it.grams - 100.0, float(math.ceil((excess_kcal / 0.90) / 10.0) * 10.0))
                            if trim_g >= 20.0:
                                it.grams -= trim_g
                                it.familiar = f"about {round(it.grams)}g portion"
                                delta_m = food_macros(dataset.food_by_id[it.food_id], -trim_g)
                                it.macros = it.macros.plus(delta_m)
                                m.macros = m.macros.plus(delta_m)
                                totals = totals.plus(delta_m)
                                weekly_food_grams[it.food_id] = max(0.0, weekly_food_grams.get(it.food_id, 0.0) - trim_g)
                                excess_kcal -= abs(delta_m.kcal)

            # Pass 3: Trim composite rice bowls (R011, R025, R026) if > 250g
            if totals.kcal > target_kcal_val * 1.03:
                excess_kcal = totals.kcal - (target_kcal_val * 1.01)
                for m in meals:
                    if totals.kcal <= target_kcal_val * 1.02:
                        break
                    for it in m.items:
                        if it.recipe_id in ("R011", "R025", "R026") and it.grams > 250.0:
                            trim_g = min(it.grams - 220.0, float(math.ceil((excess_kcal / 1.1) / 10.0) * 10.0))
                            if trim_g >= 30.0:
                                it.grams -= trim_g
                                delta_m = recipe_macros(dataset.recipe_by_id[it.recipe_id], -trim_g)
                                it.macros = it.macros.plus(delta_m)
                                m.macros = m.macros.plus(delta_m)
                                totals = totals.plus(delta_m)
                                excess_kcal -= abs(delta_m.kcal)

            # Pass 4: Trim Injera (C001) from 240g -> 180g, or 180g -> 120g (preserve 120g minimum on fasting days)
            if totals.kcal > target_kcal_val * 1.03:
                for m in meals:
                    if totals.kcal <= target_kcal_val * 1.02:
                        break
                    for it in m.items:
                        if it.food_id == "C001":
                            min_inj = 120.0 if fasting else 60.0
                            if it.grams > min_inj:
                                trim_g = 60.0
                                it.grams -= trim_g
                                inj_g = round(it.grams)
                                if inj_g >= 210:
                                    it.familiar = "2 medium rolled pieces"
                                elif inj_g >= 150:
                                    it.familiar = "1 ½ medium rolled pieces"
                                elif inj_g >= 90:
                                    it.familiar = "1 medium rolled piece"
                                else:
                                    it.familiar = "½ medium rolled piece"
                                delta_m = food_macros(dataset.food_by_id["C001"], -trim_g)
                                it.macros = it.macros.plus(delta_m)
                                m.macros = m.macros.plus(delta_m)
                                totals = totals.plus(delta_m)
                                weekly_food_grams["C001"] = max(0.0, weekly_food_grams.get("C001", 0.0) - trim_g)
                                break

        status="READY_FOR_COACH_REVIEW" if not solution.warnings else "PRACTICAL_TUNING_REQUIRED"
        day=GeneratedDay(d,current.strftime("%A"),current,fasting,meals,totals,list(dict.fromkeys(day_warnings)),status)
        days.append(day)
        all_warnings.extend(day.warnings)
    return days, weekly_food_grams, all_warnings


def generate_plan(
    *,
    answers: dict[str, Any],
    nutrition_profile: dict[str, Any],
    meals_per_day: int,
    start_date: date,
    duration_days: int,
    region: str,
    country_name: str | None = None,
    dataset: HilaweDataset | None = None,
) -> dict[str, Any]:
    if duration_days not in {7,14,30}:
        raise GenerationError("Meal engine supports 7, 14, or 30 day products")
    dataset = dataset or load_dataset()
    dietary = str(answers.get("dietary_pattern") or "").upper()
    if dietary not in {"OMNIVORE", "VEGETARIAN", "VEGAN", "PESCATARIAN"}:
        raise GenerationError("A supported dietary pattern is required before meal generation")
    targets = _target_dict(nutrition_profile)
    curr_weight = float(answers.get("current_weight_kg") or 0)
    primary_goal = str(answers.get("primary_goal") or "").upper()
    t_kcal = float(nutrition_profile.get("target_kcal") or targets.get("target_kcal") or targets.get("kcal") or 0)

    # When current_weight_kg < 55.0 and primary_goal == "MUSCLE_GAIN" and target_kcal >= 2000:
    # Split daily schedule into 3 Main Meals (~520-550 kcal) + 1 Compact High-Calorie Shake / Snack (~450 kcal)
    if curr_weight > 0 and curr_weight < 55.0 and primary_goal == "MUSCLE_GAIN" and t_kcal >= 2000:
        meals_per_day = 4

    slots = meal_structure(meals_per_day)
    pattern = str(answers.get("orthodox_fasting") or "NONE").upper()
    verified_years = dataset.meta.get("verified_fasting_calendar_years")
    try:
        all_fasting_days = fasting_days_for_period(
            start_date, duration_days, pattern, dataset.fasting_calendar,
            verified_years=verified_years,
        )
    except ValueError as exc:
        raise GenerationError(str(exc)) from exc

    if all(all_fasting_days):
        # Strict Lent or 100% fasting period: The primary core week is 100% fasting from Day 1.
        # No non-fasting days with meat/dairy are generated, and no duplicate core week is appended.
        regular_days, weekly_food_grams, all_warnings = _generate_core_week(
            dataset=dataset, answers=answers, slots=slots, targets=targets, start_date=start_date,
            fasting_days=(True,) * 7, region=region, country_name=country_name,
        )
        fasting_core: list[GeneratedDay] = []
        fasting_food_grams: dict[str, float] = {}
        seasonal_days = (False,) * duration_days
    else:
        weekly_pattern = "WED_FRI" if pattern in {"WED_FRI", "WED_FRI_AND_SEASONAL"} else "NONE"
        regular_period_days = fasting_days_for_period(start_date, duration_days, weekly_pattern, dataset.fasting_calendar)
        seasonal_days = tuple(
            all_fasting_days[index] and not regular_period_days[index]
            for index in range(duration_days)
        )
        regular_days, weekly_food_grams, all_warnings = _generate_core_week(
            dataset=dataset, answers=answers, slots=slots, targets=targets, start_date=start_date,
            fasting_days=regular_period_days[:7], region=region, country_name=country_name,
        )
        fasting_core: list[GeneratedDay] = []
        fasting_food_grams: dict[str, float] = {}
        if any(seasonal_days):
            fasting_core, fasting_food_grams, fasting_warnings = _generate_core_week(
                dataset=dataset, answers=answers, slots=slots, targets=targets, start_date=start_date,
                fasting_days=(True,) * 7, region=region, country_name=country_name,
            )
            all_warnings.extend(fasting_warnings)

    used_recipe_ids=sorted({rid for day in [*regular_days, *fasting_core] for meal in day.meals for rid in meal.recipe_ids})
    uncalibrated=[]
    for rid in used_recipe_ids:
        recipe=dataset.recipe_by_id.get(rid) or {}
        if "required" in str(recipe.get("Calibration Status") or "").lower():
            uncalibrated.append({"recipe_id":rid,"recipe_name":recipe.get("Recipe Name"),"calibration_status":recipe.get("Calibration Status")})

    plan={
        "schema_version":"1.0",
        "engine_version":ENGINE_VERSION,
        "dataset_version":dataset.version,
        "settings_version":SETTINGS_VERSION,
        "product":{
            "duration_days":duration_days,
            "meals_per_day":meals_per_day,
            "start_date":start_date.isoformat(),
            "end_date":(start_date+timedelta(days=duration_days-1)).isoformat(),
            "region":region,
            "country_name":country_name,
            "rotation_model":"7_DAY_CORE_WITH_SWAP_ROTATION",
        },
        "answers": answers,
        "client_profile": answers,
        "nutrition_targets": targets,
        "profile_summary": {
            "client_name": answers.get("full_name"),
            "current_weight_kg": answers.get("current_weight_kg"),
            "target_weight_kg": answers.get("target_weight_kg"),
            "primary_target_weight": answers.get("target_weight_kg", 83.0),
            "mesocycle_target_weight": round(float(answers.get("current_weight_kg") or 71.0) + 3.5, 1),
            "height_cm": answers.get("height_cm"),
            "age": answers.get("age"),
            "goal": answers.get("primary_goal"),
            "cuisine_style": answers.get("cuisine_style"),
            "dietary_pattern": answers.get("dietary_pattern"),
            "grocery_budget": answers.get("grocery_budget"),
            "orthodox_fasting": answers.get("orthodox_fasting"),
            "fish_during_fast": bool(answers.get("fish_during_fast")),
            "training_days_per_week": answers.get("training_days_per_week"),
            "training_type": answers.get("training_type"),
        },
        "meal_structure":[{"label":s.label,"source_slot":s.source_slot,"target_share":s.target_share} for s in slots],
        "core_week":[d.to_dict() for d in regular_days],
        "fasting_core_week":[d.to_dict() for d in fasting_core],
        "rotation":_rotation(duration_days,start_date,all_fasting_days,seasonal_days),
        "grocery":build_grocery(weekly_food_grams,dataset),
        "fasting_grocery":build_grocery(fasting_food_grams,dataset) if fasting_food_grams else None,
        "review":{
            "required":True,
            "status":"PENDING",
            "recipe_calibration_required":bool(uncalibrated),
            "uncalibrated_recipes":uncalibrated,
            "practical_warnings":list(dict.fromkeys(all_warnings)),
            "supplements_used":False,
        },
        "policy":{
            "exact_grams":True,"familiar_portions":True,"exchange_guidance":True,
            "supplements_enabled":False,"auto_delivery":False,
        },
    }
    return plan
