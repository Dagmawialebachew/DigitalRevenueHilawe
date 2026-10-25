import asyncio
import os
import json
import sys
from dotenv import load_dotenv
import asyncpg

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    
    # 1. Total counts
    user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
    intake_count = await conn.fetchval("SELECT COUNT(*) FROM meal_intakes")
    order_count = await conn.fetchval("SELECT COUNT(*) FROM meal_orders")
    payment_count = await conn.fetchval("SELECT COUNT(*) FROM meal_payments")
    audit_count = await conn.fetchval("SELECT COUNT(*) FROM meal_audit_events")
    print(f"Total Counts -> Users: {user_count}, Intakes: {intake_count}, Orders: {order_count}, Payments: {payment_count}, Audit Events: {audit_count}")

    # 2. Country Breakdown in meal_intakes & answers
    print("\n=== COUNTRY / REGION BREAKDOWN ===")
    country_rows = await conn.fetch("""
        SELECT 
            COALESCE(country_name, country_region, answers->>'country_name', answers->>'country', answers->>'region', 'UNKNOWN') as country,
            COUNT(*) as count
        FROM meal_intakes
        GROUP BY 1
        ORDER BY count DESC
    """)
    for r in country_rows:
        print(f"  {r['country']}: {r['count']}")

    # 3. Intake State & Step Breakdown
    print("\n=== INTAKE STATE BREAKDOWN ===")
    state_rows = await conn.fetch("""
        SELECT state, COUNT(*) as count
        FROM meal_intakes
        GROUP BY state
        ORDER BY count DESC
    """)
    for r in state_rows:
        print(f"  {r['state']}: {r['count']}")

    print("\n=== INTAKE CURRENT_STEP BREAKDOWN ===")
    step_rows = await conn.fetch("""
        SELECT current_step, COUNT(*) as count
        FROM meal_intakes
        GROUP BY current_step
        ORDER BY count DESC
    """)
    for r in step_rows:
        print(f"  {r['current_step']}: {r['count']}")

    # 4. Telemetry events breakdown
    print("\n=== TELEMETRY EVENT BREAKDOWN (meal_audit_events) ===")
    event_rows = await conn.fetch("""
        SELECT event_type, COUNT(*) as total_events, COUNT(DISTINCT actor_telegram_id) as unique_users
        FROM meal_audit_events
        GROUP BY event_type
        ORDER BY unique_users DESC
    """)
    for r in event_rows:
        print(f"  {r['event_type']}: {r['total_events']} events, {r['unique_users']} unique users")

    # 5. Order State Breakdown
    print("\n=== ORDER STATE BREAKDOWN ===")
    order_states = await conn.fetch("""
        SELECT state, COUNT(*) as count
        FROM meal_orders
        GROUP BY state
        ORDER BY count DESC
    """)
    for r in order_states:
        print(f"  {r['state']}: {r['count']}")

    # 6. Payment State Breakdown
    print("\n=== PAYMENT STATUS BREAKDOWN ===")
    payment_states = await conn.fetch("""
        SELECT status, COUNT(*) as count
        FROM meal_payments
        GROUP BY status
        ORDER BY count DESC
    """)
    for r in payment_states:
        print(f"  {r['status']}: {r['count']}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
