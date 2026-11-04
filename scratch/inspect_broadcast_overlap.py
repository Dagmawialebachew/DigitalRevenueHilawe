import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from database.db import Database

async def inspect():
    db = Database(settings.DATABASE_URL)
    await db.connect()

    # 1. Who has last_broadcast_msg_id IS NOT NULL?
    broadcasted_users = await db.fetch("""
        SELECT telegram_id, full_name, username, has_paid, created_at
        FROM users
        WHERE last_broadcast_msg_id IS NOT NULL;
    """)
    b_uids = [u['telegram_id'] for u in broadcasted_users]
    print(f"Total users with last_broadcast_msg_id: {len(b_uids)}")

    # 2. Check if ANY of these users exist in payments table
    payments_match = await db.fetch("""
        SELECT p.id, p.user_id, p.amount, p.status, p.created_at, u.full_name
        FROM payments p
        JOIN users u ON u.telegram_id = p.user_id
        WHERE p.user_id = ANY($1);
    """, b_uids)
    print(f"\nBroadcasted users with records in PAYMENTS: {len(payments_match)}")
    for p in payments_match:
        print("  Payment record:", dict(p))

    # 3. Check club_payments
    club_match = await db.fetch("""
        SELECT cp.id, cp.user_id, cp.amount, cp.status, cp.created_at, u.full_name
        FROM club_payments cp
        JOIN users u ON u.telegram_id = cp.user_id
        WHERE cp.user_id = ANY($1);
    """, b_uids)
    print(f"\nBroadcasted users with records in CLUB_PAYMENTS: {len(club_match)}")
    for cp in club_match:
        print("  Club payment record:", dict(cp))

    # 4. Check meal_payments
    meal_match = await db.fetch("""
        SELECT mp.id, mp.user_id, mp.expected_amount, mp.status, mp.created_at, u.full_name
        FROM meal_payments mp
        JOIN users u ON u.telegram_id = mp.user_id
        WHERE mp.user_id = ANY($1);
    """, b_uids)
    print(f"\nBroadcasted users with records in MEAL_PAYMENTS: {len(meal_match)}")
    for mp in meal_match:
        print("  Meal payment record:", dict(mp))

    # 5. Check if any user had has_paid = TRUE in users table
    paid_flag_match = await db.fetch("""
        SELECT telegram_id, full_name, has_paid 
        FROM users 
        WHERE telegram_id = ANY($1) AND has_paid = TRUE;
    """, b_uids)
    print(f"\nBroadcasted users with has_paid=TRUE: {len(paid_flag_match)}")
    for u in paid_flag_match:
        print("  has_paid=True user:", dict(u))

if __name__ == "__main__":
    asyncio.run(inspect())

