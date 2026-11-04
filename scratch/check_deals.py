import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from database.db import Database

async def run():
    db = Database(settings.DATABASE_URL)
    await db.connect()
    res = await db.fetch("""
        SELECT count(*) FILTER (WHERE deal_expires_at > NOW()) as active_deals,
               count(*) FILTER (WHERE deal_price IS NOT NULL) as deals_set
        FROM users 
        WHERE onboarding_completed = FALSE OR onboarding_completed IS NULL;
    """)
    print(dict(res[0]))

if __name__ == "__main__":
    asyncio.run(run())

