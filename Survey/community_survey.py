import logging
import asyncio
from datetime import datetime
from aiogram import Router, types, F, Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError
from config import settings

router = Router()

# --- 1. UI COMPONENTS & KEYBOARDS ---

def get_initial_survey_kb(lang: str):
    kb = InlineKeyboardBuilder()
    if lang == "AM":
        kb.button(text="🙋‍♂️ አዎ፣ በእርግጠኝነት እቀላቀላለሁ!", callback_data="club_survey:yes")
        kb.button(text="❌ አልፈልግም / አልችልም", callback_data="club_survey:no")
    else:
        kb.button(text="🙋‍♂️ Yes, Count Me In!", callback_data="club_survey:yes")
        kb.button(text="❌ No, Not Interested", callback_data="club_survey:no")
    kb.adjust(1)
    return kb.as_markup()


def get_reason_survey_kb(lang: str):
    kb = InlineKeyboardBuilder()
    if lang == "AM":
        kb.button(text="💰 ዋጋው ውድ ነው", callback_data="club_reason:price")
        kb.button(text="⏳ ጊዜ የለኝም", callback_data="club_reason:time")
        kb.button(text="🏋️‍♂️ ኮሚኒቲው(ምህበረሰቡ) አያስፈልገኝም", callback_data="club_reason:not_needed")
    else:
        kb.button(text="💰 Price is too high", callback_data="club_reason:price")
        kb.button(text="⏳ No time for live sessions", callback_data="club_reason:time")
        kb.button(text="🏋️‍♂️ Don't need a community", callback_data="club_reason:not_needed")
    kb.adjust(1)
    return kb.as_markup()


async def get_club_text(bot: Bot, uid: int, lang: str, is_paid: bool):
    try:
        chat = await bot.get_chat(uid)
        name = chat.first_name or ""
    except Exception:
        name = ""

    # Tailor the introductory hook based on payment segments
    if lang == "AM":
        hook = "የእኛን የስልጠና ፕሮግራም በመግዛት የመጀመሪያውን እርምጃ ወስደዋል።" if is_paid else "የእኛን የአካል ብቃት ቦት በመቀላቀል የመጀመሪያውን እርምጃ ወስደዋል።"
        return (
            f"ሰላም {name}! 👋\n\n"
            f"{hook} አሁን ደግሞ የጀመሩትን ለውጥ ሳያቋርጡ በዘላቂነት እንዲቀጥሉ መርዳት እንፈልጋለን።\n\n"
            f"ለዚህም ቀጥታ የኮቹን የቅርብ ክትትልና ድጋፍ የሚያገኙበት <b>Coach Hilawe Transformation Club</b> ልንጀምር አቅደናል።\n\n"
            f"<b>🔥 ምን ያገኛሉ?</b>\n"
            f"✅ በየሳምንቱ የቀጥታ ስርጭት ስብሰባ (Live Session) — ከኮቹ ጋር ቀጥታ ጥያቄና መልስ\n"
            f"✅ ስለ ልምምድዎ እና ስለ አመጋገብዎ ቀጥታ እገዛ እና ማስተካከያ ምክሮች\n"
            f"✅ ያለፉ የLive ስብሰባ ቪዲዮዎችን በማንኛውም ጊዜ መልሰው ማየት የሚችሉበት ማህደር\n\n"
            f"ይህንን የግል ክለብ በወር <b>299 ብር</b> ብቻ (በቀን ከ10 ብር ያነሰ) ብንጀምረው ለመቀላቀል ፍላጎት አለዎት?"
        )
        
    hook = "You already took the first step by joining our fitness program." if is_paid else "You already took the first step by joining our fitness community."
    return (
        f"Hey {name}! 👋\n\n"
        f"{hook} Now, we want to make sure you stay consistent and keep your hard-earned results.\n\n"
        f"To give you direct, ongoing support, we are starting the <b>Coach Hilawe Transformation Club</b>.\n\n"
        f"<b>🔥 What You Get:</b>\n"
        f"✅ 1 Live session every week with Coach Hilawe (Ask your questions directly)\n"
        f"✅ Direct help and advice to adjust your workouts and diet\n"
        f"✅ Full access to watch all past live video recordings anytime\n\n"
        f"If we open this private club for just <b>299 ETB/month</b> (less than 10 Birr a day), would you join us?"
    )

# --- 2. BROADCASTER ENGINE (ROUND 2: ALL REGISTERED NON-VOTED USERS) ---

