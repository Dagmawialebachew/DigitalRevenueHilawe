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
#  እያንዳንዱ ምስክርነት የተለየ ገዢ ስነ-ልቦናን ያጠቃልላል።
# ─────────────────────────────────────────────
from datetime import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ─────────────────────────────────────────────
#  TESTIMONIALS — 3 each, rotating by hour
#  እያንዳንዱ ምስክርነት የተለየ ገዢ ስነ-ልቦናን ያጠቃልላል።
# ─────────────────────────────────────────────
from datetime import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ─────────────────────────────────────────────
#  TESTIMONIALS — Monday-focused reality checks
#  ተጠቃሚው ሁልጊዜ ሰኞ ሰኞ የሚገባውን የውሸት ቃል የሚያጋልጡ እውነተኛ ምስክርነቶች
# ─────────────────────────────────────────────
TESTIMONIALS = {
    "AM": [
        {
            "text": (
                "እውነቱን ለመናገር — 399 ብር ስሰማ 'ምን ሊረባ ነገር ይኖረዋል?' ብዬ በጣም ጠርጥሬ ነበር። "
                "ግን ውስጥ ያለውን ሲስተም ስከፍተው ደነገጥኩ! PDF መመሪያው እጅግ ግልጽ ነው፣ "
                "ቪዲዮዎቹ ልክ ከጎኔ ሆኖ የሚያሰለጥነኝ የግል አሰልጣኝ ያለኝ ያህል ነው የሚሰማኝ። "
                "በዚህ ዋጋ ይሄን አለመግዛት ራስን መበደል ነው።"
            ),
            "name": "ዳዊት መኮንን ✅ አባል",
        },
        {
            "text": (
                "ከዚህ በፊት ብዙ የውጪ ፕሮግራሞችን ሞክሬ አልሰሩልኝም — ምክንያቱም ምግባቸው ለኛ አይሆንም። "
                "ይሄ ግን ለኛ ለኢትዮጵያውያን የተሰራ ነው። እንጀራ፣ ጥብስ፣ ሽሮ — ሁሉም የሀገራችን ምግቦች አሉ። "
                "8 ሳምንት ብቻ በስነስርዓት ተከትዬ ሆዴ ሙሉ በሙሉ ጠፋ፣ ትከሻዬ ሰፋ! ቃሌን እሰጣለሁ — ይሰራል።"
            ),
            "name": "ናትናኤል ግርማ ✅ አባል",
        },
        {
            "text": (
                "መጀመሪያ በቅናሽ ዋጋ ስገዛው ዝም ብሎ መጽሐፍ (PDF) ብቻ መስሎኝ ነበር። "
                "ግን ውስጥ ያለው የቪዲዮ ስልጠና፣ የምግብ አዘገጃጀት እና ግልጽ የሆነው እቅድ አስገርሞኛል። "
                "በዚህ ዋጋ ይሄን ያህል ጥራት ያለው ስራ ማግኘት በሀገራችን አይታሰብም።"
            ),
            "name": "ዮሴፍ ካሳ ✅ አባል",
        },
    ],
    "EN": [
        {
            "text": (
                "Honestly — when I saw 299 ETB I thought 'what could this possibly offer?' "
                "I was wrong. The PDF is detailed, the videos are premium, "
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
                "When I bought this during the last sale, I thought it was just a simple PDF. "
                "But the HD videos and the nutrition plan are professional grade. "
                "Getting this quality for this price is an absolute steal."
            ),
            "name": "Yosef K. ✅ Verified Member",
        },
    ],
}
# ─────────────────────────────────────────────
#  SOCIAL PROOF — ማህበረሰባዊ ግፊት
# ─────────────────────────────────────────────
SOCIAL_PROOF = {
    "AM": [
        "🔥 ልክ አሁኑኑ አንተ እያመነታህ ባለህበት ሰከንድ፣ 3,500+ ኢትዮጵያውያን በቦቱ ስልጠናቸውን እየሰሩ ነው።",
        # "📉 በየቀኑ በመቶዎች የሚቆጠሩ ወንዶች ወደ ጀግና ማንነታቸው ሲቀየሩ፣ አንተ ግን አሁንም በድሮው አካልህ ውስጥ ነህ።",
        "🏘️ ከቦሌ እስከ ክልል ከተሞች — በተግባር የሚያሳዩ ወንዶች ዛሬ ሰዎች በለውጥ ጀምረውታል።",
    ],
    "EN": [
        "🔥 While you look at this screen, 3,500+ Ethiopians are actively crushing their goals inside this system.",
        "📉 Every single day, hundreds of men are upgrading their physiques while you remain unchanged.",
        "🏘️ From Addis to every region — elite transformations are dropping live right now.",
    ],
}

