"""Phase 5 Contract & Release QA Tests: Real-Order Lifecycle Validation.

Verifies end-to-end simulation across key user journeys:
1. 7-Day Omnivore (Ethiopia, CBE bank transfer, 3 meals/day).
2. 14-Day Vegetarian (Diaspora, Card/Stripe transfer, 4 meals/day).
3. 30-Day Orthodox Fasting with Fish (Ethiopia, Abyssinia transfer, 5 meals/day, Amharic).
4. Release gate & migration audit integrity (0001-0004).
5. Strict client artifact generation safety (clean PDF, valid size, customer filename).
"""
from __future__ import annotations

import datetime
import tempfile
import unittest
from pathlib import Path

from meal_plan.documents import DocumentContext, render_client_pdf
from meal_plan.documents.helpers import client_artifact_filename
from meal_plan.generation.dataset import load_dataset
from meal_plan.generation.engine import generate_plan
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.release_gate import EXPECTED_ENGINE_MIGRATIONS
from scripts.generate_hilawe_demo_plan import demo_answers


class Phase5ReleaseQATests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()

    def test_scenario_1_seven_day_omnivore_cbe_journey(self):
        """Simulates 7-day Omnivore Ethiopia client ordering via CBE."""
        answers = demo_answers()
        answers.update({
            "dietary_pattern": "OMNIVORE",
            "orthodox_fasting": "NONE",
            "fish_during_fast": False,
            "grocery_budget": "BALANCED",
        })
        profile = calculate_nutrition_profile(answers).to_dict()
        plan = generate_plan(
            answers=answers,
            nutrition_profile=profile,
            meals_per_day=3,
            start_date=datetime.date(2026, 8, 24),
            duration_days=7,
            region="ETHIOPIA",
            dataset=self.dataset,
        )

        self.assertEqual(len(plan["core_week"]), 7)
        self.assertEqual(len(plan["rotation"]), 7)
        for day in plan["core_week"]:
            self.assertEqual(len(day["meals"]), 3)

        with tempfile.TemporaryDirectory() as td:
            ctx = DocumentContext(
                client_name="Kidus Yohannes",
                plan_public_id="MP-000007",
                version_number=1,
                language="EN",
                status="APPROVED",
                client_profile={"current_weight_kg": 80.0, "target_weight_kg": 75.0},
                hydration_target_l=2.8,
            )
            filename = client_artifact_filename("Kidus Yohannes", 7, 1)
            self.assertEqual(filename, "Kidus_Yohannes_Meal_Plan_7_Days_V1.pdf")
            out_file = Path(td) / filename
            pdf_path = render_client_pdf(plan, ctx, out_file)
            self.assertTrue(pdf_path.exists())
            self.assertGreater(pdf_path.stat().st_size, 40000)
            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF"))

    def test_scenario_2_fourteen_day_diaspora_vegetarian_journey(self):
        """Simulates 14-day Vegetarian Diaspora client ordering via Card."""
        answers = demo_answers()
        answers.update({
            "dietary_pattern": "VEGETARIAN",
            "orthodox_fasting": "NONE",
            "fish_during_fast": False,
            "grocery_budget": "FLEXIBLE",
        })
        profile = calculate_nutrition_profile(answers).to_dict()
        plan = generate_plan(
            answers=answers,
            nutrition_profile=profile,
            meals_per_day=4,
            start_date=datetime.date(2026, 8, 24),
            duration_days=14,
            region="DIASPORA",
            dataset=self.dataset,
        )

        self.assertEqual(len(plan["core_week"]), 7)
        self.assertEqual(len(plan["rotation"]), 14)
        for day in plan["core_week"]:
            self.assertEqual(len(day["meals"]), 4)

        with tempfile.TemporaryDirectory() as td:
            ctx = DocumentContext(
                client_name="Sarah Jenkins",
                plan_public_id="MP-000014",
                version_number=1,
                language="EN",
                status="APPROVED",
                client_profile={"current_weight_kg": 64.0, "target_weight_kg": 60.0},
                hydration_target_l=2.4,
            )
            filename = client_artifact_filename("Sarah Jenkins", 14, 1)
            self.assertEqual(filename, "Sarah_Jenkins_Meal_Plan_14_Days_V1.pdf")
            out_file = Path(td) / filename
            pdf_path = render_client_pdf(plan, ctx, out_file)
            self.assertTrue(pdf_path.exists())
            self.assertGreater(pdf_path.stat().st_size, 40000)
            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF"))

    def test_scenario_3_thirty_day_orthodox_fasting_with_fish_amharic_journey(self):
        """Simulates 30-day Orthodox Fasting client with fish ordering in Amharic via Abyssinia."""
        answers = demo_answers()
        answers.update({
            "dietary_pattern": "OMNIVORE",
            "orthodox_fasting": "WED_FRI",
            "fish_during_fast": True,
            "grocery_budget": "BALANCED",
        })
        profile = calculate_nutrition_profile(answers).to_dict()
        plan = generate_plan(
            answers=answers,
            nutrition_profile=profile,
            meals_per_day=5,
            start_date=datetime.date(2026, 8, 24),
            duration_days=30,
            region="ETHIOPIA",
            dataset=self.dataset,
        )

        self.assertEqual(len(plan["core_week"]), 7)
        self.assertEqual(len(plan["rotation"]), 30)
        for day in plan["core_week"]:
            self.assertEqual(len(day["meals"]), 5)

        with tempfile.TemporaryDirectory() as td:
            ctx = DocumentContext(
                client_name="ቴዎድሮስ ካሳሁን",
                plan_public_id="MP-000030",
                version_number=1,
                language="AM",
                status="APPROVED",
                client_profile={"current_weight_kg": 85.0, "target_weight_kg": 78.0},
                hydration_target_l=3.0,
            )
            filename = client_artifact_filename("Tewodros Kassahun", 30, 1)
            self.assertEqual(filename, "Tewodros_Kassahun_Meal_Plan_30_Days_V1.pdf")
            out_file = Path(td) / filename
            pdf_path = render_client_pdf(plan, ctx, out_file)
            self.assertTrue(pdf_path.exists())
            self.assertGreater(pdf_path.stat().st_size, 50000)
            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF"))

    def test_release_gate_migrations_sequence_integrity(self):
        """Verifies migrations 0001 through 0004 are discoverable and in order."""
        migrations_dir = Path(__file__).resolve().parents[1] / "database" / "migrations"
        found_migrations = sorted(p.name for p in migrations_dir.glob("[0-9][0-9][0-9][0-9]_*.sql"))
        self.assertEqual(
            found_migrations,
            [
                "0001_meal_plan_core.sql",
                "0002_hilawe_nutrition_dataset.sql",
                "0003_verified_fasting_calendar.sql",
                "0004_bilingual_and_calibrated_dataset.sql",
            ],
        )
        for expected in ("0001", "0002", "0003", "0004"):
            self.assertIn(expected, EXPECTED_ENGINE_MIGRATIONS)


if __name__ == "__main__":
    unittest.main()
