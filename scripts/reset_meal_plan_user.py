"""CLI script to reset a user's meal plan state directly from terminal.

Usage:
    python scripts/reset_meal_plan_user.py <telegram_id>
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from database.db import Database
from meal_plan.admin_reset import reset_user_meal_plan_data


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/reset_meal_plan_user.py <telegram_id>")
        sys.exit(1)

    try:
        user_id = int(sys.argv[1])
    except ValueError:
        print(f"Error: Invalid telegram_id '{sys.argv[1]}'. Must be an integer.")
        sys.exit(1)

    print(f"Connecting to database to reset meal plan data for user: {user_id}...")
    db = Database(settings.DATABASE_URL)
    await db.connect()

    counts = await reset_user_meal_plan_data(db._pool, user_id)
    print("Meal Plan Data Reset Results:")
    for key, val in counts.items():
        print(f"  • {key}: {val} records cleared")
    print(f"\nUser {user_id} meal plan state is now completely clean!")


if __name__ == "__main__":
    asyncio.run(main())
