"""Local/demo pricing utility for Phase 4.

Examples (run from repository root with DATABASE_URL configured):

  python scripts/meal_plan_pricing.py list
  python scripts/meal_plan_pricing.py set ETHIOPIA 7 PLAN ETB 999
  python scripts/meal_plan_pricing.py set UNITED_STATES 30 FOLLOW_UP USD 49
  python scripts/meal_plan_pricing.py quotes
  python scripts/meal_plan_pricing.py confirm-quote 12 USD 35 --set-by 123456789

This intentionally seeds nothing by itself. The product owner must choose prices.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from typing import Any


async def _open() -> tuple[Any, Any]:
    from database.db import Database
    from database.migrations.runner import apply_migrations
    from meal_plan.repository import MealPlanRepository
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise SystemExit("DATABASE_URL is required. Use your demo/local database, not production, while testing Phase 4.")
    db = Database(dsn)
    await db.connect()
    await apply_migrations(dsn, ROOT / "database" / "migrations")
    return db, MealPlanRepository(db._pool)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coach Hilawe Meal Plan pricing utility")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List active automatic prices")
    setp = sub.add_parser("set", help="Set/replace an automatic price")
    setp.add_argument("region", choices=["ETHIOPIA", "UNITED_STATES", "EUROPE", "UAE"])
    setp.add_argument("duration_days", type=int, choices=[7, 14, 30])
    setp.add_argument("service_type", choices=["PLAN", "FOLLOW_UP"])
    setp.add_argument("currency", choices=["ETB", "USD"])
    setp.add_argument("amount", type=Decimal)
    setp.add_argument("--label", default=None)
    setp.add_argument("--created-by", type=int, default=None)

    sub.add_parser("quotes", help="List pending Other-country manual quotes")
    confirm = sub.add_parser("confirm-quote", help="Confirm a pending Other-country quote")
    confirm.add_argument("quote_id", type=int)
    confirm.add_argument("currency", choices=["ETB", "USD"])
    confirm.add_argument("amount", type=Decimal)
    confirm.add_argument("--set-by", type=int, required=True)
    return parser


async def _run(args: argparse.Namespace) -> None:
    db, repo = await _open()
    try:
        if args.command == "list":
            rows = await db.fetch(
                """
                SELECT id, region, duration_days, service_type, currency, amount, label, effective_from
                FROM meal_pricing WHERE is_active=TRUE
                ORDER BY region, duration_days, service_type, effective_from DESC
                """
            )
            if not rows:
                print("No automatic Meal Plan prices configured yet.")
                return
            for row in rows:
                print(
                    f"#{row['id']} {row['region']:<14} {row['duration_days']:>2}d "
                    f"{row['service_type']:<9} {row['currency']} {row['amount']}"
                    + (f" | {row['label']}" if row['label'] else "")
                )
            return

        if args.command == "set":
            row = await repo.set_price(
                region=args.region,
                duration_days=args.duration_days,
                service_type=args.service_type,
                currency=args.currency,
                amount=args.amount,
                created_by=args.created_by,
                label=args.label,
            )
            print(
                f"Price saved: #{row['id']} {row['region']} {row['duration_days']}d "
                f"{row['service_type']} {row['currency']} {row['amount']}"
            )
            return

        if args.command == "quotes":
            rows = await db.fetch(
                """
                SELECT q.id, q.public_id, q.country_name, q.duration_days, q.service_type,
                       q.status, q.currency, q.amount, q.created_at, i.user_id
                FROM meal_quotes q
                JOIN meal_intakes i ON i.id=q.intake_id
                WHERE q.status='PENDING'
                ORDER BY q.created_at
                """
            )
            if not rows:
                print("No pending manual price quotes.")
                return
            for row in rows:
                print(
                    f"#{row['id']} user={row['user_id']} country={row['country_name']} "
                    f"{row['duration_days']}d {row['service_type']} status={row['status']}"
                )
            return

        if args.command == "confirm-quote":
            row = await repo.confirm_quote(
                args.quote_id,
                currency=args.currency,
                amount=args.amount,
                set_by=args.set_by,
            )
            print(f"Quote #{row['id']} confirmed: {row['currency']} {row['amount']}")
            return
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(_run(_parser().parse_args()))
