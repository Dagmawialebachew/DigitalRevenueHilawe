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

from datetime import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ─────────────────────────────────────────────
#  TESTIMONIALS — 3 each, rotating by hour
#  Each one targets a different buyer psychology:
#  [0] The skeptic who almost didn't buy
#  [1] The person who tried everything else
#  [2] The person who did it with a friend
# ─────────────────────────────────────────────
TESTIMONIALS = {
    "AM": [
        {
            "text": (
                "솔직히 말하면 — 100 ብር ስሰማ 'ምን ሊሰጠን ይችላል?' ብዬ ጠርጥሬ ነበር። "
                "ግን ውስጥ ያለው ነገር አስደነቀኝ። PDF-ው ግልጽ ነው፣ "
                "ቪዲዮዎቹ ልክ ከጎኔ ሆኖ የሚያሰለጥን ሰው አሉኝ ያስብለኛል። "
                "ከዚህ ዋጋ ጋር ምንም ምክንያት የለም ዝም ለማለት።"
            ),
            "name": "ዳዊት መኮንን ✅ አባል",
        },
        {
            "text": (
                "ብዙ ፕሮግራሞች ሞክሬ ነበር — ሁሉም ለምዕራባዊያን የተሰሩ ናቸው። "
                "ይሄ ግን ለኛ ነው። ጤፍ፣ ጥብስ፣ ሽሮ — ሁሉም ምግቦቻችን አሉ። "
                "8 ሳምንት ብቻ ፕሮግራሙን ስከተል ሆዴ ጠፋ፣ ትከሻዬ ሰፋ። "
                "ቃሌን ስጡኝ — ይሰራል።"
            ),
            "name": "ናትናኤል ግርማ ✅ አባል",
        },
        {
            "text": (
             "መጀመሪያ በቅናሽ ዋጋ ስገዛው ዝም ብሎ መጽሐፍ (PDF) ብቻ መስሎኝ ነበር። "
            "ግን ውስጥ ያለው የቪዲዮ ስልጠና፣ የምግብ አዘገጃጀት እና ግልጽ የሆነው እቅድ አስገርሞኛል። "
            "በዚህ ዋጋ ይሄን ያህል ጥራት ያለው ስራ ማግኘት አይታሰብም።"
        
            ),
            "name": "ዮሴፍ ካሳ ✅ አባል",
        },
    ],
    "EN": [
        {
            "text": (
                "Honestly — when I saw 100 ETB I thought 'what could this possibly offer?' "
                "I was wrong. The PDF is detailed, the videos are real, "
                "and the structure actually makes sense. "
                "There is zero excuse to scroll past this."
            ),
            "name": "Dawit M. ✅ Verified Member",
        },
        {
            "text": (
                "I've tried programs before — all built for Western diets. "
                "This one is built for us. Injera, tibs, shiro — it's all in there. "
                "8 weeks. My stomach is gone, my shoulders are wider. "
                "Take my word — it works."
            ),
            "name": "Nathanael G. ✅ Verified Member",
        },
        {
            "text": (
              "When I bought this during the last sale, I thought it was just a PDF. "
            "But the HD videos and the nutrition plan are professional grade. "
            "Getting this quality for this price is a steal."
            ),
            "name": "Yosef K. ✅ Verified Member",
        },
    ],
}

# ─────────────────────────────────────────────
#  SOCIAL PROOF — honest, community-focused
# ─────────────────────────────────────────────
SOCIAL_PROOF = {
    "AM": [
        "🤝 ከ800 በላይ ኢትዮጵያውያን ይህን ፕሮግራም አጠናቅቀዋል።",
        "🌟 በየሳምንቱ አዳዲስ ውጤቶች ወደ እኛ እየደረሱ ነው።",
        "🏘️ ከቦሌ እስከ ሐዋሳ — ሁሉም ቦታ ሰዎች ይሰሩበታል።",
    ],
    "EN": [
        "🤝 800+ Ethiopians have completed this exact program.",
        "🌟 New results land in our inbox every single week.",
        "🏘️ From Bole to Hawassa — people are doing the work.",
    ],
}

# ─────────────────────────────────────────────
#  URGENCY — honest, no fake spots
# ─────────────────────────────────────────────
URGENCY = {
    "AM": [
        "⚡ ይሄ ዋጋ ለዚህ ብሮድካስት ብቻ ነው — ቋሚ አይደለም።",
        "⚡ ከዚህ ቅናሽ በኋላ ዋጋው ወደ ቀድሞው ይመለሳል።",
        "⚡ ይሄን ለፊታችሁ ላይ ማለፍ — ከ6 ወር በኋላ ያሳዝናችኋል።",
    ],
    "EN": [
        "⚡ This price exists for this broadcast only — it will not last.",
        "⚡ After this offer closes, the price goes back up.",
        "⚡ Scrolling past this today — you'll remember it in 6 months.",
    ],
}


def get_rotating_content(lang: str):
    lang = lang.upper() if lang.upper() in ["AM", "EN"] else "EN"
    now = datetime.now()

    testi_list   = TESTIMONIALS[lang]
    proof_list   = SOCIAL_PROOF[lang]
    urgency_list = URGENCY[lang]

    # Rotates every hour — feels fresh, never crashes
    idx = (now.timetuple().tm_yday * 24) + now.hour

    return (
        testi_list[idx % len(testi_list)],
        proof_list[idx % len(proof_list)],
        urgency_list[idx % len(urgency_list)],
    )


