"""Phase 1 Ascension Broadcast Engine.

Targets 8-week graduates (>= 56 days ago) who completed their program:
- Beginner graduates -> Upgraded to Intermediate (749 Br)
- Intermediate graduates -> Upgraded to Advanced (749 Br)

Features:
- Simple, airy line-by-line spacing
- Localized header: {first_name} ከ [current] ወደ [next]
- Pure male vs female conjugation
- Atomic deal_price = 749 lock-in for 24 hours
- Paced concurrency (Semaphore=25, 0.06s sleep)
- Both Telegram commands (/ascension_recovery_dryrun, /ascension_recovery_launch) and CLI runner.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
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

logger = logging.getLogger("ASCENSION_BROADCAST")
router = Router(name="ascension_broadcast")

UPGRADE_PRICE = 749
ORIGINAL_PRICE = 1100


class AscensionStates(StatesGroup):
    confirm_dispatch = State()


def render_ascension_message(target: Dict[str, Any]) -> Tuple[str, InlineKeyboardMarkup]:
    """Renders simple, airy, personalized ascension card."""
    full_name = target.get("full_name") or ""
    first_name = full_name.strip().split()[0].capitalize() if full_name else "ወዳጄ"

    lang = (target.get("language") or "AM").upper()
    gender = (target.get("gender") or "MALE").upper()
    is_female = gender == "FEMALE"

    cur_level = (target.get("bought_level") or "BEGINNER").upper()
    target_pid = target.get("target_pid")

    if cur_level == "BEGINNER":
        next_level_am = "መካከለኛ"
        cur_level_am = "ጀማሪ"
        next_level_en = "Intermediate"
        cur_level_en = "Beginner"
    else:
        next_level_am = "አድቫንስድ"
        cur_level_am = "መካከለኛ"
        next_level_en = "Advanced"
        cur_level_en = "Intermediate"

    if lang == "AM":
        greeting = f"{first_name} እህቴ እንዴት ነሽ? አሰልጣኝ ህላዌ ነኝ።" if is_female else f"{first_name} ወንድሜ ሰላም ነህ? አሰልጣኝ ህላዌ ነኝ።"
        congrats = (
            f"የ8 ሳምንት የ{cur_level_am} ፕሮግራምሽን በቁርጠኝነት ስላጠናቀቅሽ በድጋሚ እንኳን ደስ አለሽ!"
            if is_female else
            f"የ8 ሳምንት የ{cur_level_am} ፕሮግራምህን በቁርጠኝነት ስላጠናቀቅክ በድጋሚ እንኳን ደስ አለህ!"
        )
        transition = (
            f"አሁን ሰውነትሽ የመጀመሪያውን ምዕራፍ ጨርሷል። ያገኘሽውን የሰውነት ቅርጽ ይበልጥ ለማጉላትና ወደ ላቀ ደረጃ ለመሸጋገር ትክክለኛው ጊዜ አሁን ነው።"
            if is_female else
            f"አሁን ሰውነትህ የመጀመሪያውን ምዕራፍ ጨርሷል። የተገነባውን ጥንካሬ ይበልጥ ለማጉላትና ወደ ላቀ ደረጃ ለመሸጋገር ትክክለኛው ጊዜ አሁን ነው።"
        )
        cta = (
            f"👇 <b>ከታች ያለውን ቁልፍ ተጭነሽ የ{next_level_am} ደረጃሽን አሁኑኑ ጀምሪ፦</b>"
            if is_female else
            f"👇 <b>ከታች ያለውን ቁልፍ ተጭነህ የ{next_level_am} ደረጃህን አሁኑኑ ጀምር፦</b>"
        )

        benefits = (
            f"⚡️ <b>በ{next_level_am} ደረጃ የምታገኚያቸው አዳዲስ ጥቅሞች፦</b>\n\n"
            f"🔹 <b>የላቀ የጡንቻና ቅርጽ ማጉያ</b> » ይበልጥ እንድትጠነክሪ የተዘጋጁ አዳዲስ ስልቶች\n\n"
            f"🔹 <b>ፈጣን ስብ ማቃጠል</b> » የቀረውን ቦርጭ የሚያጠፉ የተሻሻሉ እንቅስቃሴዎች\n\n"
            f"🔹 <b>ቀጥታ የቪዲዮ መመሪያ</b> » እያንዳንዱን ልምምድ በስልክሽ እያየሽ የምትሰሪበት"
            if is_female else
            f"⚡️ <b>በ{next_level_am} ደረጃ የምታገኛቸው አዳዲስ ጥቅሞች፦</b>\n\n"
            f"🔹 <b>የላቀ የጡንቻ ቅርጽ</b> » ሰውነትህ ይበልጥ እንዲጠነክር የተዘጋጁ አዳዲስ ስልቶች\n\n"
            f"🔹 <b>ፈጣን ስብ ማቃጠል</b> » የቀረውን ቦርጭ የሚያጠፉ የተሻሻሉ እንቅስቃሴዎች\n\n"
            f"🔹 <b>ቀጥታ የቪዲዮ መመሪያ</b> » እያንዳንዱን ልምምድ በስልክህ እያየህ የምትሰራበት"
        )

        text = (
            f"🎓 <b>{first_name} ከ{cur_level_am} ⇾ ወደ {next_level_am} ደረጃ</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{greeting}\n\n"
            f"{congrats}\n\n"
            f"{transition}\n\n"
            f"{benefits}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🏷️ መደበኛ ዋጋ፦ <s>{ORIGINAL_PRICE:,} ብር</s>\n\n"
            f"💎 <b>የተመራቂ ልዩ ዋጋ፦ {UPGRADE_PRICE} ብር ብቻ! (የ351 ብር ቅናሽ)</b>\n\n"
            f"⏱️ <b>ይህ ልዩ ዋጋ የሚቆየው ለቀጣዮቹ 24 ሰዓታት ብቻ ነው።</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{cta}"
        )
        btn_label = f"⚡️ የ{next_level_am} ደረጃን ክፈት ({UPGRADE_PRICE} ብር)"

    else:
        text = (
            f"🎓 <b>{first_name.upper()} FROM {cur_level_en.upper()} ⇾ TO {next_level_en.upper()}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{first_name} 👋 Coach Hilawe here.\n\n"
            f"Congratulations on successfully completing your 8-Week {cur_level_en} Program!\n\n"
            f"Now that your body has mastered this phase, it is the perfect time to elevate your progress and step into the next level.\n\n"
            f"⚡️ <b>WHAT YOU GET IN THE {next_level_en.upper()} SYSTEM:</b>\n\n"
            f"🔹 <b>Targeted Hypertrophy</b> » Advanced routines to build defined lean muscle\n\n"
            f"🔹 <b>Accelerated Fat Burn</b> » Upgraded metabolic circuits to melt stubborn fat\n\n"
            f"🔹 <b>Complete HD Video Library</b> » Step-by-step coaching directly on your phone\n\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🏷️ Regular Price: <s>{ORIGINAL_PRICE:,} ETB</s>\n\n"
            f"💎 <b>Alumni VIP Rate: {UPGRADE_PRICE} ETB Only! (Save 351 ETB)</b>\n\n"
            f"⏱️ <b>This exclusive alumni privilege is active for 24 hours only.</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👇 <b>Tap below to unlock your {next_level_en} System now:</b>"
        )
        btn_label = f"⚡️ Unlock {next_level_en} ({UPGRADE_PRICE} ETB)"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=btn_label, callback_data=f"pay_{target_pid}")]]
    )
    return text, kb


async def fetch_ascension_targets() -> List[Dict[str, Any]]:
    """Fetches Beginner & Intermediate 8-week graduates and maps their next target product."""
    # 1. Fetch all products for fast mapping
    products = await db._pool.fetch("SELECT * FROM products WHERE is_active = TRUE")
    prod_map = {}
    for p in products:
        key = (p["level"].upper(), p["frequency"], p["language"].upper())
        prod_map[key] = p["id"]

    # 2. Fetch graduates
    query = """
        SELECT 
            u.telegram_id, u.full_name, u.username, u.language, u.gender,
            p.id as bought_pid, p.level as bought_level, p.frequency as bought_freq, p.language as bought_lang,
            pay.created_at as paid_at
        FROM payments pay
        JOIN users u ON pay.user_id = u.telegram_id
        JOIN products p ON pay.product_id = p.id
        WHERE pay.status = 'approved'
          AND pay.created_at <= NOW() - INTERVAL '56 days'
          AND p.level IN ('BEGINNER', 'INTERMEDIATE')
        ORDER BY pay.created_at ASC
    """
    records = await db._pool.fetch(query)

    # 3. Exclude anyone who already bought next level
    all_approved = await db._pool.fetch("""
        SELECT user_id, p.level 
        FROM payments pay
        JOIN products p ON pay.product_id = p.id
        WHERE pay.status = 'approved'
    """)
    user_bought_levels: Dict[int, set] = {}
    for a in all_approved:
        user_bought_levels.setdefault(a["user_id"], set()).add(a["level"].upper())

    targets = []
    seen_users = set()

    for r in records:
        uid = r["telegram_id"]
        if uid in seen_users:
            continue

        cur_level = r["bought_level"].upper()
        next_level = "INTERMEDIATE" if cur_level == "BEGINNER" else "ADVANCED"

        # Check if already upgraded
        if next_level in user_bought_levels.get(uid, set()):
            continue

        # Map to next product ID
        freq = r["bought_freq"] or 3
        lang = (r["bought_lang"] or r["language"] or "AM").upper()
        target_pid = prod_map.get((next_level, freq, lang))
        if not target_pid:
            # Fallback to any active product of next level & lang
            target_pid = next((p["id"] for p in products if p["level"].upper() == next_level and p["language"].upper() == lang), None)

        if not target_pid:
            continue

        seen_users.add(uid)
        d = dict(r)
        d["target_pid"] = target_pid
        d["target_level"] = next_level
        targets.append(d)

    return targets


async def execute_ascension_broadcast(bot: Bot, admin_id: int, dry_run: bool = False) -> Dict[str, Any]:
    """Paced execution pipeline targeting 8-week graduates."""
    targets = await fetch_ascension_targets()

    if not targets:
        logger.warning("No eligible ascension graduates found.")
        return {"total": 0, "delivered": 0, "failed": 0, "blocked": 0}

    logger.info(f"Targeting {len(targets)} ascension graduates (dry_run={dry_run})...")

    # Dry-Run / Preview Mode
    if dry_run:
        sample_beg = next((t for t in targets if t["bought_level"] == "BEGINNER"), targets[0])
        sample_inter = next((t for t in targets if t["bought_level"] == "INTERMEDIATE"), None)

        preview_beg, kb_beg = render_ascension_message(sample_beg)
        preview_inter, kb_inter = render_ascension_message(sample_inter) if sample_inter else ("No intermediate sample", None)

        await bot.send_message(
            admin_id,
            f"🧪 <b>ASCENSION BROADCAST PREVIEW (DRY-RUN)</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Total Eligible Graduates:</b> <code>{len(targets)}</code> users\n"
            f"💰 <b>Upgrade Price:</b> <code>{UPGRADE_PRICE} ETB</code> (Original: 1,100 ETB)\n\n"
            f"<i>Live samples for Beginner and Intermediate graduates are below:</i>",
            parse_mode="HTML"
        )
        await bot.send_message(admin_id, preview_beg, reply_markup=kb_beg, parse_mode="HTML")
        if sample_inter and kb_inter:
            await bot.send_message(admin_id, preview_inter, reply_markup=kb_inter, parse_mode="HTML")
        return {"total": len(targets), "dry_run": True}

    # Live Dispatch: Step 1 - Atomic Postgres Lock-in
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    sync_data = [(UPGRADE_PRICE, expires_at, t["target_pid"], t["telegram_id"]) for t in targets]
    await db._pool.executemany("""
        UPDATE users 
        SET deal_price = $1, deal_expires_at = $2, matched_product_id = $3
        WHERE telegram_id = $4
    """, sync_data)
    logger.info("Synchronized deal_price = 749 for all targets in PostgreSQL.")

    # Step 2 - Concurrent Paced Dispatch
    semaphore = asyncio.Semaphore(25)
    stats = {"total": len(targets), "delivered": 0, "failed": 0, "blocked": 0}

    async def send_to_user(target: Dict[str, Any]):
        uid = target["telegram_id"]
        async with semaphore:
            try:
                msg_text, markup = render_ascension_message(target)
                await bot.send_message(chat_id=uid, text=msg_text, reply_markup=markup, parse_mode="HTML")
                stats["delivered"] += 1
                logger.info(f"✅ Ascension delivered to: {uid} ({target.get('full_name')})")

            except TelegramForbiddenError:
                stats["blocked"] += 1
                logger.warning(f"🚫 User {uid} blocked the bot.")

            except TelegramRetryAfter as retry:
                logger.warning(f"⏳ Flood control hit. Sleeping {retry.retry_after}s for {uid}...")
                await asyncio.sleep(retry.retry_after)
                try:
                    msg_text, markup = render_ascension_message(target)
                    await bot.send_message(chat_id=uid, text=msg_text, reply_markup=markup, parse_mode="HTML")
                    stats["delivered"] += 1
                except Exception as retry_err:
                    stats["failed"] += 1
                    logger.error(f"❌ Retry failed for {uid}: {retry_err}")

            except Exception as exc:
                stats["failed"] += 1
                logger.error(f"❌ Failed to dispatch to {uid}: {exc}")

            await asyncio.sleep(settings.BROADCAST_BATCH_SLEEP or 0.06)

    await asyncio.gather(*(send_to_user(t) for t in targets))

    # Step 3 - Dispatch Admin Summary
    summary = (
        f"🏁 <b>ASCENSION BROADCAST COMPLETE</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Total Targets:</b> <code>{stats['total']}</code>\n"
        f"✅ <b>Delivered:</b> <code>{stats['delivered']}</code>\n"
        f"🚫 <b>Blocked Bot:</b> <code>{stats['blocked']}</code>\n"
        f"❌ <b>Failed:</b> <code>{stats['failed']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"ℹ️ <i>Users locked at {UPGRADE_PRICE} ETB for 24 hours. Tapping button triggers CBE & BOA invoice.</i>"
    )
    await bot.send_message(admin_id, summary, parse_mode="HTML")
    return stats


# --- Admin Interactive Handlers ---

@router.message(Command("ascension_recovery_dryrun"), F.from_user.id.in_(settings.ADMIN_IDS))
async def cmd_ascension_recovery_dryrun(message: types.Message, bot: Bot):
    """Admin command to safely preview the ascension blast without touching live users."""
    await message.answer("🔍 Generating ascension blast preview from live database...")
    await execute_ascension_broadcast(bot, message.from_user.id, dry_run=True)


@router.message(Command("ascension_recovery_launch"), F.from_user.id.in_(settings.ADMIN_IDS))
async def cmd_ascension_recovery_launch(message: types.Message, state: FSMContext):
    """Admin command initiating live ascension blast with explicit confirmation."""
    targets = await fetch_ascension_targets()
    kb = InlineKeyboardBuilder()
    kb.button(text=f"🚀 Confirm & Launch Ascension Blast ({len(targets)} Users)", callback_data="confirm_ascension_blast")
    kb.button(text="❌ Abort", callback_data="cancel_ascension_blast")
    kb.adjust(1)

    await message.answer(
        f"⚠️ <b>ASCENSION BROADCAST CONFIRMATION</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"You are about to launch the Ascension broadcast to <b>{len(targets)} graduates</b> (8+ weeks):\n\n"
        f"• Beginner ⇾ Intermediate (749 Br)\n"
        f"• Intermediate ⇾ Advanced (749 Br)\n"
        f"• Locked for 24 hours in DB\n\n"
        f"Are you sure you want to proceed?",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(AscensionStates.confirm_dispatch)


@router.callback_query(AscensionStates.confirm_dispatch, F.data == "confirm_ascension_blast")
async def on_confirm_ascension_blast(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.edit_text(
        "⏳ <b>Ascension Blast In Progress...</b>\n"
        "Dispatching concurrent workers. Check your DM for the final report.",
        parse_mode="HTML"
    )
    await state.clear()
    asyncio.create_task(execute_ascension_broadcast(bot, callback.from_user.id, dry_run=False))


@router.callback_query(AscensionStates.confirm_dispatch, F.data == "cancel_ascension_blast")
async def on_cancel_ascension_blast(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Ascension blast cancelled.", parse_mode="HTML")


if __name__ == "__main__":
    import argparse
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Phase 1 Ascension Broadcast (Beginner & Intermediate Graduates)")
    parser.add_argument("--live", action="store_true", help="Launch live broadcast to graduates (default is dry-run)")
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
        print(f"🚀 Running Ascension Broadcast ({mode_str}) for admin ID: {admin_id}...")
        res = await execute_ascension_broadcast(bot, admin_id=admin_id, dry_run=is_dry)
        print("✅ Execution result:", res)
        await bot.session.close()

    asyncio.run(main())
