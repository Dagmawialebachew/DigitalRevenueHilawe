"""Offline Meal Plan release-readiness checks.

This script never prints secret values and never writes to the database. It is
safe to run against a demo or production environment before starting workers.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from meal_plan.runtime import (
    auto_approve_payments,
    business_timezone_name,
    demo_mode,
    frontend_origin,
    frontend_url,
    frontend_url_is_valid,
    generation_worker_enabled,
    guarded_local_dev_mode,
    lifecycle_worker_enabled,
    local_dev_auth_enabled,
    loopback_frontend_url_is_valid,
    meal_plan_enabled,
    review_group_id,
    reviewer_ids,
)


@dataclass(frozen=True)
class Check:
    code: str
    status: str
    message: str


def _present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _artifact_root_check() -> Check:
    root = Path(os.getenv("MEAL_PLAN_ARTIFACT_ROOT", "artifacts/meal_plans")).expanduser()
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".phase9_write_probe"
        probe.write_text("ok", encoding="ascii")
        probe.unlink(missing_ok=True)
    except OSError:
        return Check("ARTIFACT_ROOT", "BLOCK", "Meal-plan artifact root is not writable.")
    return Check("ARTIFACT_ROOT", "PASS", "Local render workspace is writable.")


def _timezone_check() -> Check:
    name = business_timezone_name()
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return Check("TIMEZONE", "BLOCK", "MEAL_PLAN_BUSINESS_TIMEZONE is not a valid IANA timezone.")
    return Check("TIMEZONE", "PASS", f"Business timezone is valid ({name}).")


def collect_checks(mode: str = "demo") -> list[Check]:
    production = mode == "production"
    checks: list[Check] = []

    checks.append(Check(
        "FEATURE_FLAG",
        "PASS" if meal_plan_enabled() else ("BLOCK" if production else "WARN"),
        "Meal Plan feature flag is enabled." if meal_plan_enabled() else "MEAL_PLAN_ENABLED is false.",
    ))
    checks.append(Check(
        "BOT_TOKEN",
        "PASS" if _present("BOT_TOKEN") else "BLOCK",
        "Bot token is configured." if _present("BOT_TOKEN") else "BOT_TOKEN is missing.",
    ))
    checks.append(Check(
        "DATABASE_URL",
        "PASS" if _present("DATABASE_URL") else "BLOCK",
        "Database URL is configured." if _present("DATABASE_URL") else "DATABASE_URL is missing.",
    ))
    if local_dev_auth_enabled() and not demo_mode():
        checks.append(Check(
            "LOCAL_DEV_AUTH_GUARD",
            "BLOCK",
            "MEAL_PLAN_LOCAL_DEV_AUTH requires MEAL_PLAN_DEMO_MODE=true.",
        ))

    if not production and guarded_local_dev_mode():
        local_frontend_ok = (
            loopback_frontend_url_is_valid(frontend_url())
            and loopback_frontend_url_is_valid(frontend_origin())
        )
        checks.append(Check(
            "LOCAL_DEV_FRONTEND",
            "PASS" if local_frontend_ok else "BLOCK",
            "Guarded localhost Mini App frontend enabled."
            if local_frontend_ok
            else "Local dev requires HTTP loopback origins on port 5173 for MEAL_PLAN_FRONTEND_URL and FRONTEND_ORIGIN.",
        ))
    else:
        checks.append(Check(
            "FRONTEND_HTTPS",
            "PASS" if frontend_url_is_valid(frontend_url()) else ("BLOCK" if production else "WARN"),
            "Mini App frontend URL is HTTPS." if frontend_url_is_valid(frontend_url()) else "MEAL_PLAN_FRONTEND_URL is missing or is not HTTPS.",
        ))
    checks.append(Check(
        "REVIEW_GROUP",
        "PASS" if review_group_id() else "BLOCK",
        "Private Coach review group is configured." if review_group_id() else "MEAL_PLAN_REVIEW_GROUP_ID is missing/invalid.",
    ))
    checks.append(Check(
        "REVIEWERS",
        "PASS" if reviewer_ids() else "BLOCK",
        "At least one Coach reviewer is configured." if reviewer_ids() else "MEAL_PLAN_REVIEWER_IDS/ADMIN_IDS contains no valid Telegram IDs.",
    ))
    checks.append(Check(
        "GENERATION_WORKER",
        "PASS" if generation_worker_enabled() else ("BLOCK" if production else "WARN"),
        "Generation worker is enabled." if generation_worker_enabled() else "Generation worker is disabled.",
    ))
    checks.append(Check(
        "LIFECYCLE_WORKER",
        "PASS" if lifecycle_worker_enabled() else ("BLOCK" if production else "WARN"),
        "Lifecycle worker is enabled." if lifecycle_worker_enabled() else "Follow-up/renewal lifecycle worker is disabled.",
    ))
    checks.append(Check(
        "PAYMENT_AUTO_APPROVAL",
        "BLOCK" if production and auto_approve_payments() else "PASS",
        "Automatic payment approval must remain off for initial production rollout."
        if production and auto_approve_payments()
        else "Payment approval mode is acceptable for this readiness check.",
    ))
    checks.append(_timezone_check())
    checks.append(_artifact_root_check())

    # Approved artifacts are archived in Telegram via reusable file_id after the
    # private review upload. Local disk is only a render workspace/recovery cache.
    checks.append(Check(
        "DURABLE_APPROVED_PDF",
        "PASS",
        "Approved PDFs can recover through persisted Telegram file IDs if local disk is lost.",
    ))

    if production:
        checks.append(Check(
            "VERIFY_API_ENV",
            "PASS" if _present("VERIFY_API") else "BLOCK",
            "VERIFY_API is configured in the environment." if _present("VERIFY_API") else "VERIFY_API is not set in environment; do not rely on the legacy source fallback for launch.",
        ))
        checks.append(Check(
            "SEASONAL_FASTING",
            "WARN",
            "Verified annual Orthodox fasting dates must be loaded before serving seasonal-fast customers; engine remains fail-closed otherwise.",
        ))
        checks.append(Check(
            "RECIPE_CALIBRATION",
            "WARN",
            "Coach must approve/calibrate starter recipe rows before broad public rollout.",
        ))

    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline Coach Hilawe Meal Plan readiness checks")
    parser.add_argument("--mode", choices=("demo", "production"), default="demo")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    checks = collect_checks(args.mode)
    blocks = sum(c.status == "BLOCK" for c in checks)
    warnings = sum(c.status == "WARN" for c in checks)

    if args.as_json:
        print(json.dumps({
            "mode": args.mode,
            "ready": blocks == 0,
            "blocks": blocks,
            "warnings": warnings,
            "checks": [asdict(c) for c in checks],
        }, indent=2))
    else:
        print(f"Coach Hilawe Meal Plan readiness - {args.mode.upper()}")
        for check in checks:
            print(f"[{check.status:5}] {check.code}: {check.message}")
        print(f"Summary: {blocks} blocker(s), {warnings} warning(s)")
        print("READY" if blocks == 0 else "NOT READY")

    return 0 if blocks == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
