from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any


@dataclass(frozen=True)
class MacroTotals:
    kcal: float = 0.0
    protein: float = 0.0
    carbs: float = 0.0
    fat: float = 0.0
    fibre: float = 0.0

    def plus(self, other: "MacroTotals") -> "MacroTotals":
        return MacroTotals(
            self.kcal + other.kcal,
            self.protein + other.protein,
            self.carbs + other.carbs,
            self.fat + other.fat,
            self.fibre + other.fibre,
        )

    def scale(self, factor: float) -> "MacroTotals":
        return MacroTotals(
            self.kcal * factor,
            self.protein * factor,
            self.carbs * factor,
            self.fat * factor,
            self.fibre * factor,
        )

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class SlotSpec:
    label: str
    source_slot: str
    target_share: float
    kcal_cap_fraction: float
    mass_cap_g: float


@dataclass
class MealItem:
    food_id: str
    food_name: str
    grams: float
    source: str
    familiar: str
    exchange_group: str | None = None
    recipe_id: str | None = None
    recipe_name: str | None = None
    prepared_grams: float | None = None
    macros: MacroTotals = field(default_factory=MacroTotals)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["macros"] = self.macros.to_dict()
        return data


@dataclass
class GeneratedMeal:
    slot: str
    source_slot: str
    template_id: str
    meal_name: str
    fasting: bool
    items: list[MealItem]
    macros: MacroTotals
    exchange_options: list[dict[str, Any]]
    warnings: list[str]
    recipe_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot": self.slot,
            "source_slot": self.source_slot,
            "template_id": self.template_id,
            "meal_name": self.meal_name,
            "fasting": self.fasting,
            "items": [x.to_dict() for x in self.items],
            "macros": self.macros.to_dict(),
            "exchange_options": self.exchange_options,
            "warnings": list(self.warnings),
            "recipe_ids": list(self.recipe_ids),
        }


@dataclass
class GeneratedDay:
    day_index: int
    day_name: str
    date: date
    fasting: bool
    meals: list[GeneratedMeal]
    totals: MacroTotals
    warnings: list[str]
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "day_index": self.day_index,
            "day_name": self.day_name,
            "date": self.date.isoformat(),
            "fasting": self.fasting,
            "meals": [m.to_dict() for m in self.meals],
            "totals": self.totals.to_dict(),
            "warnings": list(self.warnings),
            "status": self.status,
        }
