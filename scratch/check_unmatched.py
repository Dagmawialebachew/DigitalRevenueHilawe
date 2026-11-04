import asyncio
import os
import sys
from collections import Counter

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from database.db import Database

async def check_unmatched():
    db = Database(settings.DATABASE_URL)
    await db.connect()

    rows = await db.fetch("""
        SELECT u.telegram_id, u.full_name, u.language, u.gender, u.level, u.frequency, u.goal
        FROM users u
        LEFT JOIN products p ON 
            UPPER(TRIM(u.language)) = UPPER(TRIM(p.language)) AND 
            UPPER(TRIM(u.gender)) = UPPER(TRIM(p.gender)) AND 
            UPPER(REPLACE(TRIM(u.level), ' ', '_')) = UPPER(REPLACE(TRIM(p.level), ' ', '_')) AND 
            u.frequency = p.frequency
        WHERE u.onboarding_completed = TRUE 
          AND (u.has_paid = FALSE OR u.has_paid IS NULL)
          AND u.created_at >= NOW() - INTERVAL '7 days'
          AND p.id IS NULL;
    """)

    print(f"Unmatched users: {len(rows)}")
    level_cnt = Counter(r['level'] for r in rows)
    gender_cnt = Counter(r['gender'] for r in rows)
    freq_cnt = Counter(r['frequency'] for r in rows)
    lang_cnt = Counter(r['language'] for r in rows)
    print("Levels:", level_cnt)
    print("Genders:", gender_cnt)
    print("Frequencies:", freq_cnt)
    print("Languages:", lang_cnt)

    for r in rows[:10]:
        print(f"ID: {r['telegram_id']}, Lang: {r['language']}, Gender: {r['gender']}, Level: {r['level']}, Freq: {r['frequency']}")

if __name__ == "__main__":
    asyncio.run(check_unmatched())
