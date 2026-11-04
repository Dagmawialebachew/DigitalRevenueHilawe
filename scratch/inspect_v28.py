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

async def check():
    db = Database(settings.DATABASE_URL)
    await db.connect()

    v = await db.fetchrow("SELECT * FROM meal_plan_versions WHERE id = 28")
    print("--- VERSION 28 ---")
    if v:
        d = dict(v)
        d.pop("plan_json", None)
        print(d)

    arts = await db.fetch("SELECT * FROM meal_plan_artifacts WHERE plan_version_id = 28")
    print("\n--- ARTIFACTS ---")
    for a in arts:
        print(dict(a))

    order = await db.fetchrow("SELECT id, state, current_plan_version_id, updated_at FROM meal_orders WHERE id = 72")
    print("\n--- ORDER 72 ---")
    print(dict(order))

    job = await db.fetchrow("SELECT id, status, stage, attempt_count, updated_at FROM meal_generation_jobs WHERE id = 13")
    print("\n--- JOB 13 ---")
    print(dict(job))

if __name__ == "__main__":
    asyncio.run(check())

