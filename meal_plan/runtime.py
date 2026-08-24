"""Runtime configuration helpers for the Meal Plan feature.

This module intentionally reads environment variables at runtime so the meal-plan
feature can be enabled on a demo bot without changing the legacy Settings class.
No secrets or prices live here.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def meal_plan_enabled() -> bool:
    return env_bool("MEAL_PLAN_ENABLED", False)


def frontend_url() -> str:
    return os.getenv("MEAL_PLAN_FRONTEND_URL", "").strip().rstrip("/")


def frontend_url_is_valid(url: str | None = None) -> bool:
    candidate = (url if url is not None else frontend_url()).strip()
    if not candidate:
        return False
    parsed = urlparse(candidate)
    # Telegram Mini Apps require HTTPS outside Telegram's dedicated test environment.
    return parsed.scheme == "https" and bool(parsed.netloc)


def init_data_max_age_seconds() -> int:
    raw = os.getenv("MEAL_PLAN_INIT_DATA_MAX_AGE_SECONDS", "3600").strip()
    try:
        value = int(raw)
    except ValueError:
        return 3600
    return max(60, min(value, 86400))


def _env_int_list(name: str) -> tuple[int, ...]:
    values: list[int] = []
    for raw in os.getenv(name, "").split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            values.append(int(raw))
        except ValueError:
            continue
    return tuple(values)


def review_group_id() -> int:
    raw = os.getenv("MEAL_PLAN_REVIEW_GROUP_ID", "0").strip()
    try:
        return int(raw)
    except ValueError:
        return 0


def reviewer_ids() -> tuple[int, ...]:
    explicit = _env_int_list("MEAL_PLAN_REVIEWER_IDS")
    if explicit:
        return explicit
    # Reuse the existing admin list if a dedicated reviewer list is not set.
    return _env_int_list("ADMIN_IDS")


def is_reviewer(telegram_id: int) -> bool:
    return int(telegram_id) in set(reviewer_ids())


def payment_review_chat_id() -> int:
    raw = os.getenv("MEAL_PLAN_PAYMENT_REVIEW_CHAT_ID", "").strip()
    if not raw:
        raw = os.getenv("ADMIN_PAYMENT_LOG_ID", "0").strip()
    try:
        return int(raw)
    except ValueError:
        return 0


def usd_settlement_mode() -> str:
    mode = os.getenv("MEAL_PLAN_USD_SETTLEMENT_MODE", "USD").strip().upper()
    return mode if mode in {"USD", "ETB"} else "USD"


def usd_to_etb_rate():
    from decimal import Decimal, InvalidOperation
    raw = os.getenv("MEAL_PLAN_USD_TO_ETB_RATE", "").strip()
    if not raw:
        return None
    try:
        rate = Decimal(raw)
    except InvalidOperation:
        return None
    return rate if rate > 0 else None


def payment_amount_tolerance():
    from decimal import Decimal, InvalidOperation
    raw = os.getenv("MEAL_PLAN_PAYMENT_AMOUNT_TOLERANCE", "1.00").strip()
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return Decimal("1.00")
    return max(Decimal("0"), value)


def auto_approve_payments() -> bool:
    return env_bool("MEAL_PLAN_AUTO_APPROVE_PAYMENTS", False)


def generation_worker_enabled() -> bool:
    return env_bool("MEAL_PLAN_GENERATION_WORKER_ENABLED", False)


def generation_worker_interval_seconds() -> int:
    raw = os.getenv("MEAL_PLAN_GENERATION_WORKER_INTERVAL_SECONDS", "3").strip()
    try:
        value = int(raw)
    except ValueError:
        return 3
    return max(1, min(value, 60))


def review_upload_max_bytes() -> int:
    raw = os.getenv("MEAL_PLAN_REVIEW_UPLOAD_MAX_MB", "25").strip()
    try:
        mb = int(raw)
    except ValueError:
        mb = 25
    mb = max(1, min(mb, 50))
    return mb * 1024 * 1024


def coach_username() -> str:
    value = os.getenv("MEAL_PLAN_COACH_USERNAME", "").strip()
    if not value:
        return ""
    return value if value.startswith("@") else f"@{value}"


def lifecycle_worker_enabled() -> bool:
    return env_bool("MEAL_PLAN_LIFECYCLE_WORKER_ENABLED", False)


def lifecycle_interval_seconds() -> int:
    raw = os.getenv("MEAL_PLAN_LIFECYCLE_INTERVAL_SECONDS", "60").strip()
    try:
        value = int(raw)
    except ValueError:
        return 60
    return max(15, min(value, 3600))


def business_timezone_name() -> str:
    value = os.getenv("MEAL_PLAN_BUSINESS_TIMEZONE", "Africa/Addis_Ababa").strip()
    return value or "Africa/Addis_Ababa"


def checkin_hour() -> int:
    raw = os.getenv("MEAL_PLAN_CHECKIN_HOUR", "19").strip()
    try:
        value = int(raw)
    except ValueError:
        return 19
    return max(0, min(value, 23))


def checkin_missed_after_hours() -> int:
    raw = os.getenv("MEAL_PLAN_CHECKIN_MISSED_AFTER_HOURS", "72").strip()
    try:
        value = int(raw)
    except ValueError:
        return 72
    return max(24, min(value, 168))


def renewal_lead_days() -> int:
    raw = os.getenv("MEAL_PLAN_RENEWAL_LEAD_DAYS", "3").strip()
    try:
        value = int(raw)
    except ValueError:
        return 3
    return max(1, min(value, 14))


def stale_job_minutes() -> int:
    raw = os.getenv("MEAL_PLAN_STALE_JOB_MINUTES", "30").strip()
    try:
        value = int(raw)
    except ValueError:
        return 30
    return max(10, min(value, 240))


def delivery_retry_limit() -> int:
    raw = os.getenv("MEAL_PLAN_DELIVERY_RETRY_LIMIT", "5").strip()
    try:
        value = int(raw)
    except ValueError:
        return 5
    return max(1, min(value, 25))


def followup_auto_revision_enabled() -> bool:
    return env_bool("MEAL_PLAN_FOLLOWUP_AUTO_REVISION_ENABLED", True)


def demo_mode() -> bool:
    """True only when the explicit local/demo safety flag is enabled."""
    return env_bool("MEAL_PLAN_DEMO_MODE", False)


def demo_bot_id() -> int:
    """Optional Telegram bot id guard used by the local demo runner."""
    raw = os.getenv("MEAL_PLAN_DEMO_BOT_ID", "0").strip()
    try:
        value = int(raw)
    except ValueError:
        return 0
    return value if value > 0 else 0
