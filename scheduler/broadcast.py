from datetime import datetime, timezone
import random
from datetime import datetime, timezone
import random
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import random
from datetime import datetime, timezone
from datetime import datetime
import asyncio
from datetime import datetime
import logging
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import ReplyKeyboardRemove

from config import settings
from database.db import Database
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards import inline as akb
from testimonial.testimonial_questions import run_testimonial_cycle  # Updated to use your new hybrid keyboard file

class AdminStates(StatesGroup):
    # Broadcast Step
    awaiting_broadcast = State()
    awaiting_rejection_reason = State() # New state for rejection
    confirm_broadcast = State()   # Admin sees preview and clicks "Send"
    confirm_rejection = State() # Add this

router = Router()
# Move these OUTSIDE the function so they are only loaded into memory once
TESTIMONIALS = {
    "AM": [
        {"name": "ዮሴፍ ካ.", "text": "“ይህ የ299 ብር ኢንቨስትመንት በህይወቴ ካደረግኳቸው ምርጥ ውሳኔዎች አንዱ ነው። ውጤቱ የሚታየው በሳምንቱ ነው።”"},
        {"name": "ሜሮን ቲ.", "text": "“ክብደት ለመቀነስ ከዚህ በላይ ቀላል መንገድ የለም። በየቀኑ ምን መስራት እንዳለብኝ ማወቄ በራስ መተማመኔን ጨምሮታል።”"},
        {"name": "ዳዊት አ.", "text": "“ዋጋው ተመጣጣኝ ቢሆንም፣ የሚሰጠው ውጤት ግን በሺዎች ከሚቆጠሩ የግል አሰልጣኞች ይበልጣል።”"},
        {"name": "ሳምራዊት ገ.", "text": "“መጀመር ለሚከብዳችሁ ሰዎች ይህ እቅድ ምርጥ መነሻ ነው። ጊዜያችሁን አታባክኑ።”"},
        {"name": "ቃለብ ወ.", "text": "“በቀን ከ10 ብር ባነሰ ወጪ እንዲህ ያለ ለውጥ ማግኘት የማይታመን ነው። አሁን የተሻለ ማንነት አለኝ።”"},
        {"name": "ኪሩቤል ኤ.", "text": "“የሆድ ስብን ለማጥፋት ብዙ ሞክሬ ነበር፤ ግን ትክክለኛውን መንገድ ያገኘሁት እዚህ ጋር ነው።”"},
    ],
    "EN": [
        {"name": "Yosef K.", "text": "“Stop overthinking and just start. This plan is worth 10x the price. The results are real.”"},
        {"name": "Meron T.", "text": "“I wasted so much on gyms, but this structured meal plan was the missing piece to my transformation.”"},
        {"name": "Dawit A.", "text": "“The most logical and effective guide in Ethiopia. No fluff, just results for the price of a burger.”"},
        {"name": "Samrawit G.", "text": "“If you’re waiting for a sign, this is it. Don't let another month pass with regret.”"},
        {"name": "Kaleb W.", "text": "“High-performance coaching for 10 Birr a day. My energy and physique have never been better.”"},
        {"name": "Kirubel E.", "text": "“Best 299 ETB I’ve ever spent on myself. Period.”"},
    ]
}

BUYER_NAMES = {
    "AM": ["ዮሴፍ ካ.", "ሜሮን ቲ.", "ዳዊት አ.", "ሳምራዊት ገ.", "ቃለብ ወ.", "ኪሩቤል ኤ."],
    "EN": ["Yosef K.", "Meron T.", "Dawit A.", "Samrawit G.", "Kaleb W.", "Kirubel E."]
}




# def get_rotating_content(lang: str):
#     lang = lang.upper() if lang.upper() in ["AM", "EN"] else "EN"
#     now = datetime.now()
#     time_seed = (now.timetuple().tm_yday * 24) + now.hour
    
#     testi_list = TESTIMONIALS[lang]
#     buyer_list = BUYER_NAMES[lang]
    
#     idx = time_seed % len(testi_list)
#     buyer_idx = (time_seed + 3) % len(buyer_list)

#     testi = testi_list[idx]
#     buyer_name = buyer_list[buyer_idx]
    
