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

async def inspect_swaps():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)

    ans = {"grocery_budget": "SAVE", "dietary_pattern": "OMNIVORE"}
    print("--- Injera C001 (240g) Swaps ---")
    injera_swaps = build_exchange_options("C001", dataset, ans, fasting=False, base_grams=240.0, limit=6)
    for s in injera_swaps:
        print(f"  {s['food_id']} ({s['food_name_am']}): {s['grams']}g ({s['familiar_am']}) [kcal: {s['macros']['kcal']:.0f}, C: {s['macros']['carbs']:.1f}g, P: {s['macros']['protein']:.1f}g]")

    print("\n--- Boiled Potato C010 (400g) Swaps ---")
    potato_swaps = build_exchange_options("C010", dataset, ans, fasting=False, base_grams=400.0, limit=6)
    for s in potato_swaps:
        print(f"  {s['food_id']} ({s['food_name_am']}): {s['grams']}g ({s['familiar_am']}) [kcal: {s['macros']['kcal']:.0f}, C: {s['macros']['carbs']:.1f}g, P: {s['macros']['protein']:.1f}g]")

    print("\n--- Ayib A018 (100g) Swaps ---")
    ayib_swaps = build_exchange_options("A018", dataset, ans, fasting=False, base_grams=100.0, limit=6)
    for s in ayib_swaps:
        print(f"  {s['food_id']} ({s['food_name_am']}): {s['grams']}g ({s['familiar_am']}) [kcal: {s['macros']['kcal']:.0f}, C: {s['macros']['carbs']:.1f}g, P: {s['macros']['protein']:.1f}g]")

    print("\n--- Boiled Egg A011 (100g) Swaps ---")
    egg_swaps = build_exchange_options("A011", dataset, ans, fasting=False, base_grams=100.0, limit=6)
    for s in egg_swaps:
        print(f"  {s['food_id']} ({s['food_name_am']}): {s['grams']}g ({s['familiar_am']}) [kcal: {s['macros']['kcal']:.0f}, C: {s['macros']['carbs']:.1f}g, P: {s['macros']['protein']:.1f}g]")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(inspect_swaps())
