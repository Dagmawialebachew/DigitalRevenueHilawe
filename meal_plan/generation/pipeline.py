from __future__ import annotations

import logging
import uuid
from pathlib import Path

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


async def process_generation_job(bot: Bot, db: Database, review_repo: MealPlanReviewRepository, job) -> int:
    """Build one queued version all the way through private Coach review handoff.

    Numeric food selection remains deterministic Phase 6 logic. Phase 8 only ties
    the queued job, document render and Telegram review handoff together.
    """
    context = await review_repo.get_generation_context(job["id"])
    await review_repo.set_job_stage(job["id"], "FOOD_MATCHING")

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
    await review_repo.set_job_stage(job["id"], "WEEK_STRUCTURE")
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
    await review_repo.set_job_stage(job["id"], "GROCERIES")

    version = await review_repo.create_generated_version(
        job["id"],
        plan_json=plan,
        engine_version=str(plan.get("engine_version") or ""),
        dataset_version=str(plan.get("dataset_version") or ""),
        settings_version=str(plan.get("settings_version") or ""),
        generation_seed=f"deterministic:{context['order_id']}:{job['id']}",
    )

    await review_repo.set_job_stage(job["id"], "DOCUMENTS")
    name = str(context.get("full_name") or "Meal Plan Client")
    plan_public_id = f"MP-{context['order_id']:06d}"
    doc_context = DocumentContext(
        client_name=name,
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

    await review_repo.set_job_stage(job["id"], "REVIEW_HANDOFF")
    chat_id = review_group_id()
    if not chat_id:
        raise RuntimeError("MEAL_PLAN_REVIEW_GROUP_ID is not configured")

    review_context, _ = await review_repo.get_review_context(version["id"])
    card = await bot.send_message(chat_id, "⏳ Preparing Coach review packet…")

    # Attach both editable source and final PDF before exposing review actions.
    # A partial Telegram upload can therefore never be approved.
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
    return version["id"]
