"""Telegram entry flow for the personalized Meal Plan Mini App."""

from __future__ import annotations

import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import Database
from meal_plan.countries import country_label, normalize_region, validate_other_country_name
from meal_plan.keyboards import country_gate_markup, launch_markup
from meal_plan.repository_factory import get_meal_plan_repository
from meal_plan.runtime import frontend_url, frontend_url_is_valid, meal_plan_enabled

router = Router(name="meal_plan_entry")
logger = logging.getLogger(__name__)

MEAL_MENU_TEXTS = {"🥗 Meal Plan", "🥗 የምግብ ፕላን"}


class MealPlanEntryState(StatesGroup):
    waiting_other_country = State()


def _language(user) -> str:
    if user and user.get("language") in {"AM", "EN"}:
        return user["language"]
    return "AM"


def _country_prompt(lang: str) -> str:
    if lang == "EN":
        return (
            "🌍 <b>Let’s prepare your Meal Plan</b>\n\n"
            "First, choose the country or region where you currently live. "
            "This helps us prepare a plan around foods that are practical and easier to find where you are.\n\n"
            "Choose one option below."
        )
    return (
        "🌍 <b>የምግብ ፕላንዎን እንጀምር</b>\n\n"
        "መጀመሪያ በአሁኑ ጊዜ የሚኖሩበትን አገር ወይም ክልል ይምረጡ። "
        "ይህ በአካባቢዎ በቀላሉ የሚገኙ እና በተግባር ሊከተሏቸው የሚችሉ ምግቦችን "
        "መሠረት በማድረግ ፕላንዎን እንድናዘጋጅ ይረዳናል።\n\n"
        "ከታች አንዱን ይምረጡ።"
    )


def _other_prompt(lang: str) -> str:
    if lang == "EN":
        return (
            "🌍 <b>Tell us your country</b>\n\n"
            "Type the name of the country where you currently live. "
            "We’ll use it only to prepare a more practical Meal Plan for your location."
        )
    return (
        "🌍 <b>የሚኖሩበትን አገር ይጻፉ</b>\n\n"
        "በአሁኑ ጊዜ የሚኖሩበትን አገር ስም ይጻፉ። "
        "ይህን መረጃ የምንጠቀመው ለአካባቢዎ ተግባራዊ የሆነ የምግብ ፕላን ለማዘጋጀት ብቻ ነው።"
    )


async def _send_launch(message: types.Message, lang: str, intake) -> None:
    url = frontend_url()
    if not frontend_url_is_valid(url):
        logger.warning("MEAL_PLAN_FRONTEND_URL is missing or is not HTTPS")
        text = (
            "⚙️ Meal Plan Mini App is not configured on this demo yet."
            if lang == "EN"
            else "⚙️ የምግብ ፕላን Mini App አድራሻ በዚህ demo ላይ ገና አልተዘጋጀም።"
        )
        await message.answer(text)
        return

    region = intake["country_region"]
    label = country_label(region, lang, intake.get("country_name"))
    if lang == "EN":
        text = (
            f"✅ <b>Location saved: {label}</b>\n\n"
            "Your Meal Plan space is ready to open. Inside the Mini App, Coach Hilawe will guide you through the personalized assessment step by step.\n\n"
            "You can leave Telegram and return later without losing this starting point."
        )
    else:
        text = (
            f"✅ <b>አካባቢዎ ተመዝግቧል፦ {label}</b>\n\n"
            "የምግብ ፕላንዎን ለማዘጋጀት የሚጠቀሙበት Mini App አሁን ለመክፈት ዝግጁ ነው። "
            "በውስጡ ኮች ህላዌ የግል መረጃዎችዎን አንድ በአንድ በቀላሉ እንዲሞሉ ይመራዎታል።\n\n"
            "አሁን ቢዘጉትም በኋላ ተመልሰው ከዚሁ መቀጠል ይችላሉ።"
        )
    await message.answer(text, reply_markup=launch_markup(lang, url), parse_mode="HTML")


