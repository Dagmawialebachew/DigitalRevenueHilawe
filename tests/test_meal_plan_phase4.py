from __future__ import annotations

import json
import os
import unittest
from datetime import date
from pathlib import Path

from meal_plan.checkout import earliest_start_date, parse_plan_configuration
from meal_plan.health_gate import HEALTH_FLAGS, evaluate_health_gate
from meal_plan.nutrition_targets import (
    ACTIVITY_FACTORS,
    FASTING_PROTEIN_MULTIPLIER,
    calculate_nutrition_profile,
)
from meal_plan.runtime import reviewer_ids

ROOT = Path(__file__).resolve().parents[1]


def routine_answers(**overrides):
    data = {
        "age": 30,
        "calculation_sex": "MALE",
        "height_cm": 179,
        "current_weight_kg": 75.4,
        "primary_goal": "RECOMPOSITION",
        "activity_level": "ACTIVE",
        "orthodox_fasting": "WED_FRI",
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
    data.update(overrides)
    return data


class HealthGateTests(unittest.TestCase):
    def test_gate_has_exact_ten_source_checks(self):
        self.assertEqual(len(HEALTH_FLAGS), 10)
        self.assertEqual(HEALTH_FLAGS[0].code, "UNDER_18")
        self.assertEqual(HEALTH_FLAGS[-1].code, "OTHER_HEALTH_CHANGE")

    def test_all_no_is_routine(self):
        result = evaluate_health_gate(routine_answers(orthodox_fasting="NONE"))
        self.assertEqual(result.category, "ROUTINE")
        self.assertFalse(result.requires_review)
        self.assertEqual(result.codes(), [])

    def test_any_yes_requires_medical_qualified_review(self):
        result = evaluate_health_gate(routine_answers(health_kidney_liver_disease=True))
        self.assertTrue(result.requires_review)
        self.assertIn("KIDNEY_LIVER_DISEASE", result.codes())

    def test_under_18_is_derived_from_age(self):
        result = evaluate_health_gate(routine_answers(age=17))
        self.assertIn("UNDER_18", result.codes())

    def test_missing_boolean_never_silently_becomes_no(self):
        answers = routine_answers()
        del answers["health_diabetes_or_glucose_medication"]
        with self.assertRaises(ValueError):
            evaluate_health_gate(answers)


class NutritionTargetTests(unittest.TestCase):
    def test_v13_golden_example(self):
        # Golden vector recovered from the v1.3 handoff:
        # 75.4 kg, 179 cm, age 30 male, activity 1.55, recomposition, fasting.
        result = calculate_nutrition_profile(routine_answers())
        self.assertEqual(result.bmr_kcal, 1728)
        self.assertEqual(result.tdee_kcal, 2678)
        self.assertEqual(result.target_kcal, 2550)
        self.assertEqual(result.protein_g, 143)
        self.assertEqual(result.fat_g, 71)
        self.assertEqual(result.carbs_g, 335)
        self.assertAlmostEqual(result.activity_factor, 1.55)
        self.assertAlmostEqual(result.fasting_protein_multiplier, 1.05)

    def test_fasting_multiplier_is_applied_only_when_fasting(self):
        fasting = calculate_nutrition_profile(routine_answers(orthodox_fasting="WED_FRI"))
        not_fasting = calculate_nutrition_profile(routine_answers(orthodox_fasting="NONE"))
        self.assertGreater(fasting.protein_g, not_fasting.protein_g)
        self.assertEqual(str(FASTING_PROTEIN_MULTIPLIER), "1.05")

    def test_plain_language_activity_mapping_uses_source_factor_ladder(self):
        self.assertEqual(str(ACTIVITY_FACTORS["MOSTLY_SEATED"]), "1.2")
        self.assertEqual(str(ACTIVITY_FACTORS["LIGHTLY_ACTIVE"]), "1.375")
        self.assertEqual(str(ACTIVITY_FACTORS["ACTIVE"]), "1.55")
        self.assertEqual(str(ACTIVITY_FACTORS["VERY_ACTIVE"]), "1.725")
        self.assertNotIn("1.9", {str(v) for v in ACTIVITY_FACTORS.values()})

    def test_female_mifflin_constant_is_used(self):
        profile = calculate_nutrition_profile(routine_answers(calculation_sex="FEMALE", orthodox_fasting="NONE"))
        male = calculate_nutrition_profile(routine_answers(calculation_sex="MALE", orthodox_fasting="NONE"))
        self.assertLess(profile.bmr_kcal, male.bmr_kcal)


class CheckoutRulesTests(unittest.TestCase):
    TODAY = date(2026, 8, 21)

    def test_earliest_start_is_tomorrow(self):
        self.assertEqual(earliest_start_date(self.TODAY), date(2026, 8, 22))

    def test_three_four_five_meals_are_allowed(self):
        for meals in (3, 4, 5):
            config = parse_plan_configuration(
                {"meals_per_day": meals, "start_date": "2026-08-22", "duration_days": 7, "service_type": "PLAN"},
                today=self.TODAY,
            )
            self.assertEqual(config.meals_per_day, meals)

    def test_today_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_plan_configuration(
                {"meals_per_day": 4, "start_date": "2026-08-21", "duration_days": 7, "service_type": "PLAN"},
                today=self.TODAY,
            )

    def test_follow_up_is_30_days_only(self):
        for duration in (7, 14):
            with self.assertRaises(ValueError):
                parse_plan_configuration(
                    {"meals_per_day": 4, "start_date": "2026-08-22", "duration_days": duration, "service_type": "FOLLOW_UP"},
                    today=self.TODAY,
                )
        config = parse_plan_configuration(
            {"meals_per_day": 4, "start_date": "2026-08-22", "duration_days": 30, "service_type": "FOLLOW_UP"},
            today=self.TODAY,
        )
        self.assertEqual(config.ends_on, date(2026, 9, 20))


class Phase4SurfaceTests(unittest.TestCase):
    def test_phase4_checkout_routes_remain_after_later_phases(self):
        source = (ROOT / "meal_plan" / "api.py").read_text(encoding="utf-8")
        self.assertIn('/api/meal/checkout/options', source)
        self.assertIn('/api/meal/checkout/preview', source)

    def test_health_review_router_is_registered(self):
        source = (ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertIn("meal_plan_health_review_router", source)
        self.assertIn("include_router(meal_plan_health_review_router)", source)

    def test_phase4_adds_no_new_migration(self):
        migration_files = sorted((ROOT / "database" / "migrations").glob("[0-9][0-9][0-9][0-9]_*.sql"))
        names = [p.name for p in migration_files]
        self.assertIn("0001_meal_plan_core.sql", names)

    def test_frontend_phase4_surface_exists(self):
        source = (ROOT / "meal_plan_miniapp" / "src" / "ProfileCheckoutFlow.tsx").read_text(encoding="utf-8")
        for needle in ("Nutrition Profile", "3,4,5", "FOLLOW_UP", "previewCheckout"):
            self.assertIn(needle, source)
        app = (ROOT / "meal_plan_miniapp" / "src" / "App.tsx").read_text(encoding="utf-8")
        self.assertIn("HEALTH_REVIEW_REQUIRED", app)
        self.assertIn("ProfileCheckoutFlow", app)

    def test_frontend_version_is_at_least_phase4(self):
        package = json.loads((ROOT / "meal_plan_miniapp" / "package.json").read_text(encoding="utf-8"))
        major, minor, _ = [int(part) for part in package["version"].split(".")]
        self.assertGreaterEqual((major, minor), (0, 4))

    def test_reviewer_ids_prefers_dedicated_env_and_falls_back_to_admins(self):
        old_review = os.environ.get("MEAL_PLAN_REVIEWER_IDS")
        old_admin = os.environ.get("ADMIN_IDS")
        try:
            os.environ["MEAL_PLAN_REVIEWER_IDS"] = "101,202"
            os.environ["ADMIN_IDS"] = "303"
            self.assertEqual(reviewer_ids(), (101, 202))
            os.environ.pop("MEAL_PLAN_REVIEWER_IDS", None)
            self.assertEqual(reviewer_ids(), (303,))
        finally:
            if old_review is None:
                os.environ.pop("MEAL_PLAN_REVIEWER_IDS", None)
            else:
                os.environ["MEAL_PLAN_REVIEWER_IDS"] = old_review
            if old_admin is None:
                os.environ.pop("ADMIN_IDS", None)
            else:
                os.environ["ADMIN_IDS"] = old_admin


if __name__ == "__main__":
    unittest.main()
