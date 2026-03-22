import asyncio
import logging
from datetime import datetime, timezone, timedelta
from aiogram import Bot

# Ensure build_deal_message is imported correctly
from handlers.admin import build_deal_message 
async def reminder_worker(bot: Bot, db):
    logging.info("Urgent Reminder Worker Started.")
    while True:
        try:
            now = datetime.now(timezone.utc)
            
            # Fetch users with active deals
            rows = await db._pool.fetch("""
                SELECT telegram_id, language, deal_expires_at, last_broadcast_msg_id, matched_product_id, deal_price 
                FROM users 
                WHERE deal_expires_at > $1 
                  AND has_paid = FALSE 
                  AND last_broadcast_msg_id IS NOT NULL
            """, now)

            for r in rows:
                uid = r['telegram_id']
                expires = r['deal_expires_at'].replace(tzinfo=timezone.utc) if r['deal_expires_at'].tzinfo is None else r['deal_expires_at']
                msg_id = r['last_broadcast_msg_id']
                p_id = r['matched_product_id']
                
                remaining = expires - now

                # --- NEW LOGIC: If less than 2 minutes remain, just let it expire naturally ---
                if remaining < timedelta(seconds=10):
                    continue

                # --- Aggressive Edit ---
                text, kb = build_deal_message(r['language'], expires, p_id)
                
                try:
                    await bot.edit_message_caption(
                        chat_id=uid,
                        message_id=msg_id,
                        caption=text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    error_msg = str(e).lower()
                    if "there is no caption" in error_msg:
                        try:
                            await bot.edit_message_text(chat_id=uid, message_id=msg_id, text=text, reply_markup=kb, parse_mode="HTML")
                        except: pass
                    elif "message is not modified" in error_msg:
                        pass # Seconds didn't change enough yet
                    else:
                        logging.warning(f"Could not update user {uid}: {e}")

            # --- DYNAMIC SLEEP ---
            # Update every 3 minutes (180s) to keep urgency high
            await asyncio.sleep(100) 

        except Exception as e:
            logging.error(f"Global Worker Error: {e}")
            await asyncio.sleep(60) # Wait a bit before retrying if DB crashes