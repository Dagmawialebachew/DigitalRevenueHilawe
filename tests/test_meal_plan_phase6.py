from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path

from meal_plan.generation.dataset import DATASET_PATH, load_dataset
from meal_plan.generation.engine import ENGINE_VERSION, GenerationError, generate_plan
from meal_plan.generation.fasting import FastingCalendarRequired, fasting_days_for_week
from meal_plan.generation.grocery import build_grocery
from meal_plan.generation.meal_structure import meal_structure
from meal_plan.generation.safety import SUPPLEMENT_FOOD_IDS, template_is_safe
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.schema import PHASE_6_DATASET_TABLES

ROOT = Path(__file__).resolve().parents[1]


def base_answers(**overrides):
    data = {
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
    data.update(overrides)
    return data


def plan_for(meals=4, duration=30, **answer_overrides):
    answers = base_answers(**answer_overrides)
    profile = calculate_nutrition_profile(answers).to_dict()
    return generate_plan(
        answers=answers,
        nutrition_profile=profile,
        meals_per_day=meals,
        start_date=date(2026, 8, 24),
        duration_days=duration,
        region="ETHIOPIA",
    )


class DatasetTests(unittest.TestCase):
    def test_bundled_snapshot_is_exact_v13_shape(self):
        ds = load_dataset()
        self.assertEqual(ds.version, "HILAWE_MEAL_OS_V1.3_2026-08-17")
        self.assertEqual(len(ds.foods), 111)
        self.assertEqual(len(ds.recipes), 28)
        self.assertEqual(len(ds.recipe_ingredients), 157)
        self.assertEqual(len(ds.templates), 64)
        self.assertEqual(len(ds.template_components), 169)
        self.assertEqual(len(ds.exchange_groups), 49)
        self.assertEqual(len(ds.fasting_calendar), 9)
        self.assertEqual(len(ds.settings_rows), 51)

    def test_source_snapshot_contains_provenance_and_locked_policy(self):
        raw = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
        self.assertEqual(raw["meta"]["source_version"], "1.3")
        self.assertFalse(raw["meta"]["policy"]["supplements_enabled"])
        self.assertTrue(raw["meta"]["policy"]["coach_approval_required"])
        self.assertTrue(raw["meta"]["policy"]["annual_fasting_dates_must_be_verified"])

    def test_all_source_recipes_still_require_calibration(self):
        ds = load_dataset()
        requiring = [r for r in ds.recipes if "required" in str(r.get("Calibration Status") or "").lower()]
        self.assertEqual(len(requiring), 28)

    def test_phase6_migration_creates_only_nutrition_domain_tables(self):
        sql = (ROOT / "database" / "migrations" / "0002_hilawe_nutrition_dataset.sql").read_text(encoding="utf-8")
        for table in PHASE_6_DATASET_TABLES:
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", sql)
        for legacy in ("users", "products", "payments", "club_subscriptions"):
            self.assertNotIn(f"ALTER TABLE {legacy}", sql)
            self.assertNotIn(f"DROP TABLE {legacy}", sql)

    def test_database_importer_preserves_raw_source_payload(self):
        source = (ROOT / "meal_plan" / "dataset_import.py").read_text(encoding="utf-8")
        self.assertIn("source_payload", source)
        self.assertIn("ON CONFLICT", source)
        self.assertIn("dataset_version", source)
        db_loader = (ROOT / "meal_plan" / "generation" / "db_dataset.py").read_text(encoding="utf-8")
        self.assertIn("SELECT source_payload, dataset_version", db_loader)


class MealStructureTests(unittest.TestCase):
    def test_four_meal_structure_preserves_v13_source_shares(self):
        specs = meal_structure(4)
        self.assertEqual([s.target_share for s in specs], [0.25, 0.30, 0.30, 0.15])
        self.assertEqual([s.kcal_cap_fraction for s in specs], [0.32, 0.35, 0.35, 0.20])
        self.assertEqual([s.mass_cap_g for s in specs], [700, 900, 900, 450])

    def test_three_and_five_meal_extensions_sum_to_one(self):
        for count in (3, 5):
            specs = meal_structure(count)
            self.assertEqual(len(specs), count)
            self.assertAlmostEqual(sum(s.target_share for s in specs), 1.0)

    def test_engine_outputs_exact_requested_meal_count(self):
        for count in (3, 4, 5):
            plan = plan_for(meals=count, duration=7)
            self.assertTrue(all(len(day["meals"]) == count for day in plan["core_week"]))

    def test_five_meal_plan_never_reuses_same_template_twice_same_day(self):
        plan = plan_for(meals=5, duration=7)
        for day in plan["core_week"]:
            ids = [meal["template_id"] for meal in day["meals"]]
            self.assertEqual(len(ids), len(set(ids)))


class SafetyAndFastingTests(unittest.TestCase):
    def test_supplements_are_disabled_even_though_v13_contains_them(self):
        ds = load_dataset()
        self.assertTrue(SUPPLEMENT_FOOD_IDS.issubset(ds.food_by_id))
        plan = plan_for(meals=5, duration=7)
        used = {item["food_id"] for day in plan["core_week"] for meal in day["meals"] for item in meal["items"] if item["food_id"]}
        self.assertTrue(used.isdisjoint(SUPPLEMENT_FOOD_IDS))
        self.assertFalse(plan["review"]["supplements_used"])

    def test_peanut_allergy_filters_direct_and_recipe_ingredient_paths(self):
        answers = base_answers(orthodox_fasting="NONE", fish_during_fast=False, food_allergies=["PEANUTS"])
        ds = load_dataset()
        for template in ds.active_templates:
            safe, reasons = template_is_safe(template, ds, answers, fasting=False)
            if safe:
                self.assertFalse(any("allergy:PEANUTS" in r for r in reasons))
        profile = calculate_nutrition_profile(answers).to_dict()
        plan = generate_plan(
            answers=answers, nutrition_profile=profile, meals_per_day=5,
            start_date=date(2026, 8, 24), duration_days=7, region="ETHIOPIA",
        )
        text = json.dumps(plan, ensure_ascii=False).lower()
        self.assertNotIn('"food_name": "peanuts', text)
        self.assertNotIn('"food_name": "peanut', text)


    def test_vegan_and_vegetarian_patterns_are_enforced_at_ingredient_level(self):
        ds = load_dataset()
        for pattern in ("VEGETARIAN", "VEGAN"):
            plan = plan_for(meals=4, duration=7, dietary_pattern=pattern, orthodox_fasting="NONE", fish_during_fast=False)
            answers = base_answers(dietary_pattern=pattern, orthodox_fasting="NONE", fish_during_fast=False)
            for day in plan["core_week"]:
                for meal in day["meals"]:
                    template = next(t for t in ds.templates if t["Template ID"] == meal["template_id"])
                    source_fasting = str(template.get("Fasting")) == "Yes"
                    safe, reasons = template_is_safe(template, ds, answers, fasting=source_fasting)
                    self.assertTrue(safe, f"{pattern} received unsafe template {meal['template_id']}: {reasons}")
            if pattern == "VEGAN":
                self.assertTrue(all(str(next(t for t in ds.templates if t["Template ID"] == m["template_id"]).get("Fasting")) == "Yes" for d in plan["core_week"] for m in d["meals"]))

    def test_weekly_orthodox_fast_marks_wednesday_and_friday(self):
        ds = load_dataset()
        flags = fasting_days_for_week(date(2026, 8, 24), "WED_FRI", ds.fasting_calendar)
        self.assertEqual([i for i, flag in enumerate(flags) if flag], [2, 4])

    def test_fish_during_fast_alternates_lunch_then_dinner(self):
        plan = plan_for(meals=4, duration=7)
        wed, fri = plan["core_week"][2], plan["core_week"][4]
        self.assertTrue(wed["fasting"] and fri["fasting"])
        wed_fish = [m["source_slot"] for m in wed["meals"] if "fish" in m["meal_name"].lower() or "tilapia" in m["meal_name"].lower()]
        fri_fish = [m["source_slot"] for m in fri["meals"] if "fish" in m["meal_name"].lower() or "tilapia" in m["meal_name"].lower()]
        self.assertIn("Lunch", wed_fish)
        self.assertIn("Dinner", fri_fish)

    def test_seasonal_fast_fails_closed_without_verified_dates(self):
        answers = base_answers(orthodox_fasting="SEASONAL")
        profile = calculate_nutrition_profile(answers).to_dict()
        with self.assertRaises(GenerationError):
            generate_plan(
                answers=answers, nutrition_profile=profile, meals_per_day=4,
                start_date=date(2026, 8, 24), duration_days=7, region="ETHIOPIA",
            )


class PlanContractTests(unittest.TestCase):
    def test_plan_is_deterministic_for_same_inputs(self):
        first = plan_for(meals=4, duration=7)
        second = plan_for(meals=4, duration=7)
        self.assertEqual(first, second)

    def test_plan_always_requires_coach_review_and_never_auto_delivers(self):
        plan = plan_for(meals=4, duration=30)
        self.assertTrue(plan["review"]["required"])
        self.assertEqual(plan["review"]["status"], "PENDING")
        self.assertFalse(plan["policy"]["auto_delivery"])
        self.assertEqual(plan["engine_version"], ENGINE_VERSION)

    def test_rotation_contract_for_7_14_and_30_days(self):
        for duration in (7, 14, 30):
            plan = plan_for(meals=4, duration=duration)
            self.assertEqual(len(plan["rotation"]), duration)
        plan30 = plan_for(meals=4, duration=30)
        self.assertTrue(all(x["mode"] == "PRIMARY" for x in plan30["rotation"][:7]))
        self.assertTrue(all(x["mode"] == "SWAP_ROTATION" for x in plan30["rotation"][7:14]))
        self.assertTrue(all(x["mode"] == "PRIMARY" for x in plan30["rotation"][14:21]))
        self.assertTrue(all(x["mode"] == "SWAP_ROTATION" for x in plan30["rotation"][21:28]))
        self.assertEqual([x["mode"] for x in plan30["rotation"][28:]], ["PRIMARY", "PRIMARY"])

    def test_exact_familiar_and_exchange_contract_is_present(self):
        plan = plan_for(meals=4, duration=7)
        food_items = [item for d in plan["core_week"] for m in d["meals"] for item in m["items"] if item["source"] == "food"]
        self.assertTrue(food_items)
        self.assertTrue(all(item["grams"] > 0 for item in food_items))
        self.assertTrue(any(item["familiar"] for item in food_items))
        self.assertTrue(any(m["exchange_options"] for d in plan["core_week"] for m in d["meals"]))

    def test_source_recipe_calibration_is_visible_to_reviewers(self):
        plan = plan_for(meals=4, duration=7)
        self.assertTrue(plan["review"]["recipe_calibration_required"])
        self.assertTrue(plan["review"]["uncalibrated_recipes"])

    def test_grocery_uses_dry_yield_conversion(self):
        ds = load_dataset()
        rows = build_grocery({"C003": 900.0}, ds)
        rice = next(row for row in rows if row["food_id"] == "C003")
        self.assertEqual(rice["buy_weight_g"], 300.0)
        self.assertIn("dry", rice["purchase_quantity"].lower())
        self.assertIn("3.0", rice["plan_yield_guide"])


if __name__ == "__main__":
    unittest.main()
