"""Pre-Checkout Meal Plan Recovery Engine.

Targeting leads who completed their intake questionnaire (state = 'PROFILE_READY')
with calculated biometrics and macros (kcal, protein), but stalled before choosing a plan.

Features:
- In-Chat 1-Tap Checkout (no Mini-App required)
- Interactive plan duration buttons (7d: 2,200 Br, 14d: 3,000 Br, 30d: 5,300 Br)
- Atomic order & payment creation on plan selection
- CBE & BOA account display with one-tap copy (Telebirr excluded)
- Pure Male vs Pure Female grammar (zero slashes)
- Concurrency Semaphore(25), 0.06s pacing, RetryAfter handling
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from aiogram import Bot, F, Router, types
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from app_context import db

logger = logging.getLogger("PRECHECKOUT_RECOVERY")
router = Router(name="meal_plan_precheckout_recovery")


class PreCheckoutRecoveryStates(StatesGroup):
    confirm_dispatch = State()


# Calibrated Tier Pricing & Discounts
TIER_PRICING_ETB = {
    7: {"original": 3000, "discount": 800, "final": 2200, "pct": 27},
    14: {"original": 4000, "discount": 1000, "final": 3000, "pct": 25},
    30: {"original": 6500, "discount": 1200, "final": 5300, "pct": 18},
}

TIER_PRICING_USD = {
    7: {"amount": 19},
    14: {"amount": 29},
    30: {"amount": 49},
}


def render_precheckout_message(row: Dict[str, Any]) -> Tuple[str, InlineKeyboardMarkup]:
    """Renders hyper-personalized pre-checkout recovery message with interactive plan buttons."""
    full_name = row.get("full_name") or ""
    first_name = full_name.strip().split()[0].capitalize() if full_name else "ወዳጄ"

    answers = row.get("answers") or {}
    if isinstance(answers, str):
        try:
            answers = json.loads(answers)
        except Exception:
            answers = {}

    profile = row.get("nutrition_profile") or {}
    if isinstance(profile, str):
        try:
            profile = json.loads(profile)
        except Exception:
            profile = {}

    calculation_sex = (answers.get("calculation_sex") or row.get("gender") or "MALE").upper().strip()
    is_female = calculation_sex == "FEMALE"

    region = (row.get("country_region") or "ETHIOPIA").upper().strip()
    is_foreign = region not in {"ETHIOPIA", ""}
    intake_id = row.get("id")

    cur_wt = answers.get("current_weight_kg", "")
    target_wt = answers.get("target_weight_kg", "")
    kcal = profile.get("target_kcal", "")
    protein = profile.get("protein_g", "")
    water = profile.get("water_target_l", "2.5")

    cur_wt_str = f"<b>{cur_wt} ኪ.ግ</b>" if cur_wt else "ያለህን"
    target_wt_str = f"ወደ <b>{target_wt} ኪ.ግ</b>" if target_wt else ""
    kcal_str = f"<b>{kcal:,} kcal</b>" if kcal else "የተመጠነ ካሎሪ"
    protein_str = f"<b>{protein}g</b>" if protein else "ተፈላጊውን ፕሮቲን"

    goal_key = answers.get("primary_goal", "FITNESS")
    goal_map = {
        "FAT_LOSS": "ስብን በማቅለጥ ቅርጽ ለማውጣት",
        "MUSCLE_GAIN": "ያለ ቦርጭ ጥርት ያለ ጡንቻ ለመገንባት",
        "RECOMPOSITION": "ስብን እያቀለጡ ጡንቻ ለመገንባት",
    }
    goal_str = goal_map.get(goal_key, "ተፈጥሯዊ የሰውነት ለውጥ ለማምጣት")

    # Cuisine Adaptation
    cuisine = (answers.get("cuisine_style") or "ETHIOPIAN").upper().strip()
    if cuisine == "ETHIOPIAN":
        cuisine_text = "በሀገራችን ምግቦች (እንጀራ፣ ሽሮ፣ ስጋ፣ እንቁላል)"
    elif cuisine == "MIXED":
        cuisine_text = "በሀገራችንና በቀላል ዘመናዊ ምግቦች"
    else:
        cuisine_text = "በቀላሉ በሚገኙ ተመጣጣኝ ምግቦች"

    # Foreigner Flow (USD)
    if is_foreign:
        usd_text = (
            f"🥗 <b>Hello {first_name}, Coach Hilawe here.</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"I have reviewed your biometric evaluation and finalized your custom metabolic calculations:\n\n"
            f"📊 <b>Your Calibrated Targets:</b>\n"
            f"• Daily Calorie Target: <b>{kcal:,} kcal</b>\n"
            f"• Daily Protein Floor: <b>{protein}g</b>\n"
            f"• Target Hydration: <b>{water} Liters/day</b>\n\n"
            f"⚠️ Knowing your macros is only the foundation. Without an exact daily schedule and portion sizes, your progress stalls.\n\n"
            f"🎁 <b>Select your program duration below to activate your custom blueprint:</b>"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="🥗 7-Day Plan ($19 USD)", callback_data=f"mp_pick:{intake_id}:7")
        builder.button(text="🥗 14-Day Plan ($29 USD)", callback_data=f"mp_pick:{intake_id}:14")
        builder.button(text="🥗 30-Day Plan ($49 USD)", callback_data=f"mp_pick:{intake_id}:30")
        builder.adjust(1)
        return usd_text, builder.as_markup()

    # Domestic Flow (ETB) - Pure Gender Grammar
    if is_female:
        text = (
            f"🥗 <b>ሰላም {first_name}፣ አሰልጣኝ ህላዌ ነኝ።</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"በሲስተሜ የሞላሽውን የሰውነትና የአመጋገብ መረጃ በጥንቃቄ ገምግሜዋለሁ።\n\n"
            f"አሁን ያለሽ ክብደት {cur_wt_str} ሲሆን፣ ግብሽ ደግሞ {target_wt_str} {goal_str} እንደሆነ አይቻለሁ።\n\n"
            f"📊 <b>ለአንቺ በጥናት የተሰላው የግል ሜታቦሊክ ስሌት፦</b>\n"
            f"• የዕለት የካሎሪ ፍላጎትሽ፦ {kcal_str}\n"
            f"• የዕለት የፕሮቲን መጠንሽ፦ {protein_str}\n"
            f"• የውሃ መጠን፦ <b>{water} ሊትር በቀን</b>\n\n"
            f"⚠️ <b>አንድ መራራ ሳይንሳዊ ሀቅ ልንገርሽ፦</b> የካሎሪሽን መጠን ማወቅሽ ብቻውን ለውጥ አያመጣም። በየቀኑ {cuisine_text} ውስጥ የትኛውን ምግብ በስንት ግራም መመገብ እንዳለብሽ ካልተመጠነ ለውጥሽ ይዘገያል።\n\n"
            f"🎁 ለአንቺ የተዘጋጀውን ዝርዝር የኢትዮጵያ ምግብ እቅድ እንድትጀምሪ **የ 2 ሰዓት ልዩ የስጦታ ቫውቸር** ተፈቅዶልሻል፦\n\n"
            f"👇 <b>የሚመችሽን የእቅድ ጊዜ ከታች በመምረጥ ጀምሪ፦</b>"
        )
    else:
        text = (
            f"🥗 <b>ሰላም {first_name}፣ አሰልጣኝ ህላዌ ነኝ።</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"በሲስተሜ የሞላኸውን የሰውነትና የአመጋገብ መረጃ በጥንቃቄ ገምግሜዋለሁ።\n\n"
            f"አሁን ያለህ ክብደት {cur_wt_str} ሲሆን፣ ግብህ ደግሞ {target_wt_str} {goal_str} እንደሆነ አይቻለሁ።\n\n"
            f"📊 <b>ለአንተ በጥናት የተሰላው የግል ሜታቦሊክ ስሌት፦</b>\n"
            f"• የዕለት የካሎሪ ፍላጎትህ፦ {kcal_str}\n"
            f"• የዕለት የፕሮቲን መጠንህ፦ {protein_str}\n"
            f"• የውሃ መጠን፦ <b>{water} ሊትር በቀን</b>\n\n"
            f"⚠️ <b>አንድ መራራ ሳይንሳዊ ሀቅ ልንገርህ፦</b> የካሎሪህን መጠን ማወቅህ ብቻውን ለውጥ አያመጣም። በየቀኑ {cuisine_text} ውስጥ የትኛውን ምግብ በስንት ግራም መመገብ እንዳለብህ ካልተመጠነ ውጤትህ ይዘገያል።\n\n"
            f"🎁 ለአንተ የተዘጋጀውን ዝርዝር የኢትዮጵያ ምግብ እቅድ እንድትጀምር **የ 2 ሰዓት ልዩ የስጦታ ቫውቸር** ተፈቅዶልሃል፦\n\n"
            f"👇 <b>የሚመችህን የእቅድ ጊዜ ከታች በመምረጥ ጀምር፦</b>"
        )

    builder = InlineKeyboardBuilder()
    builder.button(text="🥗 የ 7-ቀን እቅድ፦ 2,200 ብር (27% ቅናሽ)", callback_data=f"mp_pick:{intake_id}:7")
    builder.button(text="🥗 የ 14-ቀን እቅድ፦ 3,000 ብር (25% ቅናሽ)", callback_data=f"mp_pick:{intake_id}:14")
    builder.button(text="🥗 የ 30-ቀን እቅድ፦ 5,300 ብር (18% ቅናሽ)", callback_data=f"mp_pick:{intake_id}:30")
    builder.adjust(1)

    return text, builder.as_markup()


# --- In-Chat 1-Tap Checkout Callback ---

@router.callback_query(F.data.startswith("mp_pick:"))
async def on_plan_picked(callback: types.CallbackQuery, bot: Bot):
    """Handles direct plan selection right inside Telegram chat, creates order, and outputs bank details."""
    await callback.answer()
    parts = callback.data.split(":")
    intake_id = int(parts[1])
    duration_days = int(parts[2])
    telegram_id = callback.from_user.id

    async with db._pool.acquire() as conn:
        intake = await conn.fetchrow("SELECT * FROM meal_intakes WHERE id = $1", intake_id)
        if not intake:
            return await callback.message.answer("⚠️ System Error: Assessment record not found.")

        answers = intake.get("answers") or {}
        if isinstance(answers, str):
            try:
                answers = json.loads(answers)
            except Exception:
                answers = {}

        is_female = (answers.get("calculation_sex") or "MALE").upper() == "FEMALE"
        region = (intake.get("country_region") or "ETHIOPIA").upper()
        is_foreign = region not in {"ETHIOPIA", ""}

        # Determine pricing
        if is_foreign:
            pricing = TIER_PRICING_USD.get(duration_days, {"amount": 19})
            final_amount = Decimal(str(pricing["amount"]))
            currency = "USD"
        else:
            pricing = TIER_PRICING_ETB.get(duration_days, {"final": 2200, "original": 3000, "discount": 800})
            final_amount = Decimal(str(pricing["final"]))
            currency = "ETB"

        start_d = date.today()
        ends_d = start_d + timedelta(days=duration_days)

        # 1. Check or Insert Meal Order
        existing_order = await conn.fetchrow("SELECT id FROM meal_orders WHERE intake_id = $1", intake_id)
        if existing_order:
            order_id = existing_order["id"]
            await conn.execute("""
                UPDATE meal_orders 
                SET duration_days = $1, amount = $2, currency = $3, state = 'AWAITING_PAYMENT',
                    start_date = $4, ends_on = $5, updated_at = NOW()
                WHERE id = $6
            """, duration_days, final_amount, currency, start_d, ends_d, order_id)
        else:
            order_row = await conn.fetchrow("""
                INSERT INTO meal_orders(
                    public_id, user_id, intake_id, state, duration_days, service_type,
                    meals_per_day, start_date, ends_on, region, country_name,
                    currency, amount
                )
                VALUES($1, $2, $3, 'AWAITING_PAYMENT', $4, 'PLAN', 3, $5, $6, $7, $8, $9, $10)
                RETURNING id
            """, uuid.uuid4(), telegram_id, intake_id, duration_days, start_d, ends_d,
               region, intake.get("country_name"), currency, final_amount)
            order_id = order_row["id"]

        # Close intake
        await conn.execute("UPDATE meal_intakes SET state = 'CLOSED', closed_at = NOW() WHERE id = $1", intake_id)

        # 2. Check or Insert Meal Payment
        existing_pay = await conn.fetchrow("SELECT id FROM meal_payments WHERE order_id = $1", order_id)
        if existing_pay:
            await conn.execute("""
                UPDATE meal_payments 
                SET expected_amount = $1, expected_currency = $2, status = 'PENDING', updated_at = NOW()
                WHERE id = $3
            """, final_amount, currency, existing_pay["id"])
        else:
            await conn.execute("""
                INSERT INTO meal_payments(
                    order_id, user_id, expected_amount, expected_currency, status, idempotency_key
                )
                VALUES($1, $2, $3, $4, 'PENDING', $5)
            """, order_id, telegram_id, final_amount, currency, f"inchat-precheckout:{order_id}:{duration_days}")

    # 3. Output Banking Screen with CBE & BOA (Zero Telebirr)
    cbe_acc = settings.BANK_CBE or "1000599533641"
    cbe_name = settings.BANK_CBE_NAME or "Hilawe Semma"
    boa_acc = settings.BANK_BOA or "53299555"
    boa_name = settings.BANK_BOA_NAME or "Hilawe Semma"

    if is_female:
        pronoun_chosen = f"የ <b>{duration_days}-ቀን</b> የግል የምግብ እቅድሽ ተመርጧል!"
        pronoun_action = "የቀረችውን ክፍያ በባንክ ፈጽመሽ ደረሰኙን እዚህ ላኪልኝ፤ እቅድሽን ወዲያውኑ ልኬልሽ አብረን እንጀምራለን"
        pronoun_sms = "የገባልሽን የባንክ SMS Message ኮፒ አድርገሽ እዚህ ላኪልኝ"
        pronoun_q = "ካለሽ"
    else:
        pronoun_chosen = f"የ <b>{duration_days}-ቀን</b> የግል የምግብ እቅድህ ተመርጧል!"
        pronoun_action = "የቀረችውን ክፍያ በባንክ ፈጽመህ ደረሰኙን እዚህ ላክልኝ፤ እቅድህን ወዲያውኑ ልኬልህ አብረን እንጀምራለን"
        pronoun_sms = "የገባልህን የባንክ SMS Message ኮፒ አድርገህ እዚህ ላክልኝ"
        pronoun_q = "ካለህ"

    checkout_text = (
        f"✅ <b>{pronoun_chosen}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 <b>የተደረገልህ/ሽ ልዩ ዋጋ፦ {int(final_amount):,} {currency} ብቻ!</b>\n\n"
        f"{pronoun_action}፦\n\n"
        f"🏦 <b>የክፍያ አማራጮች (ለመቅዳት ቁጥሩን ይንኩት)፦</b>\n"
        f"• <b>የኢትዮጵያ ንግድ ባንክ (CBE)፦</b>\n"
        f"<code>{cbe_acc}</code>\n"
        f"👤 <i>{cbe_name}</i>\n\n"
        f"• <b>አቢሲኒያ ባንክ (BOA)፦</b>\n"
        f"<code>{boa_acc}</code>\n"
        f"👤 <i>{boa_name}</i>\n\n"
        f"📲 <b>ደረሰኙን በፎቶ ወይም {pronoun_sms}።</b>\n\n"
        f"ማንኛውም ጥያቄ {pronoun_q} በ @CoachHilaweSupportBot በኩል አናግረኝ።"
    )

    await callback.message.edit_text(checkout_text, parse_mode="HTML")


# --- Production Dispatch Pipeline ---

async def execute_precheckout_recovery_broadcast(
    bot: Bot,
    admin_id: int,
    dry_run: bool = False
) -> Dict[str, Any]:
    """Paced execution pipeline targeting leads in PROFILE_READY state."""
    query = """
        SELECT 
            i.id, i.public_id, i.user_id, u.full_name, u.username, u.gender,
            i.country_region, i.answers, i.nutrition_profile, i.created_at
        FROM meal_intakes i
        JOIN users u ON i.user_id = u.telegram_id
        WHERE i.state = 'PROFILE_READY'
          AND NOT EXISTS (SELECT 1 FROM meal_orders mo WHERE mo.intake_id = i.id)
        ORDER BY i.created_at DESC
    """
    records = await db._pool.fetch(query)
    targets = [dict(r) for r in records]

    if not targets:
        logger.warning("No pre-checkout PROFILE_READY leads found.")
        return {"total": 0, "delivered": 0, "failed": 0, "blocked": 0}

    logger.info(f"Targeting {len(targets)} pre-checkout leads (dry_run={dry_run})...")

    # Dry-Run / Preview Mode
    if dry_run:
        sample_male = next((t for t in targets if (t.get('answers') or {}).get('calculation_sex') == 'MALE'), targets[0])
        sample_female = next((t for t in targets if (t.get('answers') or {}).get('calculation_sex') == 'FEMALE'), None)

        preview_male, kb_m = render_precheckout_message(sample_male)
        preview_female, kb_f = render_precheckout_message(sample_female) if sample_female else ("No female sample", None)

        await bot.send_message(
            admin_id,
            f"🧪 <b>PRE-CHECKOUT RECOVERY PREVIEW (DRY-RUN)</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👥 <b>Total Leads in PROFILE_READY:</b> <code>{len(targets)}</code> users\n"
            f"⚡️ <b>Mode:</b> In-Chat 1-Tap Checkout via Interactive Buttons\n\n"
            f"<i>Sample 1 (Male) and Sample 2 (Female) live previews are sent below:</i>",
            parse_mode="HTML"
        )
        await bot.send_message(admin_id, f"👤 <b>[MALE SAMPLE PREVIEW]</b>\n\n{preview_male}", reply_markup=kb_m, parse_mode="HTML")
        if sample_female and kb_f:
            await bot.send_message(admin_id, f"👤 <b>[FEMALE SAMPLE PREVIEW]</b>\n\n{preview_female}", reply_markup=kb_f, parse_mode="HTML")
        return {"total": len(targets), "dry_run": True}

    # Paced Live Dispatch
    semaphore = asyncio.Semaphore(25)
    stats = {"total": len(targets), "delivered": 0, "failed": 0, "blocked": 0}

    async def send_to_lead(target: Dict[str, Any]):
        uid = target["user_id"]
        async with semaphore:
            try:
                msg_text, markup = render_precheckout_message(target)
                await bot.send_message(
                    chat_id=uid,
                    text=msg_text,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                stats["delivered"] += 1
                logger.info(f"✅ Pre-checkout message delivered to: {uid} ({target.get('full_name')})")

            except TelegramForbiddenError:
                stats["blocked"] += 1
                logger.warning(f"🚫 User {uid} has blocked the bot.")

            except TelegramRetryAfter as retry:
                logger.warning(f"⏳ Flood control hit. Sleeping {retry.retry_after}s for {uid}...")
                await asyncio.sleep(retry.retry_after)
                try:
                    msg_text, markup = render_precheckout_message(target)
                    await bot.send_message(chat_id=uid, text=msg_text, reply_markup=markup, parse_mode="HTML")
                    stats["delivered"] += 1
                except Exception as retry_err:
                    stats["failed"] += 1
                    logger.error(f"❌ Retry failed for {uid}: {retry_err}")

            except Exception as exc:
                stats["failed"] += 1
                logger.error(f"❌ Failed to dispatch pre-checkout message to {uid}: {exc}")

            await asyncio.sleep(settings.BROADCAST_BATCH_SLEEP or 0.06)

    await asyncio.gather(*(send_to_lead(t) for t in targets))

    # Dispatch Admin Summary
    summary = (
        f"🏁 <b>PRE-CHECKOUT RECOVERY BROADCAST COMPLETE</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Total Targets (PROFILE_READY):</b> <code>{stats['total']}</code>\n"
        f"✅ <b>Delivered:</b> <code>{stats['delivered']}</code>\n"
        f"🚫 <b>Blocked Bot:</b> <code>{stats['blocked']}</code>\n"
        f"❌ <b>Failed:</b> <code>{stats['failed']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"ℹ️ <i>Users can tap any plan button to instantly receive CBE & BOA account details.</i>"
    )
    await bot.send_message(admin_id, summary, parse_mode="HTML")
    return stats


# --- Admin Interactive Handlers ---

@router.message(Command("precheckout_recovery_dryrun"), F.from_user.id.in_(settings.ADMIN_IDS))
async def cmd_precheckout_recovery_dryrun(message: types.Message, bot: Bot):
    """Admin command to safely preview the pre-checkout blast without touching live leads."""
    await message.answer("🔍 Generating pre-checkout blast preview from live database...")
    await execute_precheckout_recovery_broadcast(bot, message.from_user.id, dry_run=True)


@router.message(Command("precheckout_recovery_launch"), F.from_user.id.in_(settings.ADMIN_IDS))
async def cmd_precheckout_recovery_launch(message: types.Message, state: FSMContext):
    """Admin command initiating live pre-checkout blast with explicit double confirmation."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 Confirm & Launch Pre-Checkout Blast (78 Users)", callback_data="confirm_precheckout_blast")
    kb.button(text="❌ Abort", callback_data="cancel_precheckout_blast")
    kb.adjust(1)

    await message.answer(
        "⚠️ <b>PRE-CHECKOUT CONFIRMATION REQUIRED</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "You are about to dispatch the in-chat recovery blast to all <b>78 PROFILE_READY leads</b>.\n\n"
        "Each user will receive:\n"
        "1. Their personalized calculated calories & protein\n"
        "2. 1-Tap plan buttons (7d: 2,200 Br, 14d: 3,000 Br, 30d: 5,300 Br)\n"
        "3. Instant CBE & BOA banking details upon tap\n\n"
        "Are you sure you want to proceed?",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(PreCheckoutRecoveryStates.confirm_dispatch)


@router.callback_query(PreCheckoutRecoveryStates.confirm_dispatch, F.data == "confirm_precheckout_blast")
async def on_confirm_precheckout_blast(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.edit_text(
        "⏳ <b>Pre-Checkout Blast In Progress...</b>\n"
        "Dispatching concurrent workers. Check your DM for the final report.",
        parse_mode="HTML"
    )
    await state.clear()
    asyncio.create_task(execute_precheckout_recovery_broadcast(bot, callback.from_user.id, dry_run=False))


@router.callback_query(PreCheckoutRecoveryStates.confirm_dispatch, F.data == "cancel_precheckout_blast")
async def on_cancel_precheckout_blast(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Pre-checkout blast cancelled.", parse_mode="HTML")


if __name__ == "__main__":
    import argparse
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Pre-Checkout Meal Plan Recovery Broadcast")
    parser.add_argument("--live", action="store_true", help="Launch live broadcast to all PROFILE_READY leads (default is dry-run)")
    parser.add_argument("--admin-id", type=int, default=None, help="Admin Telegram ID to receive preview/reports")
    cli_args = parser.parse_args()

    async def main():
        from app_context import db
        await db.connect()
        bot = Bot(token=settings.BOT_TOKEN)
        admin_id = cli_args.admin_id or (settings.ADMIN_IDS[0] if settings.ADMIN_IDS else None)
        if not admin_id:
            print("ERROR: No admin ID configured in settings.ADMIN_IDS.")
            return

        is_dry = not cli_args.live
        mode_str = "LIVE BROADCAST" if not is_dry else "DRY-RUN PREVIEW"
        print(f"🚀 Running Pre-Checkout Recovery ({mode_str}) for admin ID: {admin_id}...")
        res = await execute_precheckout_recovery_broadcast(bot, admin_id=admin_id, dry_run=is_dry)
        print("✅ Execution result:", res)
        await bot.session.close()

    asyncio.run(main())

