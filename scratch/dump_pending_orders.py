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
    
    # 1. All 39 pending orders with exact amounts
    orders = await conn.fetch("""
        SELECT 
            o.id as order_id, o.user_id, COALESCE(u.full_name, '') as full_name, COALESCE(u.username, '') as username,
            o.duration_days, o.meals_per_day, o.amount, o.currency, o.state, o.created_at,
            i.answers->>'primary_goal' as goal,
            COALESCE(i.country_name, i.country_region, 'ETHIOPIA') as country
        FROM meal_orders o
        LEFT JOIN users u ON o.user_id = u.telegram_id
        LEFT JOIN meal_intakes i ON o.intake_id = i.id
        WHERE o.state = 'AWAITING_PAYMENT'
        ORDER BY o.created_at DESC
    """)
    print("=== PENDING ORDERS DUMP ===")
    for o in orders:
        uname = f"@{o['username']}" if o['username'] else "No Username"
        print(f"Order #{o['order_id']} | TG: {o['user_id']} | {o['full_name']} ({uname}) | {o['amount']} {o['currency']} | {o['duration_days']}d | Goal: {o['goal']} | Country: {o['country']}")

    # 2. Summary stats for durations chosen in pending orders
    dur_stats = await conn.fetch("""
        SELECT duration_days, currency, amount, COUNT(*) as count
        FROM meal_orders
        WHERE state = 'AWAITING_PAYMENT'
        GROUP BY duration_days, currency, amount
        ORDER BY count DESC
    """)
    print("\n=== DURATION BREAKDOWN IN PENDING ORDERS ===")
    for d in dur_stats:
        print(f"  {d['duration_days']} Days | {d['amount']} {d['currency']} | {d['count']} users")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