async def run_club_survey_broadcast(bot: Bot, db):
    """
    Round 2 Broadcaster: Targets EVERY registered user in the system 
    who has NOT cast a vote yet, regardless of payment history.
    """
    rows = await db._pool.fetch("""
        SELECT u.telegram_id, u.language,
               EXISTS(SELECT 1 FROM payments p WHERE p.user_id = u.telegram_id AND p.status = 'approved') as is_paid
        FROM users u
        WHERE NOT EXISTS (
            SELECT 1 FROM club_survey_results r 
            WHERE r.user_id = u.telegram_id
        )
    """)
    
    logging.info(f"🚀 Starting Club Survey Round 2 for {len(rows)} remaining users.")
    sent, skipped, failed = 0, 0, 0

    for user in rows:
        uid = user['telegram_id']
        lang = user['language'] or 'EN'
        is_paid = user['is_paid']
        
        try:
            text = await get_club_text(bot, uid, lang, is_paid)
            kb = get_initial_survey_kb(lang)
            
            await bot.send_message(chat_id=uid, text=text, reply_markup=kb, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.05)  # Safe spacing (20 msgs/sec) to perfectly obey Telegram limits
            
        except TelegramForbiddenError:
            logging.warning(f"🚫 User {uid} blocked the bot. Skipping smoothly.")
            skipped += 1
        except TelegramAPIError as tae:
            logging.error(f"⚠️ Telegram API exception for user {uid}: {tae}")
            failed += 1
        except Exception as e:
            logging.error(f"❌ Structural system error for user {uid}: {e}")
            failed += 1

    return sent, skipped, failed

# --- 3. INBOUND SURVEY RESPONSE HANDLERS ---

@router.callback_query(F.data.startswith("club_survey:"))
async def handle_club_initial_vote(callback: types.CallbackQuery, db):
    vote = callback.data.split(":")[1]
    uid = callback.from_user.id
    will_join = (vote == "yes")
    
    lang = await db._pool.fetchval("SELECT language FROM users WHERE telegram_id = $1", uid) or "EN"

    existing = await db._pool.fetchrow("SELECT will_join FROM club_survey_results WHERE user_id = $1", uid)
    if existing:
        msg = "አስተያየትዎን ከዚህ በፊት አስገብተዋል! እናመሰግናለን። 🙏" if lang == "AM" else "You have already submitted your feedback! Thank you. 🙏"
        return await callback.answer(msg, show_alert=True)

    if will_join:
        await db._pool.execute("""
            INSERT INTO club_survey_results (user_id, will_join) 
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET will_join = $2, reason_if_no = NULL
        """, uid, True)
        
        thanks = (
            "<b>በጣም ደስ ይላል! 🎉 ፍላጎትዎን መዝግበናል።</b>\n\n"
            "ክለቡን በቅርቡ በይፋ ስንጀምር መጀመሪያ ለእርስዎ ጥሪ እናደርሳለን። ስለ እምነትዎ እናመሰግናለን!"
        ) if lang == "AM" else (
            "<b>Awesome! 🎉 We've registered your interest.</b>\n\n"
            "As a club member, we will notify you immediately as soon as we launch the Inner Circle. Thank you for your support!"
        )
        await callback.message.edit_text(thanks, parse_mode="HTML")
        await callback.answer("Response saved!")
    else:
        reason_prompt = (
            "<b>አስተያየትዎ ለእኛ በጣም ጠቃሚ ነው።</b>\n\n"
            "ክለቡን ይበልጥ ለማሻሻል እንድንችል ዋናው ያልፈለጉበት ምክንያት ምን እንደሆነ ቢነግሩን ደስ ይለናል፦"
        ) if lang == "AM" else (
            "<b>Your feedback helps us grow.</b>\n\n"
            "To help us refine our service, could you tell us the main reason why you wouldn't join at this time?"
        )
        await callback.message.edit_text(reason_prompt, reply_markup=get_reason_survey_kb(lang), parse_mode="HTML")
        await callback.answer()


@router.callback_query(F.data.startswith("club_reason:"))
async def handle_club_reason_vote(callback: types.CallbackQuery, db):
    reason = callback.data.split(":")[1]
    uid = callback.from_user.id
    
    lang = await db._pool.fetchval("SELECT language FROM users WHERE telegram_id = $1", uid) or "EN"
    
    try:
        await db._pool.execute("""
            INSERT INTO club_survey_results (user_id, will_join, reason_if_no) 
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE SET will_join = $2, reason_if_no = $3
        """, uid, False, reason)
        
        final_thanks = (
            "✅ ተቀብለናል! ስለ ግልጽ አስተያየትዎ ከልብ እናመሰግናለን። ፕሮግራሞቻችንን ለማሻሻል እንጠቀምበታለን።"
        ) if lang == "AM" else (
            "<b>✅ Message received!</b>\n\nThank you for your honest feedback. We will use this to improve our system."
        )
        await callback.message.edit_text(final_thanks, parse_mode="HTML")
        await callback.answer("Feedback updated!")
    except Exception as e:
        logging.error(f"Error saving negative survey reason: {e}")
        await callback.answer("Error processing request.")

# --- 4. ADMIN ANALYTICS COMMANDS ---

