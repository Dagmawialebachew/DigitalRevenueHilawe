import asyncio
import json
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

    # 1. Check meal_orders for id = 72
    try:
        order = await db.fetchrow("SELECT * FROM meal_orders WHERE id = 72;")
        print("--- MEAL_ORDERS #72 ---")
        if order:
            print(dict(order))
        else:
            print("Order #72 not found in meal_orders")
    except Exception as e:
        print("Error fetching meal_orders:", e)

    # 2. Check orders table if exists
    try:
        orders_row = await db.fetchrow("SELECT * FROM orders WHERE id = 72;")
        print("\n--- ORDERS #72 ---")
        if orders_row:
            print(dict(orders_row))
    except Exception as e:
        print("orders table check:", e)

    # 3. Check meal_generation_jobs for order_id = 72 or id = 72
    try:
        jobs = await db.fetch("SELECT * FROM meal_generation_jobs WHERE order_id = 72 OR id = 72 ORDER BY id DESC;")
        print(f"\n--- MEAL_GENERATION_JOBS for 72 ({len(jobs)} found) ---")
        for j in jobs:
            print(dict(j))
    except Exception as e:
        print("Error fetching meal_generation_jobs:", e)

    # 4. Check meal_intakes for the user or order
    if order:
        user_id = order['user_id']
        print(f"\n--- USER {user_id} ---")
        user = await db.fetchrow("SELECT * FROM users WHERE telegram_id = $1;", user_id)
        if user:
            print(dict(user))

        intake = await db.fetchrow("SELECT * FROM meal_intakes WHERE user_id = $1 ORDER BY id DESC LIMIT 1;", user_id)
        print("\n--- MEAL_INTAKES ---")
        if intake:
            print(dict(intake))

        payments = await db.fetch("SELECT * FROM meal_payments WHERE order_id = 72 OR user_id = $1;", user_id)
        print(f"\n--- MEAL_PAYMENTS ({len(payments)} found) ---")
        for p in payments:
            print(dict(p))

    # 5. Check any other pending/running meal_generation_jobs
    all_pending_jobs = await db.fetch("SELECT * FROM meal_generation_jobs WHERE status IN ('PENDING', 'RUNNING') ORDER BY id DESC;")
    print(f"\n--- ALL PENDING / RUNNING JOBS ({len(all_pending_jobs)}) ---")
    for j in all_pending_jobs:
        print(dict(j))

asyncio.run(inspect())

