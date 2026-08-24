"""Meal Plan payment flow.

This module is isolated from the legacy workout payment FSM/tables. It reuses the
existing receipt-verification helpers as an advisory verification layer, while
meal payment approval/queueing remains idempotent and meal-order scoped.
"""

from __future__ import annotations

import asyncio
import html
import io
import logging
from decimal import Decimal

from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import WebAppInfo

from config import settings
from database.db import Database
from handlers.verify import extract_local_data, is_hilawe_receiver, verify_external
from meal_plan.repository import ConcurrentUpdate, RecordNotFound
from meal_plan.payment_rules import Settlement, amount_matches, build_settlement
from meal_plan.repository_factory import get_meal_plan_repository
from meal_plan.runtime import (
    auto_approve_payments,
    frontend_url,
    frontend_url_is_valid,
    payment_amount_tolerance,
    payment_review_chat_id,
    usd_settlement_mode,
    usd_to_etb_rate,
    is_reviewer,
)

router = Router(name="meal_plan_payment")
logger = logging.getLogger(__name__)


class MealPaymentState(StatesGroup):
    awaiting_proof = State()


def bank_accounts() -> list[dict[str, str]]:
    accounts: list[dict[str, str]] = []
    if settings.BANK_CBE:
        accounts.append({"code": "CBE", "name": "Commercial Bank of Ethiopia (CBE)", "account": settings.BANK_CBE, "holder": settings.BANK_CBE_NAME or ""})
    if settings.BANK_BOA:
        accounts.append({"code": "BOA", "name": "Bank of Abyssinia (BOA)", "account": settings.BANK_BOA, "holder": settings.BANK_BOA_NAME or ""})
    return accounts


def amount_matches(expected: Decimal | str | int | float, observed: object, *, tolerance: Decimal | None = None) -> bool:
    if observed is None:
        return False
    try:
        actual = Decimal(str(observed).replace(",", "").strip())
        target = Decimal(str(expected))
    except (InvalidOperation, ValueError, AttributeError):
        return False
    allowed = payment_amount_tolerance() if tolerance is None else tolerance
    return abs(actual - target) <= allowed


def _payment_markup(payment_id: int) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📸 Send receipt", callback_data=f"mealpay_open:{payment_id}")
    return builder.as_markup()


def _retry_markup(order_id: int) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔁 Submit another receipt", callback_data=f"mealpay_retry:{order_id}")
    return builder.as_markup()


def _review_markup(payment_id: int) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ APPROVE PAYMENT", callback_data=f"mealpay_approve:{payment_id}")
    builder.button(text="❌ REJECT / RETRY", callback_data=f"mealpay_reject:{payment_id}")
    builder.adjust(1, 1)
    return builder.as_markup()


def _format_amount(amount, currency: str) -> str:
    value = Decimal(str(amount))
    if currency == "ETB":
        return f"{value:,.2f} Br"
    return f"${value:,.2f}"


def _instruction_text(language: str, payment) -> str:
    expected = _format_amount(payment["expected_amount"], payment["expected_currency"])
    settlement = _format_amount(payment["settlement_amount"], payment["settlement_currency"])
    accounts = bank_accounts()
    account_lines = []
    for account in accounts:
        account_lines.append(
            f"🏦 <b>{html.escape(account['name'])}</b>\n"
            f"<code>{html.escape(account['account'])}</code>\n"
            f"👤 {html.escape(account['holder'] or 'Coach Hilawe')}"
        )
    bank_block = "\n\n".join(account_lines) if account_lines else "⚠️ Bank accounts are not configured on this demo."

    if language == "EN":
        conversion = "" if payment["expected_currency"] == payment["settlement_currency"] else f"\nListed price: <b>{expected}</b>\nAmount to transfer: <b>{settlement}</b>"
        return (
            "🥗 <b>HILAWE MEAL PLAN · PAYMENT</b>\n\n"
            f"Amount to transfer: <b>{settlement}</b>{conversion}\n\n"
            f"{bank_block}\n\n"
            "After transferring, tap the button below and send a clear screenshot of the receipt. "
            "Your Meal Plan order stays separate from your workout-plan purchases."
        )

    conversion = "" if payment["expected_currency"] == payment["settlement_currency"] else f"\nየተመረጠው ዋጋ፦ <b>{expected}</b>\nየሚልኩት መጠን፦ <b>{settlement}</b>"
    return (
        "🥗 <b>HILAWE የምግብ ፕላን · ክፍያ</b>\n\n"
        f"የሚልኩት መጠን፦ <b>{settlement}</b>{conversion}\n\n"
        f"{bank_block}\n\n"
        "ክፍያውን ከፈጸሙ በኋላ ከታች ያለውን ቁልፍ ተጭነው ግልጽ የደረሰኝ screenshot ይላኩ። "
        "ይህ ክፍያ ከWorkout Plan ግዢዎችዎ ተለይቶ ይመዘገባል።"
    )


