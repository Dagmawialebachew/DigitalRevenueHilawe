"""Small asyncpg migration runner for Coach Hilawe Core.

The existing application still runs `SCHEMA_SQL` during startup. This runner is
introduced in Phase 0 but is NOT called automatically. Phase 1 will add the first
meal-plan migration and define the deployment runbook.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

MIGRATION_RE = re.compile(r"^(?P<version>\d{4})_(?P<name>[a-z0-9_]+)\.sql$")


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    path: Path
    checksum: str
    sql: str


def discover_migrations(directory: Path) -> list[Migration]:
    migrations: list[Migration] = []
    if not directory.exists():
        return migrations

    for path in sorted(directory.glob("*.sql")):
        match = MIGRATION_RE.match(path.name)
        if not match:
            continue
        sql = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        migrations.append(
            Migration(
                version=match.group("version"),
                name=match.group("name"),
                path=path,
                checksum=checksum,
                sql=sql,
            )
        )

    versions = [m.version for m in migrations]
    if len(versions) != len(set(versions)):
        raise RuntimeError("Duplicate migration version detected")
    return migrations


async def apply_migrations(dsn: str, directory: Path, *, dry_run: bool = False) -> list[str]:
    """Apply pending migrations and return the versions that would/did run."""
    migrations = discover_migrations(directory)
    if dry_run:
        return [m.version for m in migrations]

    if not dsn:
        raise RuntimeError("DATABASE_URL is required to apply migrations")

    import asyncpg  # imported lazily so discovery/tests do not require a live DB

    conn = await asyncpg.connect(dsn)
    applied_now: list[str] = []
    try:
        # Serialize migration runners across Render instances/deploys.
        await conn.execute("SELECT pg_advisory_lock(731946205)")
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(4) PRIMARY KEY,
                name TEXT NOT NULL,
                checksum CHAR(64) NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )

        rows = await conn.fetch("SELECT version, checksum FROM schema_migrations")
        applied = {row["version"]: row["checksum"] for row in rows}

        for migration in migrations:
            old_checksum = applied.get(migration.version)
            if old_checksum:
                if old_checksum != migration.checksum:
                    raise RuntimeError(
                        f"Migration {migration.version} was modified after being applied"
                    )
                continue

            async with conn.transaction():
                await conn.execute(migration.sql)
                await conn.execute(
                    """
                    INSERT INTO schema_migrations(version, name, checksum)
                    VALUES($1, $2, $3)
                    """,
                    migration.version,
                    migration.name,
                    migration.checksum,
                )
            applied_now.append(migration.version)
    finally:
        try:
            await conn.execute("SELECT pg_advisory_unlock(731946205)")
        finally:
            await conn.close()

    return applied_now


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply Coach Hilawe SQL migrations")
    parser.add_argument("--dsn", default=None, help="PostgreSQL DSN; defaults to DATABASE_URL")
    parser.add_argument(
        "--directory",
        default=str(Path(__file__).resolve().parent),
        help="Migration directory",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


async def _main() -> None:
    import os

    args = _build_parser().parse_args()
    dsn = args.dsn or os.getenv("DATABASE_URL", "")
    versions = await apply_migrations(dsn, Path(args.directory), dry_run=args.dry_run)
    if args.dry_run:
        print("Discovered migrations:", ", ".join(versions) or "none")
    else:
        print("Applied migrations:", ", ".join(versions) or "none")


if __name__ == "__main__":
    asyncio.run(_main())
