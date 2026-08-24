from __future__ import annotations

import html
import logging

from aiogram import F, Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.db import Database
from meal_plan.followup_repository import MealPlanFollowUpRepository
from meal_plan.repository import ConcurrentUpdate, RecordNotFound
from meal_plan.runtime import is_reviewer, review_group_id

logger = logging.getLogger(__name__)
router = Router(name="meal_plan_followup_review")


def _repo(db: Database) -> MealPlanFollowUpRepository:
    pool = getattr(db, "_pool", None)
    if pool is None:
        raise RuntimeError("Database pool is not connected")
    return MealPlanFollowUpRepository(pool)


def followup_review_keyboard(checkin_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Client", callback_data=f"mealfollowup:client:{checkin_id}")],
        [InlineKeyboardButton(text="✅ Close after human review", callback_data=f"mealfollowup:close:{checkin_id}")],
    ])


def followup_review_text(row, reasons: list[str] | tuple[str, ...]) -> str:
    answers = dict(row.get("answers") or {})
    name = html.escape(str(row.get("full_name") or "Member"))
    username = f"@{html.escape(str(row['username']))}" if row.get("username") else "no public username"
    health = "YES - AUTOMATION BLOCKED" if row.get("health_change") else "No"
    reason_text = "\n".join(f"• {html.escape(str(reason))}" for reason in reasons) or "• Manual Coach review requested"
    return (
        "🩺 <b>HILAWE FOLLOW-UP · HUMAN REVIEW</b>\n\n"
        f"<b>{name}</b> · {username}\n"
        f"Order <code>{html.escape(str(row.get('order_public_id') or ''))}</code> · Week {row['week_number']}\n\n"
        f"Weight: <b>{answers.get('current_weight_kg','-')} kg</b>\n"
        f"Adherence: <b>{answers.get('adherence_percent','-')}%</b>\n"
        f"Energy / Hunger: <b>{answers.get('energy_rating','-')} / {answers.get('hunger_rating','-')}</b>\n"
        f"Health change: <b>{health}</b>\n"
        f"Health notes: {html.escape(str(answers.get('health_change_notes') or 'None'))}\n"
        f"Food feedback: avoid <i>{html.escape(str(answers.get('foods_to_avoid') or '-'))}</i> · prefer <i>{html.escape(str(answers.get('foods_to_prioritize') or '-'))}</i>\n\n"
        f"<b>Why this stopped:</b>\n{reason_text}\n\n"
        "No automatic revision is queued from this card. Contact the client / qualified professional as appropriate, then close the check-in when handled."
    )


async def send_followup_review(bot, db: Database, checkin_id: int, reasons: list[str] | tuple[str, ...]) -> int | None:
    chat_id = review_group_id()
    if not chat_id:
        logger.warning("MEAL_PLAN_REVIEW_GROUP_ID not configured; follow-up review remains safely held")
        return None
    row = await _repo(db).get_checkin_review_context(checkin_id)
    if not row:
        return None
    message = await bot.send_message(
        chat_id,
        followup_review_text(row, reasons),
        parse_mode="HTML",
        reply_markup=followup_review_keyboard(checkin_id),
    )
    return message.message_id


@router.callback_query(F.data.startswith("mealfollowup:"))
async def followup_review_action(callback: types.CallbackQuery, db: Database):
    if not callback.from_user or not is_reviewer(callback.from_user.id):
        return await callback.answer("Not authorized for Meal Plan follow-up review.", show_alert=True)
    parts = (callback.data or "").split(":")
    if len(parts) != 3 or parts[0] != "mealfollowup" or parts[1] not in {"client", "close"}:
        return await callback.answer("Invalid follow-up action.", show_alert=True)
    try:
        checkin_id = int(parts[2])
        if checkin_id <= 0:
            raise ValueError
    except ValueError:
        return await callback.answer("Invalid check-in ID.", show_alert=True)

    repo = _repo(db)
    try:
        row = await repo.get_checkin_review_context(checkin_id)
        if not row:
            raise RecordNotFound("Check-in not found")
        if parts[1] == "client":
            username = f"@{row['username']}" if row.get("username") else "No public username"
            return await callback.answer(
                f"{row.get('full_name') or 'Member'}\n{username}\nTelegram ID: {row['user_id']}",
                show_alert=True,
            )
        closed = await repo.close_review_checkin(checkin_id, callback.from_user.id)
        await callback.answer("Check-in closed after human review.")
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.reply(
                f"✅ Follow-up Week {closed['week_number']} closed by {html.escape(callback.from_user.full_name)}.",
                parse_mode="HTML",
            )
        except Exception:
            pass
    except (RecordNotFound, ConcurrentUpdate) as exc:
        await callback.answer(str(exc), show_alert=True)
    except Exception as exc:
        logger.exception("Follow-up review callback failed")
        await callback.answer(f"Follow-up action failed: {type(exc).__name__}", show_alert=True)
