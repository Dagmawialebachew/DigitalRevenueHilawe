import asyncio
import os
import sys
from dotenv import load_dotenv
import asyncpg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

async def main():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"), statement_cache_size=0)
    
    print("=================== SAMPLE NUTRITION FOODS ===================")
    rows = await conn.fetch("""
        SELECT food_id, food_name, food_name_en, food_name_am, category, category_am, familiar_measure
        FROM nutrition_foods 
        ORDER BY food_id ASC 
        LIMIT 30
    """)
    for r in rows:
        en = r['food_name_en'] or r['food_name']
        am = r['food_name_am'] or '<MISSING>'
        cat_am = r['category_am'] or '<MISSING>'
        meas = r['familiar_measure'] or ''
        print(f"{r['food_id']:5} | EN: {en:35} | AM: {am:30} | CAT_AM: {cat_am:25} | MEAS: {meas}")

    print("\n=================== CHECKING FOODS WITH MISSING AMHARIC ===================")
    missing_foods = await conn.fetch("""
        SELECT food_id, food_name, food_name_en, food_name_am, category_am
        FROM nutrition_foods
        WHERE food_name_am IS NULL OR food_name_am = '' OR category_am IS NULL OR category_am = ''
    """)
    print(f"Total foods with missing food_name_am or category_am: {len(missing_foods)}")
    for r in missing_foods:
        print(f"  {r['food_id']}: EN={r['food_name_en'] or r['food_name']} | AM={r['food_name_am']} | CAT_AM={r['category_am']}")

    print("\n=================== SAMPLE RECIPES IN DATABASE ===================")
    recipes = await conn.fetch("""
        SELECT recipe_id, recipe_name, recipe_name_en, recipe_name_am, method_am, ingredients_summary_am
        FROM nutrition_recipes
        ORDER BY recipe_id ASC
        LIMIT 10
    """)
    for r in recipes:
        print(f"{r['recipe_id']:5} | EN: {r['recipe_name']:35} | AM: {r['recipe_name_am']} | METHOD_AM: {bool(r['method_am'])}")

    print("\n=================== SAMPLE TEMPLATES IN DATABASE ===================")
    templates = await conn.fetch("""
        SELECT template_id, meal_name, meal_name_am, meal_slot
        FROM nutrition_templates
        ORDER BY template_id ASC
        LIMIT 10
    """)
    for t in templates:
        print(f"{t['template_id']:8} | EN: {t['meal_name']:35} | AM: {t['meal_name_am']} | SLOT: {t['meal_slot']}")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
