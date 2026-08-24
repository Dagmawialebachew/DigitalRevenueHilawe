"""Bridge from the existing Database wrapper to the isolated MealPlanRepository."""

from __future__ import annotations

from meal_plan.repository import MealPlanRepository


def get_meal_plan_repository(db) -> MealPlanRepository:
    pool = getattr(db, "_pool", None)
    if pool is None:
        raise RuntimeError("Database pool is not connected")
    return MealPlanRepository(pool)
