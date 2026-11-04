import asyncio
import os
import sys
import json
from datetime import datetime, timezone
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from database.db import Database

async def analyze():
    db = Database(settings.DATABASE_URL)
    await db.connect()

    print("==================================================")
    print("1. MAIN BOT ONBOARDING ANALYSIS (`users` table)")
    print("==================================================")

    # Total counts
    total_users = await db.fetchval("SELECT COUNT(*) FROM users;")
    completed_users = await db.fetchval("SELECT COUNT(*) FROM users WHERE onboarding_completed = TRUE;")
    incomplete_users = await db.fetchval("SELECT COUNT(*) FROM users WHERE onboarding_completed = FALSE OR onboarding_completed IS NULL;")

    print(f"Total Users: {total_users}")
    print(f"Completed Onboarding: {completed_users} ({completed_users/total_users*100:.2f}%)")
    print(f"Incomplete Onboarding: {incomplete_users} ({incomplete_users/total_users*100:.2f}%)")

    # Incomplete users breakdown
    # Where did they drop off?
    # Step 1: Language selected, but no gender selected (Dropped off at Gender step)
    # Step 2: Gender selected, but no goal selected (Dropped off at Goal step)
    # Step 3: Goal selected, but no level selected (Dropped off at Level step)
    # Step 4: Level selected, but no obstacle selected (Dropped off at Obstacle step)
    # Step 5: Obstacle selected, but no frequency selected (Dropped off at Frequency step)
    # Step 6: Frequency selected, but onboarding_completed is FALSE (Edge case/interrupted before flag set)
    # Step 0: Language not even set or default?
    
    rows = await db.fetch("""
        SELECT telegram_id, full_name, username, language, gender, level, frequency, 
               goal, obstacle, onboarding_completed, created_at, reminded, has_paid,
               claimed_new_year_2019, deal_expires_at, deal_price
        FROM users
        WHERE onboarding_completed = FALSE OR onboarding_completed IS NULL
        ORDER BY created_at DESC;
    """)

    dropoff_stages = {
        "1_Welcome / Language (No Gender)": 0,
        "2_Gender selected (No Goal)": 0,
        "3_Goal selected (No Level)": 0,
        "4_Level selected (No Obstacle)": 0,
        "5_Obstacle selected (No Frequency)": 0,
        "6_All answered but flag False": 0,
    }

    lang_counts = Counter()
    has_username_count = 0
    claimed_gift_count = 0
    reminded_count = 0
    has_paid_count = 0
    date_cohorts = Counter()

    for r in rows:
        lang = r["language"] or "UNKNOWN"
        gender = r["gender"]
        goal = r["goal"]
        lvl = r["level"]
        obstacle = r["obstacle"]
        freq = r["frequency"]
        username = r["username"]
        claimed = r["claimed_new_year_2019"]
        reminded = r["reminded"]
        has_paid = r["has_paid"]
        created = r["created_at"]

        lang_counts[lang] += 1
        if username:
            has_username_count += 1
        if claimed:
            claimed_gift_count += 1
        if reminded:
            reminded_count += 1
        if has_paid:
            has_paid_count += 1

        if created:
            month_key = created.strftime("%Y-%m")
            date_cohorts[month_key] += 1
        else:
            date_cohorts["Unknown"] += 1

        if gender is None:
            dropoff_stages["1_Welcome / Language (No Gender)"] += 1
        elif goal is None:
            dropoff_stages["2_Gender selected (No Goal)"] += 1
        elif lvl is None:
            dropoff_stages["3_Goal selected (No Level)"] += 1
        elif obstacle is None:
            dropoff_stages["4_Level selected (No Obstacle)"] += 1
        elif freq is None:
            dropoff_stages["5_Obstacle selected (No Frequency)"] += 1
        else:
            dropoff_stages["6_All answered but flag False"] += 1

    print("\n--- Incomplete Users Drop-off Stage Breakdown ---")
    for stage, count in dropoff_stages.items():
        pct = (count / incomplete_users * 100) if incomplete_users else 0
        print(f"  {stage}: {count} users ({pct:.2f}%)")

    print("\n--- Language Distribution among Incomplete Users ---")
    for l, count in lang_counts.most_common():
        pct = (count / incomplete_users * 100) if incomplete_users else 0
        print(f"  {l}: {count} ({pct:.2f}%)")

    print(f"\nUsers with Telegram Username: {has_username_count} ({has_username_count/incomplete_users*100:.2f}%)")
    print(f"Users who claimed New Year 2019 Gift: {claimed_gift_count} ({claimed_gift_count/incomplete_users*100:.2f}%)")
    print(f"Users flagged as Reminded: {reminded_count} ({reminded_count/incomplete_users*100:.2f}%)")
    print(f"Users with has_paid=True: {has_paid_count}")

    print("\n--- Drop-offs by Month Cohort ---")
    for cohort in sorted(date_cohorts.keys()):
        print(f"  {cohort}: {date_cohorts[cohort]} users")

    # Check recent dropoffs (last 7 days, 14 days, 30 days)
    now = datetime.now(timezone.utc)
    last_7d = sum(1 for r in rows if r["created_at"] and (now - r["created_at"]).days <= 7)
    last_14d = sum(1 for r in rows if r["created_at"] and (now - r["created_at"]).days <= 14)
    last_30d = sum(1 for r in rows if r["created_at"] and (now - r["created_at"]).days <= 30)
    older = incomplete_users - last_30d
    print(f"\n--- Recency Breakdown ---")
    print(f"  Last 7 days: {last_7d} ({last_7d/incomplete_users*100:.2f}%)")
    print(f"  Last 14 days: {last_14d} ({last_14d/incomplete_users*100:.2f}%)")
    print(f"  Last 30 days: {last_30d} ({last_30d/incomplete_users*100:.2f}%)")
    print(f"  Older than 30 days: {older} ({older/incomplete_users*100:.2f}%)")

    # Sample incomplete users
    print("\n--- Sample 5 Most Recent Incomplete Users ---")
    for r in rows[:5]:
        print(f"  ID: {r['telegram_id']}, Name: {r['full_name']}, @{r['username']}, Lang: {r['language']}, Gender: {r['gender']}, Goal: {r['goal']}, Created: {r['created_at']}")


    print("\n==================================================")
    print("2. MEAL PLAN INTAKE ANALYSIS (`meal_intakes` table)")
    print("==================================================")
    intakes = await db.fetch("""
        SELECT id, user_id, language, country_region, state, current_step,
               completed_at, created_at, updated_at
        FROM meal_intakes
        ORDER BY created_at DESC;
    """)
    total_intakes = len(intakes)
    completed_intakes = sum(1 for i in intakes if i["completed_at"] is not None)
    incomplete_intakes = total_intakes - completed_intakes

    print(f"Total Meal Plan Intakes Started: {total_intakes}")
    print(f"Completed Intakes: {completed_intakes} ({completed_intakes/total_intakes*100:.2f}%)")
    print(f"Incomplete/Abandoned Intakes: {incomplete_intakes} ({incomplete_intakes/total_intakes*100:.2f}%)")

    intake_steps = Counter()
    intake_states = Counter()
    intake_langs = Counter()
    intake_regions = Counter()

    for i in intakes:
        if i["completed_at"] is None:
            intake_steps[i["current_step"] or "None / Start"] += 1
            intake_states[i["state"] or "None"] += 1
            intake_langs[i["language"] or "Unknown"] += 1
            intake_regions[i["country_region"] or "Unknown"] += 1

    print("\n--- Drop-off Step in Meal Plan Intakes ---")
    for step, cnt in intake_steps.most_common():
        pct = (cnt / incomplete_intakes * 100) if incomplete_intakes else 0
        print(f"  Step '{step}': {cnt} ({pct:.2f}%)")

    print("\n--- State Distribution of Incomplete Intakes ---")
    for st, cnt in intake_states.most_common():
        print(f"  State '{st}': {cnt}")

    print("\n--- Region Distribution of Incomplete Intakes ---")
    for reg, cnt in intake_regions.most_common():
        print(f"  Region '{reg}': {cnt}")

    # Cross-reference: Did any incomplete users submit payments?
    print("\n==================================================")
    print("3. CROSS-REFERENCE: PAYMENTS & INCOMPLETE USERS")
    print("==================================================")
    incomplete_user_ids = tuple(r["telegram_id"] for r in rows)
    if incomplete_user_ids:
        payments_incomplete = await db.fetch(f"""
            SELECT p.id, p.user_id, p.amount, p.status, p.created_at
            FROM payments p
            WHERE p.user_id IN ({','.join(str(uid) for uid in incomplete_user_ids)})
        """)
        print(f"Product payments by users with incomplete onboarding: {len(payments_incomplete)}")
        for p in payments_incomplete:
            print(f"  Payment ID {p['id']}, User {p['user_id']}, Amount: {p['amount']}, Status: {p['status']}")

        club_payments_incomplete = await db.fetch(f"""
            SELECT cp.id, cp.user_id, cp.amount, cp.status, cp.created_at
            FROM club_payments cp
            WHERE cp.user_id IN ({','.join(str(uid) for uid in incomplete_user_ids)})
        """)
        print(f"Club payments by users with incomplete onboarding: {len(club_payments_incomplete)}")

        meal_payments_incomplete = await db.fetch(f"""
            SELECT mp.id, mp.user_id, mp.amount, mp.status, mp.created_at
            FROM meal_payments mp
            WHERE mp.user_id IN ({','.join(str(uid) for uid in incomplete_user_ids)})
        """)
        print(f"Meal payments by users with incomplete onboarding: {len(meal_payments_incomplete)}")
        for mp in meal_payments_incomplete:
            print(f"  Meal Payment ID {mp['id']}, User {mp['user_id']}, Amount: {mp['amount']}, Status: {mp['status']}")

if __name__ == "__main__":
    asyncio.run(analyze())

