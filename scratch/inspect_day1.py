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

    for d in plan["core_week"]:
        d_idx = d["day_index"] + 1
        print(f"Day {d_idx} ({d['day_name']}): {d['totals']['kcal']:.0f} kcal (P: {d['totals']['protein']:.0f}g, C: {d['totals']['carbs']:.0f}g, F: {d['totals']['fat']:.0f}g)")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
