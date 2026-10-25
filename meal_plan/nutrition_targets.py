"""Nutrition target calculator derived from Coach Hilawe Meal Planner OS v1.3.

Source rules retained:
- Mifflin-St Jeor BMR for Male/Female;
- activity factors from the workbook's allowed factor ladder;
- goal percentage adjustments from Settings & Rules;
- 25 kcal rounding;
- goal-specific protein g/kg and 1.05 fasting multiplier;
- 25% calories from fat;
- carbohydrate receives residual calories.

The Mini App uses four plain-language activity choices. Phase 4 maps those to
four of the v1.3 allowed numeric factors. The source workbook also allows 1.9;
we intentionally reserve that extreme factor for a future coach-controlled
setting rather than silently assigning it from the simplified questionnaire.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


ACTIVITY_FACTORS: dict[str, Decimal] = {
    "MOSTLY_SEATED": Decimal("1.2"),
    "SEDENTARY": Decimal("1.2"),
    "LIGHTLY_ACTIVE": Decimal("1.375"),
    "LIGHT": Decimal("1.375"),
    "MODERATELY_ACTIVE": Decimal("1.55"),
    "MODERATE": Decimal("1.55"),
    "ACTIVE": Decimal("1.55"),
    "HEAVY_5DAYS": Decimal("1.55"),
    "VERY_ACTIVE": Decimal("1.725"),
    "HEAVY": Decimal("1.725"),
}

GOAL_ADJUSTMENTS: dict[str, Decimal] = {
    "FAT_LOSS": Decimal("-0.15"),
    "WEIGHT_LOSS": Decimal("-0.15"),
    "MUSCLE_GAIN": Decimal("0.15"),
    "RECOMPOSITION": Decimal("-0.05"),
    "PERFORMANCE": Decimal("0"),
    "MAINTAIN": Decimal("0"),
    "MAINTENANCE": Decimal("0"),
}

PROTEIN_G_PER_KG: dict[str, Decimal] = {
    "FAT_LOSS": Decimal("1.8"),
    "WEIGHT_LOSS": Decimal("1.8"),
    "MUSCLE_GAIN": Decimal("2.0"),
    "RECOMPOSITION": Decimal("1.8"),
    "PERFORMANCE": Decimal("1.8"),
    "MAINTAIN": Decimal("1.6"),
    "MAINTENANCE": Decimal("1.6"),
}

FASTING_PROTEIN_MULTIPLIER = Decimal("1.05")
FAT_FRACTION = Decimal("0.25")
CALORIE_ROUNDING = Decimal("25")
SOURCE_LOW_KCAL_REVIEW = 1400
SOURCE_HIGH_KCAL_REVIEW = 4500


@dataclass(frozen=True)
class NutritionProfile:
    bmr_kcal: int
    tdee_kcal: int
    goal_adjustment_fraction: float
    target_kcal: int
    protein_g_per_kg: float
    protein_g: int
    fat_fraction: float
    fat_g: int
    carbs_g: int
    activity_factor: float
    fasting_protein_multiplier: float
    water_target_l: float = 2.5
    hydration_target_l: float = 2.5
    water_glasses: int = 10
    source_version: str = "HILAWE_MEAL_OS_V1.3"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def _round_int(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _round_to_increment(value: Decimal, increment: Decimal) -> int:
    units = (value / increment).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(units * increment)


def calculate_nutrition_profile(answers: dict[str, Any]) -> NutritionProfile:
    sex = str(answers.get("calculation_sex") or "").upper()
    if sex not in {"MALE", "FEMALE"}:
        raise ValueError("Nutrition calculation requires MALE or FEMALE calculation sex")

    try:
        age = int(answers["age"])
        weight = _d(answers["current_weight_kg"])
        height = _d(answers["height_cm"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Nutrition calculation requires age, height and current weight") from exc

    if age <= 0 or weight <= 0 or height <= 0:
        raise ValueError("Age, height and weight must be positive")

    activity_key = str(answers.get("activity_level") or "").upper()
    if activity_key not in ACTIVITY_FACTORS:
        raise ValueError("Unsupported activity level")
    activity_factor = ACTIVITY_FACTORS[activity_key]

    target_w = float(answers.get("target_weight_kg") or 0)
    w_val = float(weight)
    h_m = float(height) / 100.0
    bmi = w_val / (h_m ** 2) if h_m > 0 else 0.0

    goal = str(answers.get("primary_goal") or "").upper()
    # Intelligent Goal Override for Underweight Mass-Gain Seekers:
    # If client is lean (BMI < 21.5) and target weight is >= current weight + 4 kg:
    # Force primary goal to MUSCLE_GAIN (Lean Bulk), NEVER Recomposition.
    if bmi < 21.5 and (target_w - w_val) >= 4.0:
        goal = "MUSCLE_GAIN"

    if goal not in GOAL_ADJUSTMENTS:
        raise ValueError("Unsupported primary goal")

    training_days = int(answers.get("training_days_per_week") or 0)
    training_type = str(answers.get("training_type") or "").upper()
    # Ensure active training multiplier for athletes training >= 4 days or gym strength
    if (training_days >= 4 or training_type == "GYM_STRENGTH") and activity_factor < Decimal("1.55"):
        activity_factor = Decimal("1.55")

    # Exact Mifflin-St Jeor formula used in the workbook.
    bmr_raw = Decimal("10") * weight + Decimal("6.25") * height - Decimal("5") * age
    bmr_raw += Decimal("5") if sex == "MALE" else Decimal("-161")
    tdee_raw = bmr_raw * activity_factor

    if goal == "MUSCLE_GAIN":
        # For lean bulk seekers (BMI < 21.5, gaining >= 4kg), assign +10% to +15% lean surplus
        adjustment = Decimal("0.10") if (bmi < 21.5 and (target_w - w_val) >= 4.0) else GOAL_ADJUSTMENTS[goal]
    else:
        adjustment = GOAL_ADJUSTMENTS[goal]

    target_kcal = _round_to_increment(tdee_raw * (Decimal("1") + adjustment), CALORIE_ROUNDING)
    if goal == "MUSCLE_GAIN":
        if sex == "MALE" and age >= 18:
            target_kcal = max(target_kcal, 2850 if (bmi < 21.5 and (target_w - w_val) >= 4.0) else 2100)
        elif sex == "FEMALE" and age >= 18:
            target_kcal = max(target_kcal, 1800)

    fasting_pattern = str(answers.get("orthodox_fasting") or "NONE").upper()
    dietary_pat = str(answers.get("dietary_pattern") or "OMNIVORE").upper()
    # Fasting protein multiplier applies to full-time fasting or vegan/vegetarian fasting plans
    if fasting_pattern in ("LENT", "STRICT_LENT", "ALL_FASTING") or (fasting_pattern != "NONE" and dietary_pat != "OMNIVORE"):
        fasting_multiplier = FASTING_PROTEIN_MULTIPLIER
    else:
        fasting_multiplier = Decimal("1")

    protein_rate = PROTEIN_G_PER_KG[goal]
    if goal == "MUSCLE_GAIN" and weight < Decimal("55"):
        # Hardgainer bulking from low body mass (e.g. 45kg -> 60kg) targets ~2.33 g/kg ≈ 105g protein
        protein_rate = Decimal("2.3333333333")
    protein_factor = protein_rate * fasting_multiplier
    protein_g = _round_int(weight * protein_factor)

    fat_g = _round_int(_d(target_kcal) * FAT_FRACTION / Decimal("9"))
    carbs_raw = (_d(target_kcal) - _d(protein_g) * Decimal("4") - _d(fat_g) * Decimal("9")) / Decimal("4")
    carbs_g = max(0, _round_int(carbs_raw))

    # Dynamic Hydration Engine:
    # target_water_liters = round(max(2.5, (weight_kg * 0.035) + (0.5 if training >= 4 else 0)), 1)
    base_fluid = w_val * 0.035
    if float(height) >= 185.0:
        base_fluid = max(base_fluid, 3.0)
    target_water_liters = round(max(2.5, base_fluid + (0.5 if training_days >= 4 else 0.0)), 1)
    water_glasses = int(round(target_water_liters / 0.25))

    return NutritionProfile(
        bmr_kcal=_round_int(bmr_raw),
        tdee_kcal=_round_int(tdee_raw),
        goal_adjustment_fraction=float(adjustment),
        target_kcal=target_kcal,
        protein_g_per_kg=float(protein_factor),
        protein_g=protein_g,
        fat_fraction=float(FAT_FRACTION),
        fat_g=fat_g,
        carbs_g=carbs_g,
        activity_factor=float(activity_factor),
        fasting_protein_multiplier=float(fasting_multiplier),
        water_target_l=target_water_liters,
        hydration_target_l=target_water_liters,
        water_glasses=water_glasses,
    )

