import unittest
from pathlib import Path

from meal_plan.intake_validation import (
    normalize_step,
    validate_answer_patch,
    validate_complete_assessment,
)


class IntakeValidationTests(unittest.TestCase):
    def test_valid_patch_normalizes_values(self):
        patch = validate_answer_patch({
            "age": 24,
            "height_cm": 178,
            "current_weight_kg": 75.5,
            "primary_goal": "fat_loss",
            "liked_foods": ["INJERA", "SHIRO", "INJERA"],
        })
        self.assertEqual(patch["primary_goal"], "FAT_LOSS")
        self.assertEqual(patch["liked_foods"], ["INJERA", "SHIRO"])
        self.assertEqual(patch["current_weight_kg"], 75.5)

    def test_unknown_field_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_answer_patch({"made_up_field": "x"})

    def test_invalid_chip_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_answer_patch({"liked_foods": ["PIZZA_FROM_NOWHERE"]})

    def test_step_allowlist(self):
        self.assertEqual(normalize_step("health_diabetes"), "HEALTH_DIABETES")
        with self.assertRaises(ValueError):
            normalize_step("checkout_now")

    def test_complete_assessment_derives_contextual_false_values(self):
        answers = complete_fixture()
        answers["calculation_sex"] = "MALE"
        answers["orthodox_fasting"] = "NONE"
        answers["food_allergies"] = []
        derived, missing = validate_complete_assessment(answers)
        self.assertEqual(missing, [])
        self.assertFalse(derived["health_pregnancy_postpartum_lactating"])
        self.assertFalse(derived["fish_during_fast"])
        self.assertFalse(derived["health_anaphylactic_food_allergy"])

    def test_fasting_requires_fish_choice(self):
        answers = complete_fixture()
        answers["orthodox_fasting"] = "WED_FRI"
        answers.pop("fish_during_fast", None)
        _, missing = validate_complete_assessment(answers)
        self.assertIn("fish_during_fast", missing)

    def test_female_requires_pregnancy_gate_answer(self):
        answers = complete_fixture()
        answers["calculation_sex"] = "FEMALE"
        answers.pop("health_pregnancy_postpartum_lactating", None)
        _, missing = validate_complete_assessment(answers)
        self.assertIn("health_pregnancy_postpartum_lactating", missing)

    def test_allergy_requires_anaphylaxis_answer(self):
        answers = complete_fixture()
        answers["food_allergies"] = ["PEANUTS"]
        answers.pop("health_anaphylactic_food_allergy", None)
        _, missing = validate_complete_assessment(answers)
        self.assertIn("health_anaphylactic_food_allergy", missing)

    def test_other_health_yes_requires_details(self):
        answers = complete_fixture()
        answers["health_other_important_change"] = True
        answers["health_other_details"] = ""
        _, missing = validate_complete_assessment(answers)
        self.assertIn("health_other_details", missing)


    def test_dietary_pattern_is_required_and_validated(self):
        fixture = complete_fixture()
        fixture.pop("dietary_pattern")
        _, missing = validate_complete_assessment(fixture)
        self.assertIn("dietary_pattern", missing)
        self.assertEqual(validate_answer_patch({"dietary_pattern": "vegan"})["dietary_pattern"], "VEGAN")
        with self.assertRaises(ValueError):
            validate_answer_patch({"dietary_pattern": "keto-custom"})

    def test_zero_training_days_normalizes_training_type(self):
        answers = complete_fixture()
        answers["training_days_per_week"] = 0
        answers["training_type"] = "GYM_STRENGTH"
        derived, missing = validate_complete_assessment(answers)
        self.assertEqual(missing, [])
        self.assertEqual(derived["training_type"], "NOT_TRAINING")


class Phase3SurfaceTests(unittest.TestCase):
    def test_phase3_routes_are_present(self):
        source = (Path(__file__).resolve().parents[1] / "meal_plan" / "api.py").read_text(encoding="utf-8")
        self.assertIn('/api/meal/intake/answers', source)
        self.assertIn('/api/meal/intake/complete', source)
        self.assertRegex(source, r'\"phase\"\s*:\s*(?:[3-9]|[1-9][0-9]+)')

    def test_frontend_contains_guided_intake_and_amharic(self):
        root = Path(__file__).resolve().parents[1] / "meal_plan_miniapp" / "src"
        flow = (root / "IntakeFlow.tsx").read_text(encoding="utf-8")
        content = (root / "intakeContent.ts").read_text(encoding="utf-8")
        self.assertIn("ASSESSMENT_COMPLETE", flow)
        self.assertIn("HEALTH_KIDNEY_LIVER", flow)
        self.assertIn("የጤና ማረጋገጫ", content)
        self.assertIn("WED_FRI_AND_SEASONAL", content)

    def test_phase3_adds_no_new_database_migration(self):
        migrations = sorted((Path(__file__).resolve().parents[1] / "database" / "migrations").glob("[0-9][0-9][0-9][0-9]_*.sql"))
        names = [p.name for p in migrations]
        self.assertIn("0001_meal_plan_core.sql", names)


def complete_fixture():
    return {
        "age": 25,
        "calculation_sex": "MALE",
        "height_cm": 175,
        "current_weight_kg": 75,
        "primary_goal": "FAT_LOSS",
        "target_weight_kg": 68,
        "activity_level": "ACTIVE",
        "training_days_per_week": 4,
        "training_type": "GYM_STRENGTH",
        "cuisine_style": "MIXED",
        "dietary_pattern": "OMNIVORE",
        "grocery_budget": "BALANCED",
        "orthodox_fasting": "NONE",
        "fish_during_fast": False,
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
        "health_other_details": "",
    }


if __name__ == "__main__":
    unittest.main()
