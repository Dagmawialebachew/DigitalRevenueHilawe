import asyncio
import os
import json
import sys
from dotenv import load_dotenv
import asyncpg

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    tables = await conn.fetch("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name
    """)
    print("=== TABLES ===")
    for t in tables:
        print(t['table_name'])

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
