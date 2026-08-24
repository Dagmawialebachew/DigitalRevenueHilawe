from __future__ import annotations

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

    for component in dataset.components_by_template.get(str(template.get("Template ID")), []):
        grams = n(component.get("Portion g")) * scale
        if str(component.get("Item Type")) == "Food":
            fid = str(component.get("Item ID") or "")
            if fid:
                direct[fid] = direct.get(fid, 0.0) + grams
        else:
            rid = str(component.get("Item ID") or "")
            recipe = recipes.get(rid) or {}
            recipe_ids.append(rid)
            calibration = str(recipe.get("Calibration Status") or "")
            if "required" in calibration.lower():
                warnings.append(f"Recipe calibration required before final approval: {recipe.get('Recipe Name') or rid}")
            items.append(MealItem(
                food_id="",
                food_name=str(recipe.get("Recipe Name") or component.get("Item Name") or rid),
                grams=grams,
                source="recipe",
                familiar=familiar_portion(n(component.get("Servings"))*scale, "1 standard portion"),
                exchange_group=str(component.get("Exchange Note") or "") or None,
                recipe_id=rid,
                recipe_name=str(recipe.get("Recipe Name") or component.get("Item Name") or rid),
                prepared_grams=grams,
                macros=MacroTotals(
                    n(component.get("kcal"))*scale,
                    n(component.get("Protein g"))*scale,
                    n(component.get("Carbs g"))*scale,
                    n(component.get("Fat g"))*scale,
                    n(component.get("Fibre g"))*scale,
                ),
            ))

    for extra in extras:
        fid = str(extra["id"])
        direct[fid] = direct.get(fid, 0.0) + float(extra["grams"])
        meal_macros = meal_macros.plus(food_macros(foods[fid], float(extra["grams"])))

    exchange_options: list[dict[str, Any]] = []
    for fid, grams in sorted(direct.items()):
        food = foods.get(fid)
        if not food:
            continue
        item = MealItem(
            food_id=fid,
            food_name=str(food.get("Food Name") or fid),
            grams=grams,
            source="food",
            familiar=familiar_portion(grams/max(1.0,n(food.get("Standard Portion g"))), str(food.get("Familiar Measure") or "standard portion")),
            exchange_group=str(food.get("Exchange Group") or "") or None,
            macros=food_macros(food, grams),
        )
        items.append(item)
        options = build_exchange_options(fid, dataset, answers, fasting=restriction_fasting)
        if options:
            exchange_options.append({"for_food_id": fid, "for_food_name": item.food_name, "options": options})

    return GeneratedMeal(
        slot=spec.label,
        source_slot=spec.source_slot,
        template_id=str(template.get("Template ID")),
        meal_name=str(template.get("Meal Name")),
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
        for spec in slots:
            prefer_fish = spec.source_slot == fish_slot
            avoid_fish = fish_permitted and spec.source_slot in {"Lunch", "Dinner"} and spec.source_slot != fish_slot
            template = selector.choose(
                fasting=template_fasting_mode, source_slot=spec.source_slot, day_index=d, exclude_today=used_today,
                prefer_fish=prefer_fish, avoid_fish=avoid_fish, whole_food_first=fasting,
            )
            used_today.add(str(template.get("Template ID")))
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
            for fid, grams in solution.food_by_slot[spec.label].items():
                weekly_food_grams[fid]=weekly_food_grams.get(fid,0.0)+grams

        totals=solution.totals
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
    if dietary not in {"OMNIVORE", "VEGETARIAN", "VEGAN"}:
        raise GenerationError("A supported dietary pattern is required before meal generation")
    slots = meal_structure(meals_per_day)
    targets = _target_dict(nutrition_profile)
    pattern = str(answers.get("orthodox_fasting") or "NONE").upper()
    verified_years = dataset.meta.get("verified_fasting_calendar_years")
    try:
        all_fasting_days = fasting_days_for_period(
            start_date, duration_days, pattern, dataset.fasting_calendar,
            verified_years=verified_years,
        )
    except ValueError as exc:
        raise GenerationError(str(exc)) from exc

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
