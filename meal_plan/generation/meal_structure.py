from __future__ import annotations

from meal_plan.generation.models import SlotSpec


# Four-meal shares/caps are source v1.3 values. Three- and five-meal shares are
# a Phase 6 implementation extension, intentionally data-shaped and easy to change.
STRUCTURES: dict[int, tuple[SlotSpec, ...]] = {
    3: (
        SlotSpec("Breakfast", "Breakfast", 0.30, 0.36, 800),
        SlotSpec("Lunch", "Lunch", 0.35, 0.39, 950),
        SlotSpec("Dinner", "Dinner", 0.35, 0.39, 950),
    ),
    4: (
        SlotSpec("Breakfast", "Breakfast", 0.25, 0.32, 700),
        SlotSpec("Lunch", "Lunch", 0.30, 0.35, 900),
        SlotSpec("Dinner", "Dinner", 0.30, 0.35, 900),
        SlotSpec("Snack", "Snack", 0.15, 0.20, 450),
    ),
    5: (
        SlotSpec("Breakfast", "Breakfast", 0.22, 0.29, 650),
        SlotSpec("Snack 1", "Snack", 0.10, 0.15, 350),
        SlotSpec("Lunch", "Lunch", 0.28, 0.33, 850),
        SlotSpec("Snack 2", "Snack", 0.10, 0.15, 350),
        SlotSpec("Dinner", "Dinner", 0.30, 0.35, 900),
    ),
}


def meal_structure(meals_per_day: int) -> tuple[SlotSpec, ...]:
    try:
        return STRUCTURES[int(meals_per_day)]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Meal engine supports exactly 3, 4, or 5 meals per day") from exc
