import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

from database.db import Database
from meal_plan.generation.db_dataset import load_dataset_from_db

async def check_groups():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)

    groups = set()
    for x in dataset.active_exchanges:
        groups.add(x.get("Exchange Group"))
    print("Exchange groups in dataset.active_exchanges:", groups)

    # Check for C001, C010, A018 in active_exchanges
    for fid in ("C001", "C010", "A018", "A011", "C011", "C005", "C003"):
        matches = [x for x in dataset.active_exchanges if x.get("Food ID") == fid]
        print(f"FID {fid} in active_exchanges: {len(matches)} matches: {matches}")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check_groups())
