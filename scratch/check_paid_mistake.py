import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from database.db import Database

async def check():
    db = Database(settings.DATABASE_URL)
    await db.connect()

    # Get the targets that were fetched by get_hot_leads
    rows = await db.fetch("""
        SELECT u.telegram_id, u.full_name, u.has_paid
        FROM users u
        WHERE u.onboarding_completed = TRUE 
          AND (u.has_paid = FALSE OR u.has_paid IS NULL)
          AND u.created_at >= NOW() - INTERVAL '7 days';
    """)
    uids = [r['telegram_id'] for r in rows]

    # Check how many of these uids have approved payments in payments table
    approved_product = await db.fetch("""
        SELECT id, user_id, amount, status, approved_at, created_at
        FROM payments 
        WHERE user_id = ANY($1) AND status = 'approved';
    """, uids)
    print(f"Users with approved PRODUCT payments in this cohort: {len(approved_product)}")
    for p in approved_product:
        print("  Product payment:", dict(p))

    # Check club payments
    approved_club = await db.fetch("""
        SELECT id, user_id, amount, status, processed_at, created_at
        FROM club_payments 
        WHERE user_id = ANY($1) AND status = 'approved';
    """, uids)
    print(f"Users with approved CLUB payments in this cohort: {len(approved_club)}")
    for cp in approved_club:
        print("  Club payment:", dict(cp))

    # Check meal payments
    approved_meal = await db.fetch("""
        SELECT id, user_id, expected_amount, status, approved_at, created_at
        FROM meal_payments 
        WHERE user_id = ANY($1) AND status = 'APPROVED';
    """, uids)
    print(f"Users with approved MEAL payments in this cohort: {len(approved_meal)}")
    for mp in approved_meal:
        print("  Meal payment:", dict(mp))

if __name__ == "__main__":
    asyncio.run(check())

