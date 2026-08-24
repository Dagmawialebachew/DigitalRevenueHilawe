"""Create a schema-only JSON snapshot from the live PostgreSQL database.

This script does not query user rows, payment rows, or business data. It only
reads PostgreSQL metadata (tables, columns, indexes, and constraints).

Usage:
    python scripts/inspect_runtime_schema.py
    python scripts/inspect_runtime_schema.py --output runtime_schema_snapshot.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv


async def collect_schema(dsn: str) -> dict:
    if not dsn:
        raise RuntimeError("DATABASE_URL is not configured")

    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        tables = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
        columns = await conn.fetch(
            """
            SELECT table_name, column_name, data_type, udt_name, is_nullable,
                   column_default, ordinal_position
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
            """
        )
        indexes = await conn.fetch(
            """
            SELECT tablename, indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
            """
        )
        constraints = await conn.fetch(
            """
            SELECT tc.table_name, tc.constraint_name, tc.constraint_type,
                   kcu.column_name,
                   ccu.table_name AS foreign_table_name,
                   ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints tc
            LEFT JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            LEFT JOIN information_schema.constraint_column_usage ccu
              ON tc.constraint_name = ccu.constraint_name
             AND tc.table_schema = ccu.table_schema
            WHERE tc.table_schema = 'public'
            ORDER BY tc.table_name, tc.constraint_name, kcu.ordinal_position
            """
        )

        return {
            "note": "Schema metadata only; no table rows were exported.",
            "tables": [row["table_name"] for row in tables],
            "columns": [dict(row) for row in columns],
            "indexes": [dict(row) for row in indexes],
            "constraints": [dict(row) for row in constraints],
        }
    finally:
        await conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export PostgreSQL schema metadata only")
    parser.add_argument("--output", default="runtime_schema_snapshot.json")
    return parser.parse_args()


async def main() -> None:
    load_dotenv()
    args = parse_args()
    snapshot = await collect_schema(os.getenv("DATABASE_URL", ""))
    path = Path(args.output)
    path.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
    print(f"Wrote schema-only snapshot to: {path.resolve()}")
    print(f"Tables found: {len(snapshot['tables'])}")


if __name__ == "__main__":
    asyncio.run(main())
