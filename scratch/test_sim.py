import asyncio, os, json, sys
from dotenv import load_dotenv
load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")
from database.db import Database
from meal_plan.generation.dataset import load_dataset
from meal_plan.generation.solver import food_macros
from meal_plan.generation.models import MacroTotals, MealItem
from meal_plan.generation.engine import generate_plan
from datetime import date

async def run():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    row = await db._pool.fetchrow("SELECT i.answers, i.nutrition_profile FROM meal_orders o JOIN meal_intakes i ON o.intake_id = i.id WHERE o.id = 26")
    answers = row["answers"] if isinstance(row["answers"], dict) else json.loads(row["answers"])
    stored_p = row["nutrition_profile"] if isinstance(row["nutrition_profile"], dict) else json.loads(row["nutrition_profile"])
    dataset = load_dataset()
    plan = generate_plan(
        answers=answers,
        nutrition_profile=stored_p,
        meals_per_day=3,
        start_date=date(2026, 10, 26),
        duration_days=7,
        region="ETHIOPIA",
        country_name="Ethiopia",
        dataset=dataset,
    )
    core_days = plan["core_week"]
    for d_idx in (2, 4):
        d = core_days[d_idx]
        print(f"=== BEFORE Day {d_idx+1} ({d['day_name']}) ===")
        print(f"Total: {d['totals']['kcal']:.0f} kcal, P: {d['totals']['protein']:.1f}g, C: {d['totals']['carbs']:.1f}g, F: {d['totals']['fat']:.1f}g")
        for m in d["meals"]:
            print(f"  {m['slot']}: {m['macros']['kcal']:.0f} kcal, P: {m['macros']['protein']:.1f}g")
            for it in m["items"]:
                print(f"    - {it.get('food_name') or it.get('name')}: {it.get('portion_g') or it.get('grams')}g")

    await db.disconnect()

asyncio.run(run())
