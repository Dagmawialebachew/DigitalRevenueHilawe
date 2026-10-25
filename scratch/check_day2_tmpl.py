import asyncio
import os
import sys
import json
from datetime import date
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

from database.db import Database
from meal_plan.generation.engine import generate_plan
from meal_plan.generation.db_dataset import load_dataset_from_db
from meal_plan.nutrition_targets import calculate_nutrition_profile

async def check_all_days():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    row = await db.fetchrow("SELECT answers FROM meal_intakes WHERE id = (SELECT intake_id FROM meal_orders WHERE id = 19)")
    answers = row["answers"]
    if isinstance(answers, str):
        answers = json.loads(answers)
    profile = calculate_nutrition_profile(answers)
    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)

    plan = generate_plan(
        answers=answers,
        nutrition_profile=profile.to_dict(),
        meals_per_day=3,
        start_date=date(2026, 10, 26),
        duration_days=14,
        region="ETHIOPIA",
        country_name="Ethiopia",
        dataset=dataset,
    )
    for idx, day in enumerate(plan["core_week"]):
        totals = day["totals"]
        meals = day["meals"]
        print(f"Day {idx+1}: {len(meals)} meals | Totals: {totals['kcal']:.0f} kcal, P: {totals['protein']:.0f}g, C: {totals['carbs']:.0f}g, F: {totals['fat']:.0f}g")
        for m_idx, m in enumerate(meals):
            slot = m.get("slot") or f"Meal {m_idx+1}"
            title = m.get("meal_title_am") or m.get("name")
            mtot = m.get("totals", {})
            print(f"   [{slot}] {title}: {mtot.get('kcal', 0):.0f} kcal, P: {mtot.get('protein', 0):.0f}g, C: {mtot.get('carbs', 0):.0f}g, F: {mtot.get('fat', 0):.0f}g")
            for it in m.get("items", []):
                print(f"       • {it.get('food_name_am')} ({it.get('food_id') or it.get('recipe_id')}): {it.get('grams')}g")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check_all_days())