#     if lang == "AM":
#         activity = f"🔥 <b>{buyer_name}</b> እና ሌሎች 4 ሰዎች አሁን ተመዝግበዋል! 💸"
#     else:
#         activity = f"🔥 <b>{buyer_name}</b> and 4 others just joined! 💸"

#     return testi, activity


def get_rotating_content(lang: str):
    lang = lang.upper() if lang.upper() in ["AM", "EN"] else "EN"
    
    # The "Damn Good" General Testimonial
    TESTIMONIALS = {
        "AM": {
            "text": "ለመጀመር ሁሌም እጨነቅ ነበር፣ ግን ይሄ ፕሮግራም ነገሮችን በጣም ቀላል አድርጎልኛል። በተለይ በውስጡ ያለው PDF በጣም ግልፅ ነው፤ ስልጠናዎቹን የሚያሳዩት ቪዲዮዎች ደግሞ ልክ ከጎኔ ሆኖ ሰው እንደሚያሰለጥነኝ ያህል ይረዱኛል። ክብደት ለመቀነስም ሆነ ጡንቻ ለመገንባት ለሚፈልግ ሰው ከዚህ በላይ ቀላል ነገር ያለ አይመስለኝም!",
            "name": "አቤል ተፈራ (Verified Member)"
        },
        "EN": {
            "text": "I used to struggle with where to start, but this program made it so simple. The PDF guide is incredibly clear, and the videos inside are a game changer—it’s like having a trainer right next to you. Whether you want to lose fat or build muscle, this is honestly the easiest way to do it.",
            "name": "Abel T. (Verified Member)"
        }
    }

    # Dynamic Buyer Names for "Recent Activity"
    BUYERS = {
        "AM": ["ዮናስ", "ቤቴልሄም", "ዳዊት", "ሳራ", "ኤልያስ", "ሊዲያ"],
        "EN": ["Yonas", "Bethel", "Dawit", "Sara", "Elias", "Lydia"]
    }

    now = datetime.now()
    time_seed = (now.timetuple().tm_yday * 24) + now.hour
    
    testi = TESTIMONIALS[lang]
    buyer_name = BUYERS[lang][time_seed % len(BUYERS[lang])]
    
    if lang == "AM":
        activity = f"🔥 <b>{buyer_name}</b> እና ሌሎች 4 ሰዎች አሁን ተመዝግበዋል! 💸"
    else:
        activity = f"🔥 <b>{buyer_name}</b> and 4 others just joined! 💸"

    return testi, activity

def build_deal_message(lang: str, expires_at: datetime, product_id: int, price: int = 299):
    invites_left = random.choice([2,3,4]) 
    testimonial, recent_activity = get_rotating_content(lang)
    daily_cost = int(price / 60)
    

    if lang.upper() == "AM":
        header = f"<b>🚨 አብዛኛው ሰው የመረጠው ልዩ ቅናሽ ለእርስዎም ተከፍቷል!</b>"
        sub_header = f"<i>(በቅርብ ባደረግነው የዋጋ ጥናት 74% የሚሆኑ አባላቶቻችን ይህንን የክፍያ አማራጭ መርጠዋል) -- </i> <s>1000Br.</s> <b>{price}ብር</b>"
        body = (
            f"{sub_header}\n\n"
            f"ውድ ክፍያዎችን በመፍራት ለውጥዎን ለነገ አያሳድሩ። "
            f"በቀን <b>{daily_cost} ብር</b> ብቻ በሚሆን ወጪ ራስዎን ይቀይሩ።\n\n"
            
            f"<b>የአባላቶቻችን አስተያየት፦</b>\n"
            f"💬 <i>\"{testimonial['text']}\"</i>\n— <b>{testimonial['name']}</b>\n\n"
            
            f"✅ <b>በጣም ግልፅ የሆነ የPDF መመሪያ (ለአጠቃቀም ቀላል)</b>\n"
            f"✅ <b>እያንዳንዱን ስፖርት የሚያሳዩ አጋዥ ቪዲዮዎች</b>\n"
            f"✅ <b>ክብደት ለመቀነስ እና ጡንቻ ለመገንባት የሚረዱ ምግቦች</b>\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"⏳ <b>{invites_left} ክፍት ቦታዎች ብቻ ቀርተዋል!</b>\n"
            f"{recent_activity}\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>ይህንን እድል ተጠቅመው ራስዎን ለመቀየር ከታች ያለውን ቁልፍ ይንኩት፦</b>"
        )
        button_text = f"🔥 ፕሮግራሙን አግኝ"
    else:
        header = f"<b>🎯 THE PEOPLE'S CHOICE: Most requested deal unlocked!</b>"
        body = (
            f"Stop letting gym fees be your excuse. "
            f"For just <b>{daily_cost} ETB per day</b>, get a blueprint that actually works.\n\n"
            
            f"<b>What Members Are Saying:</b>\n"
            f"💬 <i>\"{testimonial['text']}\"</i>\n— <b>{testimonial['name']}</b>\n\n"
            
            f"⭐ <b>Easy-to-follow PDF Guide (Clear Instructions)</b>\n"
            f"⭐ <b>Step-by-Step Exercise Videos Included</b>\n"
            f"⭐ <b>Universal Fat Loss & Muscle Building Plan</b>\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"⏳ <b>Only {invites_left} spots remaining!</b>\n"
            f"{recent_activity}\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>Secure your transformation before the door closes:</b>"
        )
        button_text = f"🚀 GET INSTANT ACCESS"

    text = f"{header}\n\n{body}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=button_text, callback_data=f"pay_{product_id}")]
    ])
    
    return text, kb