def build_deal_message(
    lang: str,
    product_id: int,
    price: int = 100,
    original_price: int = 1000,
):
    lang = lang.upper() if lang.upper() in ["AM", "EN"] else "EN"
    testimonial, social_proof, urgency = get_rotating_content(lang)

    # 100 ETB / 60 days = 1.67 → show as "ከ2 ብር ያነሰ"
    # More persuasive than showing 1.6 ETB
    daily_anchor_am = "ከ2 ብር ያነሰ"
    daily_anchor_en = "less than 2 ETB"

    # ── AMHARIC ─────────────────────────────────────────────────────
    if lang == "AM":
        header = f"<b>{price} ብር ብቻ! ⚡️ (የ3 ሰዓት የልዩ ስጦታ)</b>\n<i>Coach Hilawe: የሁላችንም ለውጥ</i>"

        coach_voice = (
            "ሰዎቼ —\n\n"
            "ብዙዎቻችሁ ፕሮግራሙን ከረዥም ጊዜ ጀምሮ ሳትጠቀሙ ቀርታችኋል። "
            "ዋጋው ነው? ጊዜው ነው? ወይስ ጀምሮ ማቆሙን ትፈሩበታላችሁ?\n\n"
            "ዛሬ ዋጋውን ጉዳይ አቆምኩት።\n"
            f"<s>{original_price} ብር</s> → <b>{price} ብር ብቻ።</b>\n"
            f"<i>({daily_anchor_am} — በቀን። ዋጋ አይደለም ምክንያት።)</i>"
        )

        what_you_get = (
            "<b>ምን ያገኛሉ?</b>\n"
            "✅ <b>የ8 ሳምንት ሙሉ የጂም ፕሮግራም</b> — ለጀማሪ እና መካከለኛ\n"
            "✅ <b>እያንዳንዱን እንቅስቃሴ የሚያሳዩ ቪዲዮዎች</b>\n"
            "✅ <b>ለኢትዮጵያ ምግቦች የተሰራ የአመጋገብ መመሪያ</b>\n"
            "✅ <b>ግልጽ PDF — ስልክ ብቻ ይበቃል</b>"
        )

        proof_block = (
            f"━━━━━━━━━━━━━━\n"
            f"{social_proof}\n"
            f"{urgency}\n"
            f"━━━━━━━━━━━━━━"
        )

        testimonial_block = (
            f"💬 <i>\"{testimonial['text']}\"</i>\n"
            f"— <b>{testimonial['name']}</b>"
        )

        cta = "<b>ከታች ይንኩ። ዛሬ ይጀምሩ። 👇</b>"

        body = (
            f"{coach_voice}\n\n"
            f"{what_you_get}\n\n"
            f"{proof_block}\n\n"
            f"{testimonial_block}\n\n"
            f"{cta}"
        )

        button_text = f"💪 በ{price} ብር ጉዞዬን እጀምራለሁ"

    # ── ENGLISH ──────────────────────────────────────────────────────
    else:
        header = f"<b>{price} ETB ONLY! ⚡️ (3-Hour Gift)</b>\n<i>The Coach Hilawe Mission</i>"

        coach_voice = (
            "My people —\n\n"
            "A lot of you have been watching this program for a while. "
            "Is it the price? The time? Or the fear of starting and stopping again?\n\n"
            "Today I removed the price as an excuse.\n"
            f"<s>{original_price} ETB</s> → <b>{price} ETB only.</b>\n"
            f"<i>({daily_anchor_en} per day. That is not a price. That is nothing.)</i>"
        )

        what_you_get = (
            "<b>What's inside:</b>\n"
            "✅ <b>Full 8-Week Gym System</b> — beginner to intermediate\n"
            "✅ <b>Video demonstrations</b> for every single exercise\n"
            "✅ <b>Ethiopian food nutrition guide</b> — injera, tibs, shiro, all of it\n"
            "✅ <b>Clear PDF</b> — works on your phone, offline, forever"
        )

        proof_block = (
            f"━━━━━━━━━━━━━━\n"
            f"{social_proof}\n"
            f"{urgency}\n"
            f"━━━━━━━━━━━━━━"
        )

        testimonial_block = (
            f"💬 <i>\"{testimonial['text']}\"</i>\n"
            f"— <b>{testimonial['name']}</b>"
        )

        cta = "<b>Tap below. Start today. 👇</b>"

        body = (
            f"{coach_voice}\n\n"
            f"{what_you_get}\n\n"
            f"{proof_block}\n\n"
            f"{testimonial_block}\n\n"
            f"{cta}"
        )

        button_text = f"💪 START FOR {price} ETB"

    # ── ASSEMBLE ─────────────────────────────────────────────────────
    text = f"{header}\n\n{body}"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=button_text,
                callback_data=f"pay_{product_id}"
            )]
        ]
    )

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
            COALESCE(s.selected_price, 100) as effective_price
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
        COUNT(*) FILTER (WHERE effective_price = 100) as p100,
        COUNT(*) FILTER (WHERE effective_price = 199) as p199,
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
        f"├ 100 ETB (Survey): <code>{stats['p100']}</code>\n"
        f"├ 199 ETB (Survey): <code>{stats['p199']}</code>\n"
        f"├ 299 ETB (Survey): <code>{stats['p299']}</code>\n"
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
        "100": 0, "199": 0, "299": 0, "399": 0, "499": 0, "700": 0
    }

    # 2. Optimized Data Fetching (Injecting survey price directly)
    base_query = """
        SELECT 
            u.telegram_id, u.language, p.id as p_id, 
            COALESCE(s.selected_price, 100) as final_price
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
    CAMPAIGN_IMAGE_FILE_ID = "AgACAgQAAxkBAAL6qWoEjLPR-7vZ959vP36Wh5vwHL7OAAJzDmsbuP8oUAK7H-y_bWmNAQADAgADeQADOwQ"  # 🔁 replace this
    # CAMPAIGN_IMAGE_FILE_ID = "AgACAgQAAxkBAALX8Gn94mHeVAmqYUPkO9gE8xL34843AAJTDmsb9b7pU3MRcPN22trVAQADAgADeQADOwQ"  # 🔁 replace this
    
    async def send_to_user(user):
        uid = user['telegram_id']
        price_key = str(int(user['final_price']))
    
        async with semaphore:
            try:
                text, kb = build_deal_message(
    lang=user['language'],
    product_id=user['p_id'],
    price=int(user['final_price'])
)
    
                # ── SEND PHOTO WITH TEXT AS CAPTION ──────────────
                # Telegram caption limit is 1024 chars.
                # If your text ever exceeds that, we fall back to
                # photo + separate text message automatically.
    
                if len(text) <= 1024:
                    sent_msg = await bot.send_photo(
                        chat_id=uid,
                        photo=CAMPAIGN_IMAGE_FILE_ID,
                        caption=text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                else:
                    # Caption too long — send photo clean, text below
                    await bot.send_photo(
                        chat_id=uid,
                        photo=CAMPAIGN_IMAGE_FILE_ID,
                        parse_mode="HTML"
                    )
                    sent_msg = await bot.send_message(
                        chat_id=uid,
                        text=text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                # ─────────────────────────────────────────────────
    
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
    
                if any(x in err for x in ["blocked", "chat not found", "deactivated", "user_is_deactivated"]):
                    try:
                        await db._pool.execute("DELETE FROM users WHERE telegram_id = $1", uid)
                        stats["deleted"] += 1
                        logger.info(f"🗑 Cleaned user {uid} from database.")
                    except Exception as db_err:
                        stats["skipped_cleanup"] += 1
                        logger.warning(f"⚠️ Could not delete {uid} (Referenced in payments): {db_err}")
    
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
        f"├ 100 ETB: <code>{stats['100']}</code> users\n"
        f"├ 199 ETB: <code>{stats['199']}</code> users\n"
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
                COUNT(*) FILTER (WHERE prod.price = 100) as tier_100,
                COUNT(*) FILTER (WHERE prod.price = 199) as tier_199,
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
            f"├ 100 ETB Tier: <code>{stats['tier_100']}</code>\n"
            f"├ 199 ETB Tier: <code>{stats['tier_199']}</code>\n"
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



import asyncio
from aiogram import Router, types, Bot
from aiogram.filters import Command


@router.message(Command("cleanup_flash"))
async def cleanup_flash_deal(message: types.Message, bot: Bot, db):
    # 1. Security Check (Replace with your actual Admin ID)
    if message.from_user.id != settings.ADMIN_IDS[0]:  # Assuming the first ID in ADMIN_IDS is the super admin
        return

    await message.answer("🧹 <b>Starting Cleanup...</b>\nInitiating the 3-hour vanishing protocol.")

    # 2. Fetch all users who have a message ID stored
    # Using 'db._pool' assuming you use asyncpg/PostgreSQL
    targets = await db._pool.fetch(
        "SELECT telegram_id, last_broadcast_msg_id FROM users WHERE last_broadcast_msg_id IS NOT NULL"
    )

    if not targets:
        return await message.answer("❌ No active flash messages found in the database.")

    total_targets = len(targets)
    deleted_count = 0
    failed_count = 0

    # 3. The Execution (The Janitor)
    # We limit to 30 deletions per second to stay safe with Telegram
    semaphore = asyncio.Semaphore(30)

    async def delete_for_user(user_id, msg_id):
        nonlocal deleted_count, failed_count
        async with semaphore:
            try:
                await bot.delete_message(chat_id=user_id, message_id=msg_id)
                deleted_count += 1
            except Exception:
                # Message might be already deleted or user blocked the bot
                failed_count += 1

    # Run all deletions concurrently
    await asyncio.gather(*(delete_for_user(t['telegram_id'], t['last_broadcast_msg_id']) for t in targets))

    # 4. Clear the database columns so we are ready for the next deal
    await db._pool.execute("UPDATE users SET last_broadcast_msg_id = NULL")

    # 5. Final Report
    report = (
        f"✅ <b>Cleanup Complete</b>\n\n"
        f"👤 Total Users: {total_targets}\n"
        f"🗑 Deleted: {deleted_count}\n"
        f"⚠️ Skipped/Failed: {failed_count}\n\n"
        f"<i>The mission-driven flash deal has officially ended.</i>"
    )
    await message.answer(report)


# from datetime import datetime, timezone
# import random
# from datetime import datetime, timezone
# import random
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
# import random
# from datetime import datetime, timezone
# from datetime import datetime
# import asyncio
# from datetime import datetime
# import logging
# from aiogram import Router, F, types, Bot
# from aiogram.filters import Command
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import State, StatesGroup
# from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
# from aiogram.types import ReplyKeyboardRemove

# from config import settings
# from database.db import Database
# from aiogram.utils.keyboard import InlineKeyboardBuilder
# from keyboards import inline as akb
# from testimonial.testimonial_questions import run_testimonial_cycle  # Updated to use your new hybrid keyboard file

# router = Router(name="admin")
# def get_rotating_content(lang: str):
#     now = datetime.now()
#     time_seed = (now.timetuple().tm_yday * 24) + now.hour
    
#     # --- AMHARIC: Focus on Results & Value (299) ---
#     testimonials_am = [
#         {"name": "ዮሴፍ ካ.", "text": "“በ299 ብር እንዲህ ያለ ፕሮግራም ማግኘት ይቻላል ብዬ አላሰብኩም ነበር። ለጀመርኩት አዲስ ለውጥ ትልቅ ግብዓት ሆኖኛል።”"},
#         {"name": "ሜሮን ቲ.", "text": "“ክብደት ለመቀነስ ተመጣጣኝና በጣም ግልጽ የሆነ መመሪያ ነው። በየቀኑ ምን መስራት እንዳለብኝ አውቃለሁ።”"},
#         {"name": "ዳዊት አ.", "text": "“ዋጋው በጣም ቅናሽ ነው፤ ጥቅሙ ግን እጥፍ ድርብ ነው። ለጤናዬ ያደረግኩት ምርጥ ኢንቨስትመንት ነው።”"},
#         {"name": "ሳምራዊት ገ.", "text": "“ወደ ጂም ለመመለስ ለምትቸገሩ ይህ የ299 ብር እቅድ ትልቅ መነሳሳት ይፈጥራል።”"},
#         {"name": "ቃለብ ወ.", "text": "“በቀን ከ10 ብር ባነሰ ወጪ የባለሙያ ምክር ማግኘት መቻሌ አስገርሞኛል። ውጤቱ ገና በሳምንቱ ይታያል።”"},
#         {"name": "የታገሱ በ.", "text": "“ከመጠን በላይ ወጪ ከማውጣቴ በፊት ይሄን ማግኘቴ እድለኛ ነኝ። ለጀማሪዎች በጣም ቀላል ነው።”"},
#         {"name": "ኪሩቤል ኤ.", "text": "“የሆድ ስብን ለማጥፋት ትክክለኛውን መንገድ አሳይቶኛል። በ299 ብር የሚገኝ ምርጥ ውጤት!”"},
#         {"name": "ሰላም ዲ.", "text": "“ከጓደኞቼ ጋር ነው የተመዘገብነው፤ ለሁሉም ሰው የሚሆንና ውጤታማ ስልጠና ነው።”"},
#         {"name": "ናሆም ቴ.", "text": "“ቁርጠኛ ለሆነ ሰው ዋጋው እንቅፋት እንዳይሆን ተደርጎ የቀረበ ትልቅ እድል ነው።”"},
#         {"name": "ቤዛዊት ኤስ.", "text": "“ምግብ ሳልቀንስ ክብደት መቀነስ የምችልበትን መንገድ ስላሳዩኝ በጣም አመሰግናለሁ።”"},
#         {"name": "ኤፍሬም ሐ.", "text": "“ራሴን ለማስተካከል ለሳምንታት ሳመነታ ነበር፤ ይህ ፕሮግራም ግን ወዲያውኑ አስጀመረኝ።”"},
#         {"name": "መክሊት አ.", "text": "“በዚህ ዋጋ እንዲህ ያለ ጥራት ያለው መመሪያ መጠበቅ ከባድ ነው፤ ተጠቀሙበት።”"}
#     ]
    
#     recent_buyers_am = ["ዮሴፍ ካ.", "ሜሮን ቲ.", "ዳዊት አ.", "ሳምራዊት ገ.", "ቃለብ ወ.", "ኪሩቤል ኤ."]

#     # --- ENGLISH: Focus on "No Excuses" & "Sustainability" ---
#     testimonials_en = [
#         {"name": "Yosef K.", "text": "“For only 299 ETB, this is a steal. Exactly what I needed to restart my fitness journey.”"},
#         {"name": "Meron T.", "text": "“I was struggling with consistency, but this plan made it simple and affordable to get back on track.”"},
#         {"name": "Dawit A.", "text": "“The value for 299 is insane. It's cheaper than one lunch but the results last a lifetime.”"},
#         {"name": "Samrawit G.", "text": "“If you’re looking for a sign to start training again, this affordable plan is it.”"},
#         {"name": "Kaleb W.", "text": "“Expert coaching for less than 10 Birr a day. My energy levels have already spiked.”"},
#         {"name": "Kirubel E.", "text": "“Targeted my core effectively. Best 299 ETB I’ve ever spent on myself.”"},
#         {"name": "Selam D.", "text": "“Clean, structured, and very easy to follow even with a busy work schedule.”"},
#         {"name": "Nahom T.", "text": "“No more excuses about price. This is accessible for everyone who wants real growth.”"},
#         {"name": "Bezawit S.", "text": "“I learned how to fuel my body without starving. Incredible value.”"},
#         {"name": "Ephrem H.", "text": "“Stopped procrastinating and started training for the price of a coffee. Love the results!”"},
#         {"name": "Meklit A.", "text": "“High-quality structure for a fraction of the usual cost. Get in while the rate is low.”"},
#         {"name": "Yonas B.", "text": "“The most professional recovery plan I've used. Simple and effective.”"}
#     ]
    
#     recent_buyers_en = ["Yosef K.", "Meron T.", "Dawit A.", "Samrawit G.", "Kaleb W.", "Kirubel E."]

#     idx = time_seed % 12
#     buyer_idx = (time_seed + 3) % 6

#     if lang.upper() == "AM":
#         testi = testimonials_am[idx]
#         buyer_name = recent_buyers_am[buyer_idx]
#         activity = f"✅ በቅርብ ጊዜ የተመዘገቡ፦ <b>{buyer_name}... 💸</b>"
#     else:
#         testi = testimonials_en[idx]
#         buyer_name = recent_buyers_en[buyer_idx]
#         activity = f"✅ Recently joined: <b>{buyer_name}... 💸</b>"

#     return testi, activity



# def build_deal_message(lang: str, expires_at: datetime, product_id: int):
#     invites_left = random.choice([12, 15, 18]) 
#     price = 299 
    
#     testimonial, recent_activity = get_rotating_content(lang)

#     if lang.upper() == "AM":
#         header = f"<b>⭐ የ299 ብር ልዩ የቤተሰብ እድል</b>"
#         body = (
#             f"ጥሩ ቁመና ለመገንባት ውድ ክፍያዎችን መክፈል አይጠበቅብዎትም። "
#             f"የብዙዎችን ጥያቄ መሰረት በማድረግ የ8-ሳምንቱን ሙሉ ስልጠና በ<b>{price} ብር</b> ብቻ ክፍት አድርገናል።\n\n"
            
#             f"<b>የተጠቃሚዎች ምስክርነት፦</b>\n"
#             f"<i>\"{testimonial['text']}\"</i> — <b>{testimonial['name']}</b>\n\n"
            
#             f"<b>ምን ያገኛሉ?</b>\n"
#             f"🥗 <b>አመጋገብ፦</b> ለሰውነትዎ የሚስማማ የምግብ ምርጫ።\n"
#             f"💪 <b>ስልጠና፦</b> ውጤት የሚያመጡ ትክክለኛ እንቅስቃሴዎች።\n"
#             f"🤝 <b>ድጋፍ፦</b> ግብዎን እስኪመቱ የሚረዳዎት መመሪያ።\n\n"
#             f"━━━━━━━━━━━━━━\n"
#             f"💡 <b>ጠቃሚ መረጃ፦</b>\n"
#             f"🎤 ከላይ ያለውን የCoach Hilawe አጭር ኦዲዮ በማዳመጥ ስልጠናው እንዴት እንደሚሰራ ይረዱ።\n\n"
#             f"{recent_activity}\n"
#             f"በዚህ ዋጋ መቀላቀል ለሚፈልጉ <b>{invites_left}</b> ክፍት ቦታዎች አሉ።\n"
#             f"━━━━━━━━━━━━━━\n"
#             f"<b>ለመጀመር ከታች ያለውን ቁልፍ ይጫኑ፦</b>"
#         )
#         button_text = f"✅ አሁኑኑ ጀምር"
#     else:
#         header = f"<b>⭐ Community Access: Now Only 299 ETB</b>"
#         body = (
#             f"Professional fitness coaching shouldn't be a luxury. "
#             f"We’ve lowered the barrier by offering the full 8-week program for just <b>{price} ETB</b>.\n\n"
            
#             f"<b>User Spotlight:</b>\n"
#             f"<i>\"{testimonial['text']}\"</i> — <b>{testimonial['name']}</b>\n\n"
            
#             f"<b>The Framework:</b>\n"
#             f"🥗 <b>Nutrition Masterclass:</b> Eat better, not less.\n"
#             f"💪 <b>Optimized Training:</b> Workouts designed for real change.\n"
#             f"🤝 <b>Full Guidance:</b> A clear roadmap to your goals.\n\n"
#             f"━━━━━━━━━━━━━━\n"
#             f"💡 <b>Expert Tip:</b>\n"
#             f"🎤 Listen to Coach Hilawe’s voice note above for a quick breakdown.\n\n"
#             f"{recent_activity}\n"
#             f"Currently <b>{invites_left}</b> spots available at this rate.\n"
#             f"━━━━━━━━━━━━━━\n"
#             f"<b>Click below to secure your access:</b>"
#         )
#         button_text = "✅ GET STARTED"

#     text = f"{header}\n\n{body}"
#     kb = InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text=button_text, callback_data=f"pay_{product_id}")]
#     ])
    
#     return text, kb

# import os
# from datetime import datetime, timedelta

# from aiogram import types, Bot
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
# from aiogram.utils.keyboard import InlineKeyboardBuilder
# # RIGHT for aiogram v3.x
# from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError

# from config import settings
# from app_context import db  # or import your Database instance the same way other handlers do
# from aiogram.fsm.context import FSMContext
# from aiogram import Router

# # Configurable defaults (env or fallback)

# # --- Helper: target selection keyboard ---
# def broadcast_target_kb() -> InlineKeyboardMarkup:
#     kb = InlineKeyboardBuilder()
#     kb.button(text="🧪 Test (Admins only)", callback_data="broadcast_target:test")
#     kb.button(text="🎯 Unpaid only", callback_data="broadcast_target:unpaid")
#     kb.button(text="✅ Paid only", callback_data="broadcast_target:paid")
#     kb.button(text="📣 All users", callback_data="broadcast_target:all")
#     kb.adjust(2)
#     return kb.as_markup()

# # --- Step 1: Admin starts drafting a broadcast ---

# @router.message(F.text == "📢 Global Broadcast", F.from_user.id.in_(settings.ADMIN_IDS))
# async def start_broadcast(message: types.Message, state: FSMContext):
#     await message.answer(
#         "Choose target group for this broadcast:",
#         reply_markup=broadcast_target_kb()
#     )
#     await state.set_state(AdminStates.confirm_broadcast)
# # @router.message(F.text == "📢 Global Broadcast", F.from_user.id.in_(settings.ADMIN_IDS))
# # async def start_broadcast(message: types.Message, state: FSMContext):
# #     await state.set_state(AdminStates.awaiting_broadcast)
# #     await message.answer(
# #         "📢 *DRAFTING MODE*\n"
# #         "Send your message exactly as you want it to appear.\n\n"
# #         "💡 *Tip: You can use *bold*, __italic__, and even attach images/videos. "
# #         "The bot will preserve all formatting.*",
# #         reply_markup=akb.cancel_admin()
# #     )

# # # --- Step 2: Admin sends draft; show preview and confirm ---
# # @router.message(AdminStates.awaiting_broadcast)
# # async def preview_broadcast(message: types.Message, state: FSMContext):
# #     if message.text == "❌ Abort Operation":
# #         await state.clear()
# #         return await message.answer("Broadcast cancelled.", reply_markup=akb.admin_main_menu())

# #     await state.update_data(msg_to_copy=message.message_id, chat_from=message.chat.id)

# #     await message.answer("👀 *BROADCAST PREVIEW:*")
# #     await message.copy_to(message.chat.id)

# #     # Now show target selection instead of cancel
# #     await message.answer(
# #         "Choose target group for this broadcast:",
# #         reply_markup=broadcast_target_kb()
# #     )
# #     await state.set_state(AdminStates.confirm_broadcast)

# # --- Cancel handler ---
# @router.callback_query(F.data == "cancel_broadcast")
# async def cancel_broadcast(callback: types.CallbackQuery, state: FSMContext):
#     await state.clear()
#     await callback.message.answer("Broadcast cancelled.", reply_markup=akb.admin_main_menu())

# # --- Admin selected a target; show final confirmation with estimated count ---
# @router.callback_query(AdminStates.confirm_broadcast, F.data.startswith("broadcast_target:"))
# async def confirm_broadcast_target(callback: types.CallbackQuery, state: FSMContext):
#     target = callback.data.split(":", 1)[1]  # test | unpaid | paid | all

#     # Estimate target count
#     try:
#         if target == "test":
#             targets = [{'telegram_id': aid, 'language': 'EN'} for aid in settings.ADMIN_IDS]
#             filter_sql = None

#         # Inside execute_broadcast_run, update the "unpaid" block:

#         elif target == "unpaid":
#             # We JOIN with products to get the ID that matches the user's onboarding stats
#             rows = await db._pool.fetch("""
#                 SELECT u.telegram_id, u.language, p_match.id as matched_product_id
#                 FROM users u
#                 LEFT JOIN products p_match ON 
#                     u.language = p_match.language AND 
#                     u.gender = p_match.gender AND 
#                     u.level = p_match.level AND 
#                     u.frequency = p_match.frequency
#                 WHERE NOT EXISTS (
#                     SELECT 1 FROM payments p 
#                     WHERE p.user_id = u.telegram_id AND p.status = 'approved'
#                 ) AND p_match.is_active = TRUE
#             """)
#             targets = [dict(r) for r in rows]
#             filter_sql = "NOT EXISTS (SELECT 1 FROM payments p WHERE p.user_id = users.telegram_id AND p.status = 'approved')"

