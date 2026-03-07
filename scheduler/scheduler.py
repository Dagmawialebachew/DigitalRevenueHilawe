import asyncio
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import settings
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter
async def check_and_send_reminders(bot: Bot, db):
    """
    Finds dropped users, sends high-pressure alerts, and reports to Admin.
    """
    try:

        ghost_users = await db._pool.fetch("""

           SELECT telegram_id AS user_id, language, level, full_name
FROM users
WHERE last_pitch_at < NOW() - INTERVAL '3 hours' 
  AND last_pitch_at > NOW() - INTERVAL '4 hours'
  AND has_paid = FALSE 
  AND reminded = FALSE

        """)
    except Exception as e:
        logging.exception(f"DB query failed: {e}")
        return

    sent_count = 0
    failed_count = 0

    for user in ghost_users:
        uid = user["user_id"]
        lang = user["language"]
        level = user["level"].upper()
        sys_id = f"HE-{uid % 10000:04d}"

        # --- USER MESSAGES ---
        
        if lang == "EN":
            text = (
                f"👋 <b>Quick Check-in: {sys_id}</b>\n\n"
                f"Your custom <b>{level}</b> plan is 94.7% ready! I’ve been holding your 45% Founder's Discount in the system so you don't lose it. 🌟\n\n"
                "🕒 <b>Just a heads up:</b> This special reservation will reset in 59 minutes.\n\n"
                "I’d love to see you start this journey. Should we finalize your plan now, or should I open this spot for the next person?"
            )
            btn_text = "⚡️ Yes, Finish My Plan"
        else:
            text = (
                f"🎁 <b>ለእርስዎ የተዘጋጀ ስጦታ፦ {sys_id}</b>\n\n"               
                f"ያዘጋጀሁት የ<b>{level}</b> ስልጠና 94.7% ተጠናቋል! የ45% የቅናሽ ኮድዎ እንዳያልፍብዎት በሲስተሙ ውስጥ አስቀምጬሎታለሁ። 🌟\n\n"
                "🕒 <b>ትንሽ ማሳሰቢያ፦</b> ይህ ልዩ ቦታ በ59 ደቂቃ ውስጥ ይጠናቀቃል።\n\n"
                "ለውጡን አብረን ብንጀምር ደስ ይለኛል። አሁን ፕሮግራሙን ላጠናቅቅሎት ወይስ ቦታውን ለሌላ ሰው ላስተላልፈው?"
            )
            btn_text = "⚡️ አዎ፣ አሁን አጠናቅ"


        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=btn_text, callback_data="re_pitch_trigger")]
        ])

        try:
            await bot.send_message(uid, text, reply_markup=kb, parse_mode="HTML")
            await db._pool.execute(
                "UPDATE users SET reminded = TRUE WHERE telegram_id = $1", uid
            )
            sent_count += 1
            await asyncio.sleep(0.05) # anti-flood
        except TelegramForbiddenError:
                logging.warning(f"🚫 User {uid} blocked the bot. Skipping.")
                failed_count += 1
        except TelegramRetryAfter as e:
                logging.error(f"⏳ Flood limit hit. Sleeping for {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
        except TelegramAPIError as e:
                logging.error(f"⚠️ Telegram API Error for {uid}: {e}")
                failed_count += 1
        except Exception as e:
            logging.error(f"❓ Unknown error sending to {uid}: {type(e).__name__}: {e}")
            failed_count += 1

    # --- ADMIN REPORT (Easy English) ---
    if sent_count > 0 or failed_count > 0:
        admin_report = (
            "📊 <b>Scheduler REPORT</b>\n"
            "————————————————\n"
            f"✅ <b>Reminders Sent:</b> {sent_count}\n"
            f"❌ <b>Failed/Blocked:</b> {failed_count}\n"
            "————————————————\n"
            "Target: Users who dropped off 5-8 hours ago.\n"
            "Status: System is retargeting them now."
        )
        try:
            await bot.send_message(settings.ADMIN_SCHEDULER_LOG_ID, admin_report, parse_mode="HTML")
        except Exception:
            logging.error("Could not send report to Admin.")




async def test_reminder_for_user(bot: Bot, db, user_id: int):
    """Send a reminder to one specific user for testing and notify the group."""
    try:
        user = await db.get_user(user_id)
        if not user:
            logging.warning(f"No user found with ID {user_id}")
            return

        lang = user["language"]
        level = user["level"].upper()
        sys_id = f"HE-{user_id % 10000:04d}"

        if lang == "EN":
            text = (
                f"🚨 <b>ALERT: {sys_id}</b>\n\n"
                f"The <b>{level}</b> protocol you generated is 94.7% complete. "
                "The system is currently holding your 45% Founder's Discount in a temporary cache.\n\n"
                "🕒 <b>TIMING:</b> Your reservation expires in 59 minutes.\n\n"
                "<b>Action Required:</b> Should I finalize your sync now, or should I release this slot and the discount to the next athlete in the queue?"
            )
            btn_text = "⚡️ Finalize My Sync"
        else:
            text = (
                f"🚨 <b>ማንቅያ ደውል፦ {sys_id}</b>\n\n"
                f"ያዘጋጁት የ<b>{level}</b> ስልጠና 94.7% ተጠናቋል። "
                "የ45% የቅናሽ ኮድዎ በሲስተሙ ውስጥ ለጊዜው ተቀምጦ ይገኛል።\n\n"
                "🕒 <b>የጊዜ ገደብ፦</b> ይህ ቦታ በ59 ደቂቃ ውስጥ ይዘጋል።\n\n"
                "<b>ውሳኔ ይፈለጋል፦</b> አሁን ፕሮግራሙን ላጠናቅቅሎት ወይስ ቦታዎን እና ቅናሹን ወረፋ ሌላ ሰው ላስተላልፈው?"
            )
            btn_text = "⚡️ አሁን አጠናቅ"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=btn_text, callback_data="re_pitch_trigger")]
        ])

        # Send to the user
        await bot.send_message(user_id, text, reply_markup=kb, parse_mode="HTML")
        await db._pool.execute(
            "UPDATE users SET reminded = TRUE WHERE telegram_id = $1", user_id
        )

        # Notify your group/admin log channel
        admin_report = (
            "📊 <b>TEST Reminder REPORT</b>\n"
            "————————————————\n"
            f"👤 <b>User:</b> {user.get('full_name','N/A')} (ID: {user_id})\n"
            f"🌍 <b>Lang:</b> {lang}\n"
            f"📊 <b>Level:</b> {level}\n"
            "✅ Reminder sent successfully.\n"
            "————————————————\n"
            "This was a manual test run."
        )
        await bot.send_message(settings.ADMIN_SCHEDULER_LOG_ID, admin_report, parse_mode="HTML")

        logging.info(f"Reminder sent successfully to {user_id}")

    except Exception as e:
        logging.exception(f"Error sending test reminder to {user_id}: {e}")
        # Notify group of failure
        fail_report = (
            "📊 <b>TEST Reminder REPORT</b>\n"
            "————————————————\n"
            f"❌ Failed to send reminder to user ID: {user_id}\n"
            f"Error: {e}"
        )
        try:
            await bot.send_message(settings.ADMIN_SCHEDULER_LOG_ID, fail_report, parse_mode="HTML")
        except Exception:
            logging.error("Could not send failure report to Admin group.")
