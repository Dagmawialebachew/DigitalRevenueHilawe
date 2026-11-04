import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from database.db import Database

async def inspect_payments():
    db = Database(settings.DATABASE_URL)
    await db.connect()
    
    mp_cols = await db.fetch("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'meal_payments'
        ORDER BY ordinal_position;
    """)
    print("meal_payments columns:")
    for c in mp_cols:
        print(f" - {c['column_name']} ({c['data_type']})")

    # Also inspect the 5 club payments
    incomplete_rows = await db.fetch("""
        SELECT telegram_id FROM users WHERE onboarding_completed = FALSE OR onboarding_completed IS NULL
    """)
    uids = [r["telegram_id"] for r in incomplete_rows]
    
    club_payments = await db.fetch("""
        SELECT * FROM club_payments WHERE user_id = ANY($1::bigint[])
    """, uids)
    print(f"\nClub payments count: {len(club_payments)}")
    for cp in club_payments:
        print(dict(cp))

    # Also check orders
    orders = await db.fetch("""
        SELECT * FROM orders WHERE user_id = ANY($1::bigint[])
    """, uids)
    print(f"\nOrders count: {len(orders)}")
    for o in orders:
        print(dict(o))

    # Check meal_orders
    meal_orders = await db.fetch("""
        SELECT * FROM meal_orders WHERE user_id = ANY($1::bigint[])
    """, uids)
    print(f"\nMeal orders count: {len(meal_orders)}")
    for mo in meal_orders:
        print(dict(mo))

if __name__ == "__main__":
    asyncio.run(inspect_payments())

