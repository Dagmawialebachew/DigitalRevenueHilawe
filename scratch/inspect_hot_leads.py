import asyncio
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from database.db import Database

async def inspect():
    db = Database(settings.DATABASE_URL)
    await db.connect()

    rows = await db.fetch("""
        SELECT u.telegram_id, u.full_name, u.username, u.language, u.gender, 
               u.level, u.frequency, u.goal, u.obstacle, u.created_at,
               p.id as product_id, p.title as product_title, p.price as product_price
        FROM users u
        LEFT JOIN products p ON 
            UPPER(TRIM(u.language)) = UPPER(TRIM(p.language)) AND 
            UPPER(TRIM(u.gender)) = UPPER(TRIM(p.gender)) AND 
            UPPER(REPLACE(TRIM(u.level), ' ', '_')) = UPPER(REPLACE(TRIM(p.level), ' ', '_')) AND 
            u.frequency = p.frequency
        WHERE u.onboarding_completed = TRUE 
          AND (u.has_paid = FALSE OR u.has_paid IS NULL)
          AND u.created_at >= NOW() - INTERVAL '7 days'
        ORDER BY u.created_at DESC;
    """)

    print(f"Total Hot Unpaid Leads (Last 7 Days): {len(rows)}")
    
    genders = Counter(r['gender'] for r in rows)
    langs = Counter(r['language'] for r in rows)
    goals = Counter(r['goal'] for r in rows)
    levels = Counter(r['level'] for r in rows)
    freqs = Counter(r['frequency'] for r in rows)
    obstacles = Counter(r['obstacle'] for r in rows)
    matched_products = sum(1 for r in rows if r['product_id'] is not None)

    print("\nGender Breakdown:")
    for g, cnt in genders.items():
        print(f"  {g}: {cnt} ({cnt/len(rows)*100:.1f}%)")

    print("\nLanguage Breakdown:")
    for l, cnt in langs.items():
        print(f"  {l}: {cnt} ({cnt/len(rows)*100:.1f}%)")

    print("\nGoal Breakdown:")
    for g, cnt in goals.most_common():
        print(f"  {g}: {cnt} ({cnt/len(rows)*100:.1f}%)")

    print("\nLevel Breakdown:")
    for lvl, cnt in levels.most_common():
        print(f"  {lvl}: {cnt} ({cnt/len(rows)*100:.1f}%)")

    print("\nFrequency Breakdown:")
    for f, cnt in freqs.most_common():
        print(f"  {f} days/week: {cnt} ({cnt/len(rows)*100:.1f}%)")

    print("\nObstacle Breakdown:")
    for obs, cnt in obstacles.most_common():
        print(f"  {obs}: {cnt} ({cnt/len(rows)*100:.1f}%)")

    print(f"\nMatched Products: {matched_products} / {len(rows)} ({(matched_products/len(rows)*100):.1f}%)")

    print("\n--- Sample 3 Female Leads ---")
    female_samples = [r for r in rows if (r['gender'] or '').upper() == 'FEMALE'][:3]
    for r in female_samples:
        print(dict(r))

    print("\n--- Sample 3 Male Leads ---")
    male_samples = [r for r in rows if (r['gender'] or '').upper() == 'MALE'][:3]
    for r in male_samples:
        print(dict(r))

if __name__ == "__main__":
    asyncio.run(inspect())

