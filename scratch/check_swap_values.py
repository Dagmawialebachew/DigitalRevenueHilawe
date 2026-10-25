import asyncio
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.path.insert(0, ".")
from database.db import Database
from meal_plan.generation.db_dataset import load_dataset_from_db

async def main():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)
        row = await conn.fetchrow("SELECT plan_json FROM meal_plan_versions WHERE id = 15")
        plan = row["plan_json"] if isinstance(row["plan_json"], dict) else json.loads(row["plan_json"])

    d1_b = plan["core_week"][0]["meals"][0]
    print("Day 1 Breakfast items:")
    for it in d1_b["items"]:
        print(f"  {it['food_id']}: {it['grams']}g ({it['food_name']})")

    c001 = dataset.food_by_id.get("C001")
    c011 = dataset.food_by_id.get("C011")
    c010 = dataset.food_by_id.get("C010")
    c005 = dataset.food_by_id.get("C005")

    print("\nNutritional values in DB:")
    print("C001 (Injera):", c001.get("Carbs / 100 g"), "carbs/100g")
    print("C011 (Sweet Potato):", c011.get("Carbs / 100 g"), "carbs/100g")
    print("C010 (Potato):", c010.get("Carbs / 100 g"), "carbs/100g")
    print("C005 (Pasta):", c005.get("Carbs / 100 g"), "carbs/100g")

    injera_grams = next(it["grams"] for it in d1_b["items"] if it["food_id"] == "C001")
    target_carbs = injera_grams * (float(c001.get("Carbs / 100 g") or 0) / 100.0)
    sp_carbs_per_g = float(c011.get("Carbs / 100 g") or 0) / 100.0
    sp_grams = round((target_carbs / sp_carbs_per_g) / 10.0) * 10.0
    print(f"\nInjera grams: {injera_grams}g -> Target carbs: {target_carbs}g -> Sweet potato grams: {sp_grams}g")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
