import asyncio
import os
import json
import sys
import shutil
import time
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

from aiogram import Bot
from aiogram.types import FSInputFile
from database.db import Database
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan
from meal_plan.generation.db_dataset import load_dataset_from_db
from meal_plan.documents.models import DocumentContext
from meal_plan.documents.service import render_plan_artifacts
from meal_plan.review_repository import MealPlanReviewRepository
from meal_plan.review_card import review_card_text, review_keyboard
from meal_plan.runtime import review_group_id

async def main():
    print("=== TRIGGERING YOHANNES (MP-000016) MEAL PLAN TO COACH REVIEW GROUP ===")
    bot = Bot(token=os.getenv("BOT_TOKEN"))
    target_group = review_group_id()
    print(f"Target Review Group: {target_group}")
    
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    repo = MealPlanReviewRepository(db._pool)

    # 1. Fetch Order 16 details
    query = """
        SELECT o.id as order_id, o.public_id, o.user_id, o.duration_days, o.meals_per_day, o.start_date,
               i.answers, i.language, u.full_name, u.username
        FROM meal_orders o
        JOIN meal_intakes i ON o.intake_id = i.id
        LEFT JOIN users u ON o.user_id = u.telegram_id
        WHERE o.id = 16
    """
    row = await db.fetchrow(query)
    if not row:
        raise ValueError("Order 16 not found!")

    user_name = row["full_name"] or "Yohannes"
    answers = row["answers"]
    if isinstance(answers, str):
        answers = json.loads(answers)

    duration = row["duration_days"] or 7
    start_date = row["start_date"] or date(2026, 10, 26)
    order_id = row["order_id"]
    plan_public_id = f"MP-{order_id:06d}"

    print(f"Order: #{order_id} ({row['public_id']}) · Public ID: {plan_public_id}")
    print(f"Client: {user_name} (TG ID: {row['user_id']})")

    # 2. Generate Plan with hardened engine
    print("\n--- 1. Generating Hardened Plan ---")
    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)

    profile = calculate_nutrition_profile(answers)
    pdict = profile.to_dict()
    print(f"Nutrition Profile: {pdict['target_kcal']} kcal, P: {pdict['protein_g']}g, C: {pdict['carbs_g']}g, F: {pdict['fat_g']}g, Water: {pdict['hydration_target_l']}L")

    plan = generate_plan(
        answers=answers,
        nutrition_profile=pdict,
        meals_per_day=4,
        start_date=start_date,
        duration_days=duration,
        region="EUROPE",
        country_name="Germany",
        dataset=dataset,
    )

    # 3. Render Official Artifacts (DOCX & PDF)
    print("\n--- 2. Rendering Official V1 Artifacts ---")
    doc_context = DocumentContext(
        client_name=user_name,
        plan_public_id=plan_public_id,
        version_number=1,
        language="EN",
        client_profile={
            "current_weight_kg": answers.get("current_weight_kg"),
            "target_weight_kg": answers.get("target_weight_kg"),
            "goal": "MUSCLE_GAIN",
        },
        hydration_target_l=profile.water_target_l,
        status="APPROVED",
    )

    t0 = time.time()
    artifacts = render_plan_artifacts(plan, doc_context, is_client_delivery=True)
    print(f"Rendered DOCX: {artifacts.docx.path} ({artifacts.docx.byte_size/1024:.1f} KB)")
    print(f"Rendered PDF:  {artifacts.pdf.path} ({artifacts.pdf.byte_size/1024:.1f} KB)")
    print(f"Rendering took {time.time()-t0:.2f}s")

    # Friendly copies
    out_dir = artifacts.pdf.path.parent
    named_docx_path = out_dir / "Yohannes-7days-plan.docx"
    named_pdf_path = out_dir / "Yohannes-7days-plan.pdf"
    shutil.copyfile(artifacts.docx.path, named_docx_path)
    shutil.copyfile(artifacts.pdf.path, named_pdf_path)

    # Copy to workspace root if not locked by viewer
    try:
        shutil.copyfile(artifacts.docx.path, Path("Yohannes-7days-plan.docx"))
    except Exception:
        pass
    try:
        shutil.copyfile(artifacts.pdf.path, Path("Yohannes-7days-plan.pdf"))
    except Exception:
        pass

    # 4. Database Registration for Version 21
    print("\n--- 3. Updating Version 21 in Database ---")
    async with db._pool.acquire() as conn:
        v_row = await conn.fetchrow(
            """
            UPDATE meal_plan_versions
            SET plan_json = $2::jsonb,
                status = 'DRAFT',
                engine_version = $3,
                dataset_version = $4,
                settings_version = $5,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            21,
            json.dumps(plan, ensure_ascii=False, separators=(",", ":")),
            str(plan.get("engine_version") or "HILAWE_PY_ENGINE_V1.0_PHASE6"),
            str(plan.get("dataset_version") or "HILAWE_MEAL_OS_V1.3_2026-08-17"),
            str(plan.get("settings_version") or "HILAWE_ENGINE_CONFIG_V1"),
        )
        version_id = v_row["id"]
        print(f"Updated meal_plan_versions ID: {version_id} (V{v_row['version_number']})")

        # Clear old artifacts for version 21 if any and store fresh
        await conn.execute("DELETE FROM meal_plan_artifacts WHERE plan_version_id = $1", version_id)
        for art, custom_name, custom_path in [
            (artifacts.docx, "Yohannes-7days-plan.docx", named_docx_path),
            (artifacts.pdf, "Yohannes-7days-plan.pdf", named_pdf_path),
        ]:
            await repo.store_artifact(
                version_id,
                artifact_type=art.artifact_type,
                storage_key=str(custom_path.resolve()),
                original_filename=custom_name,
                content_sha256=art.sha256,
                byte_size=art.byte_size,
            )
            print(f"Stored artifact {art.artifact_type} ({custom_name})")

    # 5. Deliver Review Packet to Telegram Group (-5592866261)
    print(f"\n--- 4. Posting Review Card & Files to Telegram Group ({target_group}) ---")
    card = await bot.send_message(target_group, "⏳ Preparing official Coach review packet (V1) for Yohannes…")

    docx_file = FSInputFile(named_docx_path, filename="Yohannes-7days-plan.docx")
    pdf_file = FSInputFile(named_pdf_path, filename="Yohannes-7days-plan.pdf")

    sent_docx = await bot.send_document(
        target_group,
        docx_file,
        caption="📄 DOCX · V1 · Yohannes-7days-plan (Editable Plan)",
        reply_to_message_id=card.message_id,
    )
    if sent_docx.document and sent_docx.document.file_id:
        await repo.set_artifact_telegram_file_id(version_id, "DOCX", sent_docx.document.file_id)
        print("Sent Yohannes-7days-plan.docx to Telegram group.")

    sent_pdf = await bot.send_document(
        target_group,
        pdf_file,
        caption="📕 PDF · V1 · Yohannes-7days-plan (Flawless Hardened Plan · English)",
        reply_to_message_id=card.message_id,
    )
    if sent_pdf.document and sent_pdf.document.file_id:
        await repo.set_artifact_telegram_file_id(version_id, "PDF", sent_pdf.document.file_id)
        print("Sent Yohannes-7days-plan.pdf to Telegram group.")

    # Build review card context & update card text with buttons
    review_context, _ = await repo.get_review_context(version_id)
    card_text = review_card_text(review_context)

    await bot.edit_message_text(
        card_text,
        chat_id=target_group,
        message_id=card.message_id,
        parse_mode="HTML",
        reply_markup=review_keyboard(version_id),
    )
    print(f"Successfully posted Review Card (Message ID: {card.message_id}) in group {target_group}!")

    # 6. Mark review handoff in DB & update order
    await repo.mark_review_handoff(version_id, chat_id=target_group, message_id=card.message_id)
    async with db._pool.acquire() as conn:
        await conn.execute("UPDATE meal_orders SET state = 'REVIEW_PENDING', current_plan_version_id = $1, updated_at = NOW() WHERE id = 16", version_id)
        await conn.execute("UPDATE meal_generation_jobs SET status = 'SUCCEEDED', stage = 'COMPLETE', plan_version_id = $1, finished_at = NOW(), updated_at = NOW() WHERE order_id = 16", version_id)
    print("Database updated: meal_orders & meal_generation_jobs marked complete with V1.")

    print("\n=== YOHANNES PIPELINE COMPLETED SUCCESSFULLY! ===")
    await bot.session.close()
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
