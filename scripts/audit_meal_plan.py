import asyncio
import os
import sys
import json
from dotenv import load_dotenv
import asyncpg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()
dsn = os.getenv("DATABASE_URL")

async def inspect_meal_plan():
    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    
    report = {}

    # 1. Inspect nutrition_foods
    foods = await conn.fetch("""
        SELECT 
            food_id, food_name, local_name, food_name_en, food_name_am, 
            category, category_am, fasting_allowed, fish_item, 
            standard_portion_g, unit, familiar_measure,
            kcal_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g, fibre_per_100g,
            exchange_group, data_quality, active
        FROM nutrition_foods
        ORDER BY food_id ASC
    """)
    
    report["total_foods"] = len(foods)
    report["foods"] = []
    
    missing_amharic_foods = []
    suspicious_macros = []
    fasting_inconsistencies = []

    for f in foods:
        f_dict = dict(f)
        # Decimal to float
        for k in ["kcal_per_100g", "protein_per_100g", "carbs_per_100g", "fat_per_100g", "fibre_per_100g", "standard_portion_g"]:
            if f_dict.get(k) is not None:
                f_dict[k] = float(f_dict[k])
        report["foods"].append(f_dict)

        # Checks:
        fid = f["food_id"]
        fname = f["food_name"] or ""
        fam = f["food_name_am"] or ""
        fen = f["food_name_en"] or ""
        cat = f["category"] or ""
        cat_am = f["category_am"] or ""

        # Check 1: Missing or blank Amharic translation
        if not fam or fam.strip() == "" or fam == fname and not any(ord(c) > 127 for c in fam):
            missing_amharic_foods.append({
                "food_id": fid,
                "food_name": fname,
                "food_name_en": fen,
                "food_name_am": fam,
                "issue": "Missing or identical Latin Amharic translation"
            })

        # Check 2: Fasting logic
        # Meat/poultry/eggs/dairy should NOT be fasting
        is_animal = any(w in fname.lower() or w in fen.lower() for w in ["chicken", "beef", "goat", "lamb", "egg", "milk", "yogurt", "cheese", "meat", "turkey", "ayib"])
        if is_animal and f["fasting_allowed"] is True:
            fasting_inconsistencies.append({
                "food_id": fid,
                "name": fname,
                "issue": "Animal product marked as fasting_allowed = TRUE!"
            })
        
        # Check 3: Macro sanity
        # e.g. 0 kcal or sum of macros > 100g
        p, c, fat = f_dict.get("protein_per_100g", 0), f_dict.get("carbs_per_100g", 0), f_dict.get("fat_per_100g", 0)
        macro_sum = p + c + fat
        if macro_sum > 105: # allowing minor rounding
            suspicious_macros.append({
                "food_id": fid,
                "name": fname,
                "macro_sum": macro_sum,
                "issue": f"Protein+Carbs+Fat per 100g exceeds 100g: {macro_sum}g"
            })
        if f_dict.get("kcal_per_100g", 0) == 0 and fid not in ["F_WATER", "W001"]:
            suspicious_macros.append({
                "food_id": fid,
                "name": fname,
                "issue": "0 kcal"
            })

    # 2. Inspect nutrition_recipes
    recipes = await conn.fetch("""
        SELECT 
            recipe_id, recipe_name, local_name, recipe_name_en, recipe_name_am,
            fasting, fish, meal_role, yield_g, serving_g,
            kcal_per_serving, protein_g, carbs_g, fat_g, fibre_g,
            ingredients_summary, ingredients_summary_am, method, method_am,
            calibration_status, active
        FROM nutrition_recipes
        ORDER BY recipe_id ASC
    """)
    report["total_recipes"] = len(recipes)
    report["recipes"] = []
    missing_amharic_recipes = []
    uncalibrated_recipes = []

    for r in recipes:
        r_dict = dict(r)
        for k in ["yield_g", "serving_g", "kcal_per_serving", "protein_g", "carbs_g", "fat_g", "fibre_g"]:
            if r_dict.get(k) is not None:
                r_dict[k] = float(r_dict[k])
        report["recipes"].append(r_dict)

        rid = r["recipe_id"]
        rname = r["recipe_name"]
        ram = r["recipe_name_am"] or ""
        method_am = r["method_am"] or ""
        cal_status = r["calibration_status"]

        if not ram or ram.strip() == "":
            missing_amharic_recipes.append({"recipe_id": rid, "recipe_name": rname, "issue": "Missing recipe_name_am"})
        if not method_am or method_am.strip() == "":
            missing_amharic_recipes.append({"recipe_id": rid, "recipe_name": rname, "issue": "Missing method_am"})
        if cal_status != "CALIBRATED":
            uncalibrated_recipes.append({"recipe_id": rid, "recipe_name": rname, "calibration_status": cal_status})

    # 3. Inspect nutrition_recipe_ingredients
    ingredients = await conn.fetch("""
        SELECT 
            recipe_id, line_number, food_id, ingredient_name, ingredient_name_am,
            weight_g, prep_note, prep_note_am
        FROM nutrition_recipe_ingredients
        ORDER BY recipe_id ASC, line_number ASC
    """)
    report["total_recipe_ingredients"] = len(ingredients)
    missing_am_ingredients = []
    for ing in ingredients:
        if not ing["ingredient_name_am"] or ing["ingredient_name_am"].strip() == "":
            missing_am_ingredients.append({
                "recipe_id": ing["recipe_id"],
                "food_id": ing["food_id"],
                "ingredient_name": ing["ingredient_name"]
            })

    # 4. Inspect nutrition_templates
    templates = await conn.fetch("""
        SELECT 
            template_id, meal_name, meal_name_am, fasting, fish_required,
            meal_slot, cuisine, kcal, protein_g, carbs_g, fat_g, fibre_g
        FROM nutrition_templates
        ORDER BY template_id ASC
    """)
    report["total_templates"] = len(templates)
    missing_am_templates = []
    for t in templates:
        if not t["meal_name_am"] or t["meal_name_am"].strip() == "":
            missing_am_templates.append({
                "template_id": t["template_id"],
                "meal_name": t["meal_name"]
            })

    # Output Summary
    print(f"Total Foods: {len(foods)}")
    print(f"Missing/Flawed Amharic Foods: {len(missing_amharic_foods)}")
    for m in missing_amharic_foods[:10]:
        print(f"  {m['food_id']}: EN={m['food_name_en']} | AM={m['food_name_am']}")
    if len(missing_amharic_foods) > 10:
        print(f"  ... and {len(missing_amharic_foods) - 10} more")

    print(f"\nFasting Inconsistencies: {len(fasting_inconsistencies)}")
    for fi in fasting_inconsistencies:
        print(f"  {fi}")

    print(f"\nSuspicious Macros: {len(suspicious_macros)}")
    for sm in suspicious_macros:
        print(f"  {sm}")

    print(f"\nTotal Recipes: {len(recipes)}")
    print(f"Missing Amharic Recipes: {len(missing_amharic_recipes)}")
    print(f"Uncalibrated Recipes: {len(uncalibrated_recipes)}")
    for uc in uncalibrated_recipes:
        print(f"  {uc['recipe_id']}: {uc['recipe_name']} -> {uc['calibration_status']}")

    print(f"\nTotal Recipe Ingredients: {len(ingredients)}")
    print(f"Missing Amharic Ingredients: {len(missing_am_ingredients)}")

    print(f"\nTotal Meal Templates: {len(templates)}")
    print(f"Missing Amharic Templates: {len(missing_am_templates)}")

    # Save complete JSON analysis to file
    with open("artifacts/meal_plan_audit_full.json", "w", encoding="utf-8") as out:
        json.dump({
            "missing_amharic_foods": missing_amharic_foods,
            "fasting_inconsistencies": fasting_inconsistencies,
            "suspicious_macros": suspicious_macros,
            "missing_amharic_recipes": missing_amharic_recipes,
            "uncalibrated_recipes": uncalibrated_recipes,
            "missing_am_ingredients": missing_am_ingredients,
            "missing_am_templates": missing_am_templates,
            "foods_sample": report["foods"][:15],
            "recipes_sample": report["recipes"][:10],
        }, out, indent=2, ensure_ascii=False)
    
    print("\nDetailed audit report saved to artifacts/meal_plan_audit_full.json")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(inspect_meal_plan())
