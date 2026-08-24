"""Validation and completeness rules for the Phase 3 guided meal-plan intake.

These are input-shape / product-flow rules, not nutrition calculations. Nutrition
math and health-gate decisions remain Phase 4 responsibilities.
"""

from __future__ import annotations

import re
from typing import Any


ALLOWED_SEX = {"MALE", "FEMALE"}
ALLOWED_GOALS = {"FAT_LOSS", "MUSCLE_GAIN", "RECOMPOSITION", "MAINTAIN", "PERFORMANCE"}
ALLOWED_ACTIVITY = {"MOSTLY_SEATED", "LIGHTLY_ACTIVE", "ACTIVE", "VERY_ACTIVE"}
ALLOWED_TRAINING_TYPES = {
    "GYM_STRENGTH",
    "RUNNING_CARDIO",
    "SPORTS",
    "HOME_WORKOUT",
    "MIXED",
    "NOT_TRAINING",
}
ALLOWED_CUISINE = {"ETHIOPIAN", "INTERNATIONAL", "MIXED"}
ALLOWED_DIETARY_PATTERNS = {"OMNIVORE", "VEGETARIAN", "VEGAN"}
ALLOWED_BUDGET = {"SAVE", "BALANCED", "FLEXIBLE"}
ALLOWED_FASTING = {"NONE", "WED_FRI", "SEASONAL", "WED_FRI_AND_SEASONAL"}

FOOD_CHIPS = {
    "INJERA", "SHIRO", "MISIR", "EGGS", "CHICKEN", "BEEF", "FISH",
    "MILK_YOGURT", "RICE", "OATS", "POTATO", "AVOCADO", "GOMEN",
    "PASTA", "CHICKPEAS", "FRUIT",
}
ALLERGY_CHIPS = {
    "PEANUTS", "TREE_NUTS", "MILK", "EGGS", "FISH", "SHELLFISH",
    "WHEAT", "SOY", "SESAME",
}

HEALTH_BOOLEAN_FIELDS = {
    "health_pregnancy_postpartum_lactating",
    "health_eating_disorder_concern",
    "health_kidney_liver_disease",
    "health_diabetes_or_glucose_medication",
    "health_clinician_prescribed_diet",
    "health_severe_gi_condition",
    "health_anaphylactic_food_allergy",
    "health_unexplained_weight_change",
    "health_other_important_change",
}

TEXT_FIELDS = {
    "liked_foods_other",
    "disliked_foods_other",
    "allergy_other",
    "intolerance_other",
    "health_other_details",
}

LIST_FIELDS = {
    "liked_foods": FOOD_CHIPS,
    "disliked_foods": FOOD_CHIPS,
    "food_allergies": ALLERGY_CHIPS,
    "food_intolerances": ALLERGY_CHIPS,
}

VALID_STEPS = {
    "WELCOME", "AGE", "SEX", "BODY", "GOAL", "TARGET_WEIGHT", "ACTIVITY",
    "TRAINING", "CUISINE", "DIETARY_PATTERN", "BUDGET", "FASTING", "LIKES", "DISLIKES",
    "ALLERGIES", "INTOLERANCES", "HEALTH_PREGNANCY", "HEALTH_EATING",
    "HEALTH_KIDNEY_LIVER", "HEALTH_DIABETES", "HEALTH_CLINICIAN_DIET",
    "HEALTH_GI", "HEALTH_UNEXPLAINED_WEIGHT", "HEALTH_OTHER",
    "ASSESSMENT_COMPLETE",
}


