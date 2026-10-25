import os
import json
import math
from datetime import date
from dotenv import load_dotenv
load_dotenv('.env')

import sys
sys.path.insert(0, ".")
from database.db import Database
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan
from meal_plan.generation.db_dataset import load_dataset_from_db
import asyncio

# Let's inspect the exact recipes
async def inspect():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    row = await db.fetchrow("SELECT answers FROM meal_orders o JOIN meal_intakes i ON o.intake_id = i.id WHERE o.id = 19")
    answers = row["answers"]
    if isinstance(answers, str): answers = json.loads(answers)
    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)
    await db.disconnect()

    for rid in ["R023", "R018", "R015", "R020", "R021"]:
        r = dataset.recipe_by_id.get(rid)
        ings = dataset.ingredients_by_recipe.get(rid, [])
        print(f"Recipe {rid}: {r.get('Recipe Name')}, Yield: {r.get('Yield g')}")
        for i in ings:
            print(f"   {i.get('Food ID')}: {i.get('Ingredient')} - {i.get('Weight g')}g (kcal: {i.get('Line kcal')}, P: {i.get('Line Protein')}, C: {i.get('Line Carbs')}, F: {i.get('Line Fat')})")

asyncio.run(inspect())
