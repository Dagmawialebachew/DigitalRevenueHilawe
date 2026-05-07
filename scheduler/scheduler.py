import asyncio
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import settings
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter


async def check_and_send_reminders(bot: Bot, db):
    """
    Retargets dropped users with human, emotionally-driven copy.
    No robotic language. No system references. Pure coach voice.
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
        level = user["level"].upper() if user["level"] else "TRANSFORMATION"
        first_name = (user["full_name"] or "").split()[0] if user["full_name"] else ""

        # ─────────────────────────────────────────────
        # ENGLISH VERSION — warm, personal, urgent
        # ─────────────────────────────────────────────
        if lang == "EN":
            name_line = f"{first_name}, I" if first_name else "I"
            text = (
                f"💬 <b>{name_line} want to be honest with you.</b>\n\n"
                f"A lot of people start this journey — they get excited, they see the plan, "
                f"and then life gets in the way. They tell themselves <i>\"I'll do it later.\"</i>\n\n"
                f"Later never comes. 😔\n\n"
                f"The people who joined me this week? "
                f"They didn't wait for the perfect moment. "
                f"They decided <b>this</b> was the moment.\n\n"
                f"Your <b>{level}</b> program is still waiting for you. "
                f"And so is the discount — but not for long.\n\n"
                f"⏳ <b>This offer closes very soon.</b> After that, the price goes back up — no exceptions.\n\n"
                f"You came this far for a reason. Don't let it go to waste.\n\n"
                f"<b>Are you ready to make this real?</b>"
            )
            btn_text = "✅ Yes Coach — I'm Ready"

        # ─────────────────────────────────────────────
        # AMHARIC VERSION — emotional, direct, urgent
        # ─────────────────────────────────────────────
        else:
            name_line = f"{first_name}፣" if first_name else ""
            text = (
                f"💬 <b>{name_line} አንድ ነገር ልንገርዎ።</b>\n\n"
                f"ብዙ ሰዎች ይህን ጉዞ ይጀምራሉ — ደስተኛ ይሆናሉ፣ ፕሮግራሙን ያዩታል፣ "
                f"ከዚያ ግን <i>\"በኋላ አደርገዋለሁ\"</i> ይላሉ።\n\n"
                f"ያ 'በኋላ' ግን አይመጣም። 😔\n\n"
                f"በዚህ ሳምንት ከእኔ ጋር የተቀላቀሉት ሰዎች ፍጹም ጊዜ አልጠበቁም። "
                f"<b>አሁን</b> ትክክለኛው ጊዜ እንደሆነ ወስነው ተነሱ።\n\n"
                f"የእርስዎ <b>{level}</b> ፕሮግራም አሁንም እየጠበቀዎት ነው። "
                f"ቅናሹም ጊዜው ሳያልፍ ይቆያል — ግን ብዙ አይቆይም።\n\n"
                f"⏳ <b>ይህ ቅናሽ በቅርቡ ያልቃል።</b> ከዚያ በኋላ ዋጋው ወደ መደበኛው ይመለሳል።\n\n"
                f"እዚህ የደረሱት ምክንያት አለው። ያንን እድል አያሳልፉ።\n\n"
                f"<b>አሁን ጉዟችንን እንጀምር?</b>"
            )
            btn_text = "✅ አዎ ኮች — ዝግጁ ነኝ"

        # ─────────────────────────────────────────────
        # SEND MESSAGE
        # ─────────────────────────────────────────────
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=btn_text, callback_data="re_pitch_trigger")]
        ])

        try:
            await bot.send_message(uid, text, reply_markup=kb, parse_mode="HTML")
            await db._pool.execute(
                "UPDATE users SET reminded = TRUE WHERE telegram_id = $1", uid
            )
            sent_count += 1
            await asyncio.sleep(0.05)  # anti-flood

        except TelegramForbiddenError:
            logging.warning(f"🚫 User {uid} blocked the bot. Skipping.")
            failed_count += 1
        except TelegramRetryAfter as e:
            logging.error(f"⏳ Flood limit hit. Sleeping {e.retry_after}s")
            await asyncio.sleep(e.retry_after)
        except TelegramAPIError as e:
            logging.error(f"⚠️ Telegram API Error for {uid}: {e}")
            failed_count += 1
        except Exception as e:
            logging.error(f"❓ Unknown error for {uid}: {type(e).__name__}: {e}")
            failed_count += 1

    # ─────────────────────────────────────────────
    # ADMIN REPORT
    # ─────────────────────────────────────────────
    if sent_count > 0 or failed_count > 0:
        admin_report = (
            "📊 <b>Retargeting Report</b>\n"
            "————————————————\n"
            f"✅ <b>Messages Sent:</b> {sent_count}\n"
            f"❌ <b>Failed/Blocked:</b> {failed_count}\n"
            "————————————————\n"
            "Target: Users who dropped 3–4 hours ago.\n"
            "Copy: Human emotional retargeting v2."
        )
        try:
            await bot.send_message(
                settings.ADMIN_SCHEDULER_LOG_ID,
                admin_report,
                parse_mode="HTML"
            )
        except Exception:
            logging.error("Could not send admin report.")



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
