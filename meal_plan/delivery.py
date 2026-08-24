from __future__ import annotations

import html
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from database.db import Database
from meal_plan.repository import ConcurrentUpdate
from meal_plan.review_repository import MealPlanReviewRepository
from meal_plan.runtime import coach_username, frontend_url, frontend_url_is_valid

logger = logging.getLogger(__name__)


def _open_markup(language: str) -> InlineKeyboardMarkup | None:
    rows = []
    if frontend_url_is_valid(frontend_url()):
        rows.append([InlineKeyboardButton(
            text="🥗 ፕላኔን ክፈት" if language == "AM" else "🥗 Open my plan",
            web_app=WebAppInfo(url=frontend_url()),
        )])
    username = coach_username()
    if username:
        rows.append([InlineKeyboardButton(
            text="💬 Coach Hilaweን አነጋግር" if language == "AM" else "💬 Contact Coach Hilawe",
            url=f"https://t.me/{username.lstrip('@')}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


async def deliver_approved_plan(bot: Bot, db: Database, review_repo: MealPlanReviewRepository, plan_version_id: int):
    version, order, deliveries = await review_repo.prepare_delivery(plan_version_id)
    telegram_row = next((row for row in deliveries if row["channel"] == "TELEGRAM_DOCUMENT"), None)
    mini_row = next((row for row in deliveries if row["channel"] == "MINI_APP"), None)

    # Idempotent retry: already delivered means there is nothing left to send.
    if version["status"] == "DELIVERED" and order["state"] in {"ACTIVE", "RENEWAL_DUE"}:
        return {"version": version, "order": order, "already_delivered": True}

    user = await db.get_user(order["user_id"])
    language = (user.get("language") if user else None) or "AM"
    pdf = await review_repo.get_artifact(plan_version_id, "PDF")
    if not pdf:
        await review_repo.mark_delivery_failed(plan_version_id, "TELEGRAM_DOCUMENT", "Approved PDF artifact is missing")
        raise ConcurrentUpdate("Approved PDF artifact is missing")

    # Approval itself authorizes Mini App access to the current approved PDF.
    # Mark this channel first so a temporary Telegram send failure does not block
    # the customer from opening the approved plan in the authenticated Mini App.
    if not mini_row or mini_row["status"] != "SENT":
        await review_repo.mark_delivery_sent(plan_version_id, "MINI_APP")

    if not telegram_row or telegram_row["status"] != "SENT":
        caption = (
            "✅ <b>የግል የምግብ ፕላንዎ በCoach review ተፈቅዶ ዝግጁ ሆኗል።</b>\n\n"
            "PDFውን ከዚህ ያገኛሉ። Mini App ውስጥም ፕላንዎ ተከፍቷል።"
            if language == "AM" else
            "✅ <b>Your personalized Meal Plan has passed Coach review and is ready.</b>\n\n"
            "Your approved PDF is attached here, and the plan is also unlocked inside the Mini App."
        )
        try:
            if pdf.get("telegram_file_id"):
                sent = await bot.send_document(order["user_id"], pdf["telegram_file_id"], caption=caption, parse_mode="HTML", reply_markup=_open_markup(language))
            else:
                path = Path(str(pdf["storage_key"]))
                if not path.is_file():
                    raise FileNotFoundError(f"PDF not found: {path}")
                sent = await bot.send_document(order["user_id"], FSInputFile(path, filename=pdf["original_filename"]), caption=caption, parse_mode="HTML", reply_markup=_open_markup(language))
                if sent.document and sent.document.file_id:
                    await review_repo.set_artifact_telegram_file_id(plan_version_id, "PDF", sent.document.file_id)
            await review_repo.mark_delivery_sent(plan_version_id, "TELEGRAM_DOCUMENT", telegram_message_id=sent.message_id)
        except Exception as exc:
            logger.exception("Meal Plan Telegram delivery failed for version %s", plan_version_id)
            await review_repo.mark_delivery_failed(plan_version_id, "TELEGRAM_DOCUMENT", f"{type(exc).__name__}: {exc}")
            raise

    version, order = await review_repo.finalize_delivery(plan_version_id)
    return {"version": version, "order": order, "already_delivered": False}