#         elif target == "paid":
#             # Users WITH at least one approved payment
#             rows = await db._pool.fetch("""
#                 SELECT u.telegram_id, u.language
#                 FROM users u
#                 WHERE EXISTS (
#                     SELECT 1 FROM payments p
#                     WHERE p.user_id = u.telegram_id
#                     AND p.status = 'approved'
#                 )
#             """)
#             targets = [dict(r) for r in rows]
#             filter_sql = "EXISTS (SELECT 1 FROM payments p WHERE p.user_id = users.telegram_id AND p.status = 'approved')"

#         else:  # all users
#             rows = await db._pool.fetch("SELECT telegram_id, language FROM users")
#             targets = [dict(r) for r in rows]
#             filter_sql = "TRUE"

#     except Exception:
#         total = 0
#     total = len(targets) # Add this line
#     confirm_kb = InlineKeyboardBuilder()
#     confirm_kb.button(text="🚀 Launch Now", callback_data=f"confirm_launch:{target}")
#     confirm_kb.button(text="❌ Cancel", callback_data="cancel_broadcast")
#     confirm_kb.adjust(2)

#     await callback.message.answer(
#         f"⚠️ *FINAL CONFIRMATION*\nTarget: `{total}` users.\nMode: `{target}`\nDo you want to proceed?",
#         reply_markup=confirm_kb.as_markup()
#     )