def _require_bool(name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be true or false")
    return value


def _number(name: str, value: Any, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    number = float(value)
    if number < minimum or number > maximum:
        raise ValueError(f"{name} must be between {minimum:g} and {maximum:g}")
    return round(number, 2)


def _integer(name: str, value: Any, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _choice(name: str, value: Any, allowed: set[str]) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    normalized = value.strip().upper()
    if normalized not in allowed:
        raise ValueError(f"Unsupported {name}")
    return normalized


def _clean_text(name: str, value: Any, *, max_length: int = 300) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    cleaned = re.sub(r"\s+", " ", value.strip())
    if len(cleaned) > max_length:
        raise ValueError(f"{name} is too long")
    return cleaned


def _chip_list(name: str, value: Any, allowed: set[str]) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    if len(value) > 24:
        raise ValueError(f"{name} has too many selections")
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, str):
            raise ValueError(f"{name} contains an invalid selection")
        item = raw.strip().upper()
        if item not in allowed:
            raise ValueError(f"{name} contains unsupported selection: {item}")
        if item not in seen:
            normalized.append(item)
            seen.add(item)
    return normalized


def validate_answer_patch(patch: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(patch, dict) or not patch:
        raise ValueError("answers must contain at least one field")
    if len(patch) > 12:
        raise ValueError("too many answer fields in one request")

    normalized: dict[str, Any] = {}
    for name, value in patch.items():
        if name == "age":
            normalized[name] = _integer(name, value, minimum=10, maximum=100)
        elif name == "calculation_sex":
            normalized[name] = _choice(name, value, ALLOWED_SEX)
        elif name == "height_cm":
            normalized[name] = _number(name, value, minimum=100, maximum=250)
        elif name in {"current_weight_kg", "target_weight_kg"}:
            normalized[name] = _number(name, value, minimum=25, maximum=350)
        elif name == "primary_goal":
            normalized[name] = _choice(name, value, ALLOWED_GOALS)
        elif name == "activity_level":
            normalized[name] = _choice(name, value, ALLOWED_ACTIVITY)
        elif name == "training_days_per_week":
            normalized[name] = _integer(name, value, minimum=0, maximum=7)
        elif name == "training_type":
            normalized[name] = _choice(name, value, ALLOWED_TRAINING_TYPES)
        elif name == "cuisine_style":
            normalized[name] = _choice(name, value, ALLOWED_CUISINE)
        elif name == "dietary_pattern":
            normalized[name] = _choice(name, value, ALLOWED_DIETARY_PATTERNS)
        elif name == "grocery_budget":
            normalized[name] = _choice(name, value, ALLOWED_BUDGET)
        elif name == "orthodox_fasting":
            normalized[name] = _choice(name, value, ALLOWED_FASTING)
        elif name == "fish_during_fast":
            if value is None:
                normalized[name] = None
            else:
                normalized[name] = _require_bool(name, value)
        elif name in LIST_FIELDS:
            normalized[name] = _chip_list(name, value, LIST_FIELDS[name])
        elif name in TEXT_FIELDS:
            normalized[name] = _clean_text(name, value)
        elif name in HEALTH_BOOLEAN_FIELDS:
            normalized[name] = _require_bool(name, value)
        else:
            raise ValueError(f"Unsupported intake field: {name}")

    return normalized


def normalize_step(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("current_step must be text")
    step = value.strip().upper()
    if step not in VALID_STEPS:
        raise ValueError("Unsupported intake step")
    return step


_BASE_REQUIRED = {
    "age", "calculation_sex", "height_cm", "current_weight_kg", "primary_goal",
    "target_weight_kg", "activity_level", "training_days_per_week", "training_type",
    "cuisine_style", "dietary_pattern", "grocery_budget", "orthodox_fasting", "liked_foods",
    "disliked_foods", "food_allergies", "food_intolerances",
    "health_eating_disorder_concern", "health_kidney_liver_disease",
    "health_diabetes_or_glucose_medication", "health_clinician_prescribed_diet",
    "health_severe_gi_condition", "health_unexplained_weight_change",
    "health_other_important_change",
}


def validate_complete_assessment(answers: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return normalized derived defaults plus missing/consistency errors.

    This does not determine medical eligibility. Phase 4 evaluates the actual
    Hilawe health gate after this questionnaire is complete.
    """
    if not isinstance(answers, dict):
        return {}, ["answers"]

    missing = sorted(name for name in _BASE_REQUIRED if name not in answers)
    if missing:
        return {}, missing

    derived: dict[str, Any] = {}

    sex = answers.get("calculation_sex")
    if sex == "FEMALE":
        if "health_pregnancy_postpartum_lactating" not in answers:
            missing.append("health_pregnancy_postpartum_lactating")
    else:
        derived["health_pregnancy_postpartum_lactating"] = False

    fasting = answers.get("orthodox_fasting")
    if fasting and fasting != "NONE":
        if "fish_during_fast" not in answers or answers.get("fish_during_fast") is None:
            missing.append("fish_during_fast")
    else:
        derived["fish_during_fast"] = False

    allergies = answers.get("food_allergies") or []
    allergy_other = str(answers.get("allergy_other") or "").strip()
    if allergies or allergy_other:
        if "health_anaphylactic_food_allergy" not in answers:
            missing.append("health_anaphylactic_food_allergy")
    else:
        derived["health_anaphylactic_food_allergy"] = False

    if answers.get("health_other_important_change") and not str(answers.get("health_other_details") or "").strip():
        missing.append("health_other_details")

    # Keep training answers logically coherent without inventing nutrition rules.
    if answers.get("training_days_per_week") == 0:
        derived["training_type"] = "NOT_TRAINING"
    elif answers.get("training_type") == "NOT_TRAINING":
        missing.append("training_type")

    return derived, sorted(set(missing))
