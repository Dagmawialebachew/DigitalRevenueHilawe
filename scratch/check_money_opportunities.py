import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from database.db import Database

async def check():
    db = Database(settings.DATABASE_URL)
    await db.connect()

    # 1. Finished onboarding, pitched, but haven't paid (The Unpaid Finished Users)
    unpaid_finished = await db.fetchval("""
        SELECT COUNT(*) 
        FROM users 
        WHERE onboarding_completed = TRUE 
          AND (has_paid = FALSE OR has_paid IS NULL);
    """)
    print(f"1. Onboarding Completed but Unpaid (Workout Plans): {unpaid_finished} users")

    # 2. Users who submitted receipts that are currently PENDING in payments
    pending_product_payments = await db.fetch("""
        SELECT id, user_id, amount, proof_file_id, created_at 
        FROM payments 
        WHERE status = 'pending'
        ORDER BY created_at DESC;
    """)
    print(f"2. Pending Product Payments (Awaiting Admin Approval): {len(pending_product_payments)}")
    for p in pending_product_payments[:5]:
        print("  Product Payment:", dict(p))

    # 3. Pending Club Payments
    pending_club_payments = await db.fetch("""
        SELECT id, user_id, amount, status, created_at 
        FROM club_payments 
        WHERE status = 'pending'
        ORDER BY created_at DESC;
    """)
    print(f"3. Pending Club Payments (Awaiting Admin Approval): {len(pending_club_payments)}")
    for cp in pending_club_payments[:5]:
        print("  Club Payment:", dict(cp))

    # 4. Pending Meal Orders & Payments
    pending_meal_payments = await db.fetch("""
        SELECT id, order_id, user_id, expected_amount, status, created_at 
        FROM meal_payments 
        WHERE status = 'PENDING'
        ORDER BY created_at DESC;
    """)
    print(f"4. Pending Meal Plan Payments: {len(pending_meal_payments)}")
    for mp in pending_meal_payments[:5]:
        print("  Meal Payment:", dict(mp))

    # 5. Club members whose subscriptions are expired (Churned club members)
    expired_subs = await db.fetchval("""
        SELECT COUNT(*) 
        FROM club_subscriptions 
        WHERE is_active = FALSE OR expires_at < NOW();
    """)
    print(f"5. Expired Club Members (Re-activation Target): {expired_subs}")

    # 6. How many users completed onboarding in the last 7 days but didn't buy?
    recent_unpaid_7d = await db.fetchval("""
        SELECT COUNT(*) 
        FROM users 
        WHERE onboarding_completed = TRUE 
          AND (has_paid = FALSE OR has_paid IS NULL)
          AND created_at >= NOW() - INTERVAL '7 days';
    """)
    print(f"6. Fresh Unpaid Leads (Completed Onboarding in Last 7 Days): {recent_unpaid_7d}")

    # 7. Total paid users across all time
    paid_users = await db.fetchval("SELECT COUNT(*) FROM users WHERE has_paid = TRUE;")
    print(f"7. Confirmed Paid Users (Workout): {paid_users}")

if __name__ == "__main__":
    asyncio.run(check())