# # --- Core executor: updates DB (deal_expires_at/deal_price) and broadcasts by copying admin draft ---


# # Core executor (no draft required)
# async def execute_broadcast_run(bot: Bot, db, admin_id: int, target: str, test_mode: bool = False):
#     """
#     Send localized template messages to the selected target group.
#     - bot: aiogram Bot instance
#     - db: your Database object with _pool (asyncpg)
#     - admin_id: admin who launched the broadcast (for summary)
#     - target: 'test' | 'unpaid' | 'paid' | 'all'
#     - test_mode: if True, only send to settings.ADMIN_IDS and DO NOT update DB deals
#     """
#     BATCH_SLEEP = float(getattr(settings, "BROADCAST_BATCH_SLEEP", 0.06))
#     DEAL_PRICE = float(getattr(settings, "BROADCAST_DEAL_PRICE", 399))
#     DEAL_DURATION_HOURS = int(getattr(settings, "BROADCAST_DURATION_HOURS", 90))
#     from datetime import datetime, timezone

    
#     now = datetime.now(timezone.utc)
#     expires_at = now + timedelta(hours=DEAL_DURATION_HOURS)
    
#     targets = []
#     filter_sql = ""
    

#         # Build target list and SQL filter
#     if target == "test":
#             # 1. Grab a sample product ID to use for the test
#             sample_product = await db._pool.fetchval("SELECT id FROM products WHERE is_active = TRUE LIMIT 1")
            
