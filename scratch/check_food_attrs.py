import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

from database.db import Database
from meal_plan.generation.db_dataset import load_dataset_from_db

async def check_foods():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)

    for fid in ("C001", "C010", "A018", "A011"):
        food = dataset.food_by_id.get(fid)
        print(f"FID {fid}: {food.get('Food Name') if food else None}")
        if food:
            print(f"  Exchange Group: '{food.get('Exchange Group')}'")
            print(f"  Category: '{food.get('Category')}'")
            print(f"  Carbs / 100 g: {food.get('Carbs / 100 g')}")
            print(f"  Protein / 100 g: {food.get('Protein / 100 g')}")
            print(f"  kcal / 100 g: {food.get('kcal / 100 g')}")

    print(f"\nTotal active_exchanges: {len(dataset.active_exchanges)}")
    if dataset.active_exchanges:
        print("Sample exchange:", dataset.active_exchanges[0])

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check_foods())
