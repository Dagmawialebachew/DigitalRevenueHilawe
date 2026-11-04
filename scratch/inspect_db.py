import asyncio
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from database.db import Database

async def main():
    db = Database(settings.DATABASE_URL)
    await db.connect()
    
    # 1. Get all table names
    tables = await db.fetch("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    print("Tables in public schema:")
    for t in tables:
        print(f" - {t['table_name']}")

    # 2. Inspect users columns
    columns = await db.fetch("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'users'
        ORDER BY ordinal_position;
    """)
    print("\nUsers table columns:")
    for c in columns:
        print(f" - {c['column_name']} ({c['data_type']}) default={c['column_default']}")

    # 3. Overall user counts
    total_users = await db.fetchval("SELECT COUNT(*) FROM users;")
    completed_users = await db.fetchval("SELECT COUNT(*) FROM users WHERE onboarding_completed = TRUE;")
    incomplete_users = await db.fetchval("SELECT COUNT(*) FROM users WHERE onboarding_completed = FALSE OR onboarding_completed IS NULL;")
    print(f"\nTotal users: {total_users}")
    print(f"Completed onboarding: {completed_users}")
    print(f"Incomplete onboarding: {incomplete_users}")

if __name__ == "__main__":
    asyncio.run(main())