# ─────────────────────────────────────────────
#  URGENCY — ጊዜን የመጠቀም አስገዳጅነት
# ─────────────────────────────────────────────
URGENCY = {
    "AM": [
        "⚠️ የሰኞ እጣ ፈንታህ፦ ይህንን የ70% ቅናሽ ተጠቅመህ አሁኑኑ መጀመር ወይም እንደተለመደው ማዘግየት!",
        "⏳ ከ3 ሰዓት በኋላ ይህ መልዕክት በራሱ ይጠፋል፤ ዋጋውም ወዲያውኑ ወደ 1,000 ብር ይመለሳል።",
        "🔥 ዛሬ ካልወሰንከው፣ በሚቀጥለው ሰኞም በተመሳሳይ ደካማ አካል እና በቁጭት ውስጥ መሆንህን እወቀው።",
    ],
    "EN": [
        "⚠️ MONDAY ULTIMATUM: Break your cycle of broken promises now or remain exactly the same.",
        "⏳ In strictly 3 hours, this special 70% discount expires and price reverts to 1,000 ETB.",
        "🔥 If you bypass this today, you will face the exact same insecure reflection next Monday.",
    ],
}


def get_rotating_content(lang: str):
    lang = lang.upper() if lang.upper() in ["AM", "EN"] else "EN"
    now = datetime.now()

    testi_list   = TESTIMONIALS[lang]
    proof_list   = SOCIAL_PROOF[lang]
    urgency_list = URGENCY[lang]

    # በየሰዓቱ ይዘቱ በራሱ ይሽከረከራል — ሁሌም አዲስና አንቀጥቃጭ ስሜት ይሰጣል
    idx = (now.timetuple().tm_yday * 24) + now.hour

    return (
        testi_list[idx % len(testi_list)],
        proof_list[idx % len(proof_list)],
        urgency_list[idx % len(urgency_list)],
    )
