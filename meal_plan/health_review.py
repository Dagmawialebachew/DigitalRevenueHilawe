"""Telegram health-review handoff for flagged meal-plan intakes."""

from __future__ import annotations

import html
import logging

from aiogram import F, Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from database.db import Database
from meal_plan.health_gate import HealthGateResult, localized_flag_labels
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.repository import ConcurrentUpdate, RecordNotFound
from meal_plan.repository_factory import get_meal_plan_repository
from meal_plan.runtime import frontend_url, frontend_url_is_valid, is_reviewer, review_group_id
from meal_plan.states import IntakeState

logger = logging.getLogger(__name__)
router = Router(name="meal_plan_health_review")


def _review_keyboard(intake_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve to proceed", callback_data=f"meal_health:approve:{intake_id}"),
            InlineKeyboardButton(text="⛔ Outside scope", callback_data=f"meal_health:decline:{intake_id}"),
        ]
    ])


async def notify_health_review(bot, *, intake, identity, language: str, result: HealthGateResult) -> bool:
    chat_id = review_group_id()
    if not chat_id:
        logger.warning("Health review required but MEAL_PLAN_REVIEW_GROUP_ID is not configured")
        return False

    labels = localized_flag_labels(result, "EN")
    flags = "\n".join(f"• {html.escape(label)}" for label in labels)
    username = f"@{html.escape(identity.username)}" if identity.username else "No public username"
    text = (
        "⚕️ <b>MEAL PLAN · HEALTH REVIEW</b>\n\n"
        f"Client: <b>{html.escape(identity.first_name)}</b>\n"
        f"Telegram: {username}\n"
        f"Intake: <code>{html.escape(str(intake['public_id']))}</code>\n\n"
        "<b>Hilawe safety gate flags</b>\n"
        f"{flags}\n\n"
        "No payment has been collected. Approve only if this client may proceed with the meal-plan service."
    )
    await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=_review_keyboard(intake["id"]))
    return True


def _continue_markup(language: str) -> InlineKeyboardMarkup | None:
    url = frontend_url()
    if not frontend_url_is_valid(url):
        return None
    label = "የምግብ ፕላኑን ይቀጥሉ" if language == "AM" else "Continue Meal Plan"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label, web_app=WebAppInfo(url=url))]])


@router.callback_query(F.data.startswith("meal_health:"))
async def health_review_decision(callback: types.CallbackQuery, db: Database):
    if not is_reviewer(callback.from_user.id):
        return await callback.answer("Not authorized for meal-plan review", show_alert=True)

    try:
        _, action, raw_id = callback.data.split(":", 2)
        intake_id = int(raw_id)
    except (ValueError, AttributeError):
        return await callback.answer("Invalid review action", show_alert=True)

    repo = get_meal_plan_repository(db)
    try:
        intake = await repo.get_intake(intake_id)
        if not intake:
            raise RecordNotFound("Intake not found")
        if action == "approve":
            intake = await repo.approve_health_review(intake_id, callback.from_user.id)
            answers = dict(intake.get("answers") or {})
            profile = calculate_nutrition_profile(answers).to_dict()
            profile["health_gate"] = "MEDICAL_QUALIFIED_REVIEW_APPROVED"
            intake = await repo.store_nutrition_profile(
                intake_id,
                expected_state=IntakeState.HEALTH_APPROVED,
                profile=profile,
            )
            user = await db.get_user(intake["user_id"])
            language = user.get("language") if user and user.get("language") in {"AM", "EN"} else "AM"
            if language == "AM":
                text = (
                    "✅ <b>የጤና መረጃዎ ተገምግሟል</b>\n\n"
                    "የሰጡት መረጃ ተመልክቶ የምግብ ፕላኑን ሂደት እንዲቀጥሉ ተፈቅዷል። "
                    "አሁን ወደ Mini App ተመልሰው የእርስዎን nutrition profile ማየት እና ፕላኑን ማዋቀር ይችላሉ።"
                )
            else:
                text = (
                    "✅ <b>Your health profile has been reviewed</b>\n\n"
                    "You have been approved to continue the meal-plan process. Return to the Mini App to view your nutrition profile and configure your plan."
                )
            await callback.bot.send_message(
                intake["user_id"], text, parse_mode="HTML", reply_markup=_continue_markup(language)
            )
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.reply(
                f"✅ Approved by {html.escape(callback.from_user.full_name)} · Intake {intake_id}", parse_mode="HTML"
            )
            return await callback.answer("Approved")

        if action == "decline":
            intake = await repo.decline_health_review(intake_id, callback.from_user.id)
            user = await db.get_user(intake["user_id"])
            language = user.get("language") if user and user.get("language") in {"AM", "EN"} else "AM"
            text = (
                "የምግብ ፕላንዎ ከመዘጋጀቱ በፊት ተጨማሪ የጤና ክትትል ያስፈልጋል። ምንም ክፍያ አልተወሰደም።"
                if language == "AM"
                else "Your profile needs care outside the current automatic meal-plan workflow. No payment has been collected."
            )
            await callback.bot.send_message(intake["user_id"], text)
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.reply(
                f"⛔ Marked outside scope by {html.escape(callback.from_user.full_name)} · Intake {intake_id}", parse_mode="HTML"
            )
            return await callback.answer("Closed")

        return await callback.answer("Unknown review action", show_alert=True)
    except (ConcurrentUpdate, RecordNotFound, ValueError) as exc:
        logger.warning("Health review callback failed: %s", exc)
        return await callback.answer(str(exc), show_alert=True)
