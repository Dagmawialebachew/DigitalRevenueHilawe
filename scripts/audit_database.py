import asyncio
import os
import sys
import json
from dotenv import load_dotenv
import asyncpg
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()
dsn = os.getenv("DATABASE_URL")

async def run_audit():
    print(f"Connecting to database with statement_cache_size=0...")
    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    
    # 1. Tables overview
    tables = await conn.fetch("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    print("\n=================== PUBLIC TABLES & ROW COUNTS ===================")
    table_counts = {}
    for t in tables:
        tname = t["table_name"]
        try:
            cnt = await conn.fetchval(f'SELECT count(*) FROM "{tname}"')
            table_counts[tname] = cnt
            print(f"  {tname:35}: {cnt:>8} rows")
        except Exception as e:
            print(f"  {tname:35}: ERROR {e}")

    # 2. Users Deep Dive
    print("\n=================== USER METRICS ===================")
    total_users = await conn.fetchval("SELECT count(*) FROM users")
    onboarded = await conn.fetchval("SELECT count(*) FROM users WHERE onboarding_completed = TRUE")
    has_paid_flag = await conn.fetchval("SELECT count(*) FROM users WHERE has_paid = TRUE")
    gender_stats = await conn.fetch("SELECT gender, count(*) as c FROM users GROUP BY gender ORDER BY c DESC")
    lang_stats = await conn.fetch("SELECT language, count(*) as c FROM users GROUP BY language ORDER BY c DESC")
    level_stats = await conn.fetch("SELECT level, count(*) as c FROM users GROUP BY level ORDER BY c DESC")
    freq_stats = await conn.fetch("SELECT frequency, count(*) as c FROM users GROUP BY frequency ORDER BY c DESC")
    earliest_user = await conn.fetchval("SELECT min(created_at) FROM users")
    latest_user = await conn.fetchval("SELECT max(created_at) FROM users")

    print(f"Total Users Registered       : {total_users}")
    print(f"Onboarding Completed         : {onboarded} ({(onboarded/total_users*100 if total_users else 0):.1f}%)")
    print(f"Users with has_paid=TRUE     : {has_paid_flag} ({(has_paid_flag/total_users*100 if total_users else 0):.1f}%)")
    print(f"Earliest User Registration   : {earliest_user}")
    print(f"Latest User Registration     : {latest_user}")
    print("Gender breakdown:", {r['gender']: r['c'] for r in gender_stats})
    print("Language breakdown:", {r['language']: r['c'] for r in lang_stats})
    print("Level breakdown:", {r['level']: r['c'] for r in level_stats})
    print("Frequency breakdown:", {r['frequency']: r['c'] for r in freq_stats})

    # 3. Product Sales (Stream A: payments)
    print("\n=================== STREAM A: PRODUCT PAYMENTS ===================")
    payments_summary = await conn.fetch("""
        SELECT 
            status, 
            count(*) as count, 
            COALESCE(sum(amount), 0) as total_amount,
            min(created_at) as first_payment,
            max(created_at) as last_payment
        FROM payments 
        GROUP BY status
        ORDER BY count DESC
    """)
    for r in payments_summary:
        print(f"Status: {r['status']:12} | Count: {r['count']:>6} | Total ETB: {float(r['total_amount']):>12,.2f} | Range: {r['first_payment']} -> {r['last_payment']}")

    approved_prod_revenue = await conn.fetchval("SELECT COALESCE(sum(amount), 0) FROM payments WHERE status = 'approved'")
    approved_prod_count = await conn.fetchval("SELECT count(*) FROM payments WHERE status = 'approved'")
    unique_paying_users_prod = await conn.fetchval("SELECT count(DISTINCT user_id) FROM payments WHERE status = 'approved'")
    print(f"--> Approved Product Revenue : {float(approved_prod_revenue):,.2f} ETB across {approved_prod_count} txns ({unique_paying_users_prod} distinct buyers)")

    # 4. Club Payments (Stream B: club_payments)
    print("\n=================== STREAM B: CLUB PAYMENTS ===================")
    club_summary = await conn.fetch("""
        SELECT 
            status, 
            count(*) as count, 
            COALESCE(sum(amount), 0) as total_amount,
            min(created_at) as first_payment,
            max(created_at) as last_payment
        FROM club_payments 
        GROUP BY status
        ORDER BY count DESC
    """)
    for r in club_summary:
        print(f"Status: {r['status']:12} | Count: {r['count']:>6} | Total ETB: {float(r['total_amount']):>12,.2f} | Range: {r['first_payment']} -> {r['last_payment']}")

    approved_club_revenue = await conn.fetchval("SELECT COALESCE(sum(amount), 0) FROM club_payments WHERE status = 'approved'")
    approved_club_count = await conn.fetchval("SELECT count(*) FROM club_payments WHERE status = 'approved'")
    unique_paying_users_club = await conn.fetchval("SELECT count(DISTINCT user_id) FROM club_payments WHERE status = 'approved'")
    print(f"--> Approved Club Revenue    : {float(approved_club_revenue):,.2f} ETB across {approved_club_count} txns ({unique_paying_users_club} distinct buyers)")

    # Club Type breakdown (new vs renewal)
    try:
        club_types = await conn.fetch("SELECT payment_type, count(*), sum(amount) FROM club_payments WHERE status = 'approved' GROUP BY payment_type")
        print("Club Payment Types (Approved):", [dict(r) for r in club_types])
    except Exception as e:
        print("Could not query payment_type:", e)

    # 5. Club Subscriptions
    print("\n=================== CLUB SUBSCRIPTIONS ===================")
    total_subs = await conn.fetchval("SELECT count(*) FROM club_subscriptions")
    active_subs = await conn.fetchval("SELECT count(*) FROM club_subscriptions WHERE is_active = TRUE")
    valid_active_subs = await conn.fetchval("SELECT count(*) FROM club_subscriptions WHERE is_active = TRUE AND expires_at > NOW()")
    expired_active_subs = await conn.fetchval("SELECT count(*) FROM club_subscriptions WHERE is_active = TRUE AND expires_at <= NOW()")
    inactive_subs = await conn.fetchval("SELECT count(*) FROM club_subscriptions WHERE is_active = FALSE")
    print(f"Total Sub Records           : {total_subs}")
    print(f"Marked Active               : {active_subs} (Valid/Future: {valid_active_subs}, Expired but marked active: {expired_active_subs})")
    print(f"Marked Inactive             : {inactive_subs}")

    # 6. Total Gross Revenue
    total_verified_revenue = float(approved_prod_revenue) + float(approved_club_revenue)
    print("\n=================== TOTAL LIFETIME REVENUE ===================")
    print(f"*** TOTAL VERIFIED GROSS REVENUE: {total_verified_revenue:,.2f} ETB")
    print(f"   |-- Product Sales : {float(approved_prod_revenue):,.2f} ETB ({(float(approved_prod_revenue)/total_verified_revenue*100 if total_verified_revenue else 0):.1f}%)")
    print(f"   +-- Club Revenue  : {float(approved_club_revenue):,.2f} ETB ({(float(approved_club_revenue)/total_verified_revenue*100 if total_verified_revenue else 0):.1f}%)")

    # 7. Products Breakdown
    print("\n=================== PRODUCTS PERFORMANCE ===================")
    products = await conn.fetch("""
        SELECT 
            p.id, p.title, p.language, p.gender, p.level, p.frequency, p.price, p.is_active,
            COUNT(pay.id) FILTER (WHERE pay.status = 'approved') as sales_count,
            COALESCE(SUM(pay.amount) FILTER (WHERE pay.status = 'approved'), 0) as revenue
        FROM products p
        LEFT JOIN payments pay ON p.id = pay.product_id
        GROUP BY p.id
        ORDER BY revenue DESC
    """)
    for p in products:
        print(f"Prod #{p['id']:2} | {p['title']:30} | Lang: {p['language']} | {p['gender']:6} | Level: {p['level']:12} | Price: {float(p['price']):>6.2f} | Sales: {p['sales_count']:>4} | Rev: {float(p['revenue']):>10,.2f} ETB")

    # 8. Payout History (Distribution between Coach and Dagmawi)
    print("\n=================== PAYOUT & PROFIT LEDGER ===================")
    payouts = await conn.fetch("SELECT * FROM payout_history ORDER BY payout_date ASC")
    print(f"Payout History Records: {len(payouts)}")
    for py in payouts:
        print(f"  Payout ID: {py['id']} | Date: {py['payout_date']} | Gross: {py['gross_revenue']} | Net: {py['net_profit']} | Coach: {py['coach_share']} | Dagmawi: {py['dagmawi_share']} | Note: {py.get('expense_note', '')}")

    # 9. Meal Plan System Tables (if any exist)
    meal_tables = [t for t in table_counts.keys() if 'meal' in t or 'fasting' in t or 'nutrition' in t or 'diet' in t]
    if meal_tables:
        print("\n=================== MEAL PLAN & NUTRITION TABLES ===================")
        for mt in meal_tables:
            print(f"  {mt}: {table_counts[mt]} rows")
            sample = await conn.fetch(f'SELECT * FROM "{mt}" LIMIT 3')
            if sample:
                cols = list(sample[0].keys())
                print(f"    Columns: {cols}")

    # 10. Broadcasts & Surveys & Testimonials
    print("\n=================== ENGAGEMENT / LOGS ===================")
    if 'broadcasts' in table_counts:
        bc_cnt = table_counts['broadcasts']
        latest_bc = await conn.fetch("SELECT id, name, total_target, sent_count, failed_count, started_at FROM broadcasts ORDER BY started_at DESC LIMIT 5")
        print(f"Broadcasts count: {bc_cnt}")
        for b in latest_bc:
            print(f"  Broadcast: {b['name']} | Target: {b['total_target']} | Sent: {b['sent_count']} | Failed: {b['failed_count']} | At: {b['started_at']}")

    if 'club_checkins' in table_counts:
        ci_cnt = table_counts['club_checkins']
        unique_checkin_users = await conn.fetchval("SELECT count(DISTINCT user_id) FROM club_checkins")
        print(f"Total Club Checkins: {ci_cnt} across {unique_checkin_users} unique users")

    if 'price_survey_results' in table_counts:
        price_surveys = await conn.fetch("SELECT selected_price, count(*) as c FROM price_survey_results GROUP BY selected_price ORDER BY c DESC")
        print("Price Survey Votes:", [dict(r) for r in price_surveys])

    if 'club_survey_results' in table_counts:
        club_surveys = await conn.fetch("SELECT will_join, count(*) as c FROM club_survey_results GROUP BY will_join")
        print("Club Survey Votes:", [dict(r) for r in club_surveys])

    if 'user_testimonials' in table_counts:
        test_cnt = table_counts['user_testimonials']
        print(f"User Testimonials: {test_cnt}")

    await conn.close()
    print("\nAudit completed successfully.")

if __name__ == '__main__':
    asyncio.run(run_audit())