def build_deal_message(lang: str, product_id: int, price: int = 399, original_price: int = 1100):
    lang = lang.upper() if lang.upper() in ["AM", "EN"] else "EN"
    
    # Standard calculations for reframing value
    daily_cost = round(price / 60, 1)

    if lang == "AM":
        text = (
            f"<b>ቦታ ከመሙላቱ በፊት ይክፈቱ! 🚨 8 ሳምንት ሙሉ ሰውነትዎን የሚቀይርበት የመጨረሻ ዕድል!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"ብዙዎቻችሁ <i>'በየወሩ የሚከፈል ነው?'</i> ወይም <i>'አሁን ላይ ብር የለኝም'</i> እያላችሁ እድሉ እያመለጠችሁ ነው። <b>ግልፅ እናድርገው፦ ክፍያው የነበረው 1,100 ብር ነበር። አሁን ግን ለአንድ ወር ሳይሆን ለሙሉ 2 ወር (8 ሳምንት) የምትከፍሉት {price} ብር ብቻ ነው!</b>\n\n"
            f"ይህ ማለት በቀን <b>{daily_cost:.1f} ብር</b> ብቻ ማለት ነው! በአሁኑ ሰአት በአንድ ማኪያቶ ዋጋ ሙሉ ህይወትዎን የሚቀይር፣ ስብ የሚያቀልጥ እና ጡንቻ የሚገነባ ሲስተም በእጅዎ እያገኙ ነው። አሁንም ካመነቱ ጥፋቱ የእርስዎ ብቻ ነው።\n\n"
            f"💰 <b>የአንድ ጊዜ ልዩ ኢንቨስትመንት (ለ 8 ሳምንት ሙሉ)፦</b>\n"
            f"<s>{original_price} ብር</s> → <b>{price} ብር ብቻ! (የ65% ቅናሽ)</b>\n\n"
            f"<b>ምን ያገኛሉ?</b>\n"
            f"🔥 <b>Fat Loss & Muscle Gain፦</b> ሆድና ጎን የሚያጠፋ፣ ጠንካራ ጡንቻ የሚገነባ የአካል ብቃት ማሰልጠኛ\n"
            f"🎥 <b>ቀላል ቪዲዮዎች፦</b> እያንዳንዱን እንቅስቃሴ በስልክዎ እያዩ የሚሰሩት ግልፅ መመሪያ\n"
            f"🍲 <b>የሀገራችን ምግብ፦</b> ውድ 'የላይት' ምግቦች ሳይገዙ፣ በቤትዎ ባለው የሀበሻ ምግብ የሚሰራ የላይፍ-ስታይል አመጋገብ\n\n"
            f"⚡ <b>የአባላቶቻችን እውነተኛ ምስክርነት፦</b>\n"
            f"💬 <i>\"ክፍያው በየወሩ መስሎኝ ፈርቼ ነበር። ለአንድ ጊዜ ብቻ {price} ብር መሆኑን ሳውቅ ወዲያው ነው የጀመርኩት። በአንድ ወር ውስጥ ቦርጭ ሙሉ በሙሉ ጠፍቶ ደረቴ እና ትከሻዬ መውጣት ጀምሯል!\"</i>\n"
            f"— <b>ዮናስ ኪ.</b> ✅ (የ8 ሳምንት Transformation አባል)\n\n"
            f"⚠️ <b>ማሳሰቢያ፦</b> ይህ የዋጋ ቅናሽ በቅርቡ ይዘጋል። አሁኑኑ ተመዝግበው ለውጥዎን ይጀምሩ፦ 👇"
        )
        btn_text = f"🚀 የ 8 ሳምንት ፕሮግራሙን በ {price} ብር ክፈት"

    else:
        text = (
            f"<b>⚠️ ACCESS GATEWAY OPEN: Transform Your Body in 8 Weeks!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"Let's clear the confusion: <b>This is NOT a monthly subscription, and it is NOT an ongoing bill.</b> This is a ONE-TIME payment of just {price} ETB for the entire 8-week transformation system.\n\n"
            f"That breaks down to just <b>{daily_cost:.1f} ETB a day</b>—less than the price of a single macchiato. If you think you're 'out of cash,' you are prioritizing excuses over your health.\n\n"
            f"💰 <b>One-Time Investment (Zero Hidden Fees):</b>\n"
            f"<s>{original_price} ETB</s> → <b>{price} ETB Only! (Save 65%)</b>\n\n"
            f"<b>The Blueprint Includes:</b>\n"
            f"🔥 <b>Fat Loss & Muscle Gain:</b> Targeted routines built to strip stubborn fat and build clean muscle mass simultaneously.\n"
            f"🎥 <b>Step-by-Step Videos:</b> High-definition instructional guides right on your phone.\n"
            f"🍲 <b>100% Local Nutrition:</b> No expensive imported supplements. Achieve your goals using everyday local Ethiopian meals.\n\n"
            f"⚡ <b>Real Member Proof:</b>\n"
            f"💬 <i>\"I hesitated because I thought it was a monthly fee. When I realized {price} ETB covers the whole 8 weeks, I jumped in. Lost my belly fat and noticeably built up my chest and arms in just 4 weeks!\"</i>\n"
            f"— <b>Yonas K.</b> ✅ (Active Member)\n\n"
            f"👇 Click below to lock in your 8-week access before the price resets:"
        )
        btn_text = f"🚀 Unlock 8-Week Access for {price} ETB"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn_text, callback_data=f"pay_{product_id}")]
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
    target = callback.data.split(":", 1)[1]  # test | unpaid | paid | all | recent | recent_unpaid
    
    # Define targeting fragments to inject into the CTE
    target_filter = ""
    
    if target == "unpaid":
        # target_filter = "AND NOT EXISTS (SELECT 1 FROM payments pay WHERE pay.user_id = u.telegram_id AND pay.status = 'approved')"
        target_filter = """
        AND u.created_at >= NOW() - INTERVAL '8 weeks'
        AND NOT EXISTS (SELECT 1 FROM payments pay WHERE pay.user_id = u.telegram_id AND pay.status = 'approved')
        """
        
    elif target == "paid":
        target_filter = "AND EXISTS (SELECT 1 FROM payments pay WHERE pay.user_id = u.telegram_id AND pay.status = 'approved')"
        
    elif target == "test":
        target_filter = f"AND u.telegram_id = ANY(ARRAY{settings.ADMIN_IDS}::BIGINT[])"
        
    # 🔥 TARGET NEW SEGMENT: Everyone who joined in the last 3 weeks
    elif target == "recent":
        target_filter = "AND u.created_at >= NOW() - INTERVAL '3 weeks'"
        
    # 🔥 TARGET NEW SEGMENT: Unpaid leads who joined in the last 3 weeks (High-conversion recovery!)
    elif target == "recent_unpaid":
        target_filter = """
        AND u.created_at >= NOW() - INTERVAL '3 weeks'
        AND NOT EXISTS (SELECT 1 FROM payments pay WHERE pay.user_id = u.telegram_id AND pay.status = 'approved')
        """

    # Use a single, clean CTE. The fallback logic and targeting are handled inside.
    query = f"""
    WITH user_prices AS (
        SELECT 
            u.telegram_id,
            COALESCE(s.selected_price, 399) as effective_price
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
        f"🎯 <b>TARGETING SUMMARY: {target.upper().replace('_', ' ')}</b>\n"
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
            COALESCE(s.selected_price, 399) as final_price
        FROM users u
        INNER JOIN products p ON 
            u.language = p.language AND u.gender = p.gender AND 
            u.level = p.level AND u.frequency = p.frequency
        LEFT JOIN price_survey_results s ON s.user_id = u.telegram_id
        WHERE p.is_active = TRUE
    """
    
    if target == "unpaid":
        # base_query += " AND NOT EXISTS (SELECT 1 FROM payments pay WHERE pay.user_id = u.telegram_id AND pay.status = 'approved')"
        base_query += """
        AND u.created_at >= NOW() - INTERVAL '40 weeks'
        AND NOT EXISTS (SELECT 1 FROM payments pay WHERE pay.user_id = u.telegram_id AND pay.status = 'approved')
        """
    elif target == "paid":
        base_query += " AND EXISTS (SELECT 1 FROM payments pay WHERE pay.user_id = u.telegram_id AND pay.status = 'approved')"
    elif target == "test":
        base_query += f" AND u.telegram_id = ANY(ARRAY{settings.ADMIN_IDS}::BIGINT[])"
    
    # 🔥 Add these two new target blocks here:
    elif target == "recent":
        base_query += " AND u.created_at >= NOW() - INTERVAL '3 weeks'"
    elif target == "recent_unpaid":
        base_query += """
            AND u.created_at >= NOW() - INTERVAL '3 weeks' 
            AND NOT EXISTS (SELECT 1 FROM payments pay WHERE pay.user_id = u.telegram_id AND pay.status = 'approved')
        """

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
    CAMPAIGN_IMAGE_FILE_ID = "AgACAgQAAxkBAALX8Gn94mHeVAmqYUPkO9gE8xL34843AAJTDmsb9b7pU3MRcPN22trVAQADAgADeQADOwQ"  # 🔁 replace this
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

    # async def send_to_user(user):
    #         uid = user['telegram_id']
    #         price_key = str(int(user['final_price']))
        
    #         async with semaphore:
    #             try:
    #                 # የፅሁፍ መልዕክቱን እና በተንቀሳቃሽ ቁልፉን ማዘጋጀት
    #                 text, kb = build_deal_message(
    #                     lang=user['language'],
    #                     product_id=user['p_id'],
    #                     price=int(user['final_price'])
    #                 )
        
    #                 # ── 1. መጀመሪያ የድምፅ መልዕክቱን መላክ ──────────────────
    #                 await bot.send_voice(
    #                     chat_id=uid,
    #                     voice=CAMPAIGN_VOICE_FILE_ID
    #                 )
                    
    #                 # ── 2. በመቀጠል ሙሉ የፅሁፍ መረጃውን ከቁልፍ ጋር መላክ ───────
    #                 # የፅሁፍ ገደብ (1024) ስጋት የለብንም ምክንያቱም send_message እስከ 4096 ቁምፊዎችን ያስተናግዳል።
    #                 sent_msg = await bot.send_message(
    #                     chat_id=uid,
    #                     text=text,
    #                     reply_markup=kb,
    #                     parse_mode="HTML"
    #                 )
    #                 # ─────────────────────────────────────────────────
        
    #                 # የላክነውን የፅሁፍ መልዕክት ID በዳታቤዝ ውስጥ ማስቀመጥ (ለክፍያ ማረጋገጫ ሂደት እንዲጠቅመን)
    #                 await db._pool.execute(
    #                     "UPDATE users SET last_broadcast_msg_id = $1, matched_product_id = $2 WHERE telegram_id = $3",
    #                     sent_msg.message_id, user['p_id'], uid
    #                 )
        
    #                 stats["sent"] += 1
    #                 if price_key in stats:
    #                     stats[price_key] += 1
    #                 logger.info(f"✅ Delivered Voice + Msg: {uid} | Price: {price_key}")
        
    #             except Exception as e:
    #                 stats["failed"] += 1
    #                 err = str(e).lower()
    #                 logger.error(f"❌ Delivery Failed for {uid}: {err}")
        
    #                 if any(x in err for x in ["blocked", "chat not found", "deactivated", "user_is_deactivated"]):
    #                     try:
    #                         await db._pool.execute("DELETE FROM users WHERE telegram_id = $1", uid)
    #                         stats["deleted"] += 1
    #                         logger.info(f"🗑 Cleaned user {uid} from database.")
    #                     except Exception as db_err:
    #                         stats["skipped_cleanup"] += 1
    #                         logger.warning(f"⚠️ Could not delete {uid} (Referenced in payments): {db_err}")
        
    #             await asyncio.sleep(0.05)
    

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

