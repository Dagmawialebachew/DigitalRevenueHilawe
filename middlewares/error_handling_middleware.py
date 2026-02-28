import logging
import traceback
from io import BytesIO
from aiogram import Router, types
from aiogram.types import ErrorEvent, BufferedInputFile
from config import settings

router = Router(name="error_handler")

@router.error()
async def global_error_handler(event: ErrorEvent):
    # 1. Log the full traceback to console
    logging.exception(f"Update: {event.update}\nException: {event.exception}")

    # 2. Extract context
    bot = event.update.bot
    user = event.update.message.from_user if event.update.message else \
           event.update.callback_query.from_user if event.update.callback_query else None
    
    user_id = user.id if user else 0
    username = f"@{user.username}" if user and user.username else "Unknown"

    # 3. Notify Admin Group with a Log File
    if settings.ADMIN_ERROR_LOG_ID:
        try:
            # Create a .txt file for the full traceback (prevents message length errors)
            tb_text = traceback.format_exc()
            log_file = BufferedInputFile(tb_text.encode(), filename=f"error_{user_id}.txt")
            
            caption = (
                f"❌ *ENGINE EXCEPTION*\n"
                f"————————————————————\n"
                f"👤 *User:* {username} (`{user_id}`)\n"
                f"⚠️ *Type:* `{type(event.exception).__name__}`\n"
                f"📝 *Error:* `{str(event.exception)[:100]}`"
            )
            
            await bot.send_document(
                chat_id=settings.ADMIN_ERROR_LOG_ID,
                document=log_file,
                caption=caption,
                parse_mode="Markdown"
            )
        except Exception as log_err:
            logging.error(f"Failed to notify Admin: {log_err}")

    # 4. Notify the User gracefully
    try:
        # Default error message (Hardcoded here for safety)
        error_msg = "⚠️ An error occurred. Our team has been notified."
        
        if event.update.message:
            await event.update.message.answer(error_msg)
        elif event.update.callback_query:
            await event.update.callback_query.answer(error_msg, show_alert=True)
    except Exception:
        pass # Chat access might have been lost