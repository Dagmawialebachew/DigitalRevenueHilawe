import asyncio
import os
import sys
import csv
from datetime import datetime, timezone
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from database.db import Database

async def analyze_bot_onboarding():
    db = Database(settings.DATABASE_URL)
    await db.connect()

    # 1. Total users
    total = await db.fetchval("SELECT COUNT(*) FROM users;")
    completed = await db.fetchval("SELECT COUNT(*) FROM users WHERE onboarding_completed = TRUE;")
    incomplete = await db.fetchval("SELECT COUNT(*) FROM users WHERE onboarding_completed = FALSE OR onboarding_completed IS NULL;")

    print(f"Total Users in Bot: {total}")
    print(f"Completed Workout Onboarding: {completed} ({completed/total*100:.2f}%)")
    print(f"Incomplete Workout Onboarding: {incomplete} ({incomplete/total*100:.2f}%)")

    # 2. Check if ANY user has partial fields (gender, level, etc.) with onboarding_completed = False
    partial_checks = await db.fetchrow("""
        SELECT 
            COUNT(*) FILTER (WHERE gender IS NOT NULL) as has_gender,
            COUNT(*) FILTER (WHERE goal IS NOT NULL) as has_goal,
            COUNT(*) FILTER (WHERE level IS NOT NULL) as has_level,
            COUNT(*) FILTER (WHERE frequency IS NOT NULL) as has_frequency,
            COUNT(*) FILTER (WHERE obstacle IS NOT NULL) as has_obstacle,
            COUNT(*) FILTER (WHERE matched_product_id IS NOT NULL) as has_product,
            COUNT(*) FILTER (WHERE deal_price IS NOT NULL) as has_deal,
            COUNT(*) FILTER (WHERE last_broadcast_msg_id IS NOT NULL) as has_broadcast,
            COUNT(*) FILTER (WHERE claimed_new_year_2019 = TRUE) as claimed_gift,
            COUNT(*) FILTER (WHERE reminded = TRUE) as reminded_count,
            COUNT(*) FILTER (WHERE has_paid = TRUE) as paid_count,
            COUNT(*) FILTER (WHERE username IS NOT NULL AND username != '') as with_username,
            COUNT(*) FILTER (WHERE full_name IS NOT NULL AND full_name != '') as with_fullname
        FROM users
        WHERE onboarding_completed = FALSE OR onboarding_completed IS NULL;
    """)

    print("\n--- Field Presence in Incomplete Users (439) ---")
    for k, v in dict(partial_checks).items():
        print(f"  {k}: {v} ({v/incomplete*100:.2f}%)")

    # 3. All incomplete user records
    rows = await db.fetch("""
        SELECT telegram_id, full_name, username, language, gender, level, frequency,
               goal, obstacle, created_at, claimed_new_year_2019, deal_price, deal_expires_at,
               last_broadcast_msg_id
        FROM users
        WHERE onboarding_completed = FALSE OR onboarding_completed IS NULL
        ORDER BY created_at DESC;
    """)

    # 4. Language breakdown
    lang_counts = Counter(r["language"] or "NOT_SET" for r in rows)
    print("\n--- Language Distribution ---")
    for l, c in lang_counts.most_common():
        print(f"  {l}: {c} ({c/incomplete*100:.2f}%)")

    # 5. Cohort Analysis (by month)
    monthly_cohorts = Counter()
    for r in rows:
        ca = r["created_at"]
        if ca:
            monthly_cohorts[ca.strftime("%Y-%m")] += 1
        else:
            monthly_cohorts["Unknown"] += 1

    print("\n--- Incomplete Users by Month ---")
    for m in sorted(monthly_cohorts.keys()):
        print(f"  {m}: {monthly_cohorts[m]} users")

    # 6. Recency buckets
    now = datetime.now(timezone.utc)
    b_7d = sum(1 for r in rows if r["created_at"] and (now - r["created_at"]).days <= 7)
    b_14d = sum(1 for r in rows if r["created_at"] and (now - r["created_at"]).days <= 14)
    b_30d = sum(1 for r in rows if r["created_at"] and (now - r["created_at"]).days <= 30)
    b_60d = sum(1 for r in rows if r["created_at"] and (now - r["created_at"]).days <= 60)
    b_90d = sum(1 for r in rows if r["created_at"] and (now - r["created_at"]).days <= 90)
    older = incomplete - b_90d

    print("\n--- Recency Buckets ---")
    print(f"  Last 7 Days (Hot / Ready for Re-engagement): {b_7d} ({b_7d/incomplete*100:.2f}%)")
    print(f"  8 - 14 Days: {b_14d - b_7d} ({(b_14d - b_7d)/incomplete*100:.2f}%)")
    print(f"  15 - 30 Days: {b_30d - b_14d} ({(b_30d - b_14d)/incomplete*100:.2f}%)")
    print(f"  31 - 60 Days: {b_60d - b_30d} ({(b_60d - b_30d)/incomplete*100:.2f}%)")
    print(f"  61 - 90 Days: {b_90d - b_60d} ({(b_90d - b_60d)/incomplete*100:.2f}%)")
    print(f"  Older than 90 Days: {older} ({older/incomplete*100:.2f}%)")

    # 7. Check if any of these users interacted with workouts or products
    # e.g. Did they click any product buttons or have any broadcast interactions?
    broadcast_reached = sum(1 for r in rows if r["last_broadcast_msg_id"] is not None)
    deal_assigned = sum(1 for r in rows if r["deal_price"] is not None)
    print(f"\nBroadcast Reached: {broadcast_reached} users")
    print(f"Special Deal Assigned: {deal_assigned} users")

    # 8. Check total bot completion rate by month to see if drop-off rate is getting better or worse
    monthly_total = await db.fetch("""
        SELECT 
            TO_CHAR(created_at, 'YYYY-MM') as month,
            COUNT(*) as total_users,
            COUNT(*) FILTER (WHERE onboarding_completed = TRUE) as completed_users,
            COUNT(*) FILTER (WHERE onboarding_completed = FALSE OR onboarding_completed IS NULL) as incomplete_users
        FROM users
        WHERE created_at IS NOT NULL
        GROUP BY TO_CHAR(created_at, 'YYYY-MM')
        ORDER BY month ASC;
    """)

    print("\n--- Historical Onboarding Completion Rates by Month ---")
    print(f"{'Month':<10} | {'Total':<8} | {'Completed':<10} | {'Incomplete':<10} | {'Drop-off Rate':<12}")
    print("-" * 58)
    for m in monthly_total:
        tot = m["total_users"]
        comp = m["completed_users"]
        incomp = m["incomplete_users"]
        rate = (incomp / tot * 100) if tot > 0 else 0
        print(f"{m['month']:<10} | {tot:<8} | {comp:<10} | {incomp:<10} | {rate:>10.2f}%")

    # 9. Export all incomplete users to CSV for easy inspection / re-engagement
    csv_path = os.path.join(os.path.dirname(__file__), "incomplete_workout_onboarding_users.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "telegram_id", "full_name", "username", "language", "claimed_new_year_gift",
            "created_at", "last_broadcast_msg_id", "deal_price"
        ])
        for r in rows:
            writer.writerow([
                r["telegram_id"],
                r["full_name"] or "",
                f"@{r['username']}" if r["username"] else "",
                r["language"] or "",
                "YES" if r["claimed_new_year_2019"] else "NO",
                r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else "",
                r["last_broadcast_msg_id"] or "",
                r["deal_price"] or ""
            ])
    print(f"\nExported {len(rows)} incomplete users to: {csv_path}")

    # Top 10 most recent incomplete users
    print("\n--- Top 10 Most Recent Drop-Offs ---")
    for r in rows[:10]:
        u_str = f"@{r['username']}" if r['username'] else "No @username"
        ca_str = r['created_at'].strftime("%Y-%m-%d %H:%M") if r['created_at'] else "N/A"
        print(f"  • ID: {r['telegram_id']} | {u_str} | Lang: {r['language']} | Gift: {'Yes' if r['claimed_new_year_2019'] else 'No'} | Joined: {ca_str}")

if __name__ == "__main__":
    asyncio.run(analyze_bot_onboarding())

