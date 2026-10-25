import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

from database.db import Database
from meal_plan.generation.db_dataset import load_dataset_from_db

async def check_tmpl():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)

    for tid in ("MN-B02", "MF-B02", "MF-B07"):
        comps = dataset.components_by_template.get(tid, [])
        print(f"\nTemplate {tid} ({len(comps)} components):")
        for c in comps:
            print(f"  Item Type: {c.get('Item Type')}, Item ID: {c.get('Item ID')}, Item Name: {c.get('Item Name')}, Grams: {c.get('Grams')}, Portion Role: {c.get('Portion Role')}")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check_tmpl())
