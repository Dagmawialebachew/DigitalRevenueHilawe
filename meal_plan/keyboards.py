from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from meal_plan.countries import COUNTRY_LABELS


def country_gate_markup(lang: str) -> InlineKeyboardMarkup:
    language = lang if lang in {"AM", "EN"} else "AM"
    builder = InlineKeyboardBuilder()
    for region in ("ETHIOPIA", "UNITED_STATES", "EUROPE", "UAE", "OTHER"):
        builder.button(
            text=COUNTRY_LABELS[region][language],
            callback_data=f"meal_country:{region}",
        )
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def launch_markup(lang: str, mini_app_url: str) -> InlineKeyboardMarkup:
    language = lang if lang in {"AM", "EN"} else "AM"
    open_text = "🥗 Open Meal Plan" if language == "EN" else "🥗 የምግብ ፕላኑን ክፈት"
    change_text = "🌍 Change country" if language == "EN" else "🌍 አገር ቀይር"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=open_text, web_app=WebAppInfo(url=mini_app_url))],
            [InlineKeyboardButton(text=change_text, callback_data="meal_country_change")],
        ]
    )