async def notify_payment_ready(bot: Bot, *, user_id: int, language: str, payment) -> None:
    text = _instruction_text(language, payment)
    await bot.send_message(user_id, text, parse_mode="HTML", reply_markup=_payment_markup(payment["id"]))


@router.callback_query(F.data.startswith("mealpay_open:"))
async def open_payment_receipt(callback: types.CallbackQuery, state: FSMContext, db: Database):
    payment_id = int(callback.data.split(":", 1)[1])
    repo = get_meal_plan_repository(db)
    payment = await repo.get_payment_for_user(payment_id, callback.from_user.id)
    if not payment or payment["status"] not in {"PENDING", "VERIFYING"}:
        return await callback.answer("Payment attempt is no longer open.", show_alert=True)

    user = await db.get_user(callback.from_user.id)
    lang = (user.get("language") if user else None) or "AM"
    await state.set_state(MealPaymentState.awaiting_proof)
    await state.update_data(meal_payment_id=payment_id)
    await callback.answer()
    await callback.message.answer(
        "📸 Send the payment screenshot now."
        if lang == "EN"
        else "📸 አሁን የክፍያውን screenshot ይላኩ።",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("mealpay_retry:"))
async def retry_payment(callback: types.CallbackQuery, state: FSMContext, db: Database):
    order_id = int(callback.data.split(":", 1)[1])
    repo = get_meal_plan_repository(db)
    try:
        payment = await repo.create_retry_payment(order_id, callback.from_user.id)
    except (PermissionError, RecordNotFound, ConcurrentUpdate, ValueError) as exc:
        return await callback.answer(str(exc), show_alert=True)
    await state.set_state(MealPaymentState.awaiting_proof)
    await state.update_data(meal_payment_id=payment["id"])
    await callback.answer()
    await callback.message.answer("📸 Send the new receipt screenshot now.")


@router.message(MealPaymentState.awaiting_proof, F.photo)
async def receive_meal_payment_proof(message: types.Message, state: FSMContext, db: Database, bot: Bot):
    data = await state.get_data()
    payment_id = int(data.get("meal_payment_id") or 0)
    if not payment_id:
        await state.clear()
        return await message.answer("Please reopen your Meal Plan payment and try again.")

    repo = get_meal_plan_repository(db)
    proof_file_id = message.photo[-1].file_id
    try:
        payment, order = await repo.submit_payment_proof(payment_id, message.from_user.id, proof_file_id)
    except (PermissionError, RecordNotFound, ConcurrentUpdate) as exc:
        await state.clear()
        return await message.answer(html.escape(str(exc)))

    await state.clear()
    user = await db.get_user(message.from_user.id)
    lang = (user.get("language") if user else None) or "AM"
    await message.answer(
        "✅ <b>Receipt received.</b> We are checking the transaction details now. You can close this chat; we will notify you when the payment is confirmed."
        if lang == "EN"
        else "✅ <b>ደረሰኙ ደርሶናል።</b> አሁን የክፍያውን ዝርዝር በመፈተሽ ላይ ነን። ክፍያው ሲረጋገጥ Telegram ላይ እናሳውቅዎታለን።",
        parse_mode="HTML",
    )
    asyncio.create_task(_verify_and_handoff(bot, db, payment, order, proof_file_id))


