from __future__ import annotations

import html
import json
import logging
import uuid
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.types import FSInputFile

from database.db import Database
from meal_plan.documents import DocumentContext, render_plan_artifacts
from meal_plan.generation.db_dataset import load_dataset_from_db
from meal_plan.generation.engine import generate_plan
from meal_plan.followup_policy import apply_revision_payload
from meal_plan.review_card import review_card_text, review_keyboard
from meal_plan.review_repository import MealPlanReviewRepository
from meal_plan.runtime import review_group_id

logger = logging.getLogger(__name__)


async def update_job_progress(
    bot: Bot,
    payload_source: dict[str, Any] | Any,
    client_name: str,
    order_id: int,
    percentage: int,
    stage_title: str,
    detail_text: str = "",
) -> None:
    payload = payload_source
    if hasattr(payload_source, "get") and "payload" in payload_source:
        payload = payload_source.get("payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    if not isinstance(payload, dict):
        payload = {}

    chat_id = payload.get("progress_chat_id")
    message_id = payload.get("progress_message_id")
    if not chat_id or not message_id:
        return

    filled = min(10, max(0, percentage // 10))
    bar = "█" * filled + "░" * (10 - filled)
    icon = "✅" if percentage >= 100 else "⏳"
    text = (
        f"{icon} <b>Order #{order_id} Generation Progress</b>\n"
        f"👤 Client: <b>{html.escape(client_name)}</b>\n"
        f"────────────────────\n"
        f"<code>[{bar}] {percentage:>3}%</code> · <b>{stage_title}</b>\n"
    )
    if detail_text:
        text += f"<i>{detail_text}</i>\n"
    if percentage >= 100:
        text += "────────────────────\n🎉 <i>Delivered to Coach Review Group!</i>"

    try:
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="HTML")
    except Exception:
        # Ignore Telegram message not modified or temporary API glitches
        pass


async def process_generation_job(bot: Bot, db: Database, review_repo: MealPlanReviewRepository, job) -> int:
    """Build one queued version all the way through private Coach review handoff.

    Numeric food selection remains deterministic Phase 6 logic. Phase 8 only ties
    the queued job, document render and Telegram review handoff together.
    """
    context = await review_repo.get_generation_context(job["id"])
    client_name = str(context.get("full_name") or "Meal Plan Client")
    order_id = int(context["order_id"])

    # 25% - FOOD_MATCHING
    await review_repo.set_job_stage(job["id"], "FOOD_MATCHING")
    await update_job_progress(
        bot, context, client_name, order_id, 25,
        "🥗 Exploring & Matching Foods",
        "Selecting optimal nutrition templates and candidate foods..."
    )

    pool = getattr(db, "_pool", None)
    if pool is None:
        raise RuntimeError("Database pool is not connected")
    async with pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)

    answers = dict(context.get("answers") or {})
    nutrition_profile = dict(context.get("nutrition_profile") or {})
    answers, nutrition_profile, revision_context = apply_revision_payload(
        answers=answers,
        nutrition_profile=nutrition_profile,
        payload=dict(context.get("payload") or {}),
    )

    # 50% - WEEK_STRUCTURE
    await review_repo.set_job_stage(job["id"], "WEEK_STRUCTURE")
    await update_job_progress(
        bot, context, client_name, order_id, 50,
        "📅 Structuring 7-Day Week & Fasting",
        "Balancing meal portions, macro targets, and Orthodox fasting rules..."
    )
    plan = generate_plan(
        answers=answers,
        nutrition_profile=nutrition_profile,
        meals_per_day=int(context["meals_per_day"]),
        start_date=context["start_date"],
        duration_days=int(context["duration_days"]),
        region=str(context["region"]),
        country_name=context.get("country_name"),
        dataset=dataset,
    )
    if revision_context:
        plan["revision_context"] = revision_context

    # 75% - GROCERIES
    await review_repo.set_job_stage(job["id"], "GROCERIES")
    await update_job_progress(
        bot, context, client_name, order_id, 75,
        "🛒 Aggregating Groceries & Unpacking",
        "Unpacking composite recipes and calculating weekly shopping commodities..."
    )

    version = await review_repo.create_generated_version(
        job["id"],
        plan_json=plan,
        engine_version=str(plan.get("engine_version") or ""),
        dataset_version=str(plan.get("dataset_version") or ""),
        settings_version=str(plan.get("settings_version") or ""),
        generation_seed=f"deterministic:{context['order_id']}:{job['id']}",
    )

    # 90% - DOCUMENTS
    await review_repo.set_job_stage(job["id"], "DOCUMENTS")
    await update_job_progress(
        bot, context, client_name, order_id, 90,
        "📄 Compiling High-Def 15-Page PDF",
        "Rendering certified typography, layout tables, and client DOCX..."
    )
    plan_public_id = f"MP-{context['order_id']:06d}"
    doc_context = DocumentContext(
        client_name=client_name,
        plan_public_id=plan_public_id,
        version_number=int(version["version_number"]),
        language=str(context.get("language") or "AM"),
        client_profile={
            "current_weight_kg": answers.get("current_weight_kg"),
            "target_weight_kg": answers.get("target_weight_kg"),
            "goal": answers.get("primary_goal"),
        },
        hydration_target_l=nutrition_profile.get("hydration_target_l"),
    )
    artifacts = render_plan_artifacts(plan, doc_context)
    for artifact in (artifacts.docx, artifacts.pdf):
        await review_repo.store_artifact(
            version["id"],
            artifact_type=artifact.artifact_type,
            storage_key=str(artifact.path.resolve()),
            original_filename=artifact.filename,
            content_sha256=artifact.sha256,
            byte_size=artifact.byte_size,
        )

    # 100% - REVIEW_HANDOFF
    await review_repo.set_job_stage(job["id"], "REVIEW_HANDOFF")
    chat_id = review_group_id()
    if not chat_id:
        raise RuntimeError("MEAL_PLAN_REVIEW_GROUP_ID is not configured")

    review_context, _ = await review_repo.get_review_context(version["id"])
    card = await bot.send_message(chat_id, "⏳ Preparing Coach review packet…")

    # Attach both editable source and final PDF before exposing review actions.
    for artifact in (artifacts.docx, artifacts.pdf):
        sent = await bot.send_document(
            chat_id,
            FSInputFile(artifact.path, filename=artifact.filename),
            caption=f"{artifact.artifact_type} · V{version['version_number']} · {artifact.sha256[:12]}",
            reply_to_message_id=card.message_id,
        )
        if sent.document and sent.document.file_id:
            await review_repo.set_artifact_telegram_file_id(version["id"], artifact.artifact_type, sent.document.file_id)

    await bot.edit_message_text(
        review_card_text(review_context),
        chat_id=chat_id,
        message_id=card.message_id,
        parse_mode="HTML",
        reply_markup=review_keyboard(version["id"]),
    )
    version = await review_repo.mark_review_handoff(version["id"], chat_id=chat_id, message_id=card.message_id)
    await review_repo.finish_generation_job(job["id"], version["id"])

    # Update progress card to 100% Complete in place
    await update_job_progress(
        bot, context, client_name, order_id, 100,
        "🏅 Generation Complete · Delivered to Group",
        "Official review packet with certified 15-page PDF & DOCX posted."
    )
    return version["id"]
