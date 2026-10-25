import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")
from database.db import Database

async def main():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    rows = await db.fetch("SELECT template_id, template_name, meal_name_am FROM nutrition_templates WHERE meal_name_am LIKE '%ፋል%' OR template_name ILIKE '%ful%'")
    print("Templates found:", [dict(r) for r in rows])
    
    r_rows = await db.fetch("SELECT recipe_id, recipe_name, recipe_name_am FROM nutrition_recipes WHERE recipe_name_am LIKE '%ፋል%' OR recipe_name ILIKE '%ful%'")
    print("Recipes found:", [dict(r) for r in r_rows])

    # Also search all columns in nutrition_templates, nutrition_recipes, nutrition_foods
    any_t = await db.fetch("SELECT template_id, template_name, meal_name_am FROM nutrition_templates WHERE meal_name_am LIKE '%ፋል%' OR template_name LIKE '%ፋል%'")
    print("Templates with ፋል:", [dict(r) for r in any_t])

    any_r = await db.fetch("SELECT recipe_id, recipe_name, recipe_name_am FROM nutrition_recipes WHERE recipe_name_am LIKE '%ፋል%' OR recipe_name LIKE '%ፋል%'")
    print("Recipes with ፋል:", [dict(r) for r in any_r])

    any_f = await db.fetch("SELECT food_id, food_name, food_name_am FROM nutrition_foods WHERE food_name_am LIKE '%ፋል%' OR food_name LIKE '%ፋል%'")
    print("Foods with ፋል:", [dict(r) for r in any_f])

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