#             if not sample_product:
#                 logging.error("Broadcast Test Failed: No active products found in DB.")
#                 return {"error": "No products available"}

#             # 2. Get admins and just force the sample product ID
#             rows = await db._pool.fetch("""
#                 SELECT telegram_id, language, $2::INT as matched_product_id
#                 FROM users
#                 WHERE telegram_id = ANY($1::BIGINT[])
#             """, settings.ADMIN_IDS, sample_product)
            
#             targets = [dict(r) for r in rows]
#             filter_sql = f"telegram_id = ANY(ARRAY{settings.ADMIN_IDS}::BIGINT[])"

#     # Inside execute_broadcast_run, update the "unpaid" block:

#     elif target == "unpaid":
#         # We JOIN with products to get the ID that matches the user's onboarding stats
#         rows = await db._pool.fetch("""
#             SELECT u.telegram_id, u.language, p_match.id as matched_product_id
#             FROM users u
#             LEFT JOIN products p_match ON 
#                 u.language = p_match.language AND 
#                 u.gender = p_match.gender AND 
#                 u.level = p_match.level AND 
#                 u.frequency = p_match.frequency
#             WHERE NOT EXISTS (
#                 SELECT 1 FROM payments p 
#                 WHERE p.user_id = u.telegram_id AND p.status = 'approved'
#             ) AND p_match.is_active = TRUE
#         """)
#         targets = [dict(r) for r in rows]
#         filter_sql = "NOT EXISTS (SELECT 1 FROM payments p WHERE p.user_id = users.telegram_id AND p.status = 'approved')"

