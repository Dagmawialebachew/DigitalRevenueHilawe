from __future__ import annotations

import json
from datetime import date
from typing import Any

from meal_plan.generation.dataset import HilaweDataset, load_dataset


def _b(v: Any) -> bool:
    return str(v or "").strip().lower() in {"yes", "true", "1"}


def _date(v: Any):
    if not v:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _payload(row: dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, separators=(",", ":"))


async def import_hilawe_dataset(pool, dataset: HilaweDataset | None = None) -> dict[str, int]:
    ds = dataset or load_dataset()
    version = ds.version
    counts: dict[str, int] = {}
    async with pool.acquire() as conn:
        async with conn.transaction():
            for r in ds.foods:
                await conn.execute("""
                    INSERT INTO nutrition_foods(
                      food_id,food_name,local_name,category,fasting_allowed,fish_item,availability,budget_level,
                      standard_portion_g,unit,familiar_measure,kcal_per_100g,protein_per_100g,carbs_per_100g,fat_per_100g,
                      fibre_per_100g,exchange_group,allergen_tags,source_method,source_url,data_quality,active,yield_conversion,
                      dataset_version,source_payload,updated_at)
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25::jsonb,NOW())
                    ON CONFLICT(food_id) DO UPDATE SET
                      food_name=EXCLUDED.food_name,local_name=EXCLUDED.local_name,category=EXCLUDED.category,
                      fasting_allowed=EXCLUDED.fasting_allowed,fish_item=EXCLUDED.fish_item,availability=EXCLUDED.availability,
                      budget_level=EXCLUDED.budget_level,standard_portion_g=EXCLUDED.standard_portion_g,unit=EXCLUDED.unit,
                      familiar_measure=EXCLUDED.familiar_measure,kcal_per_100g=EXCLUDED.kcal_per_100g,
                      protein_per_100g=EXCLUDED.protein_per_100g,carbs_per_100g=EXCLUDED.carbs_per_100g,
                      fat_per_100g=EXCLUDED.fat_per_100g,fibre_per_100g=EXCLUDED.fibre_per_100g,
                      exchange_group=EXCLUDED.exchange_group,allergen_tags=EXCLUDED.allergen_tags,source_method=EXCLUDED.source_method,
                      source_url=EXCLUDED.source_url,data_quality=EXCLUDED.data_quality,active=EXCLUDED.active,
                      yield_conversion=EXCLUDED.yield_conversion,dataset_version=EXCLUDED.dataset_version,
                      source_payload=EXCLUDED.source_payload,updated_at=NOW()
                """, r.get("Food ID"),r.get("Food Name"),r.get("Local / Amharic"),r.get("Category"),_b(r.get("Fasting Allowed")),
                    _b(r.get("Fish Item")),r.get("Availability"),r.get("Budget Level"),r.get("Standard Portion g"),r.get("Unit"),
                    r.get("Familiar Measure"),r.get("kcal / 100 g"),r.get("Protein / 100 g"),r.get("Carbs / 100 g"),r.get("Fat / 100 g"),
                    r.get("Fibre / 100 g"),r.get("Exchange Group"),r.get("Allergen Tags"),r.get("Source / Method"),r.get("Source URL"),
                    r.get("Data Quality"),_b(r.get("Active")),r.get("Yield Conversion") or 1,version,_payload(r))
            counts["foods"] = len(ds.foods)

            for r in ds.recipes:
                await conn.execute("""
                  INSERT INTO nutrition_recipes(recipe_id,recipe_name,local_name,fasting,fish,meal_role,yield_g,serving_g,kcal_per_serving,
                    protein_g,carbs_g,fat_g,fibre_g,ingredients_summary,method,allergens,source_method,calibration_status,recipe_version,
                    active,dataset_version,source_payload,updated_at)
                  VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22::jsonb,NOW())
                  ON CONFLICT(recipe_id) DO UPDATE SET recipe_name=EXCLUDED.recipe_name,local_name=EXCLUDED.local_name,
                    fasting=EXCLUDED.fasting,fish=EXCLUDED.fish,meal_role=EXCLUDED.meal_role,yield_g=EXCLUDED.yield_g,
                    serving_g=EXCLUDED.serving_g,kcal_per_serving=EXCLUDED.kcal_per_serving,protein_g=EXCLUDED.protein_g,
                    carbs_g=EXCLUDED.carbs_g,fat_g=EXCLUDED.fat_g,fibre_g=EXCLUDED.fibre_g,ingredients_summary=EXCLUDED.ingredients_summary,
                    method=EXCLUDED.method,allergens=EXCLUDED.allergens,source_method=EXCLUDED.source_method,
                    calibration_status=EXCLUDED.calibration_status,recipe_version=EXCLUDED.recipe_version,active=EXCLUDED.active,
                    dataset_version=EXCLUDED.dataset_version,source_payload=EXCLUDED.source_payload,updated_at=NOW()
                """, r.get("Recipe ID"),r.get("Recipe Name"),r.get("Local Name"),_b(r.get("Fasting")),_b(r.get("Fish")),r.get("Meal Role"),
                    r.get("Yield g") or 1,r.get("Serving g"),r.get("kcal / Serving"),r.get("Protein g"),r.get("Carbs g"),r.get("Fat g"),
                    r.get("Fibre g"),r.get("Ingredients Summary"),r.get("Method"),r.get("Allergens"),r.get("Source / Method"),
                    r.get("Calibration Status"),r.get("Version"),_b(r.get("Active")),version,_payload(r))
            counts["recipes"] = len(ds.recipes)

            for r in ds.recipe_ingredients:
                await conn.execute("""
                  INSERT INTO nutrition_recipe_ingredients(recipe_id,line_number,food_id,ingredient_name,weight_g,prep_note,dataset_version,source_payload)
                  VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb)
                  ON CONFLICT(recipe_id,line_number) DO UPDATE SET food_id=EXCLUDED.food_id,ingredient_name=EXCLUDED.ingredient_name,
                    weight_g=EXCLUDED.weight_g,prep_note=EXCLUDED.prep_note,dataset_version=EXCLUDED.dataset_version,source_payload=EXCLUDED.source_payload
                """,r.get("Recipe ID"),int(r.get("Line") or 0),r.get("Food ID"),r.get("Ingredient"),r.get("Weight g") or 0,r.get("Prep Note"),version,_payload(r))
            counts["recipe_ingredients"] = len(ds.recipe_ingredients)

            for r in ds.templates:
                await conn.execute("""
                  INSERT INTO nutrition_templates(template_id,meal_name,fasting,fish_required,meal_slot,cuisine,availability,budget,kcal,
                    protein_g,carbs_g,fat_g,fibre_g,main_allergens,tags,rotation_group,active,dataset_version,source_payload,updated_at)
                  VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19::jsonb,NOW())
                  ON CONFLICT(template_id) DO UPDATE SET meal_name=EXCLUDED.meal_name,fasting=EXCLUDED.fasting,
                    fish_required=EXCLUDED.fish_required,meal_slot=EXCLUDED.meal_slot,cuisine=EXCLUDED.cuisine,availability=EXCLUDED.availability,
                    budget=EXCLUDED.budget,kcal=EXCLUDED.kcal,protein_g=EXCLUDED.protein_g,carbs_g=EXCLUDED.carbs_g,fat_g=EXCLUDED.fat_g,
                    fibre_g=EXCLUDED.fibre_g,main_allergens=EXCLUDED.main_allergens,tags=EXCLUDED.tags,rotation_group=EXCLUDED.rotation_group,
                    active=EXCLUDED.active,dataset_version=EXCLUDED.dataset_version,source_payload=EXCLUDED.source_payload,updated_at=NOW()
                """,r.get("Template ID"),r.get("Meal Name"),_b(r.get("Fasting")),_b(r.get("Fish Required")),r.get("Meal Slot"),r.get("Cuisine"),
                    r.get("Availability"),r.get("Budget"),r.get("kcal"),r.get("Protein g"),r.get("Carbs g"),r.get("Fat g"),r.get("Fibre g"),
                    r.get("Main Allergens"),r.get("Tags"),r.get("Rotation Group"),_b(r.get("Active")),version,_payload(r))
            counts["templates"] = len(ds.templates)

            for r in ds.template_components:
                await conn.execute("""
                  INSERT INTO nutrition_template_components(template_id,line_number,item_type,item_id,item_name,servings,portion_g,kcal,
                    protein_g,carbs_g,fat_g,fibre_g,exact_instruction,familiar_portion,exchange_note,allergens,optional,dataset_version,source_payload)
                  VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19::jsonb)
                  ON CONFLICT(template_id,line_number) DO UPDATE SET item_type=EXCLUDED.item_type,item_id=EXCLUDED.item_id,item_name=EXCLUDED.item_name,
                    servings=EXCLUDED.servings,portion_g=EXCLUDED.portion_g,kcal=EXCLUDED.kcal,protein_g=EXCLUDED.protein_g,carbs_g=EXCLUDED.carbs_g,
                    fat_g=EXCLUDED.fat_g,fibre_g=EXCLUDED.fibre_g,exact_instruction=EXCLUDED.exact_instruction,familiar_portion=EXCLUDED.familiar_portion,
                    exchange_note=EXCLUDED.exchange_note,allergens=EXCLUDED.allergens,optional=EXCLUDED.optional,dataset_version=EXCLUDED.dataset_version,
                    source_payload=EXCLUDED.source_payload
                """,r.get("Template ID"),int(r.get("Line") or 0),r.get("Item Type"),r.get("Item ID"),r.get("Item Name"),r.get("Servings"),
                    r.get("Portion g") or 0,r.get("kcal"),r.get("Protein g"),r.get("Carbs g"),r.get("Fat g"),r.get("Fibre g"),r.get("Exact Instruction"),
                    r.get("Familiar Portion"),r.get("Exchange Note"),r.get("Allergens"),_b(r.get("Optional")),version,_payload(r))
            counts["template_components"] = len(ds.template_components)

            for r in ds.exchange_groups:
                await conn.execute("""
                  INSERT INTO nutrition_exchange_groups(exchange_group,food_id,exchange_weight_g,kcal,protein_g,carbs_g,fat_g,fibre_g,
                    fasting_allowed,fish_item,familiar_guidance,coach_note,active,dataset_version,source_payload)
                  VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15::jsonb)
                  ON CONFLICT(exchange_group,food_id) DO UPDATE SET exchange_weight_g=EXCLUDED.exchange_weight_g,kcal=EXCLUDED.kcal,
                    protein_g=EXCLUDED.protein_g,carbs_g=EXCLUDED.carbs_g,fat_g=EXCLUDED.fat_g,fibre_g=EXCLUDED.fibre_g,
                    fasting_allowed=EXCLUDED.fasting_allowed,fish_item=EXCLUDED.fish_item,familiar_guidance=EXCLUDED.familiar_guidance,
                    coach_note=EXCLUDED.coach_note,active=EXCLUDED.active,dataset_version=EXCLUDED.dataset_version,source_payload=EXCLUDED.source_payload
                """,r.get("Exchange Group"),r.get("Food ID"),r.get("Exchange Weight g") or 1,r.get("kcal"),r.get("Protein g"),r.get("Carbs g"),
                    r.get("Fat g"),r.get("Fibre g"),_b(r.get("Fasting Allowed")),_b(r.get("Fish Item")),r.get("Familiar Guidance"),r.get("Coach Note"),
                    _b(r.get("Active")),version,_payload(r))
            counts["exchange_groups"] = len(ds.exchange_groups)

            for r in ds.fasting_calendar:
                await conn.execute("""
                  INSERT INTO nutrition_fasting_calendar(rule_id,fast_name,rule_type,weekday,start_date,end_date,fish_default,
                    client_override_allowed,verified_for_year,verification_status,notes,dataset_version,source_payload,updated_at)
                  VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::jsonb,NOW())
                  ON CONFLICT(rule_id) DO UPDATE SET fast_name=EXCLUDED.fast_name,rule_type=EXCLUDED.rule_type,weekday=EXCLUDED.weekday,
                    start_date=EXCLUDED.start_date,end_date=EXCLUDED.end_date,fish_default=EXCLUDED.fish_default,
                    client_override_allowed=EXCLUDED.client_override_allowed,verified_for_year=EXCLUDED.verified_for_year,
                    verification_status=EXCLUDED.verification_status,notes=EXCLUDED.notes,dataset_version=EXCLUDED.dataset_version,
                    source_payload=EXCLUDED.source_payload,updated_at=NOW()
                """,r.get("Rule ID"),r.get("Fast Name"),r.get("Rule Type"),r.get("Weekday"),_date(r.get("Start Date")),_date(r.get("End Date")),
                    _b(r.get("Fish Default")),_b(r.get("Client Override Allowed")),str(r.get("Verified For Year") or "") or None,
                    r.get("Verification Status"),r.get("Notes"),version,_payload(r))
            counts["fasting_calendar"] = len(ds.fasting_calendar)

            for r in ds.settings_rows:
                key=str(r.get("System Key") or "").strip()
                if not key: continue
                await conn.execute("""
                  INSERT INTO nutrition_engine_settings(setting_key,category,setting_name,value_json,unit,status,owner,notes,dataset_version,source_payload,updated_at)
                  VALUES($1,$2,$3,$4::jsonb,$5,$6,$7,$8,$9,$10::jsonb,NOW())
                  ON CONFLICT(setting_key) DO UPDATE SET category=EXCLUDED.category,setting_name=EXCLUDED.setting_name,value_json=EXCLUDED.value_json,
                    unit=EXCLUDED.unit,status=EXCLUDED.status,owner=EXCLUDED.owner,notes=EXCLUDED.notes,dataset_version=EXCLUDED.dataset_version,
                    source_payload=EXCLUDED.source_payload,updated_at=NOW()
                """,key,r.get("Category"),r.get("Setting"),json.dumps(r.get("Current Value"),ensure_ascii=False),r.get("Unit"),r.get("Status"),
                    r.get("Owner"),r.get("Notes"),version,_payload(r))
            counts["settings"] = len(ds.settings_rows)
    return counts
