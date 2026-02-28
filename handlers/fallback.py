# from aiogram import Router, F, types
# from database.db import Database
# from keyboards.reply import main_menu
# from utils.localization import get_text

# router = Router(name="fallback")

# @router.message()
# async def universal_fallback(message: types.Message, db: Database):
#     """Catches all unhandled messages."""
#     user_id = message.from_user.id
#     user = await db.get_user(user_id)

#     # 1. If user doesn't exist or hasn't finished onboarding
#     if not user or not user.get("onboarding_completed"):
#         # We don't want to spam, so we just give a direct hint
#         text = "Welcome Champion! Please use /start to begin your classification."
#         return await message.answer(text)

#     # 2. If user exists, remind them of the menu
#     lang = user.get("language", "EN")
#     text = (
#         "I didn't quite catch that. Please use the menu below to navigate." 
#         if lang == "EN" else 
#         "ይቅርታ አልገባኝም። እባክዎ ከታች ያለውን ማውጫ ይጠቀሙ።"
#     )
    
#     await message.answer(
#         text, 
#         reply_markup=main_menu(lang)
#     )

# @router.callback_query()
# async def universal_callback_fallback(callback: types.CallbackQuery):
#     """
#     Catches stale buttons or buttons from old versions of the bot.
#     """
#     # Simply answer the callback to stop the loading spinner
#     await callback.answer(
#         "This button is no longer active. Please restart with /start.",
#         show_alert=True
#     )# fallback.py
