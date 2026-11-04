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

async def main():
    db = Database(settings.DATABASE_URL)
    await db.connect()

    rows = await db.fetch("""
        SELECT conname, pg_get_constraintdef(oid) as def
        FROM pg_constraint
        WHERE conrelid = 'meal_generation_jobs'::regclass;
    """)
    for r in rows:
        print(f"Constraint: {r['conname']}\n  Def: {r['def']}\n")

if __name__ == "__main__":
    asyncio.run(main())

