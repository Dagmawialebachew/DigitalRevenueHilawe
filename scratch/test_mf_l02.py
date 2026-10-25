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
from meal_plan.generation.selection import budget_allowed, availability_allowed
from meal_plan.generation.safety import template_is_safe

async def test_mf_l02():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    row = await db.fetchrow("SELECT answers FROM meal_intakes WHERE id = (SELECT intake_id FROM meal_orders WHERE id = 19)")
    answers = row["answers"]
    if isinstance(answers, str):
        answers = json.loads(answers)
    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)

    tmpl = next(x for x in dataset.active_templates if x.get("Template ID") == "MF-L02")
    print("Testing MF-L02:")
    print("  Meal Slot:", tmpl.get("Meal Slot"))
    print("  Budget:", tmpl.get("Budget"), "-> budget_allowed:", budget_allowed(tmpl.get("Budget"), answers))
    print("  Availability:", tmpl.get("Availability"), "-> availability_allowed:", availability_allowed(tmpl.get("Availability"), "ETHIOPIA", "Ethiopia"))
    safe, reasons = template_is_safe(tmpl, dataset, answers, fasting=False)
    print("  template_is_safe:", safe, "Reasons:", reasons)

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(test_mf_l02())
