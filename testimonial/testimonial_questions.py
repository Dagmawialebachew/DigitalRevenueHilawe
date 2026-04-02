import asyncio
import logging
from aiogram import Bot, Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from datetime import datetime, timezone

from config import settings
from aiogram.fsm.state import State, StatesGroup

router = Router()

class TestimonialStates(StatesGroup):
    awaiting_text_answer = State() # For favorite_part and overall_feedback

# --- Helper: Build UI based on Question Type ---
def get_testimonial_keyboard(q_id: int, input_type: str):
    kb = InlineKeyboardBuilder()
    
    if input_type == 'rating':
        for i in range(1, 6):
            kb.button(text=f"{i} ⭐", callback_data=f"testi:{q_id}:{i}")
        kb.adjust(5)
        
    elif input_type == 'emoji':
        options = [("🔥", 3), ("👍", 2), ("👎", 1)]
        for label, val in options:
            kb.button(text=label, callback_data=f"testi:{q_id}:{val}")
        kb.adjust(3)
        
    elif input_type == 'toggle':
        kb.button(text="✅ Yes / አዎ", callback_data=f"testi:{q_id}:1")
        kb.button(text="❌ No / አይ", callback_data=f"testi:{q_id}:0")
        kb.adjust(2)
        
    return kb.as_markup()

# --- Helper: Greeting Generator ---
async def get_personalized_text(bot: Bot, uid: int, lang: str, question_text: str, is_first: bool):
    """Fetches user name from Telegram and wraps the question in a warm greeting."""
    try:
        chat = await bot.get_chat(uid)
        name = chat.first_name or ("Athlete" if lang == "EN" else "አትሌት")
    except Exception:
        name = "Athlete" if lang == "EN" else "አትሌት"

    if is_first:
        if lang == "AM":
            return (
                f"ሰላም {name}! 👋\n\n"
                f"እስካሁን በነበረን ቆይታ ጠንክረው እየሰሩ እንደሆነ አውቃለሁ። ለእርስዎ የተሻለ ውጤት እንዲመጣ "
                f"የርስዎ እውነተኛ አስተያየት ለኔ በጣም አስፈላጊ ነው።\n\n"
                f"<b>{question_text}</b>"
            )
        else:
            return (
                f"Hey {name}! 👋\n\n"
                f"I've been watching your progress and I love the dedication. To make this "
                f"experience even better for you, I need your honest feedback.\n\n"
                f"<b>{question_text}</b>"
            )
    else:
        header = "Next quick check-in... ⚡️\n\n" if lang == "EN" else "ቀጣዩ አጭር ጥያቄ... ⚡️\n\n"
        return f"{header}<b>{question_text}</b>"
async def run_testimonial_cycle(bot: Bot, db, storage, question_id: int, test_mode: bool = True):
    logging.info(f"🔍 Starting Cycle for QID: {question_id} (Test Mode: {test_mode})")
    
    # 1. Fetch current question data
    q = await db._pool.fetchrow("SELECT * FROM testimonial_questions WHERE id = $1", question_id)
    if not q:
        logging.error(f"❌ Question ID {question_id} not found in database!")
        return 0

    rows = []
    # 2. Select Targets with Gating Logic
    if test_mode:
        logging.info(f"🧪 Targetting ADMIN_IDS: {settings.ADMIN_IDS}")
        rows = await db._pool.fetch("SELECT telegram_id, language FROM users WHERE telegram_id = ANY($1::BIGINT[])", settings.ADMIN_IDS)
        prefix = "🧪 <b>[TEST MODE]</b>\n\n"
    else:
        prefix = ""
        if question_id == 1:
            # Added more explicit table aliases and logging for debugging
            query = """
                SELECT u.telegram_id, u.language 
                FROM users u
                INNER JOIN payments p ON u.telegram_id = p.user_id
                LEFT JOIN user_testimonials ut ON u.telegram_id = ut.user_id AND ut.question_id = $1
                WHERE p.status = 'approved' 
                  AND ut.user_id IS NULL
                GROUP BY u.telegram_id, u.language
            """
            logging.info(f"📡 Executing Production Query for Q1...")
            rows = await db._pool.fetch(query, question_id)
        else:
            query = """
                SELECT u.telegram_id, u.language 
                FROM users u
                LEFT JOIN user_testimonials current ON u.telegram_id = current.user_id AND current.question_id = $1
                WHERE current.user_id IS NULL
                GROUP BY u.telegram_id, u.language
            """
            logging.info(f"📡 Executing Production Query for Q{question_id}...")
            rows = await db._pool.fetch(query, question_id)

    logging.info(f"📊 Rows found in DB: {len(rows)}")
    if len(rows) == 0:
        # DEBUG: Check why you aren't in the list
        logging.info("🕵️ DEBUGGING EMPTY ROWS: Checking status of all users in DB...")
        debug_users = await db._pool.fetch("SELECT telegram_id, language FROM users LIMIT 5")
        logging.info(f"Sample users in DB: {debug_users}")
        
        # Check payment status specifically
        payment_check = await db._pool.fetch("SELECT user_id, status FROM payments")
        logging.info(f"Payment records check: {payment_check}")

    sent_count = 0
    is_first = (question_id == 1)

    for user in rows:
        uid = user['telegram_id']
        lang = user['language'] or 'EN'
        logging.info(f"✉️ Attempting to send to {uid} ({lang})")
        
        raw_question = q['question_en'] if lang == 'EN' else q['question_am']
        full_text = f"{prefix}{await get_personalized_text(bot, uid, lang, raw_question, is_first)}"
        reply_markup = get_testimonial_keyboard(q['id'], q['input_type']) if q['input_type'] != 'text' else None

        try:
            await bot.send_message(uid, full_text, reply_markup=reply_markup, parse_mode="HTML")
            logging.info(f"✅ Message sent to {uid}")
            
            if q['input_type'] == 'text':
                state_ctx = FSMContext(
                    storage=storage,
                    key=StorageKey(chat_id=uid, user_id=uid, bot_id=bot.id)
                )
                await state_ctx.set_state(TestimonialStates.awaiting_text_answer)
                await state_ctx.update_data(pending_q_id=question_id)
                logging.info(f"💾 FSM State set for {uid}")
            
            sent_count += 1
            await asyncio.sleep(0.1) # Slightly slower for local stability
            
        except Exception as e:
            logging.error(f"❌ Failed to send message to {uid}: {e}")

    return sent_count


