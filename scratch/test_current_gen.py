import json
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

async def test_gen():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    row = await db.fetchrow("SELECT answers FROM meal_orders o JOIN meal_intakes i ON o.intake_id = i.id WHERE o.id = 19")
    answers = row["answers"]
    if isinstance(answers, str):
        answers = json.loads(answers)
    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)
    await db.disconnect()

    profile = calculate_nutrition_profile(answers)
    pdict = profile.to_dict()
    print("TARGETS:", pdict)

    plan = generate_plan(
        answers=answers,
        nutrition_profile=pdict,
        meals_per_day=3,
        start_date=date(2026, 10, 26),
        duration_days=14,
        region="ETHIOPIA",
        country_name="Ethiopia",
        dataset=dataset,
    )

    days = plan["core_week"]
    print(f"Total days in core_week: {len(days)}")
    for d in days[:7]:
        m_list = d["meals"]
        print(f"\n--- Day {d['day_index'] + 1} ({d['day_name']}) | Total kcal: {d['totals']['kcal']:.1f}, P: {d['totals']['protein']:.1f}g, C: {d['totals']['carbs']:.1f}g, F: {d['totals']['fat']:.1f}g ---")
        for m in m_list:
            items_str = ", ".join(f"{it['food_name']} ({it['grams']:.0f}g)" for it in m["items"])
            swaps_str = "; ".join(f"{ex.get('for_food_name')} -> {[o.get('amharic_title') for o in ex.get('options', [])]}" for ex in m.get("exchange_options", []))
            print(f"  [{m['slot']}] {m['meal_name']}: {items_str}")
            if swaps_str:
                print(f"      Swaps: {swaps_str}")

import os
asyncio.run(test_gen())
