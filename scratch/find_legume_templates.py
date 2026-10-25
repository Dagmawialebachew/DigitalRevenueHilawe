import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

from database.db import Database
from meal_plan.generation.db_dataset import load_dataset_from_db

async def check_template_keys():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)

    t = next(x for x in dataset.active_templates if x.get('Template ID') == 'MF-L02')
    print("MF-L02 keys and values:")
    for k, v in t.items():
        print(f"  '{k}': {v}")

    t_mn = next(x for x in dataset.active_templates if x.get('Template ID') == 'MN-L07')
    print("\nMN-L07 keys and values:")
    for k, v in t_mn.items():
        print(f"  '{k}': {v}")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check_template_keys())
