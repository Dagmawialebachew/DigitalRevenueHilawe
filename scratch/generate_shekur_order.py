import asyncio
import os
import json
import sys
import time
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

async def generate_shekur():
    db_url = os.getenv("DATABASE_URL")
    db = Database(db_url)
    await db.connect()

    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)

    query = """
        SELECT o.id as order_id, o.public_id, o.user_id, o.duration_days, o.meals_per_day, o.start_date, o.ends_on,
               i.answers, u.full_name, u.username
        FROM meal_orders o
        JOIN meal_intakes i ON o.intake_id = i.id
        LEFT JOIN users u ON o.user_id = u.telegram_id
        WHERE o.id = 19
    """
    row = await db.fetchrow(query)
    if not row:
        print("Order #19 not found.")
        await db.disconnect()
        return

    user_name = row["full_name"] or "Shekur.afiff"
    answers = row["answers"]
    if isinstance(answers, str):
        answers = json.loads(answers)

    duration = row["duration_days"] or 14
    meals_per_day = row["meals_per_day"] or 3

    print(f"=== Generating Official Meal Plan for Shekur (Order #19, UUID: {row['public_id']}) ===")
    print(f"Client: {user_name} (@{row.get('username')})")
    print(f"Goal: {answers.get('primary_goal')} | Sex: {answers.get('calculation_sex')} | Age: {answers.get('age')}")
    print(f"Current weight: {answers.get('current_weight_kg')} kg -> Target: {answers.get('target_weight_kg')} kg")
    print(f"Duration: {duration} days | Meals/day: {meals_per_day}")

    profile = calculate_nutrition_profile(answers)
    pdict = profile.to_dict()
    print(f"Calculated Target Kcal: {profile.target_kcal} | Protein: {pdict.get('target_protein_g') or pdict.get('protein_g')}g | Carbs: {pdict.get('target_carbs_g') or pdict.get('carbs_g')}g | Fat: {pdict.get('target_fat_g') or pdict.get('fat_g')}g")

    start_date = row["start_date"] or date(2026, 10, 26)

    plan = generate_plan(
        answers=answers,
        nutrition_profile=profile.to_dict(),
        meals_per_day=meals_per_day,
        start_date=start_date,
        duration_days=duration,
        region="ETHIOPIA",
        country_name="Ethiopia",
        dataset=dataset,
    )

    # Check for 'ቀይ ወጥ' vs 'የበሬ ቀይ ወጥ' in plan
    plan_str = json.dumps(plan, ensure_ascii=False)
    has_ye_bere = "የበሬ ቀይ ወጥ" in plan_str
    has_qey_wot = "ቀይ ወጥ" in plan_str
    print(f"Verification: Contains 'የበሬ ቀይ ወጥ': {has_ye_bere} (Should be False)")
    print(f"Verification: Contains 'ቀይ ወጥ': {has_qey_wot} (Should be True)")

    print("\n--- GENERATED DAYS ---")
    for d_idx, day in enumerate(plan.get("days", [])):
        meal_names = [m.get("meal_name_am") or m.get("meal_name") for m in day.get("meals", [])]
        print(f"Day {d_idx+1}: {meal_names}")

    plan_public_id = f"MP-{row['order_id']:06d}"
    doc_context = DocumentContext(
        client_name=user_name,
        plan_public_id=plan_public_id,
        version_number=2,
        language="AM",
        client_profile={
            "current_weight_kg": answers.get("current_weight_kg"),
            "target_weight_kg": answers.get("target_weight_kg"),
            "goal": answers.get("primary_goal"),
        },
        hydration_target_l=pdict.get("hydration_target_l", 2.5),
    )

    t0 = time.time()
    artifacts = render_plan_artifacts(plan, doc_context)
    print(f"Successfully rendered DOCX: {artifacts.docx.path} ({artifacts.docx.byte_size/1024:.1f} KB)")
    print(f"Successfully rendered PDF:  {artifacts.pdf.path} ({artifacts.pdf.byte_size/1024:.1f} KB)")
    print(f"Render time: {time.time()-t0:.2f}s")

    await db.disconnect()
    return artifacts, plan

if __name__ == "__main__":
    asyncio.run(generate_shekur())
