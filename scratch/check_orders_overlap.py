import asyncio
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from database.db import Database
from scheduler.retarget_hot_unpaid_leads import get_hot_leads

async def inspect_more():
    db = Database(settings.DATABASE_URL)
    await db.connect()

    leads = await get_hot_leads(db)
    uids = [u['telegram_id'] for u in leads]

    # Check orders table
    orders_match = await db.fetch("""
        SELECT order_id, user_id, status, total_amount, created_at 
        FROM orders 
        WHERE user_id = ANY($1);
    """, uids)
    print(f"Orders match: {len(orders_match)}")
    for o in orders_match:
        print(dict(o))

    # Check meal_orders table
    meal_orders_match = await db.fetch("""
        SELECT id, user_id, status, package_key, created_at 
        FROM meal_orders 
        WHERE user_id = ANY($1);
    """, uids)
    print(f"\nMeal orders match: {len(meal_orders_match)}")
    for mo in meal_orders_match:
        print(dict(mo))

    # Also check if any of these users EVER had an approved payment under any table
    # Check all payments table where user_id in uids regardless of date
    any_approved = await db.fetch("""
        SELECT id, user_id, amount, status, created_at 
        FROM payments 
        WHERE user_id = ANY($1);
    """, uids)
    print(f"\nAll payments (any status) for these users: {len(any_approved)}")
    for p in any_approved:
        print(dict(p))

if __name__ == "__main__":
    asyncio.run(inspect_more())

