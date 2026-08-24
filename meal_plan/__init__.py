"""Coach Hilawe personalized meal-plan domain.

Phase 0 intentionally exposes no Telegram handlers, HTTP routes, database writes,
or generation jobs. Later phases build on the stable constants and lifecycle names
kept here.
"""

from .constants import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    MEAL_COUNTS,
    PLAN_DURATIONS_DAYS,
    PRICING_REGIONS,
    ServiceType,
)
from .states import MealPlanLifecycle

__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGES",
    "MEAL_COUNTS",
    "PLAN_DURATIONS_DAYS",
    "PRICING_REGIONS",
    "ServiceType",
    "MealPlanLifecycle",
]
