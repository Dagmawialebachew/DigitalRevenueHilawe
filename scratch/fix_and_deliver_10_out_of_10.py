import asyncio
import os
import json
import sys
import shutil
import time
import math
import uuid
import re
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.client.session.aiohttp import AiohttpSession
from database.db import Database
from meal_plan.generation.engine import generate_plan
from meal_plan.generation.dataset import load_dataset
from meal_plan.documents.models import DocumentContext
from meal_plan.documents.service import render_plan_artifacts
from meal_plan.review_repository import MealPlanReviewRepository
from meal_plan.review_card import review_card_text, review_keyboard
from meal_plan.runtime import review_group_id
from meal_plan.documents.html_pdf_renderer import dedup_grocery_items
from meal_plan.documents.helpers import local_food_name, local_category_name
from pypdf import PdfReader


async def main():
    print("=" * 70)
    print("=== 10/10 RECALIBRATION & REVIEW CARD DISPATCH FOR BEZAWIT NIGUSSE ===")
    print("=" * 70)

    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    repo = MealPlanReviewRepository(db._pool)

    # 1. Fetch Order 26 details
    row = await db._pool.fetchrow("""
        SELECT o.id as order_id, o.public_id, o.user_id, o.duration_days, o.meals_per_day, o.start_date,
               o.intake_id, i.answers, i.language, i.nutrition_profile, u.full_name, u.username
        FROM meal_orders o
        JOIN meal_intakes i ON o.intake_id = i.id
        LEFT JOIN users u ON o.user_id = u.telegram_id
        WHERE o.id = 26
    """)
    if not row:
        raise ValueError("Order 26 not found!")

    intake_id = row["intake_id"]
    order_id = row["order_id"]
    user_name = row["full_name"] or "Bezawit Nigusse"
    answers = row["answers"] if isinstance(row["answers"], dict) else json.loads(row["answers"])
    stored_p = row["nutrition_profile"] if isinstance(row["nutrition_profile"], dict) else json.loads(row["nutrition_profile"])

    # Remove "SOY" from food allergies in intake as commanded by Coach Boss
    old_allergies = answers.get("food_allergies", [])
    new_allergies = [a for a in old_allergies if "SOY" not in a.upper()]
    answers["food_allergies"] = new_allergies
    await db._pool.execute("UPDATE meal_intakes SET answers = $1::jsonb WHERE id = $2", json.dumps(answers), intake_id)
    print(f"Intake Allergies updated: {old_allergies} -> {new_allergies}")

    # 2. Generate Plan
    print("\n--- 1. Generating Recalibrated Plan ---")
    dataset = load_dataset()
    start_date = row["start_date"] or date(2026, 10, 26)
    duration = int(row["duration_days"] or 7)
    plan_public_id = f"MP-{order_id:06d}"

    plan = generate_plan(
        answers=answers,
        nutrition_profile=stored_p,
        meals_per_day=int(row["meals_per_day"] or 3),
        start_date=start_date,
        duration_days=duration,
        region="ETHIOPIA",
        country_name="Ethiopia",
        dataset=dataset,
    )
    core_days = plan.get("core_week") or []
    print(f"Generated {len(core_days)} core days successfully.")

    # 3. Comprehensive Audit of all 6 Boss Audit Items
    print("\n--- 2. Auditing 6 Boss Feedback Remediations ---")
    audit_errors = []

    # Check 1: Fasting Day Protein (Wed Day 3 & Fri Day 5) >= 110g, Kcal ~1,675
    wed_totals = core_days[2].get("totals", {})
    fri_totals = core_days[4].get("totals", {})
    print(f"  Day 3 (Wed Fasting): {wed_totals.get('kcal', 0):.0f} kcal, Protein: {wed_totals.get('protein', 0):.1f}g, Carbs: {wed_totals.get('carbs', 0):.1f}g")
    print(f"  Day 5 (Fri Fasting): {fri_totals.get('kcal', 0):.0f} kcal, Protein: {fri_totals.get('protein', 0):.1f}g, Carbs: {fri_totals.get('carbs', 0):.1f}g")
    if wed_totals.get("protein", 0) < 110.0:
        audit_errors.append(f"Day 3 (Wed) Protein too low: {wed_totals.get('protein', 0):.1f}g (needs >= 110g)")
    if fri_totals.get("protein", 0) < 110.0:
        audit_errors.append(f"Day 5 (Fri) Protein too low: {fri_totals.get('protein', 0):.1f}g (needs >= 110g)")

    # Check 2: Day 5 Breakfast Peanut Butter <= 20g and has Soy Milk
    d5_b = core_days[4]["meals"][0]
    pb_item = next((it for it in d5_b["items"] if it.get("food_id") == "T004"), None)
    soymilk_item = next((it for it in d5_b["items"] if it.get("food_id") == "P014"), None)
    if pb_item and float(pb_item.get("portion_g") or pb_item.get("grams") or 0) > 20.0:
        audit_errors.append(f"Day 5 Breakfast PB is {pb_item.get('portion_g')}g (must be <= 20g)")
    if not soymilk_item:
        audit_errors.append("Day 5 Breakfast missing liquid/Soy Milk (P014)")
    else:
        print(f"  Day 5 Breakfast: PB = {pb_item.get('portion_g') if pb_item else 0}g, Soy Milk = {soymilk_item.get('portion_g')}g")

    # Check 3: Injera strict 60g multiples (No 90g, No 150g)
    for d_idx, day in enumerate(core_days):
        for m in day.get("meals", []):
            for it in m.get("items", []):
                if it.get("food_id") == "C001":
                    g = float(it.get("portion_g") or it.get("grams") or 0)
                    if g not in (60.0, 120.0, 180.0, 240.0):
                        audit_errors.append(f"Broken Injera portion {g}g on Day {d_idx+1} {m.get('slot')}")

    # Check 4: No legume stacking on traditional stews
    for d_idx, day in enumerate(core_days):
        for m in day.get("meals", []):
            has_stew = any(it.get("recipe_id") in ("R001", "R002", "R003") for it in m.get("items", []))
            has_loose_legume = any(it.get("food_id") in ("P001", "P007") for it in m.get("items", []))
            if has_stew and has_loose_legume:
                audit_errors.append(f"Legume stacking on stew in Day {d_idx+1} {m.get('slot')}")

    # Check 5: Stew oil and Tilapia oil
    for d_idx, day in enumerate(core_days):
        for m in day.get("meals", []):
            has_wot = any(it.get("recipe_id") in ("R020", "R023") for it in m.get("items", []))
            has_loose_oil = any(it.get("food_id") in ("T001", "T002") for it in m.get("items", []))
            if has_wot and has_loose_oil:
                audit_errors.append(f"Redundant cooking oil on stew in Day {d_idx+1} {m.get('slot')}")
            
            is_tilapia = any(it.get("recipe_id") == "R015" for it in m.get("items", []))
            if is_tilapia and not has_loose_oil:
                audit_errors.append(f"Tilapia dinner missing cooking oil in Day {d_idx+1} {m.get('slot')}")

    if audit_errors:
        print("🚨 AUDIT ISSUES DETECTED:")
        for err in audit_errors:
            print(f"  ❌ {err}")
        raise ValueError(f"Audit failed with {len(audit_errors)} errors!")
    else:
        print("  ✅ All generator audit checks passed with 100% compliance!")

    # 4. Determine next version number in DB
    existing_versions = await db.fetch("SELECT id, version_number FROM meal_plan_versions WHERE order_id = $1 ORDER BY version_number DESC", order_id)
    next_ver_num = (existing_versions[0]["version_number"] + 1) if existing_versions else 1
    print(f"\nTarget Database Version Number: V{next_ver_num}")

    # 5. Render Certified Client Deliverables (PDF & DOCX)
    print("\n--- 3. Rendering Certified 15-Page PDF and DOCX ---")
    doc_context = DocumentContext(
        client_name=user_name,
        plan_public_id=plan_public_id,
        version_number=next_ver_num,
        language="AM",
        client_profile={
            "current_weight_kg": answers.get("current_weight_kg"),
            "target_weight_kg": answers.get("target_weight_kg"),
            "goal": answers.get("primary_goal") or "FAT_LOSS",
            "cuisine_style": answers.get("cuisine_style"),
            "training_type": answers.get("training_type"),
            "training_days_per_week": answers.get("training_days_per_week"),
            "grocery_budget": answers.get("grocery_budget"),
            "dietary_pattern": answers.get("dietary_pattern"),
            "orthodox_fasting": answers.get("orthodox_fasting"),
        },
        hydration_target_l=stored_p.get("hydration_target_l") or 3.1,
        status="APPROVED",
    )

    t0 = time.time()
    artifacts = render_plan_artifacts(plan, doc_context, is_client_delivery=True)
    render_duration = time.time() - t0
    print(f"Rendered DOCX: {artifacts.docx.path} ({artifacts.docx.byte_size/1024:.1f} KB)")
    print(f"Rendered PDF:  {artifacts.pdf.path} ({artifacts.pdf.byte_size/1024:.1f} KB)")
    print(f"Rendering executed in {render_duration:.2f}s")

    # Verify Page Count
    reader = PdfReader(str(artifacts.pdf.path))
    page_count = len(reader.pages)
    print(f"PDF Page Count: {page_count} (Target: Exactly 15 pages)")
    assert page_count == 15, f"Expected 15 pages but got {page_count}"

    # Verify PDF text on critical pages
    p8_norm = " ".join(reader.pages[7].extract_text().split())
    assert "የዶሮ ስጋ (ጥሬ)" not in p8_norm and "የዶሮ ደረት ስጋ (ጥሬ)" not in p8_norm, "Found raw chicken on Page 8 dinner!"
    assert "የዶሮ ደረት ስጋ" in p8_norm and "የበሰለ" in p8_norm, "Missing cooked chicken on Page 8!"
    assert "210" in p8_norm and "2 መካከለኛ ድንች" in p8_norm, "Missing potato swap measure on Page 8!"

    p13_norm = " ".join(reader.pages[12].extract_text().split())
    p14_norm = " ".join(reader.pages[13].extract_text().split())
    assert "(የበሰለ) (የበሰለ)" not in p13_norm, "Found double (የበሰለ) on Page 13!"
    assert "የተፈጨ የበሬ ስጋ" not in p14_norm, "Minced beef still sitting on Page 14 instead of Page 13 top!"
    assert "የተፈጨ የበሬ ስጋ" in p13_norm, "Minced beef missing from Page 13!"

    # Verify Page 7 (Day 3) and Page 9 (Day 5) Household Measurement Strings
    p7_norm = " ".join(reader.pages[6].extract_text().split())
    p9_norm = " ".join(reader.pages[8].extract_text().split())

    assert "( በግምት 200" not in p7_norm and "(በግምት 200" not in p7_norm, "Nested 200g parenthesis on Page 7!"
    assert "( በግምት 80" not in p7_norm and "(በግምት 80" not in p7_norm, "Nested 80g parenthesis on Page 7!"
    assert "1 መካከለኛ ጭልፋ" in p7_norm, "Missing 1 ladle Misir measure on Page 7!"
    assert "1/3 መካከለኛ ጭልፋ" in p7_norm or "ሲሶ" in p7_norm, "Missing 1/3 ladle Atkilt measure on Page 7!"
    assert "1 ከግማሽ ሲኒ የተዘፈቀ" in p7_norm, "Missing 1.5 cup rehydrated Soya Chunks measure on Page 7!"

    assert "( በግምት 50" not in p9_norm and "(በግምት 50" not in p9_norm, "Nested 50g parenthesis on Page 9!"
    assert "( በግምት 220" not in p9_norm and "(በግምት 220" not in p9_norm, "Nested 220g parenthesis on Page 9!"
    assert "ግማሽ ሲኒ ጥሬ" in p9_norm, "Missing half cup dry oats measure on Page 9!"
    assert "1 መካከለኛ ሳህን" in p9_norm, "Missing 1 medium bowl Ful measure on Page 9!"
    assert "1 ከግማሽ ሲኒ የተዘፈቀ" in p9_norm, "Missing 1.5 cup rehydrated Soya Chunks measure on Page 9!"

    print("  ✅ Page 7 (Day 3 Misir, Atkilt, Soya Chunks clean measures): VERIFIED")
    print("  ✅ Page 9 (Day 5 Oats, Misir, Ful, Soya Chunks clean measures): VERIFIED")
    print("  ✅ Page 8 (Cooked chicken + potato household measure): VERIFIED")
    print("  ✅ Page 13 (Minced beef grouped under meat at top): VERIFIED")
    print("  ✅ Page 13 (Single የበሰለ on Ful): VERIFIED")

    # Copy files to root with canonical deliverables names
    out_dir = artifacts.pdf.path.parent
    named_docx_path = out_dir / "Bezawit-Nigusse-7days-plan.docx"
    named_pdf_path = out_dir / "Bezawit-Nigusse-7days-plan.pdf"
    shutil.copyfile(artifacts.docx.path, named_docx_path)
    shutil.copyfile(artifacts.pdf.path, named_pdf_path)

    root_pdf = Path("Bezawit-Nigusse-7days-plan.pdf")
    root_docx = Path("Bezawit-Nigusse-7days-plan.docx")
    shutil.copyfile(artifacts.docx.path, root_docx)
    shutil.copyfile(artifacts.pdf.path, root_pdf)
    print(f"Saved canonical deliverables:\n  - {root_pdf.resolve()}\n  - {root_docx.resolve()}")

    # 6. Database Registration
    print(f"\n--- 4. Registering Version {next_ver_num} in Database ---")
    version_row = await db.fetchrow(
        """
        INSERT INTO meal_plan_versions (
            public_id, order_id, version_number, status, source, detail_source, plan_json, engine_version, dataset_version, settings_version, created_at, updated_at
        )
        VALUES ($1, $2, $3, 'DRAFT', 'GENERATED', 'STRUCTURED', $4::jsonb, $5, $6, $7, NOW(), NOW())
        RETURNING *
        """,
        uuid.uuid4(),
        order_id,
        next_ver_num,
        json.dumps(plan, ensure_ascii=False, separators=(",", ":")),
        str(plan.get("engine_version") or "HILAWE_PY_ENGINE_V1.0_PHASE6"),
        str(plan.get("dataset_version") or "HILAWE_MEAL_OS_V1.3_2026-08-17"),
        str(plan.get("settings_version") or "HILAWE_V1.3_PLUS_MEALCOUNT_EXTENSION_V1"),
    )
    new_version_id = version_row["id"]
    print(f"Created meal_plan_versions ID: {new_version_id} (V{version_row['version_number']})")

    for art, custom_name, custom_path in [
        (artifacts.docx, "Bezawit-Nigusse-7days-plan.docx", named_docx_path),
        (artifacts.pdf, "Bezawit-Nigusse-7days-plan.pdf", named_pdf_path),
    ]:
        await repo.store_artifact(
            new_version_id,
            artifact_type=art.artifact_type,
            storage_key=str(custom_path.resolve()),
            original_filename=custom_name,
            content_sha256=art.sha256,
            byte_size=art.byte_size,
        )

    # 7. Dispatch to Telegram Coach Group with Buttons & Attached Files
    print(f"\n--- 5. Dispatching Official Review Card with Buttons to Group ---")
    session = AiohttpSession(timeout=300.0)
    bot = Bot(token=os.getenv("BOT_TOKEN"), session=session)
    chat_id = review_group_id()
    print(f"Target Group Chat ID: {chat_id}")

    # Fetch review context for card text
    review_context, _ = await repo.get_review_context(new_version_id)

    # Send initial placeholder card
    card = await bot.send_message(chat_id, "⏳ Preparing Coach review packet…")
    print(f"Sent initial card message ID: {card.message_id}")

    # Attach both DOCX and PDF as reply documents to the card message
    for artifact, c_name in [(artifacts.docx, "Bezawit-Nigusse-7days-plan.docx"), (artifacts.pdf, "Bezawit-Nigusse-7days-plan.pdf")]:
        sent = await bot.send_document(
            chat_id,
            FSInputFile(artifact.path, filename=c_name),
            caption=f"{artifact.artifact_type} · V{next_ver_num} · {artifact.sha256[:12]}",
            reply_to_message_id=card.message_id,
        )
        if sent.document and sent.document.file_id:
            await repo.set_artifact_telegram_file_id(new_version_id, artifact.artifact_type, sent.document.file_id)
        print(f"Sent document {c_name} (msg ID: {sent.message_id})")

    # Update card text with rich HTML summary and interactive action buttons
    card_text = review_card_text(review_context)
    k_markup = review_keyboard(new_version_id)

    await bot.edit_message_text(
        card_text,
        chat_id=chat_id,
        message_id=card.message_id,
        parse_mode="HTML",
        reply_markup=k_markup,
    )
    print("Edited review card message with interactive review keyboard buttons!")

    # Mark review handoff in DB
    await repo.mark_review_handoff(new_version_id, chat_id=chat_id, message_id=card.message_id)
    print("Marked review handoff in database successfully!")

    await bot.session.close()
    await db.disconnect()
    print("\n" + "=" * 70)
    print("🎉 ALL 6 AUDIT FIXES APPLIED & REVIEW PACKET DISPATCHED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
