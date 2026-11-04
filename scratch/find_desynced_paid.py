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

async def inspect():
    db = Database(settings.DATABASE_URL)
    await db.connect()

    # Total approved in payments
    approved_payments = await db.fetch("""
        SELECT p.id, p.user_id, p.amount, p.created_at, u.has_paid, u.onboarding_completed, u.created_at as user_created
        FROM payments p
        LEFT JOIN users u ON u.telegram_id = p.user_id
        WHERE p.status = 'approved'
        ORDER BY p.created_at DESC;
    """)
    print(f"Total approved payments in payments table: {len(approved_payments)}")
    
    # Check if any user with approved payment has has_paid = FALSE or NULL in users table
    desynced = [p for p in approved_payments if not p['has_paid']]
    print(f"Approved payments where u.has_paid is FALSE or NULL: {len(desynced)}")
    for p in desynced[:10]:
        print("  Desynced paid user:", dict(p))

    # Also check if any user who has an approved payment in payments received a broadcast today
    broadcasted_paid = await db.fetch("""
        SELECT p.id, p.user_id, p.amount, p.status, p.approved_at, u.full_name, u.has_paid, u.last_broadcast_msg_id
        FROM payments p
        JOIN users u ON u.telegram_id = p.user_id
        WHERE p.status = 'approved' AND u.last_broadcast_msg_id IS NOT NULL;
    """)
    print(f"\nApproved payments users who have last_broadcast_msg_id set: {len(broadcasted_paid)}")
    for p in broadcasted_paid:
        print("  Paid user who received broadcast:", dict(p))

    # Also check who the user specifically mentioned!
    # Let's check recent payments (last 7 days)
    recent_p = await db.fetch("""
        SELECT p.id, p.user_id, p.amount, p.status, p.created_at, u.full_name, u.has_paid, u.last_broadcast_msg_id
        FROM payments p
        JOIN users u ON u.telegram_id = p.user_id
        WHERE p.created_at >= NOW() - INTERVAL '7 days'
        ORDER BY p.created_at DESC;
    """)
    print(f"\nPayments in last 7 days: {len(recent_p)}")
    for p in recent_p:
        print("  Recent payment:", dict(p))

if __name__ == "__main__":
    asyncio.run(inspect())

