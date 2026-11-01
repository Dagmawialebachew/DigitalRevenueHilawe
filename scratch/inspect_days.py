import asyncio, os, json, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")
from database.db import Database
from meal_plan.generation.engine import generate_plan
from meal_plan.generation.dataset import load_dataset
from datetime import date
from dotenv import load_dotenv
load_dotenv()

async def run():
    db = Database(os.getenv('DATABASE_URL'))
    await db.connect()
    row = await db._pool.fetchrow('SELECT answers, nutrition_profile FROM meal_intakes WHERE id = (SELECT intake_id FROM meal_orders WHERE id = 26)')
    ans = json.loads(row['answers']) if isinstance(row['answers'], str) else row['answers']
    stored_p = json.loads(row['nutrition_profile']) if isinstance(row['nutrition_profile'], str) else row['nutrition_profile']
    dataset = load_dataset()
    plan = generate_plan(answers=ans, nutrition_profile=stored_p, meals_per_day=3, start_date=date(2026, 10, 26), duration_days=7, region='ETHIOPIA', country_name='Ethiopia', dataset=dataset)
    for idx, d in enumerate(plan['core_week']):
        print(f"Day {idx+1} ({d['day_name']}, Fasting={d['fasting']}): Total P = {d['totals']['protein']:.1f}g, Kcal = {d['totals']['kcal']:.0f}")
        for m in d['meals']:
            print(f"  {m['slot']}: {m['template_id']} - {m['meal_name']}")
            for it in m['items']:
                g = it.get('portion_g') if it.get('portion_g') is not None else it.get('grams', 0)
                print(f"     * {it.get('name') or it.get('food_name')} ({it.get('food_id') or it.get('recipe_id')}): {g}g")
    await db.disconnect()

asyncio.run(run())