import os
from datetime import datetime, timedelta

from aiogram import types, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
# RIGHT for aiogram v3.x
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError

from config import settings
from app_context import db  # or import your Database instance the same way other handlers do
from aiogram.fsm.context import FSMContext
from aiogram import Router

# Configurable defaults (env or fallback)

# --- Helper: target selection keyboard ---
def broadcast_target_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🧪 Test (Admins only)", callback_data="broadcast_target:test")
    kb.button(text="🎯 Unpaid only", callback_data="broadcast_target:unpaid")
    kb.button(text="✅ Paid only", callback_data="broadcast_target:paid")
    kb.button(text="📣 All users", callback_data="broadcast_target:all")
    kb.adjust(2)
    return kb.as_markup()

# --- Step 1: Admin starts drafting a broadcast ---

@router.message(F.text == "📢 Global Broadcast", F.from_user.id.in_(settings.ADMIN_IDS))
async def start_broadcast(message: types.Message, state: FSMContext):
    await message.answer(
        "Choose target group for this broadcast:",
        reply_markup=broadcast_target_kb()
    )
    await state.set_state(AdminStates.confirm_broadcast)
# @router.message(F.text == "📢 Global Broadcast", F.from_user.id.in_(settings.ADMIN_IDS))
# async def start_broadcast(message: types.Message, state: FSMContext):
#     await state.set_state(AdminStates.awaiting_broadcast)
#     await message.answer(
#         "📢 *DRAFTING MODE*\n"
#         "Send your message exactly as you want it to appear.\n\n"
#         "💡 *Tip: You can use *bold*, __italic__, and even attach images/videos. "
#         "The bot will preserve all formatting.*",
#         reply_markup=akb.cancel_admin()
#     )

# # --- Step 2: Admin sends draft; show preview and confirm ---
# @router.message(AdminStates.awaiting_broadcast)
# async def preview_broadcast(message: types.Message, state: FSMContext):
#     if message.text == "❌ Abort Operation":
#         await state.clear()
#         return await message.answer("Broadcast cancelled.", reply_markup=akb.admin_main_menu())

#     await state.update_data(msg_to_copy=message.message_id, chat_from=message.chat.id)

#     await message.answer("👀 *BROADCAST PREVIEW:*")
#     await message.copy_to(message.chat.id)

#     # Now show target selection instead of cancel
#     await message.answer(
#         "Choose target group for this broadcast:",
#         reply_markup=broadcast_target_kb()
#     )
#     await state.set_state(AdminStates.confirm_broadcast)