@router.message(Command("trigger_club_survey"), F.from_user.id.in_(settings.ADMIN_IDS))
async def admin_trigger_club_poll(message: types.Message, bot: Bot, db):
    await message.answer("⏳ <b>Round 2 Broadcast Active:</b> Contacting remaining unvoted users...")
    sent, skipped, failed = await run_club_survey_broadcast(bot, db)
    
    report = (
        f"🏁 <b>Round 2 Broadcast Complete</b>\n\n"
        f"👥 New Target Users Contacted: <code>{sent}</code>\n"
        f"🚫 Blocked & Skipped: <code>{skipped}</code>\n"
        f"⚠️ System Exceptions Handled: <code>{failed}</code>"
    )
    await message.answer(report, parse_mode="HTML")


@router.message(Command("club_survey_status"), F.from_user.id.in_(settings.ADMIN_IDS))
async def admin_club_dryrun(message: types.Message, db):
    stats = await db._pool.fetchrow("""
        WITH system_metrics AS (
            SELECT COUNT(*) as total_users FROM users
        ),
        voted_metrics AS (
            SELECT COUNT(*) as total_voted FROM club_survey_results
        )
        SELECT s.total_users, v.total_voted FROM system_metrics s, voted_metrics v
    """)
    
    total = stats['total_users'] or 0
    received = stats['total_voted'] or 0
    remaining = total - received
    percent = (received / total * 100) if total > 0 else 0
    
    bar = "🟩" * int(percent / 10) + "⬜" * (10 - int(percent / 10))

    report = (
        "📊 <b>TOTAL CAMPAIGN STATUS REPORT</b>\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"🎯 <b>Total Global Users:</b> <code>{total}</code>\n"
        f"✅ <b>Total Votes Captured:</b> <code>{received}</code>\n"
        f"⏳ <b>Total Remaining Pool:</b> <code>{remaining}</code>\n\n"
        f"<b>Overall Participation Progress:</b>\n"
        f"{bar} {percent:.1f}%\n"
    )
    await message.answer(report, parse_mode="HTML")


@router.message(Command("club_survey_results"), F.from_user.id.in_(settings.ADMIN_IDS))
async def admin_club_detailed_analytics(message: types.Message, db):
    """
    Segregates responses transparently based on user attributes:
    - Round 1 metrics reflect premium, paid user accounts.
    - Round 2 metrics represent un-converted or standard user accounts.
    """
    rounds_data = await db._pool.fetch("""
        SELECT 
            EXISTS(SELECT 1 FROM payments p WHERE p.user_id = r.user_id AND p.status = 'approved') as is_paid,
            COUNT(*) FILTER (WHERE will_join = TRUE) as yes_count,
            COUNT(*) FILTER (WHERE will_join = FALSE) as no_count
        FROM club_survey_results r
        GROUP BY is_paid
    """)
    
    reasons = await db._pool.fetch("""
        SELECT reason_if_no, COUNT(*) as count 
        FROM club_survey_results 
        WHERE will_join = FALSE 
        GROUP BY reason_if_no
        ORDER BY count DESC
    """)

    r1_yes, r1_no = 0, 0
    r2_yes, r2_no = 0, 0

    for row in rounds_data:
        if row['is_paid']:
            r1_yes = row['yes_count']
            r1_no = row['no_count']
        else:
            r2_yes = row['yes_count']
            r2_no = row['no_count']

    r1_total = r1_yes + r1_no
    r2_total = r2_yes + r2_no
    
    r1_pct = (r1_yes / r1_total * 100) if r1_total > 0 else 0
    r2_pct = (r2_yes / r2_total * 100) if r2_total > 0 else 0

    report = (
        "📈 <b>COMPREHENSIVE SURVEY RESULTS REPORT</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💎 <b>ROUND 1: Paid Users Segment</b>\n"
        f"├ 🙋‍♂️ Will Join: <b>{r1_yes}</b> ({r1_pct:.1f}%)\n"
        f"└ 🙅‍♂️ Declined: <b>{r1_no}</b>\n"
        f"└ Total Responses: <code>{r1_total}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📢 <b>ROUND 2: Unpaid Users Segment</b>\n"
        f"├ 🙋‍♂️ Will Join: <b>{r2_yes}</b> ({r2_pct:.1f}%)\n"
        f"└ 🙅‍♂️ Declined: <b>{r2_no}</b>\n"
        f"└ Total Responses: <code>{r2_total}</code>\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📉 <b>Global Breakdown of Rejection Reasons:</b>\n"
    )
    
    if not reasons:
        report += "<i>No rejection complaints logged yet.</i>"
    else:
        for r in reasons:
            label = r['reason_if_no'] or "Unspecified"
            report += f"└ <code>{label}</code>: <b>{r['count']}</b> users\n"
            
    await message.answer(report, parse_mode="HTML")