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
    prices = [299, 399, 499]
    for p in prices:
        kb.button(text=f"{p} Br.", callback_data=f"price_survey:{p}")
    
    kb.button(text="Higher / ከዚህ በላይ", callback_data="price_survey:700")
    kb.adjust(2)
    return kb.as_markup()



async def get_survey_text(bot: Bot, uid: int, lang: str):
    try:
        chat = await bot.get_chat(uid)
        name = chat.first_name or ""
    except:
        name = "" if lang == "EN" else ""

    if lang == "AM":
        return (
            f"ሰላም {name}! 👋\n\n"
            "የ<b>የአካል ብቃት(Workout)ፕላን እና የምግብ መመሪያ</b> እስካሁን እንዳልጀመሩ አስታውያለው። "
            "ይህ እቅድ ለሁሉም ተደራሽ መሆኑን ለማረጋገጥ የእርስዎን አስተያየት እፈልጋለሁ።\n\n"
            "<i>ለእርስዎ ተመጣጣኝ የሆነው የዋጋ አማራጭ የትኛው ነው?</i>"
        )
    return (
        f"Hey {name}! 👋\n\n"
        "I noticed you haven't started your <b>Workout Plan & Meal Guidance</b> journey with us yet. "
        "I want to make sure our guides are accessible to everyone, and I'd love your honest feedback.\n\n"
        "<i>Which of these price points would make it easiest for you to get started?</i>"
    )

# --- 2. THE BROADCASTER ENGINE (WITH AUTO-CLEANUP) ---

async def run_price_survey_broadcast(bot: Bot, db):
    """
    Finds unpaid users who haven't responded yet and sends the survey.
    Handles blocks and FK violations gracefully.
    """
    # 1. FETCH: Only users who haven't paid AND haven't voted yet
    rows = await db._pool.fetch("""
        SELECT u.telegram_id, u.language 
        FROM users u
        WHERE NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.user_id = u.telegram_id AND p.status = 'approved'
        )
        AND NOT EXISTS (
            SELECT 1 FROM price_survey_results r 
            WHERE r.user_id = u.telegram_id
        )
    """)
    
    logging.info(f"🚀 Starting Survey for {len(rows)} users who haven't voted yet.")
    
    sent, skipped, failed = 0, 0, 0

    for user in rows:
        uid = user['telegram_id']
        lang = user['language'] or 'EN'
        
        try:
            text = await get_survey_text(bot, uid, lang)
            kb = get_price_survey_keyboard()
            
            await bot.send_message(chat_id=uid, text=text, reply_markup=kb, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.06) 
            
        except TelegramForbiddenError:
            # Catch block and try to delete; if FK violation happens, just skip
            logging.warning(f"🚫 User {uid} blocked. Attempting cleanup...")
            try:
                await db._pool.execute("DELETE FROM users WHERE telegram_id = $1", uid)
                skipped += 1
            except Exception: 
                # This is the Foreign Key violation catch
                logging.warning(f"⚠️ Could not delete {uid} due to existing references. Skipping.")
                skipped += 1
                
        except Exception as e:
            logging.error(f"❌ Other error for {uid}: {e}")
            failed += 1

    return sent, skipped, failed

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
    val = int(callback.data.split(":")[1])
    uid = callback.from_user.id
    
    # Check if they already voted (prevents double recording)
    existing = await db._pool.fetchval("SELECT selected_price FROM price_survey_results WHERE user_id = $1", uid)
    
    if existing:
        # Handle 2nd trial gracefully with a friendly popup
        return await callback.answer("You've already submitted your feedback! Thank you. 🙏", show_alert=True)

    try:
        await db._pool.execute("""
            INSERT INTO price_survey_results (user_id, selected_price) 
            VALUES ($1, $2)
        """, uid, val)
        
        lang = await db._pool.fetchval("SELECT language FROM users WHERE telegram_id = $1", uid)
        thanks = "✅ Got it! Thanks for the feedback." if lang == "EN" else "✅ ተቀብያለሁ! ስለ አስተያየትዎ አመሰግናለሁ።"
        
        await callback.message.edit_text(f"<b>{callback.message.text}</b>\n\n{thanks}", parse_mode="HTML")
        await callback.answer("Feedback saved!")
    except Exception as e:
        logging.error(f"Error saving survey: {e}")
        await callback.answer("Error saving response.")

from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

# --- 1. Helper for the visual report ---
async def build_results_report(db):
    # Added WHERE clause to filter for today only
    results = await db._pool.fetch("""
        SELECT selected_price, COUNT(*) as votes 
        FROM price_survey_results 
        WHERE created_at >= CURRENT_DATE
        GROUP BY selected_price 
        ORDER BY selected_price ASC
    """)
    
    if not results:
        return "No survey results recorded yet today. 🌑", None

    total_votes = sum(r['votes'] for r in results)
    now = datetime.now().strftime("%H:%M:%S")
    
    report = f"📊 <b>Today's Survey Momentum</b>\n"
    report += f"<i>Data since 00:00 AM Today | Updated: {now}</i>\n"
    report += f"━━━━━━━━━━━━━━━\n\n"

    for r in results:
        count = r['votes']
        price = r['selected_price']
        percent = (count / total_votes) * 100 if total_votes > 0 else 0
        bar_count = int(percent / 10)
        bar = "🟦" * bar_count + "⬜" * (10 - bar_count)
        
        report += f"💰 <b>{price} ETB</b>\n"
        report += f"{bar} {int(percent)}%\n"
        report += f"└ 🗳 <b>{count} votes today</b>\n\n"

    report += f"━━━━━━━━━━━━━━━\n"
    report += f"<b>Total Today:</b> {total_votes}"

    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Refresh Today's Data", callback_data="refresh_survey_results")
    
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