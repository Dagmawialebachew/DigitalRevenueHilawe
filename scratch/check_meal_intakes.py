import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from database.db import Database

async def main():
    db = Database(settings.DATABASE_URL)
    await db.connect()
    
    # Check meal_intakes
    meal_intakes_cols = await db.fetch("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'meal_intakes'
        ORDER BY ordinal_position;
    """)
    print("meal_intakes columns:")
    for c in meal_intakes_cols:
        print(f" - {c['column_name']} ({c['data_type']})")
        
    cnt_intakes = await db.fetchval("SELECT COUNT(*) FROM meal_intakes;")
    print(f"Total meal_intakes: {cnt_intakes}")
    
    # Check meal_orders
    cnt_orders = await db.fetchval("SELECT COUNT(*) FROM meal_orders;")
    print(f"Total meal_orders: {cnt_orders}")

    # Check athletes
    cnt_athletes = await db.fetchval("SELECT COUNT(*) FROM athletes;")
    print(f"Total athletes: {cnt_athletes}")

if __name__ == "__main__":
    asyncio.run(main())

