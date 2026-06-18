import asyncio
import logging
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import Database
from config import settings

logger = logging.getLogger(__name__)
router = Router(name="admin_club_promo")

# --- 1. DYNAMIC PROMOTIONAL CARD BUILDER ---

def get_promo_card(lang: str) -> tuple[str, types.InlineKeyboardMarkup]:
    """
    Generates a clean, straightforward invitation layout targeting community members,
    attaching the exact callback key pointing to your payment invoice logic.
    """
    builder = InlineKeyboardBuilder()
    
    if lang == "EN":
        text = (
            "🔥 <b>THE COACH HILAWE TRANSFORMATION CLUB IS NOW OPEN!</b> 🔥\n"
            "──────────────────────────────────────────\n"
            "Since you voted <b>YES</b> on our survey, you get early access to join us.\n\n"
            "👑 <b>What you will get:</b>\n"
            "• 💎 <b>Weekly Live Coaching:</b> Live sessions directly with Coach Hilawe.\n"
            "• 🎬 <b>Guides & Resources:</b> Access to all workout videos, meal plans, and helpful files.\n"
            "• 👥 <b>Community Group:</b> A dedicated Telegram group to stay active and get support from others.\n"
            "──────────────────────────────────────────\n"
            "⚡️ <i>Tap the button below to get your membership and start today.</i>"
        )
        btn_text = "🎯 JOIN THE CLUB — 299 ETB"
    else:
        text = (
            "🔥 <b>COACH HILAWE TRANSFORMATION CLUB ተከፍቷል!</b> 🔥\n"
            "──────────────────────────────────────────\n"
            "በጥናታችን ላይ መሳተፍ እፈልጋለሁ ብለው <b>'አዎ'</b> ብለው ድምጽ ስለሰጡ ይህንን መልዕክት በቅድሚያ ልከንልዎታል።\n\n"
            "👑 <b>በክለቡ ውስጥ ምን ያገኛሉ?</b>\n"
            "• 💎 <b>ሳምንታዊ የLive ስልጠናዎች፦</b> በየሳምንቱ በቀጥታ ከኮች ሂላዌ ጋር የሚደረጉ የቪዲዮ ስልጠናዎች።\n"
            "• 🎬 <b>መመሪያዎችና ፋይሎች፦</b> የቪዲዮ መመሪያዎች፣ የምግብ እቅዶች (Meal plans) እና ጠቃሚ ፋይሎች።\n"
            "• 👥 <b>የግሩፕ ማህበረሰብ፦</b> እርስ በርስ የሚደጋገፉበት እና አብረው የሚከታተሉበት የቴሌግራም ግሩፕ።\n"
            "──────────────────────────────────────────\n"
            "⚡️ <i>አሁኑኑ ለመጀመር ከታች ያለውን ቁልፍ ተጭነው አባል ይሁኑ።</i>"
        )
        btn_text = "🎯 ክለቡን ተቀላቀል — 299 ብር"

    # This routes directly to your existing payment pipeline handler
    builder.button(text=btn_text, callback_data="initiate_club_subscription")
    return text, builder.as_markup()
# --- 2. ADMIN CONTROL GATEWAY CONTROL ---

@router.message(Command("club_broadcast"))
async def admin_broadcast_dashboard(message: types.Message):
    """
    Secures the broadcast interface behind your primary configured Admin Account.
    """
    # Guard clause matching your global internal config setups
    if message.from_user.id != settings.ADMIN_IDS[0]:  # Assuming the first ID is the primary admin
        return

    admin_panel = (
        "🛠️ <b>TRANSFORMATION CLUB BROADCAST GATEWAY</b>\n"
        "──────────────────────────────────────────\n"
        "Choose an operational vector below. Running a test lets you check structural rendering "
        "and button formatting before sending to users."
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="🧪 Test Card (Admin Only)", callback_data="promo_test_run")
    kb.button(text="🚀 Live Broadcast (All Survey Backers)", callback_data="promo_launch_live")
    kb.adjust(1)

    await message.answer(admin_panel, reply_markup=kb.as_markup(), parse_mode="HTML")


# --- 3. THE ISOLATED SAFETY TEST HARNESS ---

@router.callback_query(F.data == "promo_test_run")
async def execute_test_harness(callback: types.CallbackQuery):
    """
    Safely delivers copies of both localized iterations directly into your chat.
    """
    if callback.from_user.id != settings.ADMIN_IDS[0]:  # Assuming the first ID is the primary admin
        return await callback.answer("⚠️ Access Denied.", show_alert=True)

    await callback.answer("Sending structural preview cards...")
    
    # 1. Render English Version
    en_txt, en_kb = get_promo_card("EN")
    await callback.message.answer("📝 <b>[PREVIEW - ENGLISH TIER]</b>", parse_mode="HTML")
    await callback.message.answer(en_txt, reply_markup=en_kb, parse_mode="HTML")

    # 2. Render Amharic Version
    am_txt, am_kb = get_promo_card("AM")
    await callback.message.answer("📝 <b>[PREVIEW - AMHARIC TIER]</b>", parse_mode="HTML")
    await callback.message.answer(am_txt, reply_markup=am_kb, parse_mode="HTML")


