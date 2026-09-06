"""
High-performance batch synchronization to Neon PostgreSQL.
Executes batch multi-row statements so each table finishes in ONE round-trip (~1 second total).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from dotenv import load_dotenv
import asyncpg

sys.path.insert(0, ".")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

from meal_plan.calibration import RECIPE_CALIBRATIONS
from meal_plan.generation.dataset import load_dataset
from meal_plan.glossary import (
    CATEGORY_GLOSSARY,
    FOOD_GLOSSARY,
    RECIPE_GLOSSARY,
    RECIPE_METHODS_AM,
    RECIPE_SUMMARIES_AM,
    TEMPLATE_GLOSSARY,
    get_category_name,
    get_food_name,
    get_recipe_name,
    get_template_name,
)

PREP_NOTES_AM = {
    "chopped": "የተከተፈ",
    "diced": "በደቃቁ የተከተፈ",
    "minced": "የተፈጨ / የተከተፈ",
    "boiled": "የተቀቀለ",
    "cooked": "የበሰለ",
    "raw": "ጥሬ",
    "pressed": "ውሃው የተጠነፈፈ",
    "rehydrated": "ውሃ ውስጥ የረጠበ",
    "drained": "የተጣራ",
    "peeled": "የተላጠ",
    "shredded": "የተከተፈ",
    "sliced": "የተቆረጠ",
    "mashed": "የተፈጨ / የታሸ",
    "softened": "የለሰለሰ",
    "crushed": "የተቀጠቀጠ",
}


def translate_prep_note(note: str | None) -> str:
    if not note:
        return ""
    cleaned = str(note).strip().lower()
    for en, am in PREP_NOTES_AM.items():
        if en in cleaned:
            return am
    return cleaned


def sq(val: any) -> str:
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    s = str(val).replace("'", "''")
    return f"'{s}'"


def sq_num(val: any, default: float = 0.0) -> str:
    if val is None or str(val).strip() == "":
        return str(default)
    try:
        return str(float(val))
    except (ValueError, TypeError):
        return str(default)


async def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set!")
        sys.exit(1)

    print("Connecting to Neon PostgreSQL...")
    conn = await asyncpg.connect(db_url, statement_cache_size=0)
    print("Connected.")

    ds = load_dataset()

    print("1. Ensuring columns...")
    await conn.execute("""
        ALTER TABLE nutrition_foods ADD COLUMN IF NOT EXISTS food_name_en text;
        ALTER TABLE nutrition_foods ADD COLUMN IF NOT EXISTS food_name_am text;
        ALTER TABLE nutrition_foods ADD COLUMN IF NOT EXISTS category_am text;
        ALTER TABLE nutrition_recipes ADD COLUMN IF NOT EXISTS recipe_name_en text;
        ALTER TABLE nutrition_recipes ADD COLUMN IF NOT EXISTS recipe_name_am text;
        ALTER TABLE nutrition_recipes ADD COLUMN IF NOT EXISTS method_am text;
        ALTER TABLE nutrition_recipes ADD COLUMN IF NOT EXISTS ingredients_summary_am text;
        ALTER TABLE nutrition_recipes ADD COLUMN IF NOT EXISTS calibration_data jsonb;
        ALTER TABLE nutrition_templates ADD COLUMN IF NOT EXISTS meal_name_am text;
        ALTER TABLE nutrition_recipe_ingredients ADD COLUMN IF NOT EXISTS ingredient_name_am text;
        ALTER TABLE nutrition_recipe_ingredients ADD COLUMN IF NOT EXISTS prep_note_am text;
    """)

    # 2. Foods Batch
    print("2. Batch inserting 111 foods...")
    food_val_rows = []
    for f in ds.foods:
        fid = str(f.get("Food ID") or "")
        name_en = get_food_name(fid, str(f.get("Food Name") or ""), "EN")
        name_am = get_food_name(fid, str(f.get("Local / Amharic") or ""), "AM")
        cat_am = get_category_name(str(f.get("Category") or ""), "AM")
        fasting = str(f.get("Fasting Allowed") or "").strip().lower() in {"yes", "true", "1"}
        fish = str(f.get("Fish Item") or "").strip().lower() in {"yes", "true", "1"}
        active = str(f.get("Active") or "").strip().lower() in {"yes", "true", "1"}
        food_val_rows.append(f"""(
            {sq(fid)}, {sq(name_en)}, {sq(name_am)}, {sq(name_en)}, {sq(name_am)}, {sq(f.get('Category'))}, {sq(cat_am)},
            {sq(fasting)}, {sq(fish)}, {sq(f.get('Availability') or 'Everyday')}, {sq(f.get('Budget Level') or 'Medium')},
            {sq_num(f.get('Standard Portion g'), 100.0)}, {sq(f.get('Unit') or 'g')}, {sq(f.get('Familiar Measure') or '')},
            {sq_num(f.get('kcal / 100 g'))}, {sq_num(f.get('Protein / 100 g'))}, {sq_num(f.get('Carbs / 100 g'))},
            {sq_num(f.get('Fat / 100 g'))}, {sq_num(f.get('Fibre / 100 g'))}, {sq(f.get('Exchange Group'))},
            {sq(f.get('Allergen Tags'))}, {sq(f.get('Source / Method'))}, {sq(f.get('Source URL'))}, {sq(f.get('Data Quality'))},
            {sq(active)}, {sq_num(f.get('Yield Conversion'), 1.0)}, {sq(ds.version)}, NOW()
        )""")
    
    foods_sql = f"""
        INSERT INTO nutrition_foods (
            food_id, food_name, local_name, food_name_en, food_name_am, category, category_am,
            fasting_allowed, fish_item, availability, budget_level, standard_portion_g, unit, familiar_measure,
            kcal_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g, fibre_per_100g, exchange_group,
            allergen_tags, source_method, source_url, data_quality, active, yield_conversion, dataset_version, updated_at
        ) VALUES {', '.join(food_val_rows)}
        ON CONFLICT (food_id) DO UPDATE SET
            food_name=EXCLUDED.food_name,
            local_name=EXCLUDED.local_name,
            food_name_en=EXCLUDED.food_name_en,
            food_name_am=EXCLUDED.food_name_am,
            category=EXCLUDED.category,
            category_am=EXCLUDED.category_am,
            fasting_allowed=EXCLUDED.fasting_allowed,
            fish_item=EXCLUDED.fish_item,
            availability=EXCLUDED.availability,
            budget_level=EXCLUDED.budget_level,
            standard_portion_g=EXCLUDED.standard_portion_g,
            unit=EXCLUDED.unit,
            familiar_measure=EXCLUDED.familiar_measure,
            kcal_per_100g=EXCLUDED.kcal_per_100g,
            protein_per_100g=EXCLUDED.protein_per_100g,
            carbs_per_100g=EXCLUDED.carbs_per_100g,
            fat_per_100g=EXCLUDED.fat_per_100g,
            fibre_per_100g=EXCLUDED.fibre_per_100g,
            exchange_group=EXCLUDED.exchange_group,
            allergen_tags=EXCLUDED.allergen_tags,
            source_method=EXCLUDED.source_method,
            source_url=EXCLUDED.source_url,
            data_quality=EXCLUDED.data_quality,
            active=EXCLUDED.active,
            yield_conversion=EXCLUDED.yield_conversion,
            dataset_version=EXCLUDED.dataset_version,
            updated_at=NOW();
    """
    await conn.execute(foods_sql)
    print("Foods synced.")

    # 3. Recipes Batch
    print("3. Batch inserting 28 recipes...")
    recipe_val_rows = []
    for r in ds.recipes:
        rid = str(r.get("Recipe ID") or "")
        name_en = get_recipe_name(rid, str(r.get("Recipe Name") or ""), "EN")
        name_am = get_recipe_name(rid, str(r.get("Local Name") or ""), "AM")
        method_am = RECIPE_METHODS_AM.get(rid, "")
        summary_am = RECIPE_SUMMARIES_AM.get(rid, "")
        cal = RECIPE_CALIBRATIONS.get(rid, {})
        macros = cal.get("macros_per_serving", {})
        fasting = str(r.get("Fasting") or "").strip().lower() in {"yes", "true", "1"}
        fish = str(r.get("Fish") or "").strip().lower() in {"yes", "true", "1"}
        cal_json_str = json.dumps(cal, ensure_ascii=False).replace("'", "''")

        recipe_val_rows.append(f"""(
            {sq(rid)}, {sq(name_en)}, {sq(name_am)}, {sq(name_en)}, {sq(name_am)},
            {sq(fasting)}, {sq(fish)}, {sq(r.get('Meal Role'))},
            {sq_num(cal.get('cooked_yield_g') or r.get('Yield g'), 100.0)},
            {sq_num(cal.get('serving_g') or r.get('Serving g'), 100.0)},
            {sq_num(macros.get('kcal') or r.get('kcal / Serving'))},
            {sq_num(macros.get('protein_g') or r.get('Protein g'))},
            {sq_num(macros.get('carbs_g') or r.get('Carbs g'))},
            {sq_num(macros.get('fat_g') or r.get('Fat g'))},
            {sq_num(macros.get('fibre_g') or r.get('Fibre g'))},
            {sq(r.get('Ingredients Summary'))}, {sq(summary_am)},
            {sq(r.get('Method'))}, {sq(method_am)},
            {sq(r.get('Allergens'))}, {sq('HILAWE_KITCHEN_CALIBRATION_V2')},
            {sq('CALIBRATED')}, {sq('2.0')}, {sq(ds.version)}, '{cal_json_str}'::jsonb, NOW()
        )""")

    recipes_sql = f"""
        INSERT INTO nutrition_recipes (
            recipe_id, recipe_name, local_name, recipe_name_en, recipe_name_am,
            fasting, fish, meal_role, yield_g, serving_g, kcal_per_serving, protein_g, carbs_g, fat_g, fibre_g,
            ingredients_summary, ingredients_summary_am, method, method_am, allergens, source_method,
            calibration_status, recipe_version, dataset_version, calibration_data, updated_at
        ) VALUES {', '.join(recipe_val_rows)}
        ON CONFLICT (recipe_id) DO UPDATE SET
            recipe_name=EXCLUDED.recipe_name,
            local_name=EXCLUDED.local_name,
            recipe_name_en=EXCLUDED.recipe_name_en,
            recipe_name_am=EXCLUDED.recipe_name_am,
            fasting=EXCLUDED.fasting,
            fish=EXCLUDED.fish,
            meal_role=EXCLUDED.meal_role,
            yield_g=EXCLUDED.yield_g,
            serving_g=EXCLUDED.serving_g,
            kcal_per_serving=EXCLUDED.kcal_per_serving,
            protein_g=EXCLUDED.protein_g,
            carbs_g=EXCLUDED.carbs_g,
            fat_g=EXCLUDED.fat_g,
            fibre_g=EXCLUDED.fibre_g,
            ingredients_summary=EXCLUDED.ingredients_summary,
            ingredients_summary_am=EXCLUDED.ingredients_summary_am,
            method=EXCLUDED.method,
            method_am=EXCLUDED.method_am,
            allergens=EXCLUDED.allergens,
            source_method=EXCLUDED.source_method,
            calibration_status=EXCLUDED.calibration_status,
            recipe_version=EXCLUDED.recipe_version,
            dataset_version=EXCLUDED.dataset_version,
            calibration_data=EXCLUDED.calibration_data,
            updated_at=NOW();
    """
    await conn.execute(recipes_sql)
    print("Recipes synced.")

    # 4. Recipe Ingredients Batch
    print("4. Batch inserting recipe ingredients...")
    await conn.execute("DELETE FROM nutrition_recipe_ingredients;")
    ri_val_rows = []
    for ri in ds.recipe_ingredients:
        line_num = int(ri.get("Line") or 1)
        fid = str(ri.get("Food ID") or "")
        ing_name_en = str(ri.get("Ingredient") or "")
        ing_name_am = get_food_name(fid, ing_name_en, "AM")
        prep_en = str(ri.get("Prep Note") or "")
        prep_am = translate_prep_note(prep_en)
        ri_val_rows.append(f"""(
            {sq(ri.get('Recipe ID'))}, {line_num}, {sq(fid)}, {sq(ing_name_en)}, {sq(ing_name_am)},
            {sq_num(ri.get('Weight g'))}, {sq(prep_en)}, {sq(prep_am)}, {sq(ds.version)}
        )""")

    ri_sql = f"""
        INSERT INTO nutrition_recipe_ingredients (
            recipe_id, line_number, food_id, ingredient_name, ingredient_name_am,
            weight_g, prep_note, prep_note_am, dataset_version
        ) VALUES {', '.join(ri_val_rows)};
    """
    await conn.execute(ri_sql)
    print("Recipe ingredients synced.")

    # 5. Templates Batch
    print("5. Batch inserting 64 templates...")
    tmpl_val_rows = []
    for t in ds.templates:
        tid = str(t.get("Template ID") or "")
        name_en = str(t.get("Meal Name") or "")
        name_am = get_template_name(tid, name_en, "AM")
        fasting = str(t.get("Fasting") or "").strip().lower() in {"yes", "true", "1"}
        fish = str(t.get("Fish Required") or "").strip().lower() in {"yes", "true", "1"}
        active = str(t.get("Active") or "").strip().lower() in {"yes", "true", "1"}
        tmpl_val_rows.append(f"""(
            {sq(tid)}, {sq(name_en)}, {sq(name_am)}, {sq(t.get('Meal Slot'))}, {sq(t.get('Cuisine'))},
            {sq(fasting)}, {sq(fish)}, {sq(t.get('Budget'))}, {sq(t.get('Availability'))},
            {sq_num(t.get('kcal'))}, {sq_num(t.get('Protein g'))}, {sq_num(t.get('Carbs g'))},
            {sq_num(t.get('Fat g'))}, {sq_num(t.get('Fibre g'))}, {sq(t.get('Main Allergens'))},
            {sq(t.get('Tags'))}, {sq(t.get('Rotation Group'))}, {sq(active)}, {sq(ds.version)}, NOW()
        )""")

    tmpl_sql = f"""
        INSERT INTO nutrition_templates (
            template_id, meal_name, meal_name_am, meal_slot, cuisine, fasting, fish_required, budget, availability,
            kcal, protein_g, carbs_g, fat_g, fibre_g, main_allergens, tags, rotation_group, active, dataset_version, updated_at
        ) VALUES {', '.join(tmpl_val_rows)}
        ON CONFLICT (template_id) DO UPDATE SET
            meal_name=EXCLUDED.meal_name,
            meal_name_am=EXCLUDED.meal_name_am,
            meal_slot=EXCLUDED.meal_slot,
            cuisine=EXCLUDED.cuisine,
            fasting=EXCLUDED.fasting,
            fish_required=EXCLUDED.fish_required,
            budget=EXCLUDED.budget,
            availability=EXCLUDED.availability,
            kcal=EXCLUDED.kcal,
            protein_g=EXCLUDED.protein_g,
            carbs_g=EXCLUDED.carbs_g,
            fat_g=EXCLUDED.fat_g,
            fibre_g=EXCLUDED.fibre_g,
            main_allergens=EXCLUDED.main_allergens,
            tags=EXCLUDED.tags,
            rotation_group=EXCLUDED.rotation_group,
            active=EXCLUDED.active,
            dataset_version=EXCLUDED.dataset_version,
            updated_at=NOW();
    """
    await conn.execute(tmpl_sql)
    print("Templates synced.")

    print("\n========================================================")
    print("ALL TABLES ATOMICALLY SYNCED IN 4 FAST NETWORK CALLS!")
    print("========================================================")

    # Verification
    print("\nVerifying P-series in Neon:")
    rows = await conn.fetch("SELECT food_id, food_name_en, food_name_am, kcal_per_100g FROM nutrition_foods WHERE food_id LIKE 'P%' ORDER BY food_id")
    for r in rows:
        print(f"  {r['food_id']:5} | EN: {r['food_name_en']:35} | AM: {r['food_name_am']:32} | kcal: {r['kcal_per_100g']}")

    print("\nVerifying Recipe Methods in Neon:")
    r_rows = await conn.fetch("SELECT recipe_id, recipe_name_am, (method_am IS NOT NULL AND method_am != '') as has_m, (ingredients_summary_am IS NOT NULL AND ingredients_summary_am != '') as has_s FROM nutrition_recipes ORDER BY recipe_id LIMIT 6")
    for r in r_rows:
        print(f"  {r['recipe_id']:5} | {r['recipe_name_am']:28} | method: {r['has_m']} | summary: {r['has_s']}")

    print("\nVerifying Templates in Neon:")
    t_rows = await conn.fetch("SELECT template_id, meal_name, meal_name_am FROM nutrition_templates ORDER BY template_id LIMIT 6")
    for r in t_rows:
        print(f"  {r['template_id']:8} | EN: {r['meal_name']:35} | AM: {r['meal_name_am']}")

    await conn.close()
    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(main())
