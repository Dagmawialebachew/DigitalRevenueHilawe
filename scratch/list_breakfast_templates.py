import asyncio, os, sys
from dotenv import load_dotenv
load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from meal_plan.generation.db_dataset import load_dataset_from_db
from database.db import Database

async def test():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    async with db._pool.acquire() as conn:
        ds = await load_dataset_from_db(conn)
    b_templates = [t for t in ds.templates if t.get("Meal Slot") == "Breakfast" and t.get("Active") == "Yes"]
    print(f"Total active breakfast templates: {len(b_templates)}")
    for t in b_templates:
        comps = ds.components_by_template.get(t["Template ID"], [])
        rec_ids = [c.get("Item ID") for c in comps]
        print(f"{t['Template ID']} | {t.get('Meal Name')} | Budget: {t.get('Budget')} | Fasting: {t.get('Fasting')} | Items: {rec_ids}")
    await db.disconnect()

asyncio.run(test())
