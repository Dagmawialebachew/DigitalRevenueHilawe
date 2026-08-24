"""Phase 4 plan configuration and checkout preparation validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from meal_plan.constants import MEAL_COUNTS, PLAN_DURATIONS_DAYS, ServiceType, service_type_allowed


@dataclass(frozen=True)
class PlanConfiguration:
    meals_per_day: int
    start_date: date
    duration_days: int
    service_type: ServiceType

    @property
    def ends_on(self) -> date:
        return self.start_date + timedelta(days=self.duration_days - 1)


def earliest_start_date(today: date | None = None) -> date:
    return (today or date.today()) + timedelta(days=1)


def parse_plan_configuration(payload: dict[str, Any], *, today: date | None = None) -> PlanConfiguration:
    try:
        meals = int(payload.get("meals_per_day"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Choose 3, 4, or 5 meals per day") from exc
    if meals not in MEAL_COUNTS:
        raise ValueError("Choose 3, 4, or 5 meals per day")

    try:
        duration = int(payload.get("duration_days"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Choose a 7, 14, or 30 day plan") from exc
    if duration not in PLAN_DURATIONS_DAYS:
        raise ValueError("Choose a 7, 14, or 30 day plan")

    try:
        service = ServiceType(str(payload.get("service_type") or "PLAN").upper())
    except ValueError as exc:
        raise ValueError("Unsupported meal-plan service type") from exc
    if not service_type_allowed(duration, service):
        raise ValueError("Meal Plan + Follow-Up is available only for the 30-day plan")

    raw_date = str(payload.get("start_date") or "").strip()
    try:
        start = date.fromisoformat(raw_date)
    except ValueError as exc:
        raise ValueError("Choose a valid plan start date") from exc
    if start < earliest_start_date(today):
        raise ValueError("The earliest plan start date is tomorrow")

    return PlanConfiguration(
        meals_per_day=meals,
        start_date=start,
        duration_days=duration,
        service_type=service,
    )
