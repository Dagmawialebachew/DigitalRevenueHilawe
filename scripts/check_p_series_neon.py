import asyncio
import os
import sys
from dotenv import load_dotenv
import asyncpg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

async def main():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"), statement_cache_size=0)
    rows = await conn.fetch("SELECT food_id, food_name, food_name_en, food_name_am FROM nutrition_foods WHERE food_id LIKE 'P%' ORDER BY food_id")
    for r in rows:
        print(f"{r['food_id']} | name: {r['food_name']} | en: {r['food_name_en']} | am: {r['food_name_am']}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
