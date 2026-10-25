import sys, json, os, asyncio, asyncpg
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

from meal_plan.generation.engine import generate_plan
from meal_plan.generation.dataset import HilaweDataset, DATASET_PATH

async def main():
    with open(DATASET_PATH, encoding='utf-8') as f:
        raw = json.load(f)
    ds = HilaweDataset(
        meta=raw.get('meta', {}),
        foods=tuple(raw.get('foods', ())),
        recipes=tuple(raw.get('recipes', ())),
        recipe_ingredients=tuple(raw.get('recipe_ingredients', ())),
        templates=tuple(raw.get('templates', ())),
        template_components=tuple(raw.get('template_components', ())),
        exchange_groups=tuple(raw.get('exchange_groups', ())),
        fasting_calendar=tuple(raw.get('fasting_calendar', ())),
        settings_rows=tuple(raw.get('settings', ())),
    )

    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    row = await conn.fetchrow('select answers from meal_intakes where user_id=481348144')
    await conn.close()
    answers = json.loads(row['answers'])

    from meal_plan.nutrition_targets import calculate_nutrition_profile
    from datetime import date
    np = calculate_nutrition_profile(answers).to_dict()
    plan = generate_plan(
        answers=answers,
        nutrition_profile=np,
        meals_per_day=3,
        start_date=date.today(),
        duration_days=14,
        region="ETHIOPIA",
        country_name="Ethiopia",
        dataset=ds,
    )
    days = plan["core_week"]
    print(f"Plan days: {len(days)}")
    for day in days[:7]:
        macros = day["totals"]
        print(f"\n=== Day {day['day_index'] + 1} (kcal={macros['kcal']:.0f}, P={macros['protein']:.0f}g, C={macros['carbs']:.0f}g, F={macros['fat']:.0f}g) ===")
        for m in day["meals"]:
            print(f"  [{m['slot']}] {m['meal_name']} (tmpl: {m['template_id']})")
            for it in m["items"]:
                print(f"     * {it['food_name']} ({it['grams']:.0f}g, {it.get('familiar')}) [fid={it.get('food_id')}, rid={it.get('recipe_id')}]")
            for ex in m.get("exchange_options", []):
                opts = [f"{o.get('food_name_am') or o.get('food_name')} ({o.get('exchange_weight_g')}g)" for o in ex.get('options', [])]
                print(f"     SWAP: for {ex.get('for_food_name')} -> {opts}")
    return

if __name__ == "__main__":
    asyncio.run(main())
