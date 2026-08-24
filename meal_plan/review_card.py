from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from meal_plan.review_logic import review_card_text


def review_keyboard(plan_version_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve", callback_data=f"mealreview:approve:{plan_version_id}"),
            InlineKeyboardButton(text="🔁 Generate Again", callback_data=f"mealreview:regen:{plan_version_id}"),
        ],
        [
            InlineKeyboardButton(text="📎 Replace Files", callback_data=f"mealreview:replace:{plan_version_id}"),
            InlineKeyboardButton(text="👤 Client", callback_data=f"mealreview:client:{plan_version_id}"),
        ],
    ])


def approved_keyboard(plan_version_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Retry / Check Delivery", callback_data=f"mealreview:deliver:{plan_version_id}")],
        [InlineKeyboardButton(text="👤 Client", callback_data=f"mealreview:client:{plan_version_id}")],
    ])
