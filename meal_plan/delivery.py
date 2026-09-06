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

    client_name = html.escape((user.get("full_name") if user else None) or "Member")
    duration = int(order.get("duration_days") or 7)
    goal = html.escape(str(order.get("service_type") or "Personal Transformation"))

    if not telegram_row or telegram_row["status"] != "SENT":
        if language == "AM":
            caption = (
                f"🎉 <b>እንኳን ደስ አለዎት! ይፋዊ የግል የአመጋገብ ፕላንዎ ዝግጁ ሆኗል!</b> 🥗🔥\n\n"
                f"👤 <b>ደንበኛ፦</b> {client_name}\n"
                f"🎯 <b>ዋና ዓላማ፦</b> {goal}\n"
                f"📅 <b>የፕላኑ ቆይታ፦</b> {duration} ቀናት\n"
                f"✨ <b>የጸደቀበት ሁኔታ፦</b> 100% የተረጋገጠ እና የጸደቀ ይፋዊ ፕላን ✅\n\n"
                f"📄 <b>የእርስዎ PDF ሰነድ ከታች ተያይዟል!</b>\n"
                f"👇 አሁኑኑ ዳውንሎድ በማድረግ ገጾቹን በጥንቃቄ ይመልከቱ።\n\n"
                f"💡 <b>የአሰልጣኝ ህላዌ ወርቃማ መመሪያ፦</b>\n"
                f"<i>«ለውጥ የሚመጣው ከወጥነት እንጂ ከአንድ ቀን ፍጹምነት አይደለም! ከዛሬ ጀምረን ውጤት እናመጣለን!»</i> 🚀💪"
            )
        else:
            caption = (
                f"🎉 <b>Congratulations! Your official personalized Meal Plan is ready!</b> 🥗🔥\n\n"
                f"👤 <b>Client:</b> {client_name}\n"
                f"🎯 <b>Goal:</b> {goal}\n"
                f"📅 <b>Duration:</b> {duration} Days\n"
                f"✨ <b>Status:</b> 100% Verified & Approved ✅\n\n"
                f"📄 <b>Your approved PDF is attached below!</b>\n"
                f"👇 Download now and review your guidelines carefully.\n\n"
                f"💡 <b>Coach Hilawe's Rule:</b>\n"
                f"<i>\"Transformation comes from consistency, not one day of perfection. Starting today, we make it happen!\"</i> 🚀💪"
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

            # Optional Welcome Voice Note Hook
            voice_file_id = getattr(settings, "COACH_WELCOME_VOICE_FILE_ID", None)
            voice_path = getattr(settings, "COACH_WELCOME_VOICE_PATH", None)
            voice_caption = "🎙 <b>የአሰልጣኝ ህላዌ ሰማ የእንኳን ደህና መጡ መልዕክት</b>" if language == "AM" else "🎙 <b>Welcome message from Coach Hilawe Semma</b>"
            if voice_file_id:
                try:
                    await bot.send_voice(order["user_id"], voice_file_id, caption=voice_caption, parse_mode="HTML")
                except Exception:
                    logger.warning("Failed to send welcome voice note to user %s", order["user_id"])
            elif voice_path and Path(voice_path).is_file():
                try:
                    await bot.send_voice(order["user_id"], FSInputFile(voice_path), caption=voice_caption, parse_mode="HTML")
                except Exception:
                    logger.warning("Failed to send welcome voice note file to user %s", order["user_id"])
        except Exception as exc:
            logger.exception("Meal Plan Telegram delivery failed for version %s", plan_version_id)
            await review_repo.mark_delivery_failed(plan_version_id, "TELEGRAM_DOCUMENT", f"{type(exc).__name__}: {exc}")
            raise

    version, order = await review_repo.finalize_delivery(plan_version_id)
    return {"version": version, "order": order, "already_delivered": False}
