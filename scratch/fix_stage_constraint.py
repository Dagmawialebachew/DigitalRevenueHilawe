import asyncio
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

async def fix():
    db = Database(settings.DATABASE_URL)
    await db.connect()

    print("Dropping existing meal_generation_jobs_stage_check constraint...")
    await db.execute("ALTER TABLE meal_generation_jobs DROP CONSTRAINT IF EXISTS meal_generation_jobs_stage_check;")

    print("Adding updated meal_generation_jobs_stage_check constraint with AI_COACH_REVIEW and FAILED...")
    await db.execute("""
        ALTER TABLE meal_generation_jobs ADD CONSTRAINT meal_generation_jobs_stage_check 
        CHECK (stage IN (
            'QUEUED','TARGETS','FOOD_MATCHING','WEEK_STRUCTURE','PORTION_TUNING','SWAPS',
            'AI_COACH_REVIEW','GROCERIES','DOCUMENTS','REVIEW_HANDOFF','COMPLETE','FAILED'
        ));
    """)
    print("Check constraint successfully updated!")

    # Verify constraint definition
    row = await db.fetchrow("""
        SELECT conname, pg_get_constraintdef(oid) as def
        FROM pg_constraint
        WHERE conrelid = 'meal_generation_jobs'::regclass AND conname = 'meal_generation_jobs_stage_check';
    """)
    print(f"Verified: {row['conname']} -> {row['def']}")

if __name__ == "__main__":
    asyncio.run(fix())