async def _verify_and_handoff(bot: Bot, db: Database, payment, order, proof_file_id: str) -> None:
    repo = get_meal_plan_repository(db)
    payload: dict[str, object] = {"outcome": "MANUAL_REVIEW", "receiver_match": False, "provider": None, "reference": None, "api_success": False, "amount_match": False}
    reference = None
    try:
        buf = io.BytesIO()
        await bot.download(proof_file_id, destination=buf)
        buf.seek(0)
        local = await extract_local_data(buf)
        reference = local.get("ref")
        provider = local.get("provider")
        payload["provider"] = provider
        payload["reference"] = reference

        bank_data = {}
        if reference:
            bank_data = await verify_external(reference, provider)
        api_success = bool(bank_data.get("success", False)) if isinstance(bank_data, dict) else False
        receiver_ok = is_hilawe_receiver(str(local.get("raw_text") or ""), bank_data if isinstance(bank_data, dict) else {})
        data = bank_data.get("data", {}) if isinstance(bank_data, dict) else {}
        observed_amount = data.get("amount") if isinstance(data, dict) else None
        if observed_amount in (None, ""):
            observed_amount = local.get("amount_fallback")
        amount_ok = amount_matches(payment["settlement_amount"], observed_amount)

        payload.update({
            "api_success": api_success,
            "receiver_match": bool(receiver_ok),
            "amount_match": amount_ok,
            "observed_amount": str(observed_amount) if observed_amount not in (None, "") else None,
            "outcome": "VERIFIED" if (api_success and receiver_ok and amount_ok) else "MANUAL_REVIEW",
        })
    except Exception as exc:
        logger.exception("Meal payment advisory verification failed")
        payload["error"] = type(exc).__name__
        payload["outcome"] = "MANUAL_REVIEW"

    await repo.store_payment_verification(payment["id"], reference=reference, payload=payload)

    if auto_approve_payments() and payload.get("outcome") == "VERIFIED":
        try:
            queued = await repo.approve_payment_and_queue_generation(payment["id"], processed_by=None)
            await _notify_user_payment_approved(bot, db, queued["order"])
            return
        except Exception:
            logger.exception("Meal payment auto-approval failed; falling back to review")

    chat_id = payment_review_chat_id()
    if not chat_id:
        logger.warning("No Meal Plan payment review chat configured; payment remains safely in PAYMENT_REVIEW")
        return

    user = await db.get_user(payment["user_id"])
    name = html.escape((user.get("full_name") if user else None) or "Member")
    username = html.escape(f"@{user.get('username')}") if user and user.get("username") else "No username"
    expected = _format_amount(payment["expected_amount"], payment["expected_currency"])
    settlement = _format_amount(payment["settlement_amount"], payment["settlement_currency"])
    status_icon = "🟢" if payload.get("outcome") == "VERIFIED" else "🟡"
    caption = (
        f"🥗 <b>MEAL PLAN PAYMENT REVIEW</b>\n"
        f"────────────────────\n"
        f"👤 <b>{name}</b> · {username}\n"
        f"🆔 <code>{payment['user_id']}</code>\n"
        f"📦 Order <code>#{order['id']}</code> · {order['duration_days']} days · {order['service_type']}\n"
        f"💰 Price: <b>{expected}</b>\n"
        f"🏦 Settlement: <b>{settlement}</b>\n"
        f"────────────────────\n"
        f"{status_icon} Verification: <b>{html.escape(str(payload.get('outcome')))}</b>\n"
        f"Provider: <code>{html.escape(str(payload.get('provider') or 'unknown'))}</code>\n"
        f"Reference: <code>{html.escape(str(payload.get('reference') or 'not extracted'))}</code>\n"
        f"Receiver match: <b>{'YES' if payload.get('receiver_match') else 'NO / UNKNOWN'}</b>\n"
        f"Amount match: <b>{'YES' if payload.get('amount_match') else 'NO / UNKNOWN'}</b>\n"
        f"────────────────────\n"
        "Approve only after the receipt is acceptable."
    )
    await bot.send_photo(chat_id, proof_file_id, caption=caption, parse_mode="HTML", reply_markup=_review_markup(payment["id"]))


async def _notify_user_payment_approved(bot: Bot, db: Database, order) -> None:
    user = await db.get_user(order["user_id"])
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
    markup = None
    if frontend_url_is_valid(frontend_url()):
        builder = InlineKeyboardBuilder()
        builder.button(text="🥗 Open Meal Plan", web_app=WebAppInfo(url=frontend_url()))
        markup = builder.as_markup()
    await bot.send_message(order["user_id"], text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data.startswith("mealpay_approve:"))
async def approve_meal_payment(callback: types.CallbackQuery, db: Database, bot: Bot):
    if not is_reviewer(callback.from_user.id):
        return await callback.answer("Not authorized.", show_alert=True)
    payment_id = int(callback.data.split(":", 1)[1])
    repo = get_meal_plan_repository(db)
    try:
        result = await repo.approve_payment_and_queue_generation(payment_id, processed_by=callback.from_user.id)
    except (RecordNotFound, ConcurrentUpdate) as exc:
        return await callback.answer(str(exc), show_alert=True)
    await callback.answer("Payment approved")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply(f"✅ Approved by {html.escape(callback.from_user.full_name)} · generation queued")
    except Exception:
        pass
    await _notify_user_payment_approved(bot, db, result["order"])


@router.callback_query(F.data.startswith("mealpay_reject:"))
async def reject_meal_payment(callback: types.CallbackQuery, db: Database, bot: Bot):
    if not is_reviewer(callback.from_user.id):
        return await callback.answer("Not authorized.", show_alert=True)
    payment_id = int(callback.data.split(":", 1)[1])
    repo = get_meal_plan_repository(db)
    try:
        result = await repo.reject_payment_for_retry(payment_id, processed_by=callback.from_user.id)
    except (RecordNotFound, ConcurrentUpdate) as exc:
        return await callback.answer(str(exc), show_alert=True)
    await callback.answer("Payment rejected")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply(f"❌ Rejected by {html.escape(callback.from_user.full_name)} · customer can retry")
    except Exception:
        pass
    user = await db.get_user(result["order"]["user_id"])
    lang = (user.get("language") if user else None) or "AM"
    text = (
        "The receipt could not be approved. Please check the transfer and submit a new clear receipt."
        if lang == "EN"
        else "የላኩት ደረሰኝ ሊፈቀድ አልቻለም። እባክዎ ክፍያውን ያረጋግጡ እና አዲስ ግልጽ ደረሰኝ ይላኩ።"
    )
    await bot.send_message(result["order"]["user_id"], text, reply_markup=_retry_markup(result["order"]["id"]))
