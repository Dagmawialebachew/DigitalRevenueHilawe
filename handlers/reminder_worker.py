# scheduler/reminder_worker.py
import asyncio
from datetime import datetime, timedelta
import os

from aiogram import Bot

REMINDER_INTERVAL = int(os.getenv("REMINDER_INTERVAL_SECONDS", "900"))  # 15 minutes

async def reminder_worker(bot: Bot, db):
    while True:
        now = datetime.utcnow()
        rows = await db._pool.fetch("SELECT telegram_id, deal_expires_at FROM users WHERE deal_expires_at IS NOT NULL AND has_paid = FALSE")
        for r in rows:
            uid = r['telegram_id']
            expires = r['deal_expires_at']
            if not expires:
                continue
            remaining = expires - now
            # send mid-run reminder at ~12 hours left (example) and final at 30 minutes
            if timedelta(hours=12) - timedelta(minutes=1) < remaining <= timedelta(hours=12) + timedelta(minutes=1):
                await safe_send(bot, uid, "Reminder: 12 hours left for your 399 ETB deal. Finish now!")
            if timedelta(minutes=31) < remaining <= timedelta(minutes=31, seconds=59):
                # skip; we want final at 30 minutes
                pass
            if timedelta(minutes=30) - timedelta(seconds=30) < remaining <= timedelta(minutes=30) + timedelta(seconds=30):
                await safe_send(bot, uid, "Final reminder: 30 minutes left to claim your 399 ETB deal.")
        await asyncio.sleep(REMINDER_INTERVAL)

async def safe_send(bot: Bot, chat_id: int, text: str):
    try:
        await bot.send_message(chat_id, text, parse_mode="Markdown")
    except Exception:
        pass
