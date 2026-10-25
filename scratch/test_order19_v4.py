import asyncio
import os
import json
import sys
from datetime import date
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

from database.db import Database
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan
from meal_plan.generation.db_dataset import load_dataset_from_db
from meal_plan.documents.models import DocumentContext
from meal_plan.documents.service import render_plan_artifacts
from meal_plan.documents.helpers import format_swap_text, local_food_name

async def test_order19():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    
    query = """
        SELECT o.id as order_id, o.public_id, o.user_id, o.duration_days, o.meals_per_day, o.start_date,
               i.answers, i.language, u.full_name, u.username
        FROM meal_orders o
        JOIN meal_intakes i ON o.intake_id = i.id
        LEFT JOIN users u ON o.user_id = u.telegram_id
        WHERE o.id = 19
    """
    row = await db.fetchrow(query)
    answers = row["answers"]
    if isinstance(answers, str):
        answers = json.loads(answers)
        
    print(f"Loaded Order 19 for {row['full_name']}")
    print(f"Weight: {answers.get('current_weight_kg')} kg, Goal: {answers.get('primary_goal')}, Budget: {answers.get('grocery_budget')}")

    profile = calculate_nutrition_profile(answers)
    pdict = profile.to_dict()
    print(f"\n--- NUTRITION PROFILE TARGETS ---")
    print(f"Target Calories: {pdict['target_kcal']} kcal")
    print(f"Target Protein:  {pdict.get('protein_g')} g (Rate: {pdict.get('protein_g_per_kg', 0):.2f} g/kg)")
    print(f"Target Carbs:    {pdict.get('carbs_g')} g")
    print(f"Target Fat:      {pdict.get('fat_g')} g")
    print(f"Hydration:       {pdict.get('hydration_target_l')} L")

    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)

    duration = row["duration_days"] or 14
    start_date = row["start_date"] or date(2026, 10, 26)

    plan = generate_plan(
        answers=answers,
        nutrition_profile=pdict,
        meals_per_day=3, # Engine will adjust to 4 for hardgainer
        start_date=start_date,
        duration_days=duration,
        region="ETHIOPIA",
        country_name="Ethiopia",
        dataset=dataset,
    )

    core_week = plan.get("core_week") or []
    print(f"\nGenerated core week with {len(core_week)} days.")

    for d_idx, day in enumerate(core_week):
        totals = day.get("totals", {})
        meals = day.get("meals", [])
        print(f"\n==================== DAY {d_idx + 1} ====================")
        print(f"Daily Totals: {totals.get('kcal', 0):.0f} kcal | P: {totals.get('protein', 0):.0f}g | C: {totals.get('carbs', 0):.0f}g | F: {totals.get('fat', 0):.0f}g")
        print(f"Meal Count: {len(meals)}")
        for m_idx, m in enumerate(meals):
            slot = m.get("slot") or f"Meal {m_idx+1}"
            title = m.get("meal_title_am") or m.get("name")
            mmac = m.get("totals", {})
            print(f"  [{slot}] {title} ({mmac.get('kcal', 0):.0f} kcal, P: {mmac.get('protein', 0):.0f}g, C: {mmac.get('carbs', 0):.0f}g, F: {mmac.get('fat', 0):.0f}g)")
            for it in m.get("items", []):
                fid = it.get("food_id") or it.get("recipe_id")
                name = it.get("food_name_am") or it.get("name")
                grams = it.get("grams", 0)
                print(f"    • {name} ({fid}): {grams:g}g")
            
            exchanges = m.get("exchanges") or []
            if exchanges:
                print(f"    Swaps available ({len(exchanges)}):")
                for ex in exchanges:
                    for_fid = ex.get("for_food_id")
                    opts = ex.get("options") or []
                    for opt in opts[:2]:
                        s_text = format_swap_text(m, {**opt, "for_food_id": for_fid}, is_am=True)
                        print(f"      - (For {for_fid}) {s_text} [Macros: {opt.get('macros')}]")

    print(f"\n==================== GROCERY LIST (WEEK 1) ====================")
    grocery = plan.get("grocery") or []
    for g in grocery:
        fid = g.get("food_id")
        item = g.get("buy_item")
        local_name = local_food_name(fid, item, "AM")
        qty = g.get("purchase_quantity")
        planned = g.get("planned_grams")
        buy_g = g.get("buy_weight_g")
        print(f"  • {local_name} ({item}, {fid}): Planned {planned}g -> Buy: {qty} ({buy_g}g)")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(test_order19())
