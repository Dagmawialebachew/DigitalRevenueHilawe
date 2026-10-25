import sys, json, os, asyncio
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()
from database.db import Database
from meal_plan.generation.dataset import load_dataset
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan
from datetime import date

async def run():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    row = await db.fetchrow("SELECT i.answers FROM meal_orders o JOIN meal_intakes i ON o.intake_id = i.id WHERE o.id = 47")
    answers = row['answers']
    if isinstance(answers, str):
        answers = json.loads(answers)
    dataset = load_dataset()
    prof = calculate_nutrition_profile(answers)
    plan = generate_plan(
        answers=answers,
        nutrition_profile=prof.to_dict(),
        meals_per_day=4,
        start_date=date(2026, 10, 26),
        duration_days=7,
        region="ETHIOPIA",
        country_name="Ethiopia",
        dataset=dataset,
    )
    print('=== ORDER 47 CORE 7 DAYS MEALS ===')
    for d in plan["core_week"]:
        day_idx = d.get('day_index')
        day_name = d.get('day_name')
        fasting = d.get('is_fasting_day')
        print(f"Day {day_idx} ({day_name}) Fasting={fasting}:")
        for m in d.get('meals', []):
            print(f"  {m.get('slot')}: {m.get('meal_name')} ({m.get('template_id')})")
    await db.disconnect()

asyncio.run(run())
sys.exit(0)
prof = calculate_nutrition_profile(intake_47)
plan = generate_plan(intake_47, prof.to_dict(), 4, date(2026, 10, 26), 7, 'ETHIOPIA', 'Ethiopia', dataset=dataset)

print('=== ORDER 47 CORE 7 DAYS MEALS ===')
for d in plan['days']:
    print(f"Day {d['day_index']} ({d['day_name']}) Fasting={d['is_fasting_day']}:")
    for m in d['meals']:
        print(f"  {m['slot']}: {m['recipe_name']}")
