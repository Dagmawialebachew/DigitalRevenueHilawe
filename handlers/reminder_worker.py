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
                    # 1. Try editing as a Photo Caption first (since that's your current EID_IMAGE style)
                    await bot.edit_message_caption(
                        chat_id=uid,
                        message_id=msg_id,
                        caption=text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    error_msg = str(e).lower()
                    
                    # 2. If it's a Text message, retry with edit_message_text
                    if "there is no caption" in error_msg or "message can't be edited" in error_msg:
                        try:
                            await bot.edit_message_text(
                                chat_id=uid,
                                message_id=msg_id,
                                text=text,
                                reply_markup=kb,
                                parse_mode="HTML"
                            )
                        except Exception as inner_e:
                            if "message is not modified" not in str(inner_e).lower():
                                logging.error(f"Failed text edit for {uid}: {inner_e}")
                    
                    # 3. Ignore common "Safe" errors
                    elif "message is not modified" in error_msg:
                        pass
                    elif "message to edit not found" in error_msg:
                        logging.warning(f"User {uid} deleted the message. Skipping.")
                    else:
                        logging.error(f"Unexpected edit error for {uid}: {e}")

        except Exception as e:
            logging.error(f"Worker Error: {e}")

        # Sleep for 1 hour before next update
        await asyncio.sleep(3600)

async def safe_send(bot: Bot, chat_id: int, text: str):
    try:
        await bot.send_message(chat_id, text, parse_mode="HTML")
    except Exception:
        pass