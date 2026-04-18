import logging
import asyncio
from datetime import datetime
from aiogram import Router, types, F, Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.exceptions import TelegramForbiddenError
from config import settings

router = Router()

# --- 1. UI COMPONENTS ---

def get_price_survey_keyboard():
    kb = InlineKeyboardBuilder()
    # Coach's requested 399, 499, 599 alternatives
    prices = [399, 499, 599]
    for p in prices:
        kb.button(text=f"{p} Br.", callback_data=f"price_survey:{p}")
    
    kb.button(text="Higher / ከዚህ በላይ", callback_data="price_survey:700")
    kb.adjust(2)
    return kb.as_markup()

async def get_survey_text(bot: Bot, uid: int, lang: str):
    try:
        chat = await bot.get_chat(uid)
        name = chat.first_name or "Athlete"
    except:
        name = "Athlete" if lang == "EN" else "አትሌት"

    if lang == "AM":
        return (
            f"ሰላም {name}! 👋\n\n"
            "የአካል ብቃት ጉዞዎን ለማቀለል አዳዲስ ነገሮችን እያዘጋጀን ነው። "
            "ይህ ፕሮግራም ለሁሉም ተደራሽ እንዲሆን ዋጋውን እያጠናን ነው፤ ለእርስዎ የትኛው ዋጋ ተመጣጣኝ ነው?"
        )
    return (
        f"Hey {name}! 👋\n\n"
        "We’re working on making our programs more accessible. To help us set the right price, "
        "which of these ranges would you be most comfortable with?"
    )

# --- 2. THE BROADCASTER ENGINE (WITH AUTO-CLEANUP) ---

async def run_price_survey_broadcast(bot: Bot, db):
    """
    Finds unpaid users, sends survey, and deletes anyone who blocked the bot.
    """
    # Fetch Unpaid Users
    rows = await db._pool.fetch("""
        SELECT u.telegram_id, u.language 
        FROM users u
        WHERE NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.user_id = u.telegram_id AND p.status = 'approved'
        )
    """)
    
    logging.info(f"🚀 Starting Survey for {len(rows)} unpaid users. Cleanup mode: ON.")
    
    sent = 0
    deleted = 0
    failed = 0

    for user in rows:
        uid = user['telegram_id']
        
        lang = user['language'] or 'EN'
        
        try:
            text = await get_survey_text(bot, uid, lang)
            kb = get_price_survey_keyboard()
            
            await bot.send_message(chat_id=uid, text=text, reply_markup=kb, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.06) # Smooth rate limiting
            
        except TelegramForbiddenError:
            # THIS IS THE BIRD WE ARE HITTING: User blocked the bot
            logging.warning(f"🗑️ User {uid} blocked the bot. Deleting from DB.")
            await db._pool.execute("DELETE FROM users WHERE telegram_id = $1", uid)
            deleted += 1
            
        except Exception as e:
            logging.error(f"❌ Other error for {uid}: {e}")
            failed += 1

    return sent, deleted, failed

# --- 3. HANDLERS ---

@router.message(Command("trigger_price_survey"), F.from_user.id.in_(settings.ADMIN_IDS))
async def admin_trigger_survey(message: types.Message, bot: Bot, db):
    await message.answer("⏳ Broadcast started. Cleaning out blocked users while sending...")
    
    sent, deleted, failed = await run_price_survey_broadcast(bot, db)
    
    report = (
        f"🏁 <b>Broadcast & Cleanup Complete</b>\n\n"
        f"✅ Successfully Sent: <code>{sent}</code>\n"
        f"🗑️ Blocked & Deleted: <code>{deleted}</code>\n"
        f"⚠️ Failed (Other): <code>{failed}</code>"
    )
    await message.answer(report, parse_mode="HTML")

