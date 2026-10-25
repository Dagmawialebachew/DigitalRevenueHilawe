import os, sys, asyncio, json
from dotenv import load_dotenv
import asyncpg

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv(r'd:\The hobby 2\DigitalRevenueHilawe\.env')

async def main():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    try:
        rows = await conn.fetch("""
            SELECT template_id, item_type, item_id, item_name, portion_g 
            FROM nutrition_template_components 
            WHERE template_id IN ('MN-B01', 'MN-B04', 'MN-B07', 'MF-B07', 'MF-B02', 'MN-B06', 'MN-B02')
        """)
        for r in rows:
            print(dict(r))
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
