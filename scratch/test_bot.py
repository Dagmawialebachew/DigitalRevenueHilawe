import asyncio, os
from dotenv import load_dotenv
from aiogram import Bot

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
bot = Bot(token=os.getenv("BOT_TOKEN"))

async def test():
    try:
        me = await bot.get_me()
        print("Bot username:", me.username, "Bot ID:", me.id)
    finally:
        await bot.session.close()

asyncio.run(test())