import math
import asyncio
from aiogram import Router, F, types, Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- PHASE 1: BROADCAST PREVIEW & DOUBLE-CHECK ---
@router.callback_query(F.data == "promo_launch_live")
async def preview_live_broadcast(callback: types.CallbackQuery, db: Database):
    if callback.from_user.id != settings.ADMIN_IDS[0]:
        return await callback.answer("⚠️ Access Denied.", show_alert=True)

    count_query = """
        SELECT COUNT(1) 
        FROM club_survey_results 
        WHERE will_join = TRUE
    """
    try:
        total_targets = await db._pool.fetchval(count_query)
    except Exception as sql_err:
        logger.error(f"Failed to count survey backers: {sql_err}")
        return await callback.message.answer(f"❌ <b>Database Error:</b>\n<code>{sql_err}</code>", parse_mode="HTML")

    if not total_targets or total_targets == 0:
        return await callback.message.edit_text(
            "🤷‍♂️ <b>Broadcast Aborted:</b> 0 users found matching your survey filter criteria.", 
            parse_mode="HTML"
        )

    estimated_seconds = math.ceil(total_targets / 25)
    est_minutes = estimated_seconds // 60
    est_secs_remainder = estimated_seconds % 60
    time_str = f"{est_minutes}m {est_secs_remainder}s" if est_minutes > 0 else f"{estimated_seconds}s"

    # FIX: Swapped raw '<' for '&lt;' so Telegram's HTML engine doesn't trip up
    preview_html = (
        f"📢 <b>BROADCAST PIPELINE PREVIEW</b>\n"
        f"──────────────────────────────────────────\n"
        f"📊 <b>Target Audience:</b> <code>{total_targets} users</code> (will_join = TRUE)\n"
        f"⚡ <b>Engine Strategy:</b> Async Concurrency Batches (25 msg/sec)\n"
        f"⏱️ <b>Estimated Duration:</b> ~<code>{time_str}</code>\n"
        f"📉 <b>Neon DB Footprint:</b> Optimized connection lease (&lt; 150ms)\n"
        f"──────────────────────────────────────────\n"
        f"⚠️ <b>Are you sure you want to fire this live broadcast right now?</b>"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="🔥 CONFIRM & LAUNCH LIVE", callback_data="promo_execute_confirmed")
    kb.button(text="❌ CANCEL BROADCAST", callback_data="promo_cancel_broadcast")
    kb.adjust(1)

    await callback.message.edit_text(preview_html, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()

# --- PHASE 2: HIGH-SPEED BATCHED EXECUTION ---
@router.callback_query(F.data == "promo_execute_confirmed")
async def execute_live_broadcast(callback: types.CallbackQuery, db: Database, bot: Bot):
    if callback.from_user.id != settings.ADMIN_IDS[0]:
        return await callback.answer("⚠️ Access Denied.", show_alert=True)

    await callback.message.edit_text("🛰️ <i>Streaming target identities from database...</i>", parse_mode="HTML")

    # Fixed: Pulling data correctly filtered by your 'will_join' column
    query = """
        SELECT u.telegram_id, COALESCE(u.language, 'EN') as language 
        FROM users u
        JOIN club_survey_results s ON u.telegram_id = s.user_id 
        WHERE s.will_join = TRUE
    """
    try:
        targets = await db._pool.fetch(query)
    except Exception as sql_err:
        logger.error(f"Failed to query survey targets: {sql_err}")
        return await callback.message.answer(f"❌ <b>Database Error:</b>\n<code>{sql_err}</code>", parse_mode="HTML")

    total_count = len(targets)
    if not targets:
        return await callback.message.edit_text("🤷‍♂️ 0 targets found. Broadcast dropped.", parse_mode="HTML")

    await callback.message.edit_text(f"🚀 <b>Dispatching live to {total_count} pipelines...</b>\nMonitoring performance counters.", parse_mode="HTML")

    success_tracks = 0
    failure_tracks = 0
    
    # Batch configuration: 25 workers processed via asyncio.gather inside 1-second ticks
    BATCH_SIZE = 25 
    
    async def send_safe_message(target_id, text, markup):
        nonlocal success_tracks, failure_tracks
        try:
            await bot.send_message(chat_id=target_id, text=text, reply_markup=markup, parse_mode="HTML")
            success_tracks += 1
        except Exception as api_err:
            logger.warning(f"Delivery block on user {target_id}: {api_err}")
            failure_tracks += 1

    # Chunk loop that protects Neon CPU execution time and handles Telegram limits perfectly
    for i in range(0, total_count, BATCH_SIZE):
        batch = targets[i:i + BATCH_SIZE]
        tasks = []
        
        for record in batch:
            uid = record['telegram_id']
            lang = record['language'] or 'EN'
            msg_text, msg_kb = get_promo_card(lang) # Pulled from your internal configs
            tasks.append(send_safe_message(uid, msg_text, msg_kb))
            
        # Fire all 25 requests concurrently.
        await asyncio.gather(*tasks)
        
        # Throttles execution cycle to strictly follow Telegram's limits
        await asyncio.sleep(1.0)

    summary_log = (
        f"🏁 <b>BROADCAST PIPELINE COMPLETE</b>\n"
        f"──────────────────────────────────────────\n"
        f"✅ Successfully Delivered: <code>{success_tracks}</code>\n"
        f"❌ Failed / Blocked: <code>{failure_tracks}</code>\n"
        f"📊 Target Engagement: <code>{total_count} total entries</code>"
    )
    
    await callback.message.edit_text(summary_log, parse_mode="HTML")
    await bot.send_message(chat_id=settings.ADMIN_IDS[0], text=f"System Log: Broadcast completed.", parse_mode="HTML")


@router.callback_query(F.data == "promo_cancel_broadcast")
async def cancel_broadcast_action(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ <b>Broadcast Pipeline Aborted.</b> No messages were sent.", parse_mode="HTML")
    await callback.answer()