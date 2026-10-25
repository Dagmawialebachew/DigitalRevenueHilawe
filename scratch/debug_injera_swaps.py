import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

from database.db import Database
from meal_plan.generation.db_dataset import load_dataset_from_db
from meal_plan.generation.swaps import build_exchange_options

async def debug_injera_swaps():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)

    ans = {"grocery_budget": "SAVE", "dietary_pattern": "OMNIVORE"}
    all_swaps = build_exchange_options("C001", dataset, ans, fasting=False, base_grams=240.0, limit=20)
    print("All Injera swaps count:", len(all_swaps))
    for idx, s in enumerate(all_swaps):
        print(f"  [{idx+1}] {s['food_id']} ({s['food_name_am']}): {s['grams']}g ({s['familiar_am']}) [kcal: {s['macros']['kcal']:.0f}, diff: {abs(s['macros']['kcal'] - 340.8):.1f}]")

    # Check if C011 is in all_swaps
    c011 = [s for s in all_swaps if s['food_id'] == 'C011']
    print("\nC011 in all_swaps:", c011)

    # Let's inspect active_exchanges entries for Starch
    print("\nStarch exchanges in dataset.active_exchanges:")
    for x in dataset.active_exchanges:
        if x.get("Exchange Group") == "Starch":
            print(f"  FID: {x.get('Food ID')}, Active: {x.get('Active')}, Fasting: {x.get('Fasting Allowed')}")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(debug_injera_swaps())
