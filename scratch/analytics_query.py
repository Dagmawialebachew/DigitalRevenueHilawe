import asyncio
import os
import sys
import json
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
import config
import asyncpg

async def analyze():
    conn = await asyncpg.connect(config.settings.DATABASE_URL)
    
    print("=" * 60)
    print("DATABASE COHORT & REVENUE ANALYSIS")
    print(f"Current Execution Time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    
    # 1. Total Users
    total_users = await conn.fetchval("SELECT count(*) FROM users")
    onboarded_users = await conn.fetchval("SELECT count(*) FROM users WHERE onboarding_completed = TRUE")
    has_paid_users = await conn.fetchval("SELECT count(*) FROM users WHERE has_paid = TRUE")
    print(f"Total registered users: {total_users}")
    print(f"Onboarded users: {onboarded_users}")
    print(f"Flagged has_paid users: {has_paid_users}")

    # 2. Payments Breakdown (Workout Programs)
    pmt_counts = await conn.fetch("""
        SELECT status, count(*), COALESCE(sum(amount), 0) as total_rev
        FROM payments 
        GROUP BY status
    """)
    print("\n--- WORKOUT PAYMENTS BY STATUS ---")
    for r in pmt_counts:
        print(f"Status: {r['status']:<10} Count: {r['count']:<5} Sum: {r['total_rev']} ETB")

    # 3. Approved Workout Payments by Product
    approved_by_prod = await conn.fetch("""
        SELECT p.id, p.title, p.level, p.price, count(pay.id) as paid_count, sum(pay.amount) as total_rev
        FROM payments pay
        JOIN products p ON pay.product_id = p.id
        WHERE pay.status = 'approved'
        GROUP BY p.id, p.title, p.level, p.price
        ORDER BY p.id
    """)
    print("\n--- APPROVED PAYMENTS BY PRODUCT ---")
    for r in approved_by_prod:
        print(f"Product #{r['id']} ({r['level']}): {r['paid_count']} buyers | Rev: {r['total_rev']} ETB | Title: {r['title'][:40]}")

    # 4. Dates of approved payments
    date_summary = await conn.fetchrow("""
        SELECT 
            MIN(COALESCE(approved_at, created_at)) as min_date,
            MAX(COALESCE(approved_at, created_at)) as max_date,
            COUNT(*) as total_approved
        FROM payments
        WHERE status = 'approved'
    """)
    print("\n--- APPROVED PAYMENTS TIMELINE ---")
    print(f"Earliest Approved: {date_summary['min_date']}")
    print(f"Latest Approved:   {date_summary['max_date']}")
    print(f"Total Approved:    {date_summary['total_approved']}")

    # 5. Cohort 8+ Weeks Ago Analysis
    # 8 weeks = 56 days
    now = datetime.now(timezone.utc)
    cutoff_8w = now - timedelta(days=56)
    print(f"\nCutoff for 8-weeks completed: {cutoff_8w.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    cohort_8w = await conn.fetch("""
        SELECT 
            p.level,
            COUNT(DISTINCT pay.user_id) as distinct_users,
            COUNT(pay.id) as total_orders
        FROM payments pay
        JOIN products p ON pay.product_id = p.id
        WHERE pay.status = 'approved' 
          AND COALESCE(pay.approved_at, pay.created_at) <= $1
        GROUP BY p.level
        ORDER BY p.level
    """, cutoff_8w)
    print("\n--- USERS WHO BOUGHT 8+ WEEKS AGO (PROGRAM FINISHED) ---")
    total_finished = 0
    for r in cohort_8w:
        print(f"Level {r['level']:<15}: {r['distinct_users']} distinct users finished")
        total_finished += r['distinct_users']
    print(f"Total distinct users finished 8-week program: {total_finished}")

    # 6. More granular time cohorts
    cohort_time_bins = await conn.fetch("""
        SELECT 
            CASE 
                WHEN COALESCE(pay.approved_at, pay.created_at) <= NOW() - INTERVAL '8 weeks' THEN '8+ weeks (Finished)'
                WHEN COALESCE(pay.approved_at, pay.created_at) <= NOW() - INTERVAL '6 weeks' THEN '6-8 weeks (Almost finished)'
                WHEN COALESCE(pay.approved_at, pay.created_at) <= NOW() - INTERVAL '4 weeks' THEN '4-6 weeks (Midway)'
                ELSE '< 4 weeks (Fresh)'
            END as cohort,
            p.level,
            COUNT(DISTINCT pay.user_id) as users_count
        FROM payments pay
        JOIN products p ON pay.product_id = p.id
        WHERE pay.status = 'approved'
        GROUP BY 1, p.level
        ORDER BY 1, p.level
    """)
    print("\n--- ALL COHORT STAGES BY LEVEL ---")
    for r in cohort_time_bins:
        print(f"{r['cohort']:<28} | Level: {r['level']:<12} | Users: {r['users_count']}")

    # 7. Check if any users bought multiple workout programs
    repeat_buyers = await conn.fetch("""
        SELECT user_id, count(DISTINCT product_id) as prod_count, array_agg(product_id) as prod_ids
        FROM payments
        WHERE status = 'approved'
        GROUP BY user_id
        HAVING count(DISTINCT product_id) > 1
    """)
    print(f"\n--- REPEAT WORKOUT BUYERS: {len(repeat_buyers)} ---")
    for rb in repeat_buyers[:5]:
        print(dict(rb))

    # 8. Meal Plan Database State
    print("\n--- MEAL PLAN DATABASE STATE ---")
    try:
        mp_orders = await conn.fetch("SELECT state, count(*), COALESCE(sum(amount), 0) as total_amt FROM meal_orders GROUP BY state")
        print("meal_orders state counts:")
        for r in mp_orders:
            print(dict(r))
    except Exception as e:
        print(f"Error querying meal_orders: {e}")

    try:
        mp_payments = await conn.fetch("SELECT status, count(*), COALESCE(sum(expected_amount), 0) as total_amt FROM meal_payments GROUP BY status")
        print("meal_payments status counts:")
        for r in mp_payments:
            print(dict(r))
    except Exception as e:
        print(f"Error querying meal_payments: {e}")

    try:
        approved_mp = await conn.fetch("""
            SELECT mp.id, mp.order_id, mp.user_id, mp.status, mp.expected_amount, mp.expected_currency,
                   mo.state as order_state, mo.duration_days, mo.region, mo.created_at,
                   u.full_name, u.username
            FROM meal_payments mp
            JOIN meal_orders mo ON mp.order_id = mo.id
            LEFT JOIN users u ON mo.user_id = u.telegram_id
            ORDER BY mp.id
        """)
        print(f"\nAll Meal Plan Payments ({len(approved_mp)}):")
        for p in approved_mp:
            print(dict(p))
    except Exception as e:
        print(f"Error fetching meal plans: {e}")

    try:
        intake_stats = await conn.fetch("""
            SELECT status, count(*) FROM meal_intakes GROUP BY status
        """)
        print("\nmeal_intakes status counts:")
        for r in intake_stats:
            print(dict(r))
    except Exception as e:
        print(f"Error querying meal_intakes: {e}")

    try:
        pricing_rows = await conn.fetch("SELECT * FROM meal_pricing ORDER BY region, duration_days")
        print("\nMeal Pricing Matrix:")
        for pr in pricing_rows:
            print(dict(pr))
    except Exception as e:
        print(f"Error querying meal_pricing: {e}")

    # 9. Club Payments & Subscriptions check
    try:
        club_p = await conn.fetch("SELECT status, count(*) FROM club_payments GROUP BY status")
        print("\nclub_payments status counts:")
        for r in club_p:
            print(dict(r))
    except Exception as e:
        print(f"Error querying club_payments: {e}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(analyze())
