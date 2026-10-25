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
    print("=== STARTING SHEKUR.AFIFF V3 GENERATION & DELIVERY PIPELINE ===")
    bot = Bot(token=os.getenv("BOT_TOKEN"))
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    repo = MealPlanReviewRepository(db._pool)

    # 1. Fetch Order 19
    query = """
        SELECT o.id as order_id, o.public_id, o.user_id, o.duration_days, o.meals_per_day, o.start_date,
               i.answers, i.language, u.full_name, u.username
        FROM meal_orders o
        JOIN meal_intakes i ON o.intake_id = i.id
        LEFT JOIN users u ON o.user_id = u.telegram_id
        WHERE o.id = 19
    """
    row = await db.fetchrow(query)
    user_name = row["full_name"] or "Shekur.afiff"
    answers = row["answers"]
    if isinstance(answers, str):
        answers = json.loads(answers)

    duration = row["duration_days"] or 14
    meals_per_day = row["meals_per_day"] or 3
    start_date = row["start_date"] or date(2026, 10, 26)
    target_group = review_group_id()

    print(f"Order: #{row['order_id']} ({row['public_id']})")
    print(f"Client: {user_name} (@{row.get('username')}, TG ID: {row['user_id']})")
    print(f"Target Review Group: {target_group}")

    # 2. Load dataset and generate V3 plan
    print("\n--- 1. Generating Meal Plan V3 ---")
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

    # 3. Render official DOCX & PDF
    print("\n--- 2. Rendering Official V3 Artifacts ---")
    t0 = time.time()
    artifacts = render_plan_artifacts(plan, doc_context)
    print(f"Rendered DOCX: {artifacts.docx.path} ({artifacts.docx.byte_size/1024:.1f} KB)")
    print(f"Rendered PDF:  {artifacts.pdf.path} ({artifacts.pdf.byte_size/1024:.1f} KB)")
    print(f"Rendering took {time.time()-t0:.2f}s")

    # Prepare renamed files: 14-days-meal-plan.docx and 14-days-meal-plan.pdf
    out_dir = artifacts.pdf.path.parent
    named_docx_path = out_dir / "14-days-meal-plan.docx"
    named_pdf_path = out_dir / "14-days-meal-plan.pdf"
    shutil.copyfile(artifacts.docx.path, named_docx_path)
    shutil.copyfile(artifacts.pdf.path, named_pdf_path)
    print(f"Created delivery copies:\n  - {named_docx_path}\n  - {named_pdf_path}")

    # Also copy to root artifacts or expected paths if needed
    root_v3_pdf = Path("MP-000019-Shekur-afiff-V3.pdf")
    shutil.copyfile(artifacts.pdf.path, root_v3_pdf)
    print(f"Exported to workspace root: {root_v3_pdf.resolve()}")

    # 4. Register Version 3 in database
    print("\n--- 3. Registering Version 3 in Database ---")
    import uuid
    version_uuid = uuid.uuid4()
    async with db._pool.acquire() as conn:
        v_row = await conn.fetchrow(
            """
            INSERT INTO meal_plan_versions(
                public_id, order_id, version_number, status, plan_json, engine_version, dataset_version, settings_version, generation_seed
            )
            VALUES($1, 19, 3, 'REVIEW_PENDING', $2, $3, $4, $5, $6)
            ON CONFLICT (order_id, version_number) DO UPDATE
            SET plan_json = EXCLUDED.plan_json, status = 'REVIEW_PENDING', updated_at = NOW()
            RETURNING *
            """,
            version_uuid,
            json.dumps(plan, ensure_ascii=False, separators=(",", ":")),
            str(plan.get("engine_version") or "HILAWE_PY_ENGINE_V1.0_PHASE6"),
            str(plan.get("dataset_version") or "HILAWE_MEAL_OS_V1.3_2026-08-17"),
            str(plan.get("settings_version") or "HILAWE_ENGINE_CONFIG_V1"),
            "deterministic:19:3",
        )
        version_id = v_row["id"]
        print(f"Registered meal_plan_versions ID: {version_id} (V3, UUID: {v_row['public_id']})")

        # Store artifacts
        for art, custom_name, custom_path in [
            (artifacts.docx, "14-days-meal-plan.docx", named_docx_path),
            (artifacts.pdf, "14-days-meal-plan.pdf", named_pdf_path),
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
    card = await bot.send_message(target_group, "⏳ Preparing updated Coach review packet (V3) for Shekur…")

    # Send DOCX and PDF with requested filenames: 14-days-meal-plan.docx and 14-days-meal-plan.pdf
    docx_file = FSInputFile(named_docx_path, filename="14-days-meal-plan.docx")
    pdf_file = FSInputFile(named_pdf_path, filename="14-days-meal-plan.pdf")

    sent_docx = await bot.send_document(
        target_group,
        docx_file,
        caption="📄 DOCX · V3 · 14-days-meal-plan",
        reply_to_message_id=card.message_id,
    )
    if sent_docx.document and sent_docx.document.file_id:
        await repo.set_artifact_telegram_file_id(version_id, "DOCX", sent_docx.document.file_id)
        print("Sent 14-days-meal-plan.docx to Telegram group.")

    sent_pdf = await bot.send_document(
        target_group,
        pdf_file,
        caption="📕 PDF · V3 · 14-days-meal-plan",
        reply_to_message_id=card.message_id,
    )
    if sent_pdf.document and sent_pdf.document.file_id:
        await repo.set_artifact_telegram_file_id(version_id, "PDF", sent_pdf.document.file_id)
        print("Sent 14-days-meal-plan.pdf to Telegram group.")

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
        await conn.execute("UPDATE meal_orders SET state = 'ACTIVE', current_plan_version_id = $1, updated_at = NOW() WHERE id = 19", version_id)
        await conn.execute("UPDATE meal_generation_jobs SET status = 'SUCCEEDED', stage = 'COMPLETE', plan_version_id = $1, finished_at = NOW(), updated_at = NOW() WHERE order_id = 19", version_id)
    print("Database updated: meal_orders & meal_generation_jobs marked complete with V3.")

    print("\n=== V3 PIPELINE COMPLETED SUCCESSFULLY! ===")
    await bot.session.close()
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
