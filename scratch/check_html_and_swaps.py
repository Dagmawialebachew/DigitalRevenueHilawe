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
from meal_plan.documents.html_pdf_renderer import render_html_document

async def check_html_and_swaps():
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

    profile = calculate_nutrition_profile(answers)
    pdict = profile.to_dict()

    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)

    plan = generate_plan(
        answers=answers,
        nutrition_profile=pdict,
        meals_per_day=3,
        start_date=row["start_date"] or date(2026, 10, 26),
        duration_days=row["duration_days"] or 14,
        region="ETHIOPIA",
        country_name="Ethiopia",
        dataset=dataset,
    )

    doc_context = DocumentContext(
        client_name=row["full_name"] or "Shekur.afiff",
        plan_public_id=f"MP-{row['order_id']:06d}",
        version_number=4,
        language="AM",
        client_profile={
            "current_weight_kg": answers.get("current_weight_kg"),
            "target_weight_kg": answers.get("target_weight_kg"),
            "goal": answers.get("primary_goal"),
        },
        hydration_target_l=2.5,
    )

    html = render_html_document(plan, doc_context, is_client_delivery=True)
    with open("scratch/plan_v4_test.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Rendered HTML saved to scratch/plan_v4_test.html")

    # Let's inspect all meal-swap divs from the HTML
    import re
    swaps = re.findall(r'<div class="meal-swap">(.*?)</div>', html)
    print(f"\nFound {len(swaps)} meal swap lines in HTML:")
    for idx, s in enumerate(swaps):
        print(f"  [{idx+1}] {s}")

    # Let's inspect Day 1 to 7 meal titles and ingredients from HTML
    cards = re.findall(r'<div class="meal-card">.*?<span class="slot-tag">(.*?)</span>.*?<span class="meal-title">(.*?)</span>(.*?)</div>\s*</div>', html, re.DOTALL)
    print(f"\nFound {len(cards)} meal cards in HTML:")
    for slot, title, body in cards[:12]:
        bullets = re.findall(r'<li>(.*?)</li>', body)
        print(f"\n[{slot}] {title}")
        for b in bullets:
            print(f"   • {b.strip()}")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check_html_and_swaps())