#     elif target == "paid":
#         # Users WITH at least one approved payment
#         rows = await db._pool.fetch("""
#             SELECT u.telegram_id, u.language
#             FROM users u
#             WHERE EXISTS (
#                 SELECT 1 FROM payments p
#                 WHERE p.user_id = u.telegram_id
#                 AND p.status = 'approved'
#             )
#         """)
#         targets = [dict(r) for r in rows]
#         filter_sql = "EXISTS (SELECT 1 FROM payments p WHERE p.user_id = users.telegram_id AND p.status = 'approved')"

#     else:  # all users
#         rows = await db._pool.fetch("SELECT telegram_id, language FROM users")
#         targets = [dict(r) for r in rows]
#         filter_sql = "TRUE"


#     total = len(targets)
#     from datetime import datetime, timezone

#     expires_at = datetime.now(timezone.utc) + timedelta(hours=DEAL_DURATION_HOURS)

#     # Persist broadcast run (best-effort)
#     broadcast_id = None
#     try:
#         row = await db._pool.fetchrow(
#             "INSERT INTO broadcasts (name, target_filter, language, expires_at, total_target, admin_id) VALUES ($1,$2,$3,$4,$5,$6) RETURNING id",
#             f"1-day deal {datetime.utcnow().isoformat()}",
#             target,
#             None,
#             expires_at,
#             total,
#             admin_id
#         )
#         if row:
#             broadcast_id = row['id']
#     except Exception as e:
#         logging.warning("Failed to create broadcasts row: %s", e)

