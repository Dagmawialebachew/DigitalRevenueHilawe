from __future__ import annotations

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
from meal_plan.generation.solver import DaySolver, food_macros, n, template_macros
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
    if any(w in r_lower for w in ("wot", "alicha", "minchet", "shiro", "misir", "dinich")):
        return "1 medium ladle"
    if any(w in r_lower for w in ("tibs", "kitfo", "steak", "fillet")):
        return "1 palm portion"
    if any(w in r_lower for w in ("firfir", "ful", "salad", "bowl", "gomen", "fosolia")):
        return "1 small bowl"
    if "toast" in r_lower:
        return "1 slice"
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
    meal_macros = template_macros(template).scale(scale)

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
            grams = n(component.get("Portion g")) * scale
            if str(component.get("Item Type")) == "Food":
                fid = str(component.get("Item ID") or "")
                if fid:
                    if is_save_budget and fid == "T001":
                        fid = "T002"
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
                is_stew = any(w in r_name.lower() for w in ("wot", "alicha", "minchet", "shiro", "misir", "stew", "ወጥ", "አልጫ"))
                if is_stew:
                    grams = max(25.0, round(grams / 25.0) * 25.0)

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
                items.append(MealItem(
                    food_id="",
                    food_name=r_name,
                    grams=grams,
                    source="recipe",
                    familiar=familiar_portion(n(component.get("Servings"))*r_frac, _recipe_familiar_measure(rid, r_name)),
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

        for extra in extras:
            fid = str(extra["id"])
            direct[fid] = direct.get(fid, 0.0) + float(extra["grams"])
            meal_macros = meal_macros.plus(food_macros(foods[fid], float(extra["grams"])))

        # Mandatory Cooking Oil Anchor for Savory Meat/Fish Dishes (5g-10g cooking oil)
        has_savory_meat_fish = any(
            r in ("R023", "R020", "R017", "R016", "R018", "R019", "R015", "R014")
            for r in recipe_ids
        )
        if has_savory_meat_fish:
            oil_fid = "T002" if is_save_budget else "T001"
            if direct.get(oil_fid, 0.0) < 6.0:
                oil_needed = 6.0 - direct.get(oil_fid, 0.0)
                direct[oil_fid] = 6.0
                meal_macros = meal_macros.plus(food_macros(foods[oil_fid], oil_needed))

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
        elif fid == "A015":
            if round(grams) == 200:
                fam = "በግምት ሶስት አራተኛ ትልቅ ብርጭቆ"
            elif round(grams) == 250:
                fam = "1 large glass"
            else:
                fam = familiar_portion(grams/max(1.0,n(food.get("Standard Portion g"))), str(food.get("Familiar Measure") or "standard portion"))
        elif fid == "C001":
            # Standardize Injera: 1 medium rolled Injera = 120g (60g = 0.5 roll, 120g = 1 roll, 180g = 1.5 rolls, 240g = 2 rolls)
            grams = max(60.0, round(grams / 60.0) * 60.0)
            inj_rolls = grams / 120.0
            if inj_rolls == 1.0: fam = "1 medium rolled piece"
            elif inj_rolls == 1.5: fam = "1 ½ medium rolled piece"
            elif inj_rolls == 2.0: fam = "2 medium rolled piece"
            elif inj_rolls == 0.5: fam = "½ medium rolled piece"
            else: fam = f"{inj_rolls:.1f} medium rolled piece"
        elif fid == "C010":
            # Round potato to clean multiples of 50g (e.g. 200g, 250g, 300g, 350g, 400g)
            grams = max(100.0, round(grams / 50.0) * 50.0)
            fam = familiar_portion(grams/max(1.0,n(food.get("Standard Portion g"))), str(food.get("Familiar Measure") or "standard portion"))
        else:
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
        fish_permitted = fasting and dietary == "OMNIVORE" and bool(answers.get("fish_during_fast"))
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

        totals = MacroTotals()
        for m in meals:
            totals = totals.plus(m.macros)

        # Caloric floor adjustment for hardgainer plans: if below 2,050 kcal, bump 1.5 rolls (180g) injera to 2 rolls (240g)
        target_kcal_floor = targets.get("target_kcal") or targets.get("kcal") or 0.0
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
                        )
                        for ex in m.exchange_options:
                            if ex.get("for_food_id") == "C001":
                                ex["options"] = options
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
        "nutrition_targets":targets,
        "profile_summary":{
            "goal":answers.get("primary_goal"),"cuisine_style":answers.get("cuisine_style"),
            "dietary_pattern":answers.get("dietary_pattern"),
            "grocery_budget":answers.get("grocery_budget"),"orthodox_fasting":answers.get("orthodox_fasting"),
            "fish_during_fast":bool(answers.get("fish_during_fast")),"training_days_per_week":answers.get("training_days_per_week"),
            "training_type":answers.get("training_type"),
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
