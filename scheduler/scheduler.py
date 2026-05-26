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