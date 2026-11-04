import asyncio
import json
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

async def test():
    db = Database(settings.DATABASE_URL)
    await db.connect()
    try:
        await db.execute(
            "UPDATE meal_generation_jobs SET payload = payload || $2::jsonb WHERE id = $1",
            13,
            json.dumps({"test": 123})
        )
        print("COLON-COLON SUCCESS!")
    except Exception as e:
        print("COLON-COLON FAILED:", e)

    try:
        await db.execute(
            "UPDATE meal_generation_jobs SET payload = payload || CAST($2 AS jsonb) WHERE id = $1",
            13,
            json.dumps({"test": 456})
        )
        print("CAST SUCCESS!")
    except Exception as e:
        print("CAST FAILED:", e)

if __name__ == "__main__":
    asyncio.run(test())

