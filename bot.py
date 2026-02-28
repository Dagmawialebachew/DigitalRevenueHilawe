import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from config import settings
from app_context import bot, dp, db
from middlewares.language import LanguageMiddleware
from handlers import all_routers

for r in all_routers:
    dp.include_router(r)
# Middlewares
from middlewares.throttling_middleware import ThrottlingMiddleware
from middlewares.error_handling_middleware import router as error_router
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# --- Dispatcher Setup ---
dp.message.middleware(ThrottlingMiddleware(message_interval=0.8))
dp.callback_query.middleware(ThrottlingMiddleware(message_interval=0.5))

dp.message.middleware(LanguageMiddleware(db)) 
dp.callback_query.middleware(LanguageMiddleware(db))

# Order matters: Admin first to override generic handlers
dp.include_router(error_router) # Add this last

# --- Bot Commands ---
async def set_commands(bot: Bot, admin_ids: list[int], lang: str = "EN"):
    # English commands
    user_commands_en = [
        BotCommand(command="start", description="🚀 Start Transformation"),
        BotCommand(command="help", description="❓ Get Assistance"),
    ]
    admin_commands_en = user_commands_en + [
        BotCommand(command="admin", description="🔐 Admin Panel"),
    ]

    # Amharic commands
    user_commands_am = [
        BotCommand(command="start", description="🚀 ለውጥን ጀምር"),
        BotCommand(command="help", description="❓ እርዳታ ያግኙ"),
    ]
    admin_commands_am = user_commands_am + [
        BotCommand(command="admin", description="🔐 የአስተዳደር ፓነል"),
    ]

    # Pick based on language
    if lang == "AM":
        await bot.set_my_commands(user_commands_am, scope=BotCommandScopeDefault())
        for admin_id in admin_ids:
            try:
                await bot.set_my_commands(admin_commands_am, scope=BotCommandScopeChat(chat_id=admin_id))
            except Exception as e:
                logging.error(f"Failed to set Amharic commands for admin {admin_id}: {e}")
    else:
        await bot.set_my_commands(user_commands_en, scope=BotCommandScopeDefault())
        for admin_id in admin_ids:
            try:
                await bot.set_my_commands(admin_commands_en, scope=BotCommandScopeChat(chat_id=admin_id))
            except Exception as e:
                logging.error(f"Failed to set English commands for admin {admin_id}: {e}")

# --- Startup / Shutdown ---
async def on_startup(bot: Bot):
    logging.info("🚀 Initializing Coach Hilawe Engine...")
    await db.connect()
    await db.setup() # Runs SCHEMA_SQL
    await set_commands(bot, settings.ADMIN_IDS)
    
    if os.getenv("WEBHOOK_BASE_URL"):
        webhook_url = f"{settings.WEBHOOK_BASE_URL}/webhook"
        await bot.set_webhook(webhook_url, drop_pending_updates=True)
        logging.info(f"Webhook set to: {webhook_url}")

async def on_shutdown(bot: Bot):
    logging.info("🛑 Shutting down engine...")
    await db.disconnect()
    await bot.session.close()

#
async def create_app() -> web.Application:
    app = web.Application()
    
    # Health check for deployment (Render/Railway/Heroku)
    app.router.add_get("/health", lambda r: web.Response(text="OK"))

    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path="/webhook")
    
    setup_application(app, dp, bot=bot)
    
    app.on_startup.append(lambda _: on_startup(bot))
    app.on_cleanup.append(lambda _: on_shutdown(bot))
    
    return app

# --- Polling Mode ---
async def start_polling():
    await on_startup(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown(bot)

if __name__ == "__main__":
    if "--polling" in sys.argv:
        # Development mode
        asyncio.run(start_polling())
    else:
        # Production mode with webhook
        port = settings.PORT
        logging.info(f"Starting webhook on port {port}")
        web.run_app(create_app(), host="0.0.0.0", port=port)
