import asyncio
import logging
import os
import sys

from aiohttp import web
import aiohttp_cors

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import settings
from app_context import bot, dp, db
from middlewares.language import LanguageMiddleware
from middlewares.throttling_middleware import ThrottlingMiddleware
from middlewares.error_handling_middleware import router as error_router

# Import your admin API route setup (aiohttp style)
from api.api import setup_admin_routes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# --- Dispatcher middlewares and routers ---
dp.message.middleware(ThrottlingMiddleware(message_interval=0.8))
dp.callback_query.middleware(ThrottlingMiddleware(message_interval=0.5))

# Language middleware expects a db instance; app_context.db is used at runtime
dp.message.middleware(LanguageMiddleware(db))
dp.callback_query.middleware(LanguageMiddleware(db))

# Include other routers (handlers)
from handlers import all_routers
for r in all_routers:
    dp.include_router(r)

# Error handling router should be included last so it can override
dp.include_router(error_router)

# --- Bot commands helper ---
async def set_commands(bot: Bot, admin_ids: list[int], lang: str = "EN"):
    user_commands_en = [
        BotCommand(command="start", description="🚀 Start Transformation"),
        BotCommand(command="help", description="❓ Get Assistance"),
    ]
    admin_commands_en = user_commands_en + [
        BotCommand(command="admin", description="🔐 Admin Panel"),
    ]

    user_commands_am = [
        BotCommand(command="start", description="🚀 ለውጥን ጀምር"),
        BotCommand(command="help", description="❓ እርዳታ ያግኙ"),
    ]
    admin_commands_am = user_commands_am + [
        BotCommand(command="admin", description="🔐 የአስተዳደር ፓነል"),
    ]

    try:
        if lang == "AM":
            await bot.set_my_commands(user_commands_am, scope=BotCommandScopeDefault())
            for admin_id in admin_ids:
                await bot.set_my_commands(admin_commands_am, scope=BotCommandScopeChat(chat_id=admin_id))
        else:
            await bot.set_my_commands(user_commands_en, scope=BotCommandScopeDefault())
            for admin_id in admin_ids:
                await bot.set_my_commands(admin_commands_en, scope=BotCommandScopeChat(chat_id=admin_id))
    except Exception as e:
        logging.exception("Failed to set bot commands: %s", e)

# --- Startup / Shutdown lifecycle ---
async def on_startup(bot: Bot):
    logging.info("🚀 Initializing Coach Hilawe Engine...")
    await db.connect()
    await db.setup()  # run schema if needed
    await set_commands(bot, settings.ADMIN_IDS)

    # Set webhook if provided
    if os.getenv("WEBHOOK_BASE_URL"):
        webhook_url = f"{settings.WEBHOOK_BASE_URL}/webhook"
        try:
            await bot.set_webhook(webhook_url, drop_pending_updates=True)
            logging.info("Webhook set to: %s", webhook_url)
        except Exception:
            logging.exception("Failed to set webhook")

async def on_shutdown(bot: Bot):
    logging.info("🛑 Shutting down engine...")
    try:
        await db.disconnect()
    except Exception:
        logging.exception("Error disconnecting DB")
    try:
        await bot.session.close()
    except Exception:
        logging.exception("Error closing bot session")

# --- App factory (aiohttp) ---
async def create_app() -> web.Application:
    app = web.Application()

    # Attach shared resources
    app["bot"] = bot
    app["db"] = db

    # Health check
    async def health_check(request):
        return web.json_response({"status": "ok"})
    app.router.add_get("/health", health_check)

    # Register Telegram webhook handler
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path="/webhook")

    # Register admin API routes (aiohttp style)
    setup_admin_routes(app)

    # If you have other API groups (like asbeza), register them here:
    # from handlers.asbeza_api import setup_asbeza_routes
    # setup_asbeza_routes(app)

    # Static uploads (optional)
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "./uploads")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    app["upload_dir"] = UPLOAD_DIR
    app.router.add_static("/uploads", UPLOAD_DIR, show_index=False)

    # Setup CORS with aiohttp_cors
    cors = aiohttp_cors.setup(app, defaults={
        # allow your production and local dev origins explicitly
        os.environ.get("FRONTEND_ORIGIN", "http://127.0.0.1:5500"): aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods="*"
        ),
        # wildcard fallback (use with caution in production)
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods="*"
        ),
    })

    # Apply CORS to all routes
    for route in list(app.router.routes()):
        try:
            cors.add(route)
        except Exception:
            # some routes (like static) may not be CORS-wrappable; ignore
            pass

    # Integrate aiogram dispatcher with aiohttp app
    setup_application(app, dp, bot=bot)

    # Startup / cleanup hooks
    app.on_startup.append(lambda _: asyncio.create_task(on_startup(bot)))
    app.on_cleanup.append(lambda _: asyncio.create_task(on_shutdown(bot)))

    return app

# --- Polling mode for local development ---
async def start_polling():
    await db.connect()
    await db.setup()
    await set_commands(bot, settings.ADMIN_IDS)
    # If you have scheduled jobs, start them here (scheduler.start())
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown(bot)

# --- Entrypoint ---
if __name__ == "__main__":
    if "--polling" in sys.argv:
        asyncio.run(start_polling())
    else:
        port = int(os.getenv("PORT", "8080"))
        logging.info("Starting webhook + API server on http://0.0.0.0:%s", port)
        web.run_app(create_app(), host="0.0.0.0", port=port)
