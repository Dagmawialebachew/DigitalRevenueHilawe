import asyncio
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

from database.db import Database
from meal_plan.generation.db_dataset import load_dataset_from_db
from meal_plan.generation.selection import TemplateSelector

async def check_day3_lunch_scores():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    row = await db.fetchrow("SELECT answers FROM meal_intakes WHERE id = (SELECT intake_id FROM meal_orders WHERE id = 19)")
    answers = row["answers"]
    if isinstance(answers, str):
        answers = json.loads(answers)
    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)

    selector = TemplateSelector(dataset, answers, region="ETHIOPIA", country_name="Ethiopia")
    # Simulate Day 1 & Day 2 choices
    selector.choose(fasting=False, source_slot="Breakfast", day_index=0)
    selector.choose(fasting=False, source_slot="Lunch", day_index=0)
    selector.choose(fasting=False, source_slot="Dinner", day_index=0)
    selector.choose(fasting=False, source_slot="Breakfast", day_index=1)
    selector.choose(fasting=False, source_slot="Lunch", day_index=1)
    selector.choose(fasting=False, source_slot="Dinner", day_index=1)

    # Now for Day 3 (day_index=2) Lunch:
    cands = selector.candidates(fasting=False, source_slot="Lunch")
    print(f"Candidates for Day 3 Lunch ({len(cands)}):")
    for c in cands:
        tid = c.get("Template ID")
        print(f"  {tid}: {c.get('Meal Name')}")

    chosen = selector.choose(fasting=False, source_slot="Lunch", day_index=2)
    print(f"\nChosen for Day 3 Lunch: {chosen.get('Template ID')}: {chosen.get('Meal Name')}")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check_day3_lunch_scores())
