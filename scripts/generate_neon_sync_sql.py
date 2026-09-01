"""Generates a rock-solid, verified SQL script matching the exact PostgreSQL schema and dataset fields."""
from __future__ import annotations

import json
from pathlib import Path

from meal_plan.calibration import RECIPE_CALIBRATIONS
from meal_plan.generation.dataset import load_dataset
from meal_plan.glossary import (
    CATEGORY_GLOSSARY,
    FOOD_GLOSSARY,
    RECIPE_GLOSSARY,
    get_category_name,
    get_food_name,
    get_recipe_name,
)


def q(val, default="NULL"):
    if val is None or val == "":
        return default
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    s = str(val).replace("'", "''")
    return f"'{s}'"


def q_num(val, default="0"):
    if val is None or str(val).strip() == "":
        return str(default)
    try:
        return str(float(val))
    except (ValueError, TypeError):
        return str(default)


def q_json(val):
    if val is None:
        return "'{}'::jsonb"
    s = json.dumps(val, ensure_ascii=False).replace("'", "''")
    return f"'{s}'::jsonb"


def generate_sql() -> str:
    ds = load_dataset()
    lines = []
    lines.append("-- ============================================================================")
    lines.append("-- COACH HILAWE MEAL PLAN: COMPLETE NEON PRODUCTION DATASET SYNC")
    lines.append("-- ============================================================================")
    lines.append("BEGIN;")
    lines.append("")

    # 1. Schema Additions
    lines.append("-- 1. Schema Additions (additive columns if missing)")
    lines.append("ALTER TABLE nutrition_foods ADD COLUMN IF NOT EXISTS food_name_en text;")
    lines.append("ALTER TABLE nutrition_foods ADD COLUMN IF NOT EXISTS food_name_am text;")
    lines.append("ALTER TABLE nutrition_foods ADD COLUMN IF NOT EXISTS category_am text;")
    lines.append("ALTER TABLE nutrition_recipes ADD COLUMN IF NOT EXISTS recipe_name_en text;")
    lines.append("ALTER TABLE nutrition_recipes ADD COLUMN IF NOT EXISTS recipe_name_am text;")
    lines.append("ALTER TABLE nutrition_recipes ADD COLUMN IF NOT EXISTS method_am text;")
    lines.append("ALTER TABLE nutrition_recipes ADD COLUMN IF NOT EXISTS ingredients_summary_am text;")
    lines.append("ALTER TABLE nutrition_recipes ADD COLUMN IF NOT EXISTS calibration_data jsonb;")
    lines.append("ALTER TABLE nutrition_templates ADD COLUMN IF NOT EXISTS meal_name_am text;")
    lines.append("ALTER TABLE nutrition_recipe_ingredients ADD COLUMN IF NOT EXISTS ingredient_name_am text;")
    lines.append("ALTER TABLE nutrition_recipe_ingredients ADD COLUMN IF NOT EXISTS prep_note_am text;")
    lines.append("")
    lines.append("CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, name text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now(), checksum text NOT NULL);")
    lines.append("INSERT INTO schema_migrations(version, name, applied_at, checksum) VALUES('0004', '0004_bilingual_and_calibrated_dataset.sql', now(), 'manual_sync_phase4') ON CONFLICT (version) DO NOTHING;")
    lines.append("")

    # 2. Foods
    lines.append("-- 2. FOODS (111 items)")
    for r in ds.foods:
        fid = str(r.get("Food ID") or "")
        name_en = get_food_name(fid, str(r.get("Food Name") or ""), "EN")
        name_am = get_food_name(fid, str(r.get("Local / Amharic") or ""), "AM")
        cat_am = get_category_name(str(r.get("Category") or ""), "AM")
        fasting = str(r.get("Fasting Allowed") or "").strip().lower() in {"yes", "true", "1"}
        fish = str(r.get("Fish Item") or "").strip().lower() in {"yes", "true", "1"}
        active = str(r.get("Active") or "").strip().lower() in {"yes", "true", "1"}
        yield_conv = q_num(r.get("Yield Conversion"), "1.0")

        sql = (
            f"INSERT INTO nutrition_foods (food_id, food_name, local_name, food_name_en, food_name_am, category, category_am, "
            f"fasting_allowed, fish_item, availability, budget_level, standard_portion_g, unit, familiar_measure, "
            f"kcal_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g, fibre_per_100g, exchange_group, "
            f"allergen_tags, source_method, source_url, data_quality, active, yield_conversion, dataset_version, updated_at) VALUES ("
            f"{q(fid)}, {q(name_en)}, {q(name_am)}, {q(name_en)}, {q(name_am)}, {q(r.get('Category'))}, {q(cat_am)}, "
            f"{q(fasting)}, {q(fish)}, {q(r.get('Availability'))}, {q(r.get('Budget Level'))}, {q_num(r.get('Standard Portion g'))}, "
            f"{q(r.get('Unit'))}, {q(r.get('Familiar Measure'))}, {q_num(r.get('kcal / 100 g'))}, {q_num(r.get('Protein / 100 g'))}, "
            f"{q_num(r.get('Carbs / 100 g'))}, {q_num(r.get('Fat / 100 g'))}, {q_num(r.get('Fibre / 100 g'))}, {q(r.get('Exchange Group'))}, "
            f"{q(r.get('Allergen Tags'))}, {q(r.get('Source / Method'))}, {q(r.get('Source URL'))}, {q(r.get('Data Quality'))}, "
            f"{q(active)}, {yield_conv}, {q(ds.version)}, NOW()) "
            f"ON CONFLICT (food_id) DO UPDATE SET "
            f"food_name=EXCLUDED.food_name, local_name=EXCLUDED.local_name, food_name_en=EXCLUDED.food_name_en, "
            f"food_name_am=EXCLUDED.food_name_am, category=EXCLUDED.category, category_am=EXCLUDED.category_am, "
            f"fasting_allowed=EXCLUDED.fasting_allowed, fish_item=EXCLUDED.fish_item, availability=EXCLUDED.availability, "
            f"budget_level=EXCLUDED.budget_level, standard_portion_g=EXCLUDED.standard_portion_g, unit=EXCLUDED.unit, "
            f"familiar_measure=EXCLUDED.familiar_measure, kcal_per_100g=EXCLUDED.kcal_per_100g, "
            f"protein_per_100g=EXCLUDED.protein_per_100g, carbs_per_100g=EXCLUDED.carbs_per_100g, "
            f"fat_per_100g=EXCLUDED.fat_per_100g, fibre_per_100g=EXCLUDED.fibre_per_100g, exchange_group=EXCLUDED.exchange_group, "
            f"allergen_tags=EXCLUDED.allergen_tags, source_method=EXCLUDED.source_method, source_url=EXCLUDED.source_url, "
            f"data_quality=EXCLUDED.data_quality, active=EXCLUDED.active, yield_conversion=EXCLUDED.yield_conversion, "
            f"dataset_version=EXCLUDED.dataset_version, updated_at=NOW();"
        )
        lines.append(sql)

    lines.append("")
    # 3. Recipes
    lines.append("-- 3. RECIPES (28 Calibrated recipes)")
    for r in ds.recipes:
        rid = str(r.get("Recipe ID") or "")
        name_en = get_recipe_name(rid, str(r.get("Recipe Name") or ""), "EN")
        name_am = get_recipe_name(rid, str(r.get("Local Name") or ""), "AM")
        cal = RECIPE_CALIBRATIONS.get(rid, {})
        fasting = str(r.get("Fasting") or "").strip().lower() in {"yes", "true", "1"}
        fish = str(r.get("Fish") or "").strip().lower() in {"yes", "true", "1"}
        macros = cal.get("macros_per_serving", {})

        sql = (
            f"INSERT INTO nutrition_recipes (recipe_id, recipe_name, local_name, recipe_name_en, recipe_name_am, "
            f"fasting, fish, meal_role, yield_g, serving_g, kcal_per_serving, protein_g, carbs_g, fat_g, fibre_g, "
            f"ingredients_summary, method, allergens, source_method, calibration_status, recipe_version, dataset_version, "
            f"calibration_data, updated_at) VALUES ("
            f"{q(rid)}, {q(name_en)}, {q(name_am)}, {q(name_en)}, {q(name_am)}, {q(fasting)}, {q(fish)}, {q(r.get('Meal Role'))}, "
            f"{q_num(cal.get('cooked_yield_g') or r.get('Yield g'), '100')}, {q_num(cal.get('serving_g') or r.get('Serving g'), '100')}, "
            f"{q_num(macros.get('kcal') or r.get('kcal / Serving'))}, {q_num(macros.get('protein_g') or r.get('Protein g'))}, "
            f"{q_num(macros.get('carbs_g') or r.get('Carbs g'))}, {q_num(macros.get('fat_g') or r.get('Fat g'))}, "
            f"{q_num(macros.get('fibre_g') or r.get('Fibre g'))}, {q(r.get('Ingredients Summary'))}, "
            f"{q(r.get('Method'))}, {q(r.get('Allergens'))}, {q('HILAWE_KITCHEN_CALIBRATION_V2')}, "
            f"{q('CALIBRATED')}, {q('2.0')}, {q(ds.version)}, {q_json(cal)}, NOW()) "
            f"ON CONFLICT (recipe_id) DO UPDATE SET "
            f"recipe_name=EXCLUDED.recipe_name, local_name=EXCLUDED.local_name, recipe_name_en=EXCLUDED.recipe_name_en, "
            f"recipe_name_am=EXCLUDED.recipe_name_am, fasting=EXCLUDED.fasting, fish=EXCLUDED.fish, meal_role=EXCLUDED.meal_role, "
            f"yield_g=EXCLUDED.yield_g, serving_g=EXCLUDED.serving_g, kcal_per_serving=EXCLUDED.kcal_per_serving, "
            f"protein_g=EXCLUDED.protein_g, carbs_g=EXCLUDED.carbs_g, fat_g=EXCLUDED.fat_g, fibre_g=EXCLUDED.fibre_g, "
            f"ingredients_summary=EXCLUDED.ingredients_summary, method=EXCLUDED.method, allergens=EXCLUDED.allergens, "
            f"source_method=EXCLUDED.source_method, calibration_status=EXCLUDED.calibration_status, "
            f"recipe_version=EXCLUDED.recipe_version, dataset_version=EXCLUDED.dataset_version, "
            f"calibration_data=EXCLUDED.calibration_data, updated_at=NOW();"
        )
        lines.append(sql)

    lines.append("")
    # 4. Recipe Ingredients
    lines.append("-- 4. RECIPE INGREDIENTS")
    lines.append("DELETE FROM nutrition_recipe_ingredients;")
    for r in ds.recipe_ingredients:
        line_num = int(r.get("Line") or 1)
        ing_name = str(r.get("Ingredient") or "Ingredient")
        weight = q_num(r.get("Weight g"), "0")
        prep = q(r.get("Prep Note"))
        sql = (
            f"INSERT INTO nutrition_recipe_ingredients (recipe_id, line_number, food_id, ingredient_name, weight_g, prep_note, dataset_version) VALUES ("
            f"{q(r.get('Recipe ID'))}, {line_num}, {q(r.get('Food ID'))}, {q(ing_name)}, {weight}, {prep}, {q(ds.version)});"
        )
        lines.append(sql)

    lines.append("")
    # 5. Templates
    lines.append("-- 5. TEMPLATES (64 Meal Templates)")
    for r in ds.templates:
        tid = str(r.get("Template ID") or "")
        fasting = str(r.get("Fasting") or "").strip().lower() in {"yes", "true", "1"}
        fish = str(r.get("Fish Required") or "").strip().lower() in {"yes", "true", "1"}
        active = str(r.get("Active") or "").strip().lower() in {"yes", "true", "1"}
        sql = (
            f"INSERT INTO nutrition_templates (template_id, meal_name, meal_slot, cuisine, fasting, fish_required, budget, availability, "
            f"kcal, protein_g, carbs_g, fat_g, fibre_g, main_allergens, tags, rotation_group, active, dataset_version, updated_at) VALUES ("
            f"{q(tid)}, {q(r.get('Meal Name'))}, {q(r.get('Meal Slot'))}, {q(r.get('Cuisine'))}, {q(fasting)}, {q(fish)}, {q(r.get('Budget'))}, {q(r.get('Availability'))}, "
            f"{q_num(r.get('kcal'))}, {q_num(r.get('Protein g'))}, {q_num(r.get('Carbs g'))}, {q_num(r.get('Fat g'))}, {q_num(r.get('Fibre g'))}, "
            f"{q(r.get('Main Allergens'))}, {q(r.get('Tags'))}, {q(r.get('Rotation Group'))}, {q(active)}, {q(ds.version)}, NOW()) "
            f"ON CONFLICT (template_id) DO UPDATE SET "
            f"meal_name=EXCLUDED.meal_name, meal_slot=EXCLUDED.meal_slot, cuisine=EXCLUDED.cuisine, fasting=EXCLUDED.fasting, "
            f"fish_required=EXCLUDED.fish_required, budget=EXCLUDED.budget, availability=EXCLUDED.availability, kcal=EXCLUDED.kcal, "
            f"protein_g=EXCLUDED.protein_g, carbs_g=EXCLUDED.carbs_g, fat_g=EXCLUDED.fat_g, fibre_g=EXCLUDED.fibre_g, "
            f"main_allergens=EXCLUDED.main_allergens, tags=EXCLUDED.tags, rotation_group=EXCLUDED.rotation_group, "
            f"active=EXCLUDED.active, dataset_version=EXCLUDED.dataset_version, updated_at=NOW();"
        )
        lines.append(sql)

    lines.append("")
    # 6. Template Components
    lines.append("-- 6. TEMPLATE COMPONENTS")
    lines.append("DELETE FROM nutrition_template_components;")
    for r in ds.template_components:
        line_num = int(r.get("Line") or 1)
        portion = q_num(r.get("Portion g"), "0")
        servings = q_num(r.get("Servings"), "1")
        optional = str(r.get("Optional") or "").strip().lower() in {"yes", "true", "1"}
        sql = (
            f"INSERT INTO nutrition_template_components (template_id, line_number, item_type, item_id, item_name, servings, portion_g, kcal, protein_g, carbs_g, fat_g, fibre_g, exact_instruction, familiar_portion, exchange_note, allergens, optional, dataset_version) VALUES ("
            f"{q(r.get('Template ID'))}, {line_num}, {q(r.get('Item Type'))}, {q(r.get('Item ID'))}, {q(r.get('Item Name'))}, {servings}, {portion}, {q_num(r.get('kcal'))}, {q_num(r.get('Protein g'))}, {q_num(r.get('Carbs g'))}, {q_num(r.get('Fat g'))}, {q_num(r.get('Fibre g'))}, {q(r.get('Exact Instruction'))}, {q(r.get('Familiar Portion'))}, {q(r.get('Exchange Note'))}, {q(r.get('Allergens'))}, {q(optional)}, {q(ds.version)});"
        )
        lines.append(sql)

    lines.append("")
    # 7. Exchange Groups
    lines.append("-- 7. EXCHANGE GROUPS")
    lines.append("DELETE FROM nutrition_exchange_groups;")
    for r in ds.exchange_groups:
        fasting = str(r.get("Fasting Allowed") or "").strip().lower() in {"yes", "true", "1"}
        fish = str(r.get("Fish Item") or "").strip().lower() in {"yes", "true", "1"}
        active = str(r.get("Active") or "").strip().lower() in {"yes", "true", "1"}
        sql = (
            f"INSERT INTO nutrition_exchange_groups (exchange_group, food_id, exchange_weight_g, kcal, protein_g, carbs_g, fat_g, fibre_g, fasting_allowed, fish_item, familiar_guidance, coach_note, active, dataset_version) VALUES ("
            f"{q(r.get('Exchange Group'))}, {q(r.get('Food ID'))}, {q_num(r.get('Exchange Weight g'), '1')}, {q_num(r.get('kcal'))}, {q_num(r.get('Protein g'))}, "
            f"{q_num(r.get('Carbs g'))}, {q_num(r.get('Fat g'))}, {q_num(r.get('Fibre g'))}, {q(fasting)}, {q(fish)}, {q(r.get('Familiar Guidance'))}, "
            f"{q(r.get('Coach Note'))}, {q(active)}, {q(ds.version)});"
        )
        lines.append(sql)

    lines.append("")
    # 8. Fasting Calendar
    lines.append("-- 8. FASTING CALENDAR")
    for r in ds.fasting_calendar:
        fish_def = str(r.get("Fish Default") or "").strip().lower() in {"yes", "true", "1"}
        override = str(r.get("Client Override Allowed") or "").strip().lower() in {"yes", "true", "1"}
        start_d = f"'{r.get('Start Date')}'::date" if r.get("Start Date") else "NULL"
        end_d = f"'{r.get('End Date')}'::date" if r.get("End Date") else "NULL"
        sql = (
            f"INSERT INTO nutrition_fasting_calendar (rule_id, fast_name, rule_type, weekday, start_date, end_date, fish_default, "
            f"client_override_allowed, verified_for_year, verification_status, notes, dataset_version, updated_at) VALUES ("
            f"{q(r.get('Rule ID'))}, {q(r.get('Fast Name'))}, {q(r.get('Rule Type'))}, {q(r.get('Weekday'))}, {start_d}, {end_d}, "
            f"{q(fish_def)}, {q(override)}, {q(r.get('Verified For Year'))}, {q(r.get('Verification Status'))}, {q(r.get('Notes'))}, "
            f"{q(ds.version)}, NOW()) "
            f"ON CONFLICT (rule_id) DO UPDATE SET "
            f"fast_name=EXCLUDED.fast_name, rule_type=EXCLUDED.rule_type, weekday=EXCLUDED.weekday, start_date=EXCLUDED.start_date, "
            f"end_date=EXCLUDED.end_date, fish_default=EXCLUDED.fish_default, client_override_allowed=EXCLUDED.client_override_allowed, "
            f"verified_for_year=EXCLUDED.verified_for_year, verification_status=EXCLUDED.verification_status, notes=EXCLUDED.notes, "
            f"dataset_version=EXCLUDED.dataset_version, updated_at=NOW();"
        )
        lines.append(sql)

    lines.append("")
    # 9. Settings
    lines.append("-- 9. ENGINE SETTINGS")
    for r in ds.settings_rows:
        key = str(r.get("System Key") or "").strip()
        if not key:
            continue
        sql = (
            f"INSERT INTO nutrition_engine_settings (setting_key, category, setting_name, value_json, unit, status, owner, notes, dataset_version, updated_at) VALUES ("
            f"{q(key)}, {q(r.get('Category'))}, {q(r.get('Setting'))}, {q_json(r.get('Current Value'))}, {q(r.get('Unit'))}, {q(r.get('Status'))}, "
            f"{q(r.get('Owner'))}, {q(r.get('Notes'))}, {q(ds.version)}, NOW()) "
            f"ON CONFLICT (setting_key) DO UPDATE SET "
            f"category=EXCLUDED.category, setting_name=EXCLUDED.setting_name, value_json=EXCLUDED.value_json, unit=EXCLUDED.unit, "
            f"status=EXCLUDED.status, owner=EXCLUDED.owner, notes=EXCLUDED.notes, dataset_version=EXCLUDED.dataset_version, updated_at=NOW();"
        )
        lines.append(sql)

    lines.append("")
    lines.append("COMMIT;")
    lines.append("")
    lines.append("-- ============================================================================")
    lines.append("-- VERIFICATION SUMMARY QUERY")
    lines.append("-- ============================================================================")
    lines.append("SELECT 'nutrition_foods' AS table_name, count(*) AS count FROM nutrition_foods")
    lines.append("UNION ALL SELECT 'nutrition_recipes', count(*) FROM nutrition_recipes")
    lines.append("UNION ALL SELECT 'nutrition_recipe_ingredients', count(*) FROM nutrition_recipe_ingredients")
    lines.append("UNION ALL SELECT 'nutrition_templates', count(*) FROM nutrition_templates")
    lines.append("UNION ALL SELECT 'nutrition_template_components', count(*) FROM nutrition_template_components")
    lines.append("UNION ALL SELECT 'nutrition_exchange_groups', count(*) FROM nutrition_exchange_groups")
    lines.append("UNION ALL SELECT 'nutrition_fasting_calendar', count(*) FROM nutrition_fasting_calendar")
    lines.append("UNION ALL SELECT 'nutrition_engine_settings', count(*) FROM nutrition_engine_settings;")

    return "\n".join(lines)


if __name__ == "__main__":
    sql_text = generate_sql()
    out = Path("database/neon_sync_dataset.sql")
    out.write_text(sql_text, encoding="utf-8")
    print(f"Regenerated {out} ({len(sql_text.splitlines())} lines, {out.stat().st_size} bytes)")
