"""Check that the Phase 1 meal-plan tables exist in the configured PostgreSQL DB."""

from __future__ import annotations

import asyncio
import os

from meal_plan.schema import REQUIRED_TABLES


async def main() -> int:
    dsn = os.getenv("DATABASE_URL", "")
    if not dsn:
        print("DATABASE_URL is not set")
        return 2
    try:
        import asyncpg
    except ImportError:
        print("asyncpg is not installed in this environment")
        return 2

    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            """
            SELECT tablename
            FROM pg_catalog.pg_tables
            WHERE schemaname = current_schema()
              AND tablename = ANY($1::text[])
            """,
            list(REQUIRED_TABLES),
        )
        existing = {row["tablename"] for row in rows}
        missing = [name for name in REQUIRED_TABLES if name not in existing]
        if missing:
            print("Missing meal-plan tables:")
            for name in missing:
                print(f"  - {name}")
            return 1
        print(f"Phase 1 schema ready: {len(REQUIRED_TABLES)} required tables found")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