#     # Update users with deal info (skip in test mode)
#     print('here is filters_sql', filter_sql)
#     if filter_sql:
#         try:
#             await db._pool.execute(
#                 "UPDATE users SET deal_expires_at = $1, deal_price = $2 WHERE " + filter_sql,
#                 expires_at,
#                 DEAL_PRICE
#             )
#         except Exception as e:
#             logging.warning("Failed to update users with deal info: %s", e)

#     sent = 0
#     failed = 0
#     print('here are targets', targets)
#     deleted_count = 0  # Track removed users

#     for user in targets:
#         uid = user.get('telegram_id')
#         lang = user.get('language') or 'EN'
        
#         # Try to get the ID from the database row first
#         p_id = user.get('matched_product_id')
        
#         # If it's missing (backfill didn't catch it or new user), find it manually
#         if not p_id:
#             # We fetch user details to perform a match
#             u_detail = await db._pool.fetchrow(
#                 "SELECT language, level, frequency, gender FROM users WHERE telegram_id = $1", 
#                 uid
#             )
#             if u_detail:
#                 # Find matching product
#                 matched = await db._pool.fetchrow("""
#                     SELECT id FROM products 
#                     WHERE language = $1 AND gender = $2 AND level = $3 AND frequency = $4
#                     AND is_active = TRUE LIMIT 1
#                 """, u_detail['language'], u_detail['gender'], u_detail['level'], u_detail['frequency'])
                
#                 if matched:
#                     p_id = matched['id']
#                 else:
#                     logging.warning(f"No matching product for user {uid} stats.")
#                     continue
#             else:
#                 continue

#         try:
#                 text, kb = build_deal_message(lang, expires_at, p_id)
                
#                 # USE YOUR IMAGE FILE ID HERE
#                 # If you don't have the file_id yet, you can use a URL or local path
#                 EID_IMAGE = "AgACAgQAAxkBAAJUpmnaGaRTgE7YEUuuv1APRgr6oQSKAALiDGsb_NbRUkqWa0dpKBy-AQADAgADeQADOwQ" 
#                 VOICE_FILE_ID = "AwACAgQAAxkBAAKMUGnsWpYTz4-F53S7znEbifGIgEqOAAIuHQACPshhUzSMsnnk6RpxOwQ" # main
#                 # VOICE_FILE_ID = "CQACAgQAAxkBAAIGvWnkeNgyytPGvMAxQOBdbqZ4WAIzAALpGwACzAgoU3N3WvzGKmx3OwQ" #demo