async def testimonial_scheduler(bot: Bot, db, storage):
    logging.info("🕒 Testimonial Scheduler Initialized.")
    PRODUCTION_READY = True

    while True:
        try:
            last_sent = await db._pool.fetchrow("SELECT question_id, sent_at FROM testimonial_logs ORDER BY sent_at DESC LIMIT 1")

            if last_sent:
                elapsed = datetime.now(timezone.utc) - last_sent['sent_at']
                logging.info(f"⏰ Last send was Q{last_sent['question_id']} at {last_sent['sent_at']} ({int(elapsed.total_seconds())}s ago)")
                
                if elapsed.total_seconds() < (3 * 3600):
                    wait_time = (3 * 3600) - elapsed.total_seconds()
                    logging.info(f"⏳ Cooldown active. Next check in {int(wait_time)}s.")
                    await asyncio.sleep(60) # Check every minute instead of sleeping hours so you can debug faster
                    continue
                last_q_id = last_sent['question_id']
            else:
                logging.info("🆕 No logs found. Starting fresh from Q1.")
                last_q_id = 0

            next_q = await db._pool.fetchrow("SELECT id FROM testimonial_questions WHERE id > $1 AND is_active = TRUE ORDER BY id ASC LIMIT 1", last_q_id)

            if not next_q:
                logging.info("🏁 No more questions to send. Sleeping...")
                await asyncio.sleep(3600)
                continue

            q_id = next_q['id']
            logging.info(f"🚀 Triggering cycle for QID {q_id}...")
            
            # RUN CYCLE FIRST, THEN LOG (to prevent locking if 0 people get it)
            sent = await run_testimonial_cycle(bot, db, storage, q_id, test_mode=(not PRODUCTION_READY))
            
            if sent > 0:
                await db._pool.execute("INSERT INTO testimonial_logs (question_id) VALUES ($1)", q_id)
                logging.info(f"🎊 Cycle Complete. Sent to {sent} users.")
            else:
                logging.warning(f"⚠️ Cycle ran but 0 users were eligible for Q{q_id}. Retrying in 5 mins.")
                await asyncio.sleep(300) 

        except Exception as e:
            logging.error(f"🚨 Scheduler CRITICAL ERROR: {e}")
            await asyncio.sleep(60)   
            
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

router = Router()

@router.callback_query(F.data.startswith("testi:"))
async def handle_testimonial_click(callback: types.CallbackQuery, db):
    # Format: testi:{question_id}:{value}
    data_parts = callback.data.split(":")
    if len(data_parts) != 3:
        return
        
    _, q_id, value = data_parts
    q_id = int(q_id)
    uid = callback.from_user.id
    
    # 1. Check if they already answered to prevent spam
    exists = await db._pool.fetchval(
        "SELECT 1 FROM user_testimonials WHERE user_id = $1 AND question_id = $2",
        uid, q_id
    )
    
    if exists:
        return await callback.answer("You've already answered this! / ይህንን ቀደም ብለው መልሰዋል።", show_alert=True)

    # 2. Save the rating to the DB
    await db._pool.execute(
        "INSERT INTO user_testimonials (user_id, question_id, rating_value) VALUES ($1, $2, $3)",
        uid, q_id, int(value)
    )

    # 3. Success Feedback (Edit the message to clear the buttons)
    lang = await db._pool.fetchval("SELECT language FROM users WHERE telegram_id = $1", uid)
    
    msg = "✅ Received! I really appreciate your feedback." if lang == "EN" else "✅ ተቀብያለው! ስለ አስተያየትዎ አመሰግናለው።"
    
    await callback.message.edit_text(f"<b>{callback.message.text}</b>\n\n{msg}", parse_mode="HTML")
    await callback.answer()
    
    

@router.message(TestimonialStates.awaiting_text_answer, F.text)
async def handle_testimonial_text(message: types.Message, state: FSMContext, db):
    state_data = await state.get_data()
    q_id = state_data.get("pending_q_id")
    uid = message.from_user.id

    if not q_id:
        await state.clear()
        return

    # Save or update the text feedback
    await db._pool.execute("""
        INSERT INTO user_testimonials (user_id, question_id, feedback_text) 
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, question_id) DO UPDATE SET feedback_text = $3
    """, uid, q_id, message.text)

    # Success message
    lang = await db._pool.fetchval("SELECT language FROM users WHERE telegram_id = $1", uid)
    thanks = "🔥 Got it! Your feedback has been recorded." if lang == "EN" else "✅ ተቀብያለው! ስለ አስተያየትዎ አመሰግናለው።"
    
    await message.answer(thanks)
    await state.clear() # Clear the state so they can use other bot features