@router.callback_query(F.data.startswith("price_survey:"))
async def handle_survey_response(callback: types.CallbackQuery, db):
    data_parts = callback.data.split(":")
    selected_val = int(data_parts[1])
    uid = callback.from_user.id
    
    try:
        await db._pool.execute("""
            INSERT INTO price_survey_results (user_id, selected_price) 
            VALUES ($1, $2) 
            ON CONFLICT (user_id) DO UPDATE SET selected_price = $2
        """, uid, selected_val)
        
        lang = await db._pool.fetchval("SELECT language FROM users WHERE telegram_id = $1", uid)
        thanks = "✅ Got it! Thanks for the feedback." if lang == "EN" else "✅ ተቀብያለሁ! ስለ አስተያየትዎ አመሰግናለሁ።"
        
        await callback.message.edit_text(f"<b>{callback.message.text}</b>\n\n{thanks}", parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logging.error(f"Error saving survey: {e}")
        await callback.answer("Error saving response.")

from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

# --- 1. Helper for the visual report ---
async def build_results_report(db):
    results = await db._pool.fetch("""
        SELECT selected_price, COUNT(*) as votes 
        FROM price_survey_results 
        GROUP BY selected_price 
        ORDER BY selected_price ASC
    """)
    
    if not results:
        return "No survey results yet.", None

    total_votes = sum(r['votes'] for r in results)
    now = datetime.now().strftime("%H:%M:%S")
    
    report = f"📊 <b>Live Price Survey Results</b>\n"
    report += f"<i>Last Updated: {now}</i>\n"
    report += f"━━━━━━━━━━━━━━━\n\n"

    for r in results:
        count = r['votes']
        price = r['selected_price']
        # Calculate percentage for a simple progress bar
        percent = (count / total_votes) * 100 if total_votes > 0 else 0
        bar_count = int(percent / 10) # 1 block per 10%
        bar = "🟦" * bar_count + "⬜" * (10 - bar_count)
        
        report += f"💰 <b>{price} ETB</b>\n"
        report += f"{bar} {int(percent)}%\n"
        report += f"└ 🗳 <b>{count} votes</b>\n\n"

    report += f"━━━━━━━━━━━━━━━\n"
    report += f"<b>Total Responses:</b> {total_votes}"

    # Build the refresh button
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Refresh Data", callback_data="refresh_survey_results")
    
    return report, kb.as_markup()

# --- 2. Handlers ---

@router.message(Command("survey_results"), F.from_user.id.in_(settings.ADMIN_IDS))
async def show_results_command(message: types.Message, db):
    """Initial trigger for the report."""
    report, markup = await build_results_report(db)
    await message.answer(report, reply_markup=markup, parse_mode="HTML")

@router.callback_query(F.data == "refresh_survey_results", F.from_user.id.in_(settings.ADMIN_IDS))
async def refresh_results_callback(callback: types.CallbackQuery, db):
    """Updates the existing message with fresh data."""
    report, markup = await build_results_report(db)
    
    # Only edit if the content actually changed (prevents telegram error for 'message is not modified')
    try:
        await callback.message.edit_text(report, reply_markup=markup, parse_mode="HTML")
        await callback.answer("Results Refreshed! ⚡️")
    except Exception as e:
        # Usually happens if someone clicks refresh and no new data has come in
        await callback.answer("Data is already up to date.")
        
@router.message(Command("survey_dryrun"), F.from_user.id.in_(settings.ADMIN_IDS))
async def survey_dryrun(message: types.Message, db):
    """Calculates how many users are eligible, surveyed, and remaining."""
    stats = await db._pool.fetchrow("""
        WITH target_users AS (
            SELECT telegram_id FROM users u
            WHERE NOT EXISTS (
                SELECT 1 FROM payments p 
                WHERE p.user_id = u.telegram_id AND p.status = 'approved'
            )
        )
        SELECT 
            (SELECT COUNT(*) FROM target_users) as total_target,
            (SELECT COUNT(*) FROM price_survey_results WHERE user_id IN (SELECT telegram_id FROM target_users)) as received_count
    """)
    
    total = stats['total_target']
    received = stats['received_count']
    remaining = total - received
    
    # Calculate completion percentage
    percent = (received / total * 100) if total > 0 else 0
    bar_count = int(percent / 10)
    progress_bar = "🟩" * bar_count + "⬜" * (10 - bar_count)

    report = (
        "🔍 <b>SURVEY STATUS REPORT</b>\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"🎯 <b>Total Unpaid Targets:</b> <code>{total}</code>\n"
        f"✅ <b>Responses Received:</b> <code>{received}</code>\n"
        f"⏳ <b>Pending / Not Voted:</b> <code>{remaining}</code>\n\n"
        f"<b>Participation Rate:</b>\n"
        f"{progress_bar} {percent:.1f}%\n\n"
        "<i>Note: 'Received' counts unique votes in the database.</i>"
    )
    await message.answer(report, parse_mode="HTML")

@router.message(Command("test_survey_flow"), F.from_user.id.in_(settings.ADMIN_IDS))
async def test_survey_flow(message: types.Message, bot: Bot, db):
    """Sends the survey ONLY to admins to test the UI and callback."""
    await message.answer("🧪 <b>TEST MODE:</b> Sending survey to admins only...")
    
    sent = 0
    for admin_id in settings.ADMIN_IDS:
        try:
            # We assume admins speak EN for the test or fetch their lang
            text = await get_survey_text(bot, admin_id, "EN") 
            kb = get_price_survey_keyboard()
            await bot.send_message(chat_id=admin_id, text=f"🧪 [TEST]\n{text}", reply_markup=kb, parse_mode="HTML")
            sent += 1
        except Exception as e:
            logging.error(f"Test failed for {admin_id}: {e}")

    await message.answer(f"✅ Test survey sent to {sent} admins. Go click the buttons to test the DB save!")