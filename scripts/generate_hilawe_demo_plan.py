"""Generate a deterministic local Phase 6 demo plan without touching Telegram/DB."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from meal_plan.generation.engine import generate_plan
from meal_plan.nutrition_targets import calculate_nutrition_profile


def demo_answers() -> dict:
    return {
        "age": 30,
        "calculation_sex": "MALE",
        "height_cm": 179,
        "current_weight_kg": 75.4,
        "primary_goal": "RECOMPOSITION",
        "activity_level": "ACTIVE",
        "training_days_per_week": 4,
        "training_type": "GYM_STRENGTH",
        "cuisine_style": "MIXED",
        "dietary_pattern": "OMNIVORE",
        "grocery_budget": "BALANCED",
        "orthodox_fasting": "WED_FRI",
        "fish_during_fast": True,
        "liked_foods": ["INJERA", "CHICKEN"],
        "disliked_foods": [],
        "food_allergies": [],
        "food_intolerances": [],
        "health_pregnancy_postpartum_lactating": False,
        "health_eating_disorder_concern": False,
        "health_kidney_liver_disease": False,
        "health_diabetes_or_glucose_medication": False,
        "health_clinician_prescribed_diet": False,
        "health_severe_gi_condition": False,
        "health_anaphylactic_food_allergy": False,
        "health_unexplained_weight_change": False,
        "health_other_important_change": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--meals", type=int, choices=(3, 4, 5), default=4)
    parser.add_argument("--days", type=int, choices=(7, 14, 30), default=30)
    parser.add_argument("--start", default="2026-08-24")
    parser.add_argument("--output", default="phase6_demo_plan.json")
    args = parser.parse_args()

    answers = demo_answers()
    profile = calculate_nutrition_profile(answers).to_dict()
    plan = generate_plan(
        answers=answers,
        nutrition_profile=profile,
        meals_per_day=args.meals,
        start_date=date.fromisoformat(args.start),
        duration_days=args.days,
        region="ETHIOPIA",
    )
    path = Path(args.output)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {path.resolve()}")
    print(f"Engine: {plan['engine_version']} | Dataset: {plan['dataset_version']}")
    print(f"Core week: {len(plan['core_week'])} days | Rotation: {len(plan['rotation'])} days")
    print(f"Coach review required: {plan['review']['required']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
