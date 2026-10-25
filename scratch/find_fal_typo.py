import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")
from database.db import Database

async def main():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()

    for table in ["nutrition_templates", "nutrition_recipes", "nutrition_foods", "nutrition_template_components"]:
        q = f"SELECT * FROM {table} WHERE source_payload::text LIKE '%ፋል%'"
        try:
            records = await db.fetch(q)
            print(f"Table {table} matched: {len(records)}")
            for r in records:
                print(r)
        except Exception as e:
            print(f"Error checking {table}: {e}")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