#                 # sent_msg = await bot.send_photo(
#                 #     chat_id=uid,
#                 #     photo=EID_IMAGE,
#                 #     caption=text,
#                 #     reply_markup=kb,
#                 #     parse_mode="HTML"
#                 # )
#                 await bot.send_voice(
#                     chat_id=uid,
#                     voice=VOICE_FILE_ID,
#                     caption="🎤 መልዕክት ከኮች ህላዌ (Listen to this first)" # Static caption
#                 )

#                 # 2. Send the Deal Message as a separate Text Message
#                 # This message is EDITABLE by your reminder_worker
#                 sent_msg = await bot.send_message(
#                     chat_id=uid,
#                     text=text,
#                     reply_markup=kb,
#                     parse_mode="HTML"
#                 )
                
#                 # 2. SAVE for future editing (countdown updates)
#                 await db._pool.execute("""
#                     UPDATE users SET 
#                         last_broadcast_msg_id = $1, 
#                         matched_product_id = $2 
#                     WHERE telegram_id = $3
#                 """, sent_msg.message_id, p_id, uid)
                
#                 sent += 1
#                 await asyncio.sleep(BATCH_SLEEP)
            
#         except Exception as e:
#             failed += 1
#             error_str = str(e).lower()
#             if "blocked" in error_str or "chat not found" in error_str or "deactivated" in error_str:
#                 try:
#                     # SILENT DELETE: Wipe the user so we don't waste resources next time
#                     await db._pool.execute("DELETE FROM users WHERE telegram_id = $1", uid)
#                     deleted_count += 1
#                     logging.info(f"User {uid} removed from DB (Reason: Bot Blocked/Deactivated)")
#                 except Exception as db_e:
#                     logging.error(f"Failed to delete dead user {uid} from DB: {db_e}")
#             else:
#                 logging.error(f"Transient failure for {uid}: {e}")
            
            
#     # Update broadcast stats if we created a row
#     if broadcast_id:
#         try:
#             await db._pool.execute(
#                 "UPDATE broadcasts SET sent_count = $1, failed_count = $2 WHERE id = $3",
#                 sent, failed, broadcast_id
#             )
#         except Exception as e:
#             logging.warning("Failed to update broadcast stats: %s", e)

#     # Notify admin with summary (best-effort)
#     try:
#         summary = (
#             f"🏁 *BROADCAST COMPLETE*\n\n"
#             f"✅ Sent: `{sent}`\n"
#             f"❌ Failed: `{failed}`\n"
#             f"🗑 Removed from DB: `{deleted_count}`\n\n"
#             f"Broadcast id: `{broadcast_id}`"
#         )
#         await bot.send_message(admin_id, summary, parse_mode="Markdown")
#     except Exception:
#         pass

#     return {"broadcast_id": broadcast_id, "sent": sent, "failed": failed, "deleted": deleted_count}


# # Confirm-launch callback (no draft checks)
# @router.callback_query(F.data.startswith("confirm_launch:"))
# async def on_confirm_launch(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
#     target = callback.data.split(":", 1)[1]
#     admin_id = callback.from_user.id

#     await callback.message.edit_text(f"🚀 Launch Initiated... Target mode: `{target}`")
#     test_mode = (target == "test")

#     asyncio.create_task(execute_broadcast_run(bot, db, admin_id, target, test_mode=test_mode))
#     await state.clear()

# # --- Optional: quick dry-run command (returns counts without sending) ---
# @router.message(F.text == "/broadcast_dryrun", F.from_user.id.in_(settings.ADMIN_IDS))
# async def broadcast_dryrun(message: types.Message):
#     # returns counts for unpaid/paid/all
#     try:
#         # Use the SAME logic as your broadcast executor
#         unpaid = await db._pool.fetchrow("""
#             SELECT COUNT(*) AS cnt FROM users u 
#             WHERE NOT EXISTS (SELECT 1 FROM payments p WHERE p.user_id = u.telegram_id AND p.status = 'approved')
#         """)
#         paid = await db._pool.fetchrow("""
#             SELECT COUNT(*) AS cnt FROM users u 
#             WHERE EXISTS (SELECT 1 FROM payments p WHERE p.user_id = u.telegram_id AND p.status = 'approved')
#         """)
#         total = await db._pool.fetchrow("SELECT COUNT(*) AS cnt FROM users")
#         await message.answer(
#             f"Dry run counts:\n• Unpaid: `{unpaid['cnt']}`\n• Paid: `{paid['cnt']}`\n• Total: `{total['cnt']}`",
#             parse_mode="Markdown"
#         )
#     except Exception as e:
#         await message.answer(f"Failed to fetch counts: {e}")
        
        
# @router.message(Command("test_feedback"), F.from_user.id.in_(settings.ADMIN_IDS))
# async def cmd_test_feedback(message: types.Message, db, bot: Bot, state: FSMContext):
#     args = message.text.split()
#     if len(args) < 2: 
#         return await message.answer("Usage: /test_feedback 1")
    
#     try:
#         q_id = int(args[1])
        
#         # Pull storage directly from the state object's internal reference
#         storage = state.storage 

#         from testimonial.testimonial_questions import run_testimonial_cycle
#         count = await run_testimonial_cycle(bot, db, storage, q_id, test_mode=True)
        
#         await message.answer(f"✅ Test mode active. Sent to {count} admins.")
        
#     except Exception as e:
#         logging.error(f"Test feedback error: {e}")
#         # Send as plain text to avoid the "can't parse entities" HTML error
#         await message.answer(f"❌ Error: {str(e)}", parse_mode=None)