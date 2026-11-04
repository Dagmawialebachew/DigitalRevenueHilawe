import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from database.db import Database

async def run():
    db = Database(settings.DATABASE_URL)
    await db.connect()
    
    rows = await db.fetch("SELECT telegram_id, full_name, username, language, created_at FROM users WHERE onboarding_completed = FALSE OR onboarding_completed IS NULL")
    uids = [r["telegram_id"] for r in rows]
    print(f"Total incomplete users in users table: {len(uids)}")
    
    # Check meal payments
    mp = await db.fetch("SELECT id, order_id, user_id, expected_amount, status, created_at FROM meal_payments WHERE user_id = ANY($1)", uids)
    print(f"Meal payments count: {len(mp)}")
    for p in mp:
        print("  Meal payment:", dict(p))

    # Check meal intakes
    mi = await db.fetch("SELECT id, user_id, language, current_step, completed_at, created_at FROM meal_intakes WHERE user_id = ANY($1)", uids)
    print(f"Meal intakes started by these incomplete main users: {len(mi)}")
    for i in mi:
        print("  Meal intake:", dict(i))

    # Check if any incomplete users have entries in club_subscriptions
    cs = await db.fetch("SELECT user_id, is_active, expires_at FROM club_subscriptions WHERE user_id = ANY($1)", uids)
    print(f"Club subscriptions for incomplete main users: {len(cs)}")
    for s in cs:
        print("  Subscription:", dict(s))

    # Check survey results
    ps = await db.fetch("SELECT * FROM price_survey_results WHERE user_id = ANY($1)", uids)
    print(f"Price survey results for incomplete main users: {len(ps)}")
    
    csurv = await db.fetch("SELECT * FROM club_survey_results WHERE user_id = ANY($1)", uids)
    print(f"Club survey results for incomplete main users: {len(csurv)}")
    for s in csurv:
        print("  Club survey:", dict(s))

if __name__ == "__main__":
    asyncio.run(run())

