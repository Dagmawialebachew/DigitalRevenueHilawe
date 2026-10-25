import asyncio
import os
import json
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import asyncpg

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    
    # 1. Order details for Awaiting Payment (Cohort 1)
    print("=== COHORT 1: ORDERS AWAITING PAYMENT (HIGHEST INTENT) ===")
    orders = await conn.fetch("""
        SELECT 
            o.id as order_id, o.user_id, COALESCE(u.full_name, '') as full_name, COALESCE(u.username, '') as username,
            o.duration_days, o.meals_per_day, o.amount, o.currency, o.state, o.created_at,
            p.status as payment_status, p.bank_code, p.proof_file_id IS NOT NULL as has_proof
        FROM meal_orders o
        LEFT JOIN users u ON o.user_id = u.telegram_id
        LEFT JOIN meal_payments p ON o.id = p.order_id
        WHERE o.state = 'AWAITING_PAYMENT'
        ORDER BY o.created_at DESC
    """)
    total_etb = sum(r['amount'] for r in orders if r['currency'] == 'ETB' and r['amount'])
    total_usd = sum(r['amount'] for r in orders if r['currency'] == 'USD' and r['amount'])
    print(f"Total Pending Orders: {len(orders)}")
    print(f"Stuck Revenue Value: {total_etb:,.0f} ETB + {total_usd:,.0f} USD")
    print(f"Sample pending users (first 10):")
    for r in orders[:10]:
        print(f"  Order #{r['order_id']} | User: {r['full_name']} (@{r['username']}, ID: {r['user_id']}) | {r['amount']} {r['currency']} | {r['duration_days']}d | Proof: {r['has_proof']} | Created: {r['created_at'].strftime('%Y-%m-%d %H:%M')}")

    # 2. Profile Ready cohort (Cohort 2)
    print("\n=== COHORT 2: PROFILE READY (COMPLETED INTAKE, NEVER ORDERED) ===")
    profile_ready = await conn.fetch("""
        SELECT 
            m.id, m.user_id, COALESCE(u.full_name, '') as full_name, COALESCE(u.username, '') as username,
            COALESCE(m.country_name, m.country_region, 'ETHIOPIA') as country,
            m.answers->>'primary_goal' as goal,
            m.nutrition_profile->>'target_kcal' as kcal,
            m.updated_at
        FROM meal_intakes m
        LEFT JOIN users u ON m.user_id = u.telegram_id
        LEFT JOIN meal_orders o ON m.id = o.intake_id
        WHERE m.state = 'PROFILE_READY' AND o.id IS NULL
        ORDER BY m.updated_at DESC
    """)
    print(f"Total Users in Profile Ready (No Order): {len(profile_ready)}")
    for r in profile_ready[:10]:
        print(f"  Intake #{r['id']} | {r['full_name']} (@{r['username']}, ID: {r['user_id']}) | Country: {r['country']} | Goal: {r['goal']} | {r['kcal']} kcal | Last: {r['updated_at'].strftime('%Y-%m-%d %H:%M')}")

    # 3. Intake In-Progress drop-offs by question
    print("\n=== COHORT 3: INTAKE IN-PROGRESS (MID-QUIZ DROP-OFFS) ===")
    in_progress = await conn.fetch("""
        SELECT 
            current_step, COUNT(*) as count
        FROM meal_intakes
        WHERE state = 'INTAKE_IN_PROGRESS'
        GROUP BY current_step
        ORDER BY count DESC
    """)
    for r in in_progress:
        print(f"  Step: {r['current_step']} -> {r['count']} users")

    # 4. Activity recency
    print("\n=== INTAKE RECENCY DISTRIBUTION ===")
    now = datetime.now(timezone.utc)
    recency = await conn.fetch("""
        SELECT 
            CASE 
                WHEN updated_at >= NOW() - INTERVAL '24 hours' THEN 'Past 24 Hours'
                WHEN updated_at >= NOW() - INTERVAL '3 days' THEN '1 to 3 Days Ago'
                WHEN updated_at >= NOW() - INTERVAL '7 days' THEN '4 to 7 Days Ago'
                ELSE 'Older than 7 Days'
            END as recency_bucket,
            COUNT(*) as count
        FROM meal_intakes
        GROUP BY 1
        ORDER BY count DESC
    """)
    for r in recency:
        print(f"  {r['recency_bucket']}: {r['count']} intakes")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
