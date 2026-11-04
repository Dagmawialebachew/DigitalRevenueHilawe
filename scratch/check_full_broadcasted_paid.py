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

async def main():
    db = Database(settings.DATABASE_URL)
    await db.connect()

    # Find all users who received the hot leads broadcast (last_broadcast_msg_id between 454350 and 455000)
    # or last_broadcast_msg_id IS NOT NULL with updated time today
    broadcasted_users = await db.fetch("""
        SELECT u.telegram_id, u.full_name, u.username, u.has_paid, u.last_broadcast_msg_id
        FROM users u
        WHERE u.last_broadcast_msg_id >= 454300;
    """)
    print(f"Total users with today's hot-lead broadcast msg id: {len(broadcasted_users)}")
    uids = [u['telegram_id'] for u in broadcasted_users]

    # Check workout payments for these
    wp = await db.fetch("""
        SELECT p.id, p.user_id, p.amount, p.status, p.created_at, p.approved_at, u.full_name, u.username
        FROM payments p
        JOIN users u ON u.telegram_id = p.user_id
        WHERE p.user_id = ANY($1)
        ORDER BY p.id DESC;
    """, uids)
    print(f"\n--- Workout Payments among broadcasted users ({len(wp)}) ---")
    for r in wp:
        print(f"  Payment #{r['id']} | User {r['user_id']} ({r['full_name']} @{r['username']}) | Amount: {r['amount']} ETB | Status: {r['status']} | Created: {r['created_at']} | Approved: {r['approved_at']}")

    # Check meal payments for these
    mp = await db.fetch("""
        SELECT mp.id, mp.user_id, mp.expected_amount, mp.status, mp.created_at, mp.approved_at, u.full_name, u.username
        FROM meal_payments mp
        JOIN users u ON u.telegram_id = mp.user_id
        WHERE mp.user_id = ANY($1)
        ORDER BY mp.id DESC;
    """, uids)
    print(f"\n--- Meal Payments among broadcasted users ({len(mp)}) ---")
    for r in mp:
        print(f"  Meal Payment #{r['id']} | User {r['user_id']} ({r['full_name']} @{r['username']}) | Amount: {r['expected_amount']} ETB | Status: {r['status']} | Created: {r['created_at']} | Approved: {r['approved_at']}")

    # Check Yodahe's details specifically:
    yodahe = await db.fetchrow("SELECT * FROM payments WHERE id = 696;")
    print("\n--- Payment #696 (Yodahe) details ---")
    print(dict(yodahe))

if __name__ == "__main__":
    asyncio.run(main())

