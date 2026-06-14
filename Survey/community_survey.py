import logging
import asyncio
from datetime import datetime
from aiogram import Router, types, F, Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.exceptions import TelegramForbiddenError
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
        kb.button(text="🏋️‍♂️ ማህበረሰቡ አያስፈልገኝም", callback_data="club_reason:not_needed")
    else:
        kb.button(text="💰 Price is too high", callback_data="club_reason:price")
        kb.button(text="⏳ No time for live sessions", callback_data="club_reason:time")
        kb.button(text="🏋️‍♂️ Don't need a community", callback_data="club_reason:not_needed")
    kb.adjust(1)
    return kb.as_markup()


async def get_club_text(bot: Bot, uid: int, lang: str):
    try:
        chat = await bot.get_chat(uid)
        name = chat.first_name or ""
    except Exception:
        name = ""

    if lang == "AM":
        
       return (
        f"ሰላም {name}! 👋\n\n"
        "የእኛን የስልጠና ፕሮግራም በመግዛት የመጀመሪያውን እርምጃ ወስደዋል። አሁን ደግሞ የጀመሩትን ለውጥ ሳያቋርጡ በዘላቂነት እንዲቀጥሉ መርዳት እንፈልጋለን።\n\n"
        "ለዚህም ቀጥታ የኮቹን የቅርብ ክትትልና ድጋፍ የሚያገኙበት <b>Coach Hilawe Transformation Club</b> ልንጀምር አቅደናል።\n\n"
        "<b>🔥 ምን ያገኛሉ?</b>\n"
        "✅ በየሳምንቱ የቀጥታ ስርጭት ስብሰባ (Live Session) — ከኮቹ ጋር ቀጥታ ጥያቄና መልስ\n"
        "✅ ስለ ልምምድዎ እና ስለ አመጋገብዎ ቀጥታ እገዛ እና ማስተካከያ ምክሮች\n"
        "✅ ያለፉ የLive ስብሰባ ቪዲዮዎችን በማንኛውም ጊዜ መልሰው ማየት የሚችሉበት ማህደር\n\n"
        "ይህንን የግል ክለብ በወር <b>299 ብር</b> ብቻ (በቀን ከ10 ብር ያነሰ) ብንጀምረው ለመቀላቀል ፍላጎት አለዎት?"
    )
       
    return (
            f"Hey {name}! 👋\n\n"
            "You already took the first step by joining our fitness program. Now, we want to make sure you stay consistent and keep your hard-earned results.\n\n"
            "To give you direct, ongoing support, we are starting the <b>Coach Hilawe Transformation Club</b>.\n\n"
            "<b>🔥 What You Get:</b>\n"
            "✅ 1 Live session every week with Coach Hilawe (Ask your questions directly)\n"
            "✅ Direct help and advice to adjust your workouts and diet\n"
            "✅ Full access to watch all past live video recordings anytime\n\n"
            "If we open this private club for just <b>299 ETB/month</b> (less than 10 Birr a day), would you join us?"
        )
# --- 2. BROADCASTER ENGINE (TARGETING PAID USERS ONLY) ---

async def run_club_survey_broadcast(bot: Bot, db):
    """
    Finds ONLY paid users (approved status) who haven't responded to the club poll yet.
    """
    rows = await db._pool.fetch("""
        SELECT DISTINCT u.telegram_id, u.language 
        FROM users u
        JOIN payments p ON p.user_id = u.telegram_id
        WHERE p.status = 'approved'
        AND NOT EXISTS (
            SELECT 1 FROM club_survey_results r 
            WHERE r.user_id = u.telegram_id
        )
    """)
    
    logging.info(f"🚀 Starting Club Survey Broadcast for {len(rows)} paid users.")
    sent, skipped, failed = 0, 0, 0

    for user in rows:
        uid = user['telegram_id']
        lang = user['language'] or 'EN'
        
        try:
            text = await get_club_text(bot, uid, lang)
            kb = get_initial_survey_kb(lang)
            
            await bot.send_message(chat_id=uid, text=text, reply_markup=kb, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.06) # Protection against rate limiting
            
        except TelegramForbiddenError:
            logging.warning(f"🚫 Paid user {uid} blocked the bot. Skipping cleanup to protect payment history cascade.")
            skipped += 1
        except Exception as e:
            logging.error(f"❌ Error sending survey to {uid}: {e}")
            failed += 1

    return sent, skipped, failed

# --- 3. INBOUND SURVEY RESPONSE HANDLERS ---

