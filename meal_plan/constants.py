"""Locked product constants for the Coach Hilawe meal-plan product.

Do not put prices, secrets, Telegram IDs, or deployment URLs in this module.
Prices will become database/config data in a later phase.
"""

from enum import StrEnum

DEFAULT_LANGUAGE = "AM"
LANGUAGES: tuple[str, ...] = ("AM", "EN")

PRICING_REGIONS: tuple[str, ...] = (
    "ETHIOPIA",
    "UNITED_STATES",
    "EUROPE",
    "UAE",
    "OTHER",
)

PLAN_DURATIONS_DAYS: tuple[int, ...] = (7, 14, 30)
MEAL_COUNTS: tuple[int, ...] = (3, 4, 5)


class ServiceType(StrEnum):
    PLAN = "PLAN"
    FOLLOW_UP = "FOLLOW_UP"


def service_type_allowed(duration_days: int, service_type: ServiceType | str) -> bool:
    """Return whether a service type is valid for the chosen duration.

    The Follow-Up service is intentionally a 30-day-only product.
    """
    normalized = ServiceType(service_type)
    if normalized is ServiceType.FOLLOW_UP:
        return duration_days == 30
    return duration_days in PLAN_DURATIONS_DAYS
