import asyncio
import os
import json
import sys
import re
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

async def test_rendering():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    
    query = """
        SELECT o.id as order_id, o.public_id, o.user_id, o.duration_days, o.meals_per_day, o.start_date,
               i.answers, i.language, u.full_name
        FROM meal_orders o
        JOIN meal_intakes i ON o.intake_id = i.id
        LEFT JOIN users u ON o.user_id = u.telegram_id
        WHERE o.id = 19
    """
    row = await db.fetchrow(query)
    answers = row["answers"]
    if isinstance(answers, str):
        answers = json.loads(answers)

    duration = row["duration_days"] or 14
    meals_per_day = row["meals_per_day"] or 3
    start_date = row["start_date"] or date(2026, 10, 26)
    user_name = row["full_name"] or "Shekur.afiff"

    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)

    profile = calculate_nutrition_profile(answers)
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

    pdict = profile.to_dict()
    plan_public_id = f"MP-{row['order_id']:06d}"
    doc_context = DocumentContext(
        client_name=user_name,
        plan_public_id=plan_public_id,
        version_number=3,
        language=str(row.get("language") or "AM"),
        client_profile={
            "current_weight_kg": answers.get("current_weight_kg"),
            "target_weight_kg": answers.get("target_weight_kg"),
            "goal": answers.get("primary_goal"),
        },
        hydration_target_l=pdict.get("hydration_target_l", 2.5),
    )

    artifacts = render_plan_artifacts(plan, doc_context)
    html_path = artifacts.pdf.path.with_suffix(".html")
    html_content = html_path.read_text(encoding="utf-8")

    print("\n=== HTML CHECKS ===")
    # 1. Check footer notice
    footers = re.findall(r'<div class="notice">(.*?)</div>', html_content)
    print(f"Total footer notices: {len(footers)}")
    if footers:
        print("Sample footer notice:", footers[0])
        clean_match = "ይህ ፕላን የተዘጋጀው ለ <strong>Shekur.afiff</strong> ብቻ ነው።" in footers[0]
        print(f"Footer space and name formatting: {'PASS' if clean_match else 'FAIL'}")

    # 2. Check double em-dashes
    double_dashes = re.findall(r'——|—\s*—|--+', html_content)
    print(f"Double em-dashes found: {len(double_dashes)} ({'PASS' if not double_dashes else 'FAIL'})")

    # 3. Check water tracker glyph
    has_droplet = '<svg' in html_content and 'viewBox="0 0 24 24"' in html_content and 'የቀኑ የውሃ መከታተያ' in html_content
    print(f"Water tracker SVG droplet: {'PASS' if has_droplet else 'FAIL'}")

    # 4. Check cottage cheese in html
    has_cottage = "ኮቴጅ" in html_content or "cottage" in html_content.lower()
    print(f"Cottage cheese in HTML: {'FAIL' if has_cottage else 'PASS (0 instances)'}")

    print(f"\nPDF generated at: {artifacts.pdf.path} ({artifacts.pdf.byte_size/1024:.1f} KB)")
    print(f"DOCX generated at: {artifacts.docx.path} ({artifacts.docx.byte_size/1024:.1f} KB)")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(test_rendering())
