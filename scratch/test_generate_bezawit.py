import asyncio
import os
import json
import sys
from datetime import date
from dotenv import load_dotenv
import asyncpg

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

from database.db import Database
from meal_plan.generation.engine import generate_plan
from meal_plan.generation.db_dataset import load_dataset_from_db

async def main():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    
    order = await db.fetchrow("""
        SELECT o.*, i.language, i.answers, i.nutrition_profile, u.full_name, u.username
        FROM meal_orders o
        JOIN meal_intakes i ON o.intake_id = i.id
        LEFT JOIN users u ON o.user_id = u.telegram_id
        WHERE o.id = 26
    """)
    answers = order['answers']
    if isinstance(answers, str):
        answers = json.loads(answers)
    stored_p = order['nutrition_profile']
    if isinstance(stored_p, str):
        stored_p = json.loads(stored_p)

    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)

    print("Generating plan for Bezawit Nigusse...")
    plan = generate_plan(
        answers=answers,
        nutrition_profile=stored_p,
        meals_per_day=3,
        start_date=order['start_date'] or date(2026, 10, 26),
        duration_days=7,
        region="ETHIOPIA",
        country_name="Ethiopia",
        dataset=dataset,
    )

    print("Plan keys returned:", list(plan.keys()))
    if "days" in plan:
        print(f"Plan generated successfully! Days: {len(plan['days'])}")
    else:
        print("Plan content:", plan)
        n = day.get("nutrition", {}) or day.get("nutrition_totals", {})
        print(f"Day {day['day_number']} ({day.get('day_name_en')}) - Kcal: {n.get('kcal')}, P: {n.get('protein_g')}g, C: {n.get('carbs_g')}g, F: {n.get('fat_g')}g")
        for meal in day["meals"]:
            m_items = [f"{item['food_name_en']} ({item['display_amount_en'] or item['display_amount_am']})" for item in meal["items"]]
            print(f"  {meal['slot_name']}: {', '.join(m_items)}")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
