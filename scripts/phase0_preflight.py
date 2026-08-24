"""Non-destructive Phase 0 preflight checks.

The script never prints secret values. It checks only whether expected settings
are present and whether the meal-plan feature is still safely disabled.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


REQUIRED_EXISTING = (
    "BOT_TOKEN",
    "DATABASE_URL",
    "WEBHOOK_BASE_URL",
    "VERIFY_API",
)

MEAL_PLAN_KEYS = (
    "MEAL_PLAN_ENABLED",
    "MEAL_PLAN_FRONTEND_URL",
    "MEAL_PLAN_REVIEW_GROUP_ID",
    "MEAL_PLAN_STORAGE_DIR",
)


def _present(key: str) -> bool:
    return bool(os.getenv(key, "").strip())


def main() -> int:
    load_dotenv()
    print("Coach Hilawe Core — Phase 0 preflight")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Repo:   {Path.cwd()}")
    print()

    missing = []
    for key in REQUIRED_EXISTING:
        ok = _present(key)
        print(f"{'OK' if ok else 'MISSING':7} {key}")
        if not ok:
            missing.append(key)

    print()
    for key in MEAL_PLAN_KEYS:
        value = os.getenv(key, "")
        if key == "MEAL_PLAN_ENABLED":
            normalized = value.strip().lower() if value else "false (default)"
            print(f"INFO    {key}={normalized}")
        else:
            print(f"INFO    {key}: {'configured' if value.strip() else 'not configured yet'}")

    enabled = os.getenv("MEAL_PLAN_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }
    if enabled:
        print("\nWARNING: MEAL_PLAN_ENABLED is true during Phase 0. Set it to false.")
        return 2

    if missing:
        print("\nPreflight found missing existing production variables. No secrets were printed.")
        return 1

    print("\nPASS: Phase 0 configuration is safe; meal-plan feature remains disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
