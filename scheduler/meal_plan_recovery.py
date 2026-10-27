"""High-Conversion Meal Plan Recovery Engine.

Targeting abandoned meal plan orders (state = 'AWAITING_PAYMENT') with calibrated
tiered discounts, zero-fluff visual typography, and low-latency delivery.

Business Rules:
- 7-day plan: 800 ETB discount (3,000 -> 2,200 ETB, 27% OFF)
- 14-day plan: 1,000 ETB discount (4,000 -> 3,000 ETB, 25% OFF)
- 30-day plan: 1,200 ETB discount (6,500 -> 5,300 ETB, 18% OFF)
- 30-day follow-up: 1,400 ETB discount (8,000 -> 6,600 ETB, 18% OFF)
- Foreigners (USD): $0 discount (No discount rule)
- Bank Accounts: CBE and BOA ONLY (Telebirr excluded)
- Gender Conjugation: Pure Male or Pure Female (Zero slash grammar)
- Delivery Architecture: Concurrency Semaphore(25), Atomic DB Pre-Sync, RetryAfter handling
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
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

logger = logging.getLogger("MEAL_PLAN_RECOVERY")
router = Router(name="meal_plan_recovery")


class MealPlanRecoveryStates(StatesGroup):
    confirm_dispatch = State()


def compute_plan_discount(duration_days: int, service_type: str, region: str, currency: str, original_amount: float) -> Dict[str, Any]:
    """Computes exact tiered discount according to Coach Hilawe business rules."""
    region_clean = (region or "").upper().strip()
    curr_clean = (currency or "").upper().strip()

    # Rule: Foreigners / Diaspora (USD / non-Ethiopia) receive ZERO discount
    if region_clean != "ETHIOPIA" or curr_clean != "ETB":
        return {
            "has_discount": False,
            "discount_amount": 0,
            "discounted_amount": int(original_amount),
            "discount_pct": 0,
            "is_foreign": True,
        }

    # Domestic Tiered Discounts (ETB)
    if duration_days == 7:
        discount = 800.0
    elif duration_days == 14:
        discount = 1000.0
    elif duration_days == 30 and service_type == "FOLLOW_UP":
        discount = 1400.0
    elif duration_days == 30:
        discount = 1200.0
    else:
        discount = 1000.0

    discounted = max(original_amount - discount, 500.0)
    pct = round((discount / original_amount) * 100) if original_amount > 0 else 0

    return {
        "has_discount": True,
        "discount_amount": int(discount),
        "discounted_amount": int(discounted),
        "discount_pct": pct,
        "is_foreign": False,
    }


def render_recovery_message(user_row: Dict[str, Any]) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    """Renders hyper-personalized recovery copy with exact 7-emoji budget and zero-slash grammar."""
    full_name = user_row.get("full_name") or ""
    first_name = full_name.strip().split()[0].capitalize() if full_name else "ወዳጄ"

    answers = user_row.get("answers") or {}
    if isinstance(answers, str):
        try:
            answers = json.loads(answers)
        except Exception:
            answers = {}

    profile = user_row.get("nutrition_profile") or {}
    if isinstance(profile, str):
        try:
            profile = json.loads(profile)
        except Exception:
            profile = {}

    calculation_sex = (answers.get("calculation_sex") or user_row.get("gender") or "MALE").upper().strip()
    is_female = calculation_sex == "FEMALE"

    duration_days = user_row.get("duration_days") or 7
    service_type = user_row.get("service_type") or "PLAN"
    region = user_row.get("region") or "ETHIOPIA"
    currency = user_row.get("currency") or "ETB"
    original_amount = float(user_row.get("amount") or 3000.0)

    pricing = compute_plan_discount(duration_days, service_type, region, currency, original_amount)

    cur_wt = answers.get("current_weight_kg", "")
    target_wt = answers.get("target_weight_kg", "")
    kcal = profile.get("target_kcal", "")
    protein = profile.get("protein_g", "")

    # Clean fallback strings if values are missing
    cur_wt_str = f"<b>{cur_wt} ኪ.ግ</b>" if cur_wt else "ያለህን"
    target_wt_str = f"ወደ <b>{target_wt} ኪ.ግ</b>" if target_wt else ""
    kcal_str = f"<b>{kcal:,} kcal</b>" if kcal else "የተመጠነ ካሎሪ"
    protein_str = f"<b>{protein}g</b>" if protein else "ተፈላጊውን ፕሮቲን"

    # Cuisine Adaptation
    cuisine = (answers.get("cuisine_style") or "ETHIOPIAN").upper().strip()
    if cuisine == "ETHIOPIAN":
        cuisine_text = "ሙሉ በሙሉ በሀገራችን ምግቦች የተበጀውን"
    elif cuisine == "MIXED":
        cuisine_text = "በሀገራችንና በቀላል ዘመናዊ ምግቦች የተዋቀረውን"
    else:
        cuisine_text = "በቀላሉ በሚገኙ ተመጣጣኝ ምግቦች የተዘጋጀውን"

    # Foreigner Flow (USD)
    if pricing["is_foreign"]:
        usd_text = (
            f"🥗 <b>Hello {first_name}, Coach Hilawe here.</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"I have finalized your personalized metabolic calculation based on your biometric profile:\n\n"
            f"📊 <b>Your Calibrated Targets:</b>\n"
            f"• Daily Calorie Target: <b>{kcal:,} kcal</b>\n"
            f"• Daily Protein Floor: <b>{protein}g</b>\n"
            f"• Hydration Goal: <b>{profile.get('water_target_l', '2.5')} Liters/day</b>\n\n"
            f"⚠️ <b>Priority Allocation Notice:</b>\n"
            f"Each personalized meal plan requires hands-on review. Your {duration_days}-Day custom blueprint is currently locked in my dashboard awaiting activation.\n\n"
            f"💳 <b>Activation Total:</b> <code>${int(original_amount)} USD</code>\n\n"
            f"👇 <b>Tap below to complete activation and unlock your plan:</b>"
        )
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"💳 Unlock {duration_days}-Day Plan (${int(original_amount)} USD)", callback_data=f"mp_pay_{user_row.get('order_id')}")]
            ]
        )
        return usd_text, markup

    # Domestic Flow (ETB) - Strict Zero-Slash Grammar
    disc_amt = pricing["discount_amount"]
    final_amt = pricing["discounted_amount"]
    disc_pct = pricing["discount_pct"]
    orig_amt_int = int(original_amount)

    cbe_acc = settings.BANK_CBE or "1000599533641"
    cbe_name = settings.BANK_CBE_NAME or "Hilawe Semma"
    boa_acc = settings.BANK_BOA or "53299555"
    boa_name = settings.BANK_BOA_NAME or "Hilawe Semma"

    if is_female:
        text = (
            f"🥗 <b>ሰላም {first_name}፣ አሰልጣኝ ህላዌ ነኝ።</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"በሲስተሜ የሞላሽውን የምግብ ፍላጎትና የሰውነት መረጃ በጥንቃቄ ገምግሜዋለሁ።\n\n"
            f"አሁን ያለሽ ክብደት {cur_wt_str} ሲሆን፣ ግብሽ ደግሞ {target_wt_str} የሰውነት ለውጥ ማምጣት እንደሆነ አይቻለሁ።\n\n"
            f"📊 ሜታቦሊዝምሽን በጥናት አስልቼ የዕለት የካሎሪ ፍላጎትሽን በ {kcal_str} እና የፕሮቲን መጠንሽን በ {protein_str} መጥኜ {cuisine_text} እቅድሽን ሰርቼ ጨርሻለሁ።\n\n"
            f"⚠️ <b>አስቸኳይ ማሳሰቢያ፦</b> እያንዳንዱን እቅድ በግል ስለምከታተል አሁን ላይ ከ 5 ሰዎች በላይ ማስተናገድ አልችልም። ክፍያሽን በዚህ 2 ሰዓት ውስጥ የምትፈጽሚ ከሆነ የ {disc_amt:,} ብር ስጦታ አበረክትልሻለሁ።\n\n"
            f"🎁 <b>የ 2 ሰዓት የ{disc_amt:,} ብር ልዩ ስጦታ፦</b>\n"
            f"├ መደበኛ ዋጋ፦ <s>{orig_amt_int:,} ብር</s>\n"
            f"└ 🔥 <b>ለ{first_name} የተደረገ ዋጋ፦ {final_amt:,} ብር ብቻ! ({disc_pct}% ቅናሽ)</b>\n\n"
            f"የቀረችውን ክፍያ በባንክ ፈጽመሽ ደረሰኙን እዚህ ላኪልኝ፤ እቅድሽን ወዲያውኑ ልኬልሽ አብረን እንጀምራለን፦\n\n"
            f"🏦 <b>የክፍያ አማራጮች (ለመቅዳት ቁጥሩን ይንኩት)፦</b>\n"
            f"• <b>የኢትዮጵያ ንግድ ባንክ (CBE)፦</b>\n"
            f"<code>{cbe_acc}</code>\n"
            f"👤 <i>{cbe_name}</i>\n\n"
            f"• <b>አቢሲኒያ ባንክ (BOA)፦</b>\n"
            f"<code>{boa_acc}</code>\n"
            f"👤 <i>{boa_name}</i>\n\n"
            f"📲 <b>ደረሰኙን በፎቶ ወይም የገባልሽን የባንክ SMS Message ኮፒ አድርገሽ እዚህ ላኪልኝ።</b>\n\n"
            f"ማንኛውም ጥያቄ ካለሽ በ @CoachHilaweSupportBot በኩል አናግረኝ።"
        )
    else:
        text = (
            f"🥗 <b>ሰላም {first_name}፣ አሰልጣኝ ህላዌ ነኝ።</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"በሲስተሜ የሞላኸውን የምግብ ፍላጎትና የሰውነት መረጃ በጥንቃቄ ገምግሜዋለሁ።\n\n"
            f"አሁን ያለህ ክብደት {cur_wt_str} ሲሆን፣ ግብህ ደግሞ {target_wt_str} የሰውነት ለውጥ ማምጣት እንደሆነ አይቻለሁ።\n\n"
            f"📊 ሜታቦሊዝምህን በጥናት አስልቼ የዕለት የካሎሪ ፍላጎትህን በ {kcal_str} እና የፕሮቲን መጠንህን በ {protein_str} መጥኜ {cuisine_text} እቅድህን ሰርቼ ጨርሻለሁ።\n\n"
            f"⚠️ <b>አስቸኳይ ማሳሰቢያ፦</b> እያንዳንዱን እቅድ በግል ስለምከታተል አሁን ላይ ከ 5 ሰዎች በላይ ማስተናገድ አልችልም። ክፍያህን በዚህ 2 ሰዓት ውስጥ የምትፈጽም ከሆነ የ {disc_amt:,} ብር ስጦታ አበረክትልሃለሁ።\n\n"
            f"🎁 <b>የ 2 ሰዓት የ{disc_amt:,} ብር ልዩ ስጦታ፦</b>\n"
            f"├ መደበኛ ዋጋ፦ <s>{orig_amt_int:,} ብር</s>\n"
            f"└ 🔥 <b>ለ{first_name} የተደረገ ዋጋ፦ {final_amt:,} ብር ብቻ! ({disc_pct}% ቅናሽ)</b>\n\n"
            f"የቀረችውን ክፍያ በባንክ ፈጽመህ ደረሰኙን እዚህ ላክልኝ፤ እቅድህን ወዲያውኑ ልኬልህ አብረን እንጀምራለን፦\n\n"
            f"🏦 <b>የክፍያ አማራጮች (ለመቅዳት ቁጥሩን ይንኩት)፦</b>\n"
            f"• <b>የኢትዮጵያ ንግድ ባንክ (CBE)፦</b>\n"
            f"<code>{cbe_acc}</code>\n"
            f"👤 <i>{cbe_name}</i>\n\n"
            f"• <b>አቢሲኒያ ባንክ (BOA)፦</b>\n"
            f"<code>{boa_acc}</code>\n"
            f"👤 <i>{boa_name}</i>\n\n"
            f"📲 <b>ደረሰኙን በፎቶ ወይም የገባልህን የባንክ SMS Message ኮፒ አድርገህ እዚህ ላክልኝ።</b>\n\n"
            f"ማንኛውም ጥያቄ ካለህ በ @CoachHilaweSupportBot በኩል አናግረኝ።"
        )

    return text, None


async def execute_meal_plan_recovery_broadcast(
    bot: Bot,
    admin_id: int,
    dry_run: bool = False
) -> Dict[str, Any]:
    """Production-grade execution pipeline modeled directly after scheduler/broadcast.py."""
    query = """
        SELECT 
            mo.id as order_id,
            mo.user_id,
            u.full_name,
            u.username,
            u.gender,
            mo.duration_days,
            mo.service_type,
            mo.region,
            mo.currency,
            mo.amount,
            i.answers,
            i.nutrition_profile
        FROM meal_orders mo
        JOIN meal_intakes i ON mo.intake_id = i.id
        JOIN users u ON mo.user_id = u.telegram_id
        WHERE mo.state = 'AWAITING_PAYMENT'
        ORDER BY mo.created_at DESC
    """
    records = await db._pool.fetch(query)
    targets = [dict(r) for r in records]

    if not targets:
        logger.warning("No abandoned meal plan orders found.")
        return {"total": 0, "delivered": 0, "failed": 0, "blocked": 0}

    logger.info(f"Targeting {len(targets)} abandoned meal plan leads (dry_run={dry_run})...")

    # Dry-Run / Preview Mode
    if dry_run:
        sample_male = next((t for t in targets if (t.get('answers') or {}).get('calculation_sex') == 'MALE'), targets[0])
        sample_female = next((t for t in targets if (t.get('answers') or {}).get('calculation_sex') == 'FEMALE'), None)

        preview_male, _ = render_recovery_message(sample_male)
        preview_female, _ = render_recovery_message(sample_female) if sample_female else ("No female sample", None)

        report = (
            f"🧪 <b>MEAL PLAN RECOVERY PREVIEW (DRY-RUN)</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👥 <b>Total Targets in Awaiting Payment:</b> <code>{len(targets)}</code> users\n"
            f"💰 <b>Total Pipeline Value:</b> <code>{sum(float(t['amount']) for t in targets):,.2f} ETB/USD</code>\n\n"
            f"<b>Sample 1 (Male Preview):</b>\n\n{preview_male}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Sample 2 (Female Preview):</b>\n\n{preview_female}"
        )
        await bot.send_message(admin_id, report, parse_mode="HTML")
        return {"total": len(targets), "dry_run": True}

    # STEP 1: ATOMIC DATABASE PRE-SYNC
    # Synchronize Postgres expected_amount BEFORE dispatching messages so verification succeeds instantly
    sync_records = []
    for t in targets:
        disc = compute_plan_discount(t['duration_days'], t['service_type'], t['region'], t['currency'], float(t['amount']))
        sync_records.append((disc['discounted_amount'], t['order_id']))

    await db._pool.executemany("""
        UPDATE meal_payments 
        SET expected_amount = $1, updated_at = NOW()
        WHERE order_id = $2 AND status = 'PENDING'
    """, sync_records)
    logger.info("Synchronized discounted expected_amounts in meal_payments table.")

    # STEP 2: CONCURRENT PACED DISPATCH (Semaphore=25, Sleep=0.06s)
    semaphore = asyncio.Semaphore(25)
    stats = {"total": len(targets), "delivered": 0, "failed": 0, "blocked": 0}

    async def send_to_lead(target: Dict[str, Any]):
        uid = target["user_id"]
        async with semaphore:
            try:
                msg_text, markup = render_recovery_message(target)
                await bot.send_message(
                    chat_id=uid,
                    text=msg_text,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                stats["delivered"] += 1
                logger.info(f"✅ Recovery message delivered to: {uid} ({target.get('full_name')})")

            except TelegramForbiddenError:
                stats["blocked"] += 1
                logger.warning(f"🚫 User {uid} has blocked the bot.")

            except TelegramRetryAfter as retry:
                logger.warning(f"⏳ Flood control hit. Sleeping {retry.retry_after}s for {uid}...")
                await asyncio.sleep(retry.retry_after)
                try:
                    msg_text, markup = render_recovery_message(target)
                    await bot.send_message(chat_id=uid, text=msg_text, reply_markup=markup, parse_mode="HTML")
                    stats["delivered"] += 1
                except Exception as retry_err:
                    stats["failed"] += 1
                    logger.error(f"❌ Retry failed for {uid}: {retry_err}")

            except Exception as exc:
                stats["failed"] += 1
                logger.error(f"❌ Failed to dispatch recovery message to {uid}: {exc}")

            await asyncio.sleep(settings.BROADCAST_BATCH_SLEEP or 0.06)

    await asyncio.gather(*(send_to_lead(t) for t in targets))

    # STEP 3: DISPATCH ADMIN SUMMARY REPORT
    summary = (
        f"🏁 <b>MEAL PLAN RECOVERY BROADCAST COMPLETE</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Total Targets:</b> <code>{stats['total']}</code>\n"
        f"✅ <b>Delivered:</b> <code>{stats['delivered']}</code>\n"
        f"🚫 <b>Blocked Bot:</b> <code>{stats['blocked']}</code>\n"
        f"❌ <b>Failed:</b> <code>{stats['failed']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"ℹ️ <i>Lead accounts are synced with discounted expected_amounts for instant receipt verification.</i>"
    )
    await bot.send_message(admin_id, summary, parse_mode="HTML")
    return stats


# --- Admin Interactive Handlers ---

@router.message(Command("mealplan_recovery_dryrun"), F.from_user.id.in_(settings.ADMIN_IDS))
async def cmd_mealplan_recovery_dryrun(message: types.Message, bot: Bot):
    """Admin command to safely preview the recovery blast without touching live leads."""
    await message.answer("🔍 Generating recovery blast preview from live database...")
    await execute_meal_plan_recovery_broadcast(bot, message.from_user.id, dry_run=True)


@router.message(Command("mealplan_recovery_launch"), F.from_user.id.in_(settings.ADMIN_IDS))
async def cmd_mealplan_recovery_launch(message: types.Message, state: FSMContext):
    """Admin command initiating live recovery blast with explicit double confirmation."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 Confirm & Launch Recovery Blast", callback_data="confirm_mealplan_recovery")
    kb.button(text="❌ Abort", callback_data="cancel_mealplan_recovery")
    kb.adjust(1)

    await message.answer(
        "⚠️ <b>CONFIRMATION REQUIRED</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "You are about to dispatch the hyper-personalized recovery blast to all abandoned meal plan checkouts.\n\n"
        "This will:\n"
        "1. Atomically sync the discounted prices into PostgreSQL\n"
        "2. Deliver CBE & BOA payment details to active leads\n\n"
        "Are you sure you want to proceed?",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(MealPlanRecoveryStates.confirm_dispatch)


@router.callback_query(MealPlanRecoveryStates.confirm_dispatch, F.data == "confirm_mealplan_recovery")
async def on_confirm_mealplan_recovery(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.edit_text(
        "⏳ <b>Recovery Dispatch In Progress...</b>\n"
        "Dispatching concurrent workers. Check your DM for the final report.",
        parse_mode="HTML"
    )
    await state.clear()
    asyncio.create_task(execute_meal_plan_recovery_broadcast(bot, callback.from_user.id, dry_run=False))


@router.callback_query(MealPlanRecoveryStates.confirm_dispatch, F.data == "cancel_mealplan_recovery")
async def on_cancel_mealplan_recovery(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Meal plan recovery blast cancelled.", parse_mode="HTML")
