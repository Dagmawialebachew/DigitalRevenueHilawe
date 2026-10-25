import os, sys, asyncio, json
from dotenv import load_dotenv
import asyncpg

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv(r'd:\The hobby 2\DigitalRevenueHilawe\.env')

async def main():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    try:
        templates = await conn.fetch("SELECT template_id, meal_name, meal_slot, fasting, budget FROM nutrition_templates WHERE meal_slot = 'Breakfast' ORDER BY template_id")
        print('\nBreakfast Templates:')
        for t in templates:
            print(dict(t))
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
