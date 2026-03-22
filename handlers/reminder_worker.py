import asyncio
import logging
from datetime import datetime, timezone, timedelta
from aiogram import Bot

# Ensure build_deal_message is imported correctly
from handlers.admin import build_deal_message 

async def reminder_worker(bot: Bot, db):
    while True:
        try:
            # 1. FIXED: Use offset-aware UTC time
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
                expires = r['deal_expires_at']
                msg_id = r['last_broadcast_msg_id']
                p_id = r['matched_product_id']
                price = r['deal_price'] or 299 # Fallback to 299
                
                # Ensure expires is aware (Safety check)
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                
                remaining = expires - now

                # --- CASE 1: Final Hour Push (Send NEW Message) ---
                if timedelta(minutes=0) < remaining <= timedelta(hours=1):
                    final_text = (
                        f"🚨 <b>LAST HOUR!</b>\nYour {price} ETB Eid gift is about to expire. Final chance to start!" 
                        if r['language'] == 'EN' else 
                        f"🚨 <b>መጨረሻ ሰዓት!</b>\nየ{price} ብር የኢድ ስጦታ ሊያበቃ ጥቂት ደቂቃዎች ብቻ ቀርተዋል። አሁኑኑ ይጠቀሙ!"
                    )
                    await safe_send(bot, uid, final_text)

                # --- CASE 2: Live Edit (Update Caption & Countdown) ---
                # Since the broadcast is a PHOTO, we must edit the CAPTION
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
                    # Usually "Message to edit not found" or "Content is the same"
                    if "message is not modified" in str(e).lower():
                        pass
                    elif "message to edit not found" in str(e).lower():
                        logging.warning(f"Message {msg_id} deleted by user {uid}. Skipping edit.")
                    else:
                        logging.error(f"Failed to edit caption for user {uid}: {e}") 

        except Exception as e:
            logging.error(f"Worker Error: {e}")

        # Sleep for 1 hour before next update
        await asyncio.sleep(3600)

async def safe_send(bot: Bot, chat_id: int, text: str):
    try:
        await bot.send_message(chat_id, text, parse_mode="HTML")
    except Exception:
        pass