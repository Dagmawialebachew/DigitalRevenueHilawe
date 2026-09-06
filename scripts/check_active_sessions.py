import asyncio
import os
import sys
from dotenv import load_dotenv
import asyncpg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

async def main():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"), statement_cache_size=0)
    rows = await conn.fetch("""
        SELECT pid, state, query, age(clock_timestamp(), query_start) as duration, wait_event_type, wait_event
        FROM pg_stat_activity
        WHERE pid <> pg_backend_pid()
        ORDER BY duration DESC
    """)
    print(f"Total active/idle sessions: {len(rows)}")
    for r in rows:
        print(f"PID: {r['pid']} | State: {r['state']} | Wait: {r['wait_event_type']}:{r['wait_event']} | Duration: {r['duration']} | Query: {r['query'][:120] if r['query'] else 'None'}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