@router.message(F.text.in_(MEAL_MENU_TEXTS))
async def open_meal_plan_entry(message: types.Message, state: FSMContext, db: Database):
    if not meal_plan_enabled():
        return await message.answer(
            "Meal Plan is not enabled on this bot yet."
            if message.text == "🥗 Meal Plan"
            else "የምግብ ፕላኑ በዚህ bot ላይ ገና አልተከፈተም።"
        )

    await state.clear()
    user = await db.get_user(message.from_user.id)
    if not user:
        return await message.answer("Please send /start first." if message.text == "🥗 Meal Plan" else "እባክዎ መጀመሪያ /start ይላኩ።")

    lang = _language(user)
    repo = get_meal_plan_repository(db)
    active_order = await repo.get_current_order_for_user(message.from_user.id)
    if active_order:
        intake = await repo.get_intake(active_order["intake_id"])
        return await _send_launch(message, lang, intake)

    intake = await repo.create_or_resume_intake(
        message.from_user.id,
        lang,
        source="BOT_MENU",
    )

    if intake.get("country_region"):
        return await _send_launch(message, lang, intake)

    await message.answer(_country_prompt(lang), reply_markup=country_gate_markup(lang), parse_mode="HTML")


@router.callback_query(F.data == "meal_country_change")
async def change_country(callback: types.CallbackQuery, state: FSMContext, db: Database):
    if not meal_plan_enabled():
        return await callback.answer("Meal Plan is disabled", show_alert=True)
    await state.clear()
    user = await db.get_user(callback.from_user.id)
    lang = _language(user)
    repo = get_meal_plan_repository(db)
    if await repo.get_current_order_for_user(callback.from_user.id):
        return await callback.answer("Country is locked while a Meal Plan order is active.", show_alert=True)
    await callback.message.edit_text(_country_prompt(lang), reply_markup=country_gate_markup(lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("meal_country:"))
async def select_country(callback: types.CallbackQuery, state: FSMContext, db: Database):
    if not meal_plan_enabled():
        return await callback.answer("Meal Plan is disabled", show_alert=True)

    user = await db.get_user(callback.from_user.id)
    if not user:
        return await callback.answer("Please send /start first", show_alert=True)
    lang = _language(user)

    try:
        region = normalize_region(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return await callback.answer("Invalid country selection", show_alert=True)

    repo = get_meal_plan_repository(db)
    intake = await repo.create_or_resume_intake(callback.from_user.id, lang, source="BOT_MENU")

    if region == "OTHER":
        await state.set_state(MealPlanEntryState.waiting_other_country)
        await state.update_data(meal_intake_id=intake["id"], meal_language=lang)
        await callback.message.edit_text(_other_prompt(lang), parse_mode="HTML")
        return await callback.answer()

    intake = await repo.set_intake_country(
        intake["id"],
        callback.from_user.id,
        region,
        country_name=None,
    )
    await callback.message.delete()
    await _send_launch(callback.message, lang, intake)
    await callback.answer()


@router.message(MealPlanEntryState.waiting_other_country, F.text)
async def receive_other_country(message: types.Message, state: FSMContext, db: Database):
    data = await state.get_data()
    lang = data.get("meal_language") or "AM"
    intake_id = data.get("meal_intake_id")
    if not intake_id:
        await state.clear()
        return await message.answer("Please open Meal Plan again." if lang == "EN" else "እባክዎ የምግብ ፕላኑን እንደገና ይክፈቱ።")

    try:
        country_name = validate_other_country_name(message.text)
    except ValueError:
        return await message.answer(
            "Please type a valid country name (2–80 characters)."
            if lang == "EN"
            else "እባክዎ የአገሩን ስም በግልጽ ይጻፉ (ከ2 እስከ 80 ፊደላት)።"
        )

    repo = get_meal_plan_repository(db)
    intake = await repo.set_intake_country(
        int(intake_id),
        message.from_user.id,
        "OTHER",
        country_name=country_name,
    )
    await state.clear()
    await _send_launch(message, lang, intake)
