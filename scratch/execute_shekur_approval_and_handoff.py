import asyncio
import os
import json
import sys
import time
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardMarkup
from database.db import Database
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan
from meal_plan.generation.db_dataset import load_dataset_from_db
from meal_plan.documents.models import DocumentContext
from meal_plan.documents.service import render_plan_artifacts
from meal_plan.review_repository import MealPlanReviewRepository
from meal_plan.review_card import review_card_text, review_keyboard
from meal_plan.payment import _notify_user_payment_approved
from meal_plan.runtime import review_group_id

async def main():
    print("=== STARTING OFFICIAL ORDER APPROVAL & HANDOFF PIPELINE ===")
    bot = Bot(token=os.getenv("BOT_TOKEN"))
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    repo = MealPlanReviewRepository(db._pool)

    # 1. Fetch Order 19 & Client context
    query = """
        SELECT o.id as order_id, o.public_id, o.user_id, o.duration_days, o.meals_per_day, o.start_date, o.ends_on,
               o.state as order_state, o.amount, o.currency,
               i.answers, i.language, u.full_name, u.username
        FROM meal_orders o
        JOIN meal_intakes i ON o.intake_id = i.id
        LEFT JOIN users u ON o.user_id = u.telegram_id
        WHERE o.id = 19
    """
    row = await db.fetchrow(query)
    if not row:
        print("Error: Order 19 not found.")
        await bot.session.close()
        await db.disconnect()
        return

    user_name = row["full_name"] or "Shekur.afiff"
    answers = row["answers"]
    if isinstance(answers, str):
        answers = json.loads(answers)

    duration = row["duration_days"] or 14
    meals_per_day = row["meals_per_day"] or 3
    start_date = row["start_date"] or date(2026, 10, 26)

    print(f"Order: #{row['order_id']} ({row['public_id']})")
    print(f"Client: {user_name} (@{row.get('username')}, TG ID: {row['user_id']})")
    print(f"Goal: {answers.get('primary_goal')} | Duration: {duration}d | Meals: {meals_per_day}/day")

    # 2. Trigger user payment confirmation message (the exact message triggered by the Approve button)
    print("\n--- 1. Sending Payment Approved notification to Client ---")
    try:
        user = await db.get_user(row["user_id"])
        lang = (user.get("language") if user else None) or "AM"
        if lang == "EN":
            text = (
                "✅ <b>Payment confirmed.</b>\n\n"
                "Your Meal Plan order is now in the preparation queue. The next stage builds your personalized nutrition plan before it is sent for Coach review."
            )
        else:
            text = (
                "✅ <b>ክፍያዎ ተረጋግጧል።</b>\n\n"
                "የምግብ ፕላን ትዕዛዝዎ አሁን ወደ ዝግጅት ተራ ገብቷል። ቀጣዩ ደረጃ የግል ፕላንዎን ከመገንባት በኋላ ለCoach review ይልካል።"
            )
        await bot.send_message(row["user_id"], text, parse_mode="HTML")
        print(f"Successfully notified client {row['user_id']} of payment approval & queue entry.")
    except Exception as e:
        print(f"Notice: Could not send Telegram message to client directly: {e}")

    # 3. Update order state in DB
    async with db._pool.acquire() as conn:
        await conn.execute("UPDATE meal_orders SET state = 'GENERATING', updated_at = NOW(), version = version + 1 WHERE id = 19")
        print("Updated meal_orders state -> GENERATING")

    # 4. Generate plan with latest engine fixes
    print("\n--- 2. Generating Meal Plan with latest fixes & ቀይ ወጥ ---")
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
        version_number=2,
        language=str(row.get("language") or "AM"),
        client_profile={
            "current_weight_kg": answers.get("current_weight_kg"),
            "target_weight_kg": answers.get("target_weight_kg"),
            "goal": answers.get("primary_goal"),
        },
        hydration_target_l=pdict.get("hydration_target_l", 2.5),
    )

    # 5. Render DOCX and PDF
    print("\n--- 3. Rendering DOCX & PDF ---")
    t0 = time.time()
    artifacts = render_plan_artifacts(plan, doc_context)
    print(f"Rendered DOCX: {artifacts.docx.path} ({artifacts.docx.byte_size/1024:.1f} KB)")
    print(f"Rendered PDF:  {artifacts.pdf.path} ({artifacts.pdf.byte_size/1024:.1f} KB)")
    print(f"Rendering complete in {time.time()-t0:.2f}s")

    # 6. Create Version 2 in database
    print("\n--- 4. Registering Version & Artifacts in DB ---")
    import uuid
    version_uuid = uuid.uuid4()
    async with db._pool.acquire() as conn:
        v_row = await conn.fetchrow(
            """
            INSERT INTO meal_plan_versions(
                public_id, order_id, version_number, status, plan_json, engine_version, dataset_version, settings_version, generation_seed
            )
            VALUES($1, 19, 2, 'REVIEW_PENDING', $2, $3, $4, $5, $6)
            ON CONFLICT (order_id, version_number) DO UPDATE
            SET plan_json = EXCLUDED.plan_json, status = 'REVIEW_PENDING', updated_at = NOW()
            RETURNING *
            """,
            version_uuid,
            json.dumps(plan, ensure_ascii=False, separators=(",", ":")),
            str(plan.get("engine_version") or "HILAWE_PY_ENGINE_V1.0_PHASE6"),
            str(plan.get("dataset_version") or "HILAWE_MEAL_OS_V1.3_2026-08-17"),
            str(plan.get("settings_version") or "HILAWE_ENGINE_CONFIG_V1"),
            f"deterministic:19:2",
        )
        version_id = v_row["id"]
        print(f"Registered meal_plan_versions ID: {version_id} (Version V2, UUID: {v_row['public_id']})")

        # Store artifacts
        for art in (artifacts.docx, artifacts.pdf):
            await repo.store_artifact(
                version_id,
                artifact_type=art.artifact_type,
                storage_key=str(art.path.resolve()),
                original_filename=art.filename,
                content_sha256=art.sha256,
                byte_size=art.byte_size,
            )
            print(f"Stored artifact {art.artifact_type} ({art.filename})")

    # 7. Post Review Packet to the Dedicated Meal Plan Group (-5592866261)
    target_group = review_group_id()
    print(f"\n--- 5. Delivering Review Packet to Telegram Group ({target_group}) ---")
    card = await bot.send_message(target_group, "⏳ Preparing Coach review packet for Shekur…")

    # Send DOCX and PDF as replies to the review card
    for art in (artifacts.docx, artifacts.pdf):
        sent = await bot.send_document(
            target_group,
            FSInputFile(art.path, filename=art.filename),
            caption=f"{art.artifact_type} · V2 · {art.sha256[:12]}",
            reply_to_message_id=card.message_id,
        )
        if sent.document and sent.document.file_id:
            await repo.set_artifact_telegram_file_id(version_id, art.artifact_type, sent.document.file_id)
            print(f"Sent {art.artifact_type} with Telegram File ID: {sent.document.file_id[:20]}...")

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

    # 8. Mark review handoff in DB & update order
    await repo.mark_review_handoff(version_id, chat_id=target_group, message_id=card.message_id)
    async with db._pool.acquire() as conn:
        await conn.execute("UPDATE meal_orders SET state = 'ACTIVE', current_plan_version_id = $1, updated_at = NOW() WHERE id = 19", version_id)
        # Update generation job status to SUCCEEDED
        await conn.execute("UPDATE meal_generation_jobs SET status = 'SUCCEEDED', stage = 'COMPLETE', plan_version_id = $1, finished_at = NOW(), updated_at = NOW() WHERE order_id = 19", version_id)
    print("Database updated: meal_orders & meal_generation_jobs marked complete.")

    print("\n=== PIPELINE COMPLETED SUCCESSFULLY! ===")
    await bot.session.close()
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
