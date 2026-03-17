# scheduler/reminder_worker.py
import asyncio
import logging
import random
from datetime import datetime, timedelta
from aiogram import Bot

from handlers.admin import build_deal_message

async def reminder_worker(bot: Bot, db):
    while True:
        try:
            now = datetime.utcnow()
            # Fetch users with active deals
            rows = await db._pool.fetch("""
                SELECT telegram_id, language, deal_expires_at, last_broadcast_msg_id, matched_product_id 
                FROM users 
                WHERE deal_expires_at > $1 AND has_paid = FALSE AND last_broadcast_msg_id IS NOT NULL
            """, now)

            for r in rows:
                uid = r['telegram_id']
                expires = r['deal_expires_at']
                msg_id = r['last_broadcast_msg_id']
                p_id = r['matched_product_id']
                remaining = expires - now

                # --- CASE 1: Final Hour Push (Send NEW Message) ---
                if timedelta(minutes=50) < remaining <= timedelta(hours=1):
                    final_text = (
                        "🚨 <b>LAST HOUR!</b>\nYour 399 ETB deal is about to expire. This is your final chance." 
                        if r['language'] == 'EN' else 
                        "🚨 <b>መጨረሻ ሰዓት!</b>\nየ399 ብር ቅናሹ ሊያበቃ ጥቂት ደቂቃዎች ብቻ ቀርተዋል። አሁኑኑ ይጠቀሙ!"
                    )
                    await safe_send(bot, uid, final_text)

                # --- CASE 2: Live Edit (Update Clock & Slots) ---
                # We update the original broadcast message
                text, kb = build_deal_message(r['language'], expires, p_id)
                
                try:
                    await bot.edit_message_text(
                        chat_id=uid,
                        message_id=msg_id,
                        text=text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass # Message might have been deleted by user

        except Exception as e:
            logging.error(f"Worker Error: {e}")

        # Sleep for 1 hour before updating the clocks again
        await asyncio.sleep(3600)

async def safe_send(bot: Bot, chat_id: int, text: str):
    try:
        await bot.send_message(chat_id, text, parse_mode="HTML")
    except Exception:
        pass