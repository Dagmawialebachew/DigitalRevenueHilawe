import asyncio
import os
import json
import sys
import time
from datetime import date
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, ".")

from database.db import Database
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan
from meal_plan.generation.dataset import load_dataset
from meal_plan.documents.models import DocumentContext
from meal_plan.documents.html_pdf_renderer import render_html_pdf

async def generate_order(order_id: int):
    db_url = os.getenv("DATABASE_URL")
    db = Database(db_url)
    await db.connect()

    query = f"""
        SELECT o.id as order_id, o.public_id, o.user_id, o.duration_days, o.meals_per_day, o.created_at,
               i.answers, i.nutrition_profile, u.full_name, u.username
        FROM meal_orders o
        JOIN meal_intakes i ON o.intake_id = i.id
        LEFT JOIN users u ON o.user_id = u.telegram_id
        WHERE o.id = {order_id}
    """
    row = await db.fetchrow(query)
    if not row:
        print(f"Order #{order_id} not found.")
        await db.disconnect()
        return

    user_name = row["full_name"] or "Mengesha Kebede"
    answers = row["answers"]
    if isinstance(answers, str):
        answers = json.loads(answers)

    duration = row["duration_days"] or answers.get("duration_days") or 30
    meals_per_day = row["meals_per_day"] or answers.get("meals_per_day") or 4
    if not answers.get("full_name"):
        answers["full_name"] = user_name

    print(f"=== Generating Official Meal Plan for Order #{order_id} ({row['public_id']}) ===")
    print(f"Client: {user_name} (@{row.get('username')})")
    print(f"Goal: {answers.get('primary_goal')} | Age: {answers.get('age')} | Sex: {answers.get('calculation_sex')}")
    print(f"Weight: {answers.get('current_weight_kg')} kg -> Target: {answers.get('target_weight_kg')} kg")
    print(f"Duration: {duration} days | Meals/day: {meals_per_day} | Fasting: {answers.get('orthodox_fasting')}")

    profile = calculate_nutrition_profile(answers)
    dataset = load_dataset()

    plan = generate_plan(
        answers=answers,
        nutrition_profile=profile.to_dict(),
        meals_per_day=meals_per_day,
        start_date=date(2026, 10, 26),
        duration_days=duration,
        region="ETHIOPIA",
        country_name="Ethiopia",
        dataset=dataset,
    )

    context = DocumentContext(
        client_name=user_name,
        language="AM",
        plan_public_id=f"HILAWE-ORDER-{order_id}",
        version_number="1.0",
        client_profile=answers,
    )

    out_pdf = f"PENDING_CLIENT_ORDER_{order_id}.pdf"
    t0 = time.time()
    render_html_pdf(plan, context, out_pdf, is_client_delivery=True)
    pdf_size_kb = os.path.getsize(out_pdf) / 1024
    print(f"[SUCCESS] Generated client meal plan PDF -> {out_pdf} ({pdf_size_kb:.1f} KB in {time.time()-t0:.1f}s)")

    await db.disconnect()

async def main():
    # Generate for both order 47 and 49
    for oid in (47, 49):
        await generate_order(oid)

if __name__ == "__main__":
    asyncio.run(main())