@router.callback_query(F.data.startswith("club_survey:"))
async def handle_club_initial_vote(callback: types.CallbackQuery, db):
    vote = callback.data.split(":")[1]
    uid = callback.from_user.id
    will_join = True if vote == "yes" else False
    
    lang = await db._pool.fetchval("SELECT language FROM users WHERE telegram_id = $1", uid) or "EN"

    # Anti-double vote restriction
    existing = await db._pool.fetchrow("SELECT will_join FROM club_survey_results WHERE user_id = $1", uid)
    if existing:
        msg = "አስተያየትዎን ከዚህ በፊት አስገብተዋል! እናመሰግናለን። 🙏" if lang == "AM" else "You have already submitted your feedback! Thank you. 🙏"
        return await callback.answer(msg, show_alert=True)

    if will_join:
        # Save positive vote to DB instantly
        await db._pool.execute("""
            INSERT INTO club_survey_results (user_id, will_join) 
            VALUES ($1, $2)
        """, uid, True)
        
        thanks = (
            "<b>በጣም ደስ ይላል! 🎉 ፍላጎትዎን መዝግበናል።</b>\n\n"
            "ክለቡን በቅርቡ በይፋ ስንጀምር መጀመሪያ ለእርስዎ ጥሪ እናደርሳለን። ስለ እምነትዎ እናመሰግናለን!"
        ) if lang == "AM" else (
            "<b>Awesome! 🎉 We've registered your interest.</b>\n\n"
            "As a founding member, we will notify you immediately as soon as we launch the Inner Circle. Thank you for your support!"
        )
        await callback.message.edit_text(thanks, parse_mode="HTML")
        await callback.answer("Response saved!")
    else:
        # User clicked No: Display reasons grid without inserting to DB yet to avoid breaking flow
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
    
    # Commit the 'No' option alongside the reason safely
    try:
        await db._pool.execute("""
            INSERT INTO club_survey_results (user_id, will_join, reason_if_no) 
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE SET will_join = $2, reason_if_no = $3
        """, uid, False, reason)
        
        final_thanks = (
            "✅ ተቀብለናል! ስለ ግልጽ አስተያየትዎ ከልብ እናመሰግናለን። ፕሮግራሞቻችንን ለማሻሻል እንጠቀምበታለን።"
        ) if lang == "AM" else (
            "✅ Message received! Thank you for your honest feedback. We will use this to improve our system."
        )
        await callback.message.edit_text(final_thanks, parse_mode="HTML")
        await callback.answer("Feedback updated!")
    except Exception as e:
        logging.error(f"Error saving negative survey reason: {e}")
        await callback.answer("Error processing request.")

# --- 4. ADMIN ANALYTICS COMMANDS ---

@router.message(Command("trigger_club_survey"), F.from_user.id.in_(settings.ADMIN_IDS))
async def admin_trigger_club_poll(message: types.Message, bot: Bot, db):
    await message.answer("⏳ Processing broadcast to all paid customers...")
    sent, skipped, failed = await run_club_survey_broadcast(bot, db)
    
    report = (
        f"🏁 <b>Club Survey Broadcast Complete</b>\n\n"
        f"👥 Target Paid Users Contacted: <code>{sent}</code>\n"
        f"🚫 Blocked & Skipped: <code>{skipped}</code>\n"
        f"⚠️ System Failures: <code>{failed}</code>"
    )
    await message.answer(report, parse_mode="HTML")


@router.message(Command("club_survey_status"), F.from_user.id.in_(settings.ADMIN_IDS))
async def admin_club_dryrun(message: types.Message, db):
    stats = await db._pool.fetchrow("""
        WITH total_paid AS (
            SELECT COUNT(DISTINCT user_id) as total FROM payments WHERE status = 'approved'
        ),
        voted_count AS (
            SELECT COUNT(*) as total FROM club_survey_results
        )
        SELECT 
            p.total as total_paid,
            v.total as total_voted
        FROM total_paid p, voted_count v
    """)
    
    total = stats['total_paid'] or 0
    received = stats['total_voted'] or 0
    remaining = total - received
    percent = (received / total * 100) if total > 0 else 0
    
    bar = "🟩" * int(percent / 10) + "⬜" * (10 - int(percent / 10))

    report = (
        "📊 <b>CLUB SURVEY RUNTIME STATUS</b>\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"🎯 <b>Total Paid Pool:</b> <code>{total}</code> users\n"
        f"✅ <b>Votes Captured:</b> <code>{received}</code> submissions\n"
        f"⏳ <b>Awaiting Responses:</b> <code>{remaining}</code> pending\n\n"
        f"<b>Conversion Rate Metrics:</b>\n"
        f"{bar} {percent:.1f}%\n"
    )
    await message.answer(report, parse_mode="HTML")


@router.message(Command("club_survey_results"), F.from_user.id.in_(settings.ADMIN_IDS))
async def admin_club_detailed_analytics(message: types.Message, db):
    totals = await db._pool.fetchrow("""
        SELECT 
            COUNT(*) FILTER (WHERE will_join = TRUE) as yes_count,
            COUNT(*) FILTER (WHERE will_join = FALSE) as no_count
        FROM club_survey_results
    """)
    
    reasons = await db._pool.fetch("""
        SELECT reason_if_no, COUNT(*) as count 
        FROM club_survey_results 
        WHERE will_join = FALSE 
        GROUP BY reason_if_no
    """)

    yes = totals['yes_count'] or 0
    no = totals['no_count'] or 0
    total = yes + no
    yes_pct = (yes / total * 100) if total > 0 else 0

    report = (
        "📈 <b>INNER CIRCLE MARKET DESIRE REPORT</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🙋‍♂️ <b>Willing to Join (299 ETB):</b> <code>{yes}</code> ({yes_pct:.1f}%)\n"
        f"🙅‍♂️ <b>Declined / Not Interested:</b> <code>{no}</code>\n"
        f"📊 <b>Total Feedback Pool:</b> {total}\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📉 <b>Breakdown of Rejection Reasons:</b>\n"
    )
    
    if not reasons:
        report += "<i>No rejection complaints logged yet.</i>"
    else:
        for r in reasons:
            label = r['reason_if_no'] or "Unspecified"
            report += f"└ <code>{label}</code>: <b>{r['count']}</b> users\n"
            
    await message.answer(report, parse_mode="HTML")