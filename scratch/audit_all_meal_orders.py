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

    print("=== 1. ALL MEAL ORDERS WITH NON-TERMINAL STATE ===")
    orders = await db.fetch("""
        SELECT o.id, o.user_id, o.state, o.amount, o.paid_at, o.approved_at, u.full_name, u.username
        FROM meal_orders o
        LEFT JOIN users u ON u.telegram_id = o.user_id
        WHERE o.state NOT IN ('DELIVERED', 'COMPLETED', 'EXPIRED', 'CANCELLED')
        ORDER BY o.id DESC;
    """)
    for o in orders:
        print(f"  Order #{o['id']} | User: {o['user_id']} ({o['full_name']} / @{o['username']}) | State: {o['state']} | Amount: {o['amount']} | PaidAt: {o['paid_at']} | ApprovedAt: {o['approved_at']}")

    print("\n=== 2. ALL APPROVED OR PENDING MEAL PAYMENTS ===")
    payments = await db.fetch("""
        SELECT p.id, p.order_id, p.user_id, p.expected_amount, p.status, p.verification_reference, p.created_at, p.approved_at, u.full_name, o.state as order_state
        FROM meal_payments p
        LEFT JOIN meal_orders o ON o.id = p.order_id
        LEFT JOIN users u ON u.telegram_id = p.user_id
        WHERE p.status IN ('APPROVED', 'PENDING')
        ORDER BY p.id DESC;
    """)
    for p in payments:
        print(f"  Payment #{p['id']} | Order #{p['order_id']} ({p['order_state']}) | User: {p['user_id']} ({p['full_name']}) | Amount: {p['expected_amount']} | Status: {p['status']} | Ref: {p['verification_reference']} | ApprovedAt: {p['approved_at']}")

    print("\n=== 3. ALL FAILED / RUNNING / PENDING GENERATION JOBS ===")
    jobs = await db.fetch("""
        SELECT j.id, j.order_id, j.status, j.stage, j.attempt_count, j.last_error_code, j.last_error_message, j.created_at, j.updated_at
        FROM meal_generation_jobs j
        WHERE j.status IN ('FAILED', 'RUNNING', 'PENDING')
        ORDER BY j.id DESC;
    """)
    for j in jobs:
        print(f"  Job #{j['id']} | Order #{j['order_id']} | Status: {j['status']} | Stage: {j['stage']} | Attempts: {j['attempt_count']} | Err: {j['last_error_code']} - {j['last_error_message'][:100] if j['last_error_message'] else 'None'}")

if __name__ == "__main__":
    asyncio.run(main())

