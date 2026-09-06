"""
Syncs all foods (fixing P-series), recipes (with Amharic methods and summaries),
recipe ingredients, templates (with meal_name_am), components and exchange groups
directly to Neon PostgreSQL using asyncpg with statement_cache_size=0.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
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


async def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set!")
        sys.exit(1)

    print("Connecting to Neon PostgreSQL...")
    conn = await asyncpg.connect(db_url, statement_cache_size=0)
    print("Connected successfully.")

    ds = load_dataset()

    async with conn.transaction():
        # 1. Schema Additions
        print("Ensuring database columns exist...")
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

        # 2. Sync Foods
        print(f"Syncing {len(ds.foods)} foods to nutrition_foods (including canonical P-series)...")
        for f in ds.foods:
            fid = str(f.get("Food ID") or "")
            name_en = get_food_name(fid, str(f.get("Food Name") or ""), "EN")
            name_am = get_food_name(fid, str(f.get("Local / Amharic") or ""), "AM")
            cat_am = get_category_name(str(f.get("Category") or ""), "AM")
            fasting = str(f.get("Fasting Allowed") or "").strip().lower() in {"yes", "true", "1"}
            fish = str(f.get("Fish Item") or "").strip().lower() in {"yes", "true", "1"}
            active = str(f.get("Active") or "").strip().lower() in {"yes", "true", "1"}
            yield_conv = float(f.get("Yield Conversion") or 1.0)
            portion_g = float(f.get("Standard Portion g") or 100.0)
            kcal = float(f.get("kcal / 100 g") or 0.0)
            protein = float(f.get("Protein / 100 g") or 0.0)
            carbs = float(f.get("Carbs / 100 g") or 0.0)
            fat = float(f.get("Fat / 100 g") or 0.0)
            fibre = float(f.get("Fibre / 100 g") or 0.0)

            await conn.execute("""
                INSERT INTO nutrition_foods (
                    food_id, food_name, local_name, food_name_en, food_name_am, category, category_am,
                    fasting_allowed, fish_item, availability, budget_level, standard_portion_g, unit, familiar_measure,
                    kcal_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g, fibre_per_100g, exchange_group,
                    allergen_tags, source_method, source_url, data_quality, active, yield_conversion, dataset_version, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7,
                    $8, $9, $10, $11, $12, $13, $14,
                    $15, $16, $17, $18, $19, $20,
                    $21, $22, $23, $24, $25, $26, $27, NOW()
                )
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
            """,
                fid, name_en, name_am, name_en, name_am, str(f.get("Category")), cat_am,
                fasting, fish, str(f.get("Availability") or "Everyday"), str(f.get("Budget Level") or "Medium"),
                portion_g, str(f.get("Unit") or "g"), str(f.get("Familiar Measure") or ""),
                kcal, protein, carbs, fat, fibre, str(f.get("Exchange Group") or ""),
                str(f.get("Allergen Tags") or ""), str(f.get("Source / Method") or ""),
                str(f.get("Source URL") or ""), str(f.get("Data Quality") or ""),
                active, yield_conv, ds.version
            )

        # 3. Sync Recipes
        print(f"Syncing {len(ds.recipes)} calibrated recipes (with Amharic methods and summaries)...")
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
            yield_g = float(cal.get("cooked_yield_g") or r.get("Yield g") or 100.0)
            serving_g = float(cal.get("serving_g") or r.get("Serving g") or 100.0)
            kcal = float(macros.get("kcal") or r.get("kcal / Serving") or 0.0)
            protein = float(macros.get("protein_g") or r.get("Protein g") or 0.0)
            carbs = float(macros.get("carbs_g") or r.get("Carbs g") or 0.0)
            fat = float(macros.get("fat_g") or r.get("Fat g") or 0.0)
            fibre = float(macros.get("fibre_g") or r.get("Fibre g") or 0.0)

            await conn.execute("""
                INSERT INTO nutrition_recipes (
                    recipe_id, recipe_name, local_name, recipe_name_en, recipe_name_am,
                    fasting, fish, meal_role, yield_g, serving_g, kcal_per_serving, protein_g, carbs_g, fat_g, fibre_g,
                    ingredients_summary, ingredients_summary_am, method, method_am, allergens, source_method,
                    calibration_status, recipe_version, dataset_version, calibration_data, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
                    $16, $17, $18, $19, $20, $21,
                    $22, $23, $24, $25, NOW()
                )
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
            """,
                rid, name_en, name_am, name_en, name_am,
                fasting, fish, str(r.get("Meal Role") or ""),
                yield_g, serving_g, kcal, protein, carbs, fat, fibre,
                str(r.get("Ingredients Summary") or ""), summary_am,
                str(r.get("Method") or ""), method_am,
                str(r.get("Allergens") or ""), "HILAWE_KITCHEN_CALIBRATION_V2",
                "CALIBRATED", "2.0", ds.version, json.dumps(cal)
            )

        # 4. Sync Recipe Ingredients
        print(f"Syncing {len(ds.recipe_ingredients)} recipe ingredients with Amharic names and prep notes...")
        await conn.execute("DELETE FROM nutrition_recipe_ingredients;")
        for ri in ds.recipe_ingredients:
            line_num = int(ri.get("Line") or 1)
            fid = str(ri.get("Food ID") or "")
            ing_name_en = str(ri.get("Ingredient") or "")
            ing_name_am = get_food_name(fid, ing_name_en, "AM")
            weight = float(ri.get("Weight g") or 0.0)
            prep_en = str(ri.get("Prep Note") or "")
            prep_am = translate_prep_note(prep_en)

            await conn.execute("""
                INSERT INTO nutrition_recipe_ingredients (
                    recipe_id, line_number, food_id, ingredient_name, ingredient_name_am,
                    weight_g, prep_note, prep_note_am, dataset_version
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);
            """,
                str(ri.get("Recipe ID")), line_num, fid, ing_name_en, ing_name_am,
                weight, prep_en, prep_am, ds.version
            )

        # 5. Sync Templates
        print(f"Syncing {len(ds.templates)} meal templates with Amharic names...")
        for t in ds.templates:
            tid = str(t.get("Template ID") or "")
            name_en = str(t.get("Meal Name") or "")
            name_am = get_template_name(tid, name_en, "AM")
            fasting = str(t.get("Fasting") or "").strip().lower() in {"yes", "true", "1"}
            fish = str(t.get("Fish Required") or "").strip().lower() in {"yes", "true", "1"}
            active = str(t.get("Active") or "").strip().lower() in {"yes", "true", "1"}
            kcal = float(t.get("kcal") or 0.0)
            protein = float(t.get("Protein g") or 0.0)
            carbs = float(t.get("Carbs g") or 0.0)
            fat = float(t.get("Fat g") or 0.0)
            fibre = float(t.get("Fibre g") or 0.0)

            await conn.execute("""
                INSERT INTO nutrition_templates (
                    template_id, meal_name, meal_name_am, meal_slot, cuisine, fasting, fish_required, budget, availability,
                    kcal, protein_g, carbs_g, fat_g, fibre_g, main_allergens, tags, rotation_group, active, dataset_version, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9,
                    $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, NOW()
                )
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
            """,
                tid, name_en, name_am, str(t.get("Meal Slot")), str(t.get("Cuisine")),
                fasting, fish, str(t.get("Budget")), str(t.get("Availability")),
                kcal, protein, carbs, fat, fibre, str(t.get("Main Allergens")),
                str(t.get("Tags")), str(t.get("Rotation Group")), active, ds.version
            )

        # 6. Sync Template Components
        print(f"Syncing {len(ds.template_components)} template components...")
        await conn.execute("DELETE FROM nutrition_template_components;")
        for tc in ds.template_components:
            line_num = int(tc.get("Line") or 1)
            portion = float(tc.get("Portion g") or 0.0)
            servings = float(tc.get("Servings") or 1.0)
            optional = str(tc.get("Optional") or "").strip().lower() in {"yes", "true", "1"}
            kcal = float(tc.get("kcal") or 0.0)
            protein = float(tc.get("Protein g") or 0.0)
            carbs = float(tc.get("Carbs g") or 0.0)
            fat = float(tc.get("Fat g") or 0.0)
            fibre = float(tc.get("Fibre g") or 0.0)

            await conn.execute("""
                INSERT INTO nutrition_template_components (
                    template_id, line_number, item_type, item_id, item_name, servings, portion_g,
                    kcal, protein_g, carbs_g, fat_g, fibre_g, exact_instruction, familiar_portion,
                    exchange_note, allergens, optional, dataset_version
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18);
            """,
                str(tc.get("Template ID")), line_num, str(tc.get("Item Type")), str(tc.get("Item ID")),
                str(tc.get("Item Name")), servings, portion, kcal, protein, carbs, fat, fibre,
                str(tc.get("Exact Instruction") or ""), str(tc.get("Familiar Portion") or ""),
                str(tc.get("Exchange Note") or ""), str(tc.get("Allergens") or ""), optional, ds.version
            )

        # 7. Sync Exchange Groups
        print(f"Syncing {len(ds.exchange_groups)} exchange groups...")
        await conn.execute("DELETE FROM nutrition_exchange_groups;")
        for eg in ds.exchange_groups:
            fasting = str(eg.get("Fasting Allowed") or "").strip().lower() in {"yes", "true", "1"}
            fish = str(eg.get("Fish Item") or "").strip().lower() in {"yes", "true", "1"}
            active = str(eg.get("Active") or "").strip().lower() in {"yes", "true", "1"}
            weight = float(eg.get("Exchange Weight g") or 1.0)
            kcal = float(eg.get("kcal") or 0.0)
            protein = float(eg.get("Protein g") or 0.0)
            carbs = float(eg.get("Carbs g") or 0.0)
            fat = float(eg.get("Fat g") or 0.0)
            fibre = float(eg.get("Fibre g") or 0.0)

            await conn.execute("""
                INSERT INTO nutrition_exchange_groups (
                    exchange_group, food_id, exchange_weight_g, kcal, protein_g, carbs_g, fat_g, fibre_g,
                    fasting_allowed, fish_item, familiar_guidance, coach_note, active, dataset_version
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14);
            """,
                str(eg.get("Exchange Group")), str(eg.get("Food ID")), weight, kcal, protein, carbs, fat, fibre,
                fasting, fish, str(eg.get("Familiar Guidance") or ""), str(eg.get("Coach Note") or ""),
                active, ds.version
            )

        # Migration tracking
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version text PRIMARY KEY,
                name text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now(),
                checksum text NOT NULL
            );
            INSERT INTO schema_migrations(version, name, applied_at, checksum)
            VALUES('0005', '0005_full_amharic_dataset_sync.sql', now(), 'amharic_first_rollout')
            ON CONFLICT (version) DO NOTHING;
        """)

    print("\n========================================================")
    print("ALL TABLES ATOMICALLY SYNCED TO NEON POSTGRESQL!")
    print("========================================================")

    # Verification Query
    print("\nVerifying P001-P015:")
    p_rows = await conn.fetch("SELECT food_id, food_name_en, food_name_am, kcal_per_100g FROM nutrition_foods WHERE food_id LIKE 'P%' ORDER BY food_id")
    for r in p_rows:
        print(f"  {r['food_id']:5} | EN: {r['food_name_en']:35} | AM: {r['food_name_am']:30} | kcal: {r['kcal_per_100g']}")

    print("\nVerifying Recipe Methods:")
    r_rows = await conn.fetch("SELECT recipe_id, recipe_name_am, method_am IS NOT NULL as has_method, ingredients_summary_am IS NOT NULL as has_summary FROM nutrition_recipes ORDER BY recipe_id LIMIT 5")
    for r in r_rows:
        print(f"  {r['recipe_id']:5} | {r['recipe_name_am']:30} | method: {r['has_method']} | summary: {r['has_summary']}")

    print("\nVerifying Templates:")
    t_rows = await conn.fetch("SELECT template_id, meal_name, meal_name_am FROM nutrition_templates ORDER BY template_id LIMIT 5")
    for r in t_rows:
        print(f"  {r['template_id']:8} | EN: {r['meal_name']:35} | AM: {r['meal_name_am']}")

    await conn.close()
    print("\nConnection closed. Done.")


if __name__ == "__main__":
    asyncio.run(main())
