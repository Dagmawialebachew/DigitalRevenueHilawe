import asyncio
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.path.insert(0, ".")
from database.db import Database

async def main():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    async with db._pool.acquire() as conn:
        row = await conn.fetchrow("SELECT plan_json FROM meal_plan_versions WHERE id = 15")
        plan = row["plan_json"] if isinstance(row["plan_json"], dict) else json.loads(row["plan_json"])

    d2 = plan["core_week"][1]
    print(f"Day 2 Total: {d2['totals']['kcal']} kcal (P: {d2['totals']['protein']}g, C: {d2['totals']['carbs']}g, F: {d2['totals']['fat']}g)")
    for m in d2["meals"]:
        print(f"\nMeal: {m['meal_name']} ({m['macros']['kcal']} kcal)")
        for it in m["items"]:
            print(f"  - {it['food_name']} ({it['food_id']}): {it['grams']}g ({it['familiar']}) -> {it['macros']['kcal']} kcal")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
