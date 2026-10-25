import asyncio, os, sys
from dotenv import load_dotenv
import asyncpg

load_dotenv(r'd:\The hobby 2\DigitalRevenueHilawe\.env')
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    cols = await conn.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'meal_plan_versions'")
    for c in cols:
        print(c['column_name'], c['data_type'])
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