# --- Cancel handler ---
@router.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Broadcast cancelled.", reply_markup=akb.admin_main_menu())
    
    
@router.callback_query(F.data.startswith("confirm_launch:"))
async def on_confirm_launch(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    target = callback.data.split(":", 1)[1]
    admin_id = callback.from_user.id

    # UI Feedback: Use a punchier, professional status update
    await callback.message.edit_text(
        f"⏳ <b>Broadcast Engine Started</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"Mode: <code>{target.upper()}</code>\n"
        f"Status: <i>Dispatching concurrent tasks...</i>\n\n"
        f"Check your DMs for the final report shortly.",
        parse_mode="HTML"
    )

    # Launching the optimized concurrent task
    asyncio.create_task(execute_broadcast_run(bot, db, admin_id, target))
    
    await state.clear()

# --- Admin selected a target; show final confirmation with estimated count ---
@router.callback_query(AdminStates.confirm_broadcast, F.data.startswith("broadcast_target:"))
async def confirm_broadcast_target(callback: types.CallbackQuery, state: FSMContext):
    target = callback.data.split(":", 1)[1]  # test | unpaid | paid | all
    
    # Define targeting fragments to inject into the CTE
    target_filter = ""
    if target == "unpaid":
        target_filter = "AND NOT EXISTS (SELECT 1 FROM payments pay WHERE pay.user_id = u.telegram_id AND pay.status = 'approved')"
    elif target == "paid":
        target_filter = "AND EXISTS (SELECT 1 FROM payments pay WHERE pay.user_id = u.telegram_id AND pay.status = 'approved')"
    elif target == "test":
        target_filter = f"AND u.telegram_id = ANY(ARRAY{settings.ADMIN_IDS}::BIGINT[])"

    # Use a single, clean CTE. The fallback logic and targeting are handled inside.
    query = f"""
    WITH user_prices AS (
        SELECT 
            u.telegram_id,
            COALESCE(s.selected_price, 299) as effective_price
        FROM users u
        INNER JOIN products p ON 
            UPPER(TRIM(u.language)) = UPPER(TRIM(p.language)) AND 
            UPPER(TRIM(u.gender)) = UPPER(TRIM(p.gender)) AND 
            UPPER(REPLACE(TRIM(u.level), ' ', '_')) = UPPER(REPLACE(TRIM(p.level), ' ', '_')) AND 
            u.frequency = p.frequency
        LEFT JOIN price_survey_results s ON s.user_id = u.telegram_id
        WHERE p.is_active = TRUE 
        {target_filter}
    )
    SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE effective_price = 299) as p299,
        COUNT(*) FILTER (WHERE effective_price = 399) as p399,
        COUNT(*) FILTER (WHERE effective_price = 499) as p499,
        COUNT(*) FILTER (WHERE effective_price = 700) as p700
    FROM user_prices
    """

    stats = await db._pool.fetchrow(query)
    
    confirm_kb = InlineKeyboardBuilder()
    confirm_kb.button(text="🚀 Launch Broadcast", callback_data=f"confirm_launch:{target}")
    confirm_kb.button(text="❌ Abort", callback_data="cancel_broadcast")
    confirm_kb.adjust(1)

    report = (
        f"🎯 <b>TARGETING SUMMARY: {target.upper()}</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"👥 Total Users: <code>{stats['total']}</code>\n\n"
        f"💰 <b>Tier Breakdown:</b>\n"
        f"├ 299 ETB (Survey + Default): <code>{stats['p299']}</code>\n"
        f"├ 399 ETB (Survey): <code>{stats['p399']}</code>\n"
        f"├ 499 ETB (Survey): <code>{stats['p499']}</code>\n"
        f"└ 700 ETB (Survey): <code>{stats['p700']}</code>\n"
        f"━━━━━━━━━━━━━━\n"
        f"⚠️ <b>Ready to push the button?</b>"
    )

    await callback.message.answer(report, reply_markup=confirm_kb.as_markup(), parse_mode="HTML")

import logging
import asyncio
from datetime import datetime, timedelta, timezone

# Professional Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BROADCAST_ENGINE")

async def execute_broadcast_run(bot: Bot, db, admin_id: int, target: str):
    """
    Indestructible Broadcast Engine with Social Proof & Real-time Logging.
    """
    # 1. Configuration & Safety
    BATCH_LIMIT = 25  # Respecting Telegram's 30 msg/sec limit
    semaphore = asyncio.Semaphore(BATCH_LIMIT)
    DEAL_DURATION = int(getattr(settings, "BROADCAST_DURATION_HOURS", 90))
    expires_at = datetime.now(timezone.utc) + timedelta(hours=DEAL_DURATION)
    
    # Initialize high-granularity stats
    stats = {
        "sent": 0, "failed": 0, "deleted": 0, "skipped_cleanup": 0,
        "299": 0, "399": 0, "499": 0, "700": 0
    }

    # 2. Optimized Data Fetching (Injecting survey price directly)
    base_query = """
        SELECT 
            u.telegram_id, u.language, p.id as p_id, 
            COALESCE(s.selected_price, 299) as final_price
        FROM users u
        INNER JOIN products p ON 
            u.language = p.language AND u.gender = p.gender AND 
            u.level = p.level AND u.frequency = p.frequency
        LEFT JOIN price_survey_results s ON s.user_id = u.telegram_id
        WHERE p.is_active = TRUE
    """
    
    if target == "unpaid":
        base_query += " AND NOT EXISTS (SELECT 1 FROM payments pay WHERE pay.user_id = u.telegram_id AND pay.status = 'approved')"
    elif target == "test":
        base_query += f" AND u.telegram_id = ANY(ARRAY{settings.ADMIN_IDS}::BIGINT[])"

    targets = await db._pool.fetch(base_query)
    if not targets:
        logger.warning(f"⚠️ Broadcast aborted: No users found for target '{target}'")
        return {"error": "No users found"}

    logger.info(f"🚀 Initializing broadcast for {len(targets)} targets...")

    # 3. Synchronized Pre-Update (Locking in prices before sending)
    sync_data = [(t['final_price'], expires_at, t['telegram_id']) for t in targets]
    await db._pool.executemany(
        "UPDATE users SET deal_price = $1, deal_expires_at = $2 WHERE telegram_id = $3",
        sync_data
    )

    # 4. Atomic & Fault-Tolerant Sender Task
    async def send_to_user(user):
        uid = user['telegram_id']
        price_key = str(int(user['final_price'])) 
        
        async with semaphore:
            try:
                # Generate specialized 2030-tech style content
                text, kb = build_deal_message(
                    user['language'], 
                    expires_at, 
                    user['p_id'], 
                    user['final_price']
                )
                
                sent_msg = await bot.send_message(
                    chat_id=uid,
                    text=text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )

                # Persist context for the countdown/analytics workers
                await db._pool.execute(
                    "UPDATE users SET last_broadcast_msg_id = $1, matched_product_id = $2 WHERE telegram_id = $3",
                    sent_msg.message_id, user['p_id'], uid
                )
                
                stats["sent"] += 1
                if price_key in stats:
                    stats[price_key] += 1
                logger.info(f"✅ Delivered: {uid} | Price: {price_key}")
                
            except Exception as e:
                stats["failed"] += 1
                err = str(e).lower()
                logger.error(f"❌ Delivery Failed for {uid}: {err}")

                # 5. Safe Cleanup (Protected from ForeignKeyViolationError)
                if any(x in err for x in ["blocked", "chat not found", "deactivated", "user_is_deactivated"]):
                    try:
                        await db._pool.execute("DELETE FROM users WHERE telegram_id = $1", uid)
                        stats["deleted"] += 1
                        logger.info(f"🗑 Cleaned user {uid} from database.")
                    except Exception as db_err:
                        # If user has payment history, we can't delete them, so we just log it
                        stats["skipped_cleanup"] += 1
                        logger.warning(f"⚠️ Could not delete {uid} (Referenced in payments): {db_err}")
            
            # Intelligent pacing
            await asyncio.sleep(0.05)

    # 6. Parallel Non-Blocking Execution
    await asyncio.gather(*(send_to_user(u) for u in targets))

    # 7. Premium Admin Insight Report
    logger.info(f"🏁 Broadcast finished. Success: {stats['sent']}, Failed: {stats['failed']}")
    
    summary = (
        f"🏁 <b>BROADCAST ENGINE COMPLETE</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"✅ <b>Delivered:</b> <code>{stats['sent']}</code>\n"
        f"❌ <b>Failed:</b> <code>{stats['failed']}</code>\n"
        f"🗑 <b>Database Cleaned:</b> <code>{stats['deleted']}</code>\n"
        f"⚠️ <b>Blocked (Preserved):</b> <code>{stats['skipped_cleanup']}</code>\n\n"
        f"💰 <b>Price Tier Distribution:</b>\n"
        f"├ 299 ETB: <code>{stats['299']}</code> users\n"
        f"├ 399 ETB: <code>{stats['399']}</code> users\n"
        f"├ 499 ETB: <code>{stats['499']}</code> users\n"
        f"└ 700 ETB: <code>{stats['700']}</code> users\n"
        f"━━━━━━━━━━━━━━\n"
        f"ℹ️ <i>Real-time logs available in console.</i>"
    )
    
    await bot.send_message(admin_id, summary, parse_mode="HTML")
    return stats

@router.message(F.text == "/broadcast_dryrun", F.from_user.id.in_(settings.ADMIN_IDS))
async def broadcast_dryrun(message: types.Message):
    try:
        # One query to rule them all: Single pass over the user/product join
        stats = await db._pool.fetchrow("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE NOT EXISTS (
                    SELECT 1 FROM payments p WHERE p.user_id = u.telegram_id AND p.status = 'approved'
                )) as unpaid_count,
                COUNT(*) FILTER (WHERE EXISTS (
                    SELECT 1 FROM payments p WHERE p.user_id = u.telegram_id AND p.status = 'approved'
                )) as paid_count,
                COUNT(*) FILTER (WHERE prod.price = 299) as tier_299,
                COUNT(*) FILTER (WHERE prod.price = 399) as tier_399,
                COUNT(*) FILTER (WHERE prod.price = 499) as tier_499
            FROM users u
            LEFT JOIN products prod ON 
                u.language = prod.language AND u.gender = prod.gender AND 
                u.level = prod.level AND u.frequency = prod.frequency
            WHERE prod.is_active = TRUE
        """)

        report = (
            f"📊 <b>BROADCAST PRE-FLIGHT DATA</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"👥 <b>Audience Segments:</b>\n"
            f"├ Total Users: <code>{stats['total']}</code>\n"
            f"├ Unpaid (Targets): <code>{stats['unpaid_count']}</code>\n"
            f"└ Paid (Retention): <code>{stats['paid_count']}</code>\n\n"
            f"💰 <b>Pricing Distribution:</b>\n"
            f"├ 299 ETB Tier: <code>{stats['tier_299']}</code>\n"
            f"├ 399 ETB Tier: <code>{stats['tier_399']}</code>\n"
            f"└ 499 ETB Tier: <code>{stats['tier_499']}</code>\n"
            f"━━━━━━━━━━━━━━\n"
            f"<i>Note: Counts based on active product matching.</i>"
        )
        
        await message.answer(report, parse_mode="HTML")

    except Exception as e:
        logging.error(f"Dryrun failed: {e}")
        await message.answer("❌ <b>Error:</b> Database synchronization failed during stats fetch.")
        
        
        
        
@router.message(Command("test_feedback"), F.from_user.id.in_(settings.ADMIN_IDS))
async def cmd_test_feedback(message: types.Message, db, bot: Bot, state: FSMContext):
    args = message.text.split()
    if len(args) < 2: 
        return await message.answer("Usage: /test_feedback 1")
    
    try:
        q_id = int(args[1])
        
        # Pull storage directly from the state object's internal reference
        storage = state.storage 

        from testimonial.testimonial_questions import run_testimonial_cycle
        count = await run_testimonial_cycle(bot, db, storage, q_id, test_mode=True)
        
        await message.answer(f"✅ Test mode active. Sent to {count} admins.")
        
    except Exception as e:
        logging.error(f"Test feedback error: {e}")
        # Send as plain text to avoid the "can't parse entities" HTML error
        await message.answer(f"❌ Error: {str(e)}", parse_mode=None)