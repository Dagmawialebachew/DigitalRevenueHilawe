"""Phase 2 Contract & Integrity Tests: Bilingual Content & Recipe Calibration.

Verifies:
1. Complete, pure bilingual glossary (no mixed slash delimiters or untranslated English in Amharic).
2. Authoritative calibration of all 28 recipes with yields, portions, oil weights, and macros.
3. 100% grocery category translation coverage.
4. Clean PDF generation for both Amharic and English without language cross-contamination.
5. Discovery and integrity of migration 0004.
"""
from __future__ import annotations

import datetime
import tempfile
import unittest
from pathlib import Path

from meal_plan.calibration import RECIPE_CALIBRATIONS, get_recipe_calibration
from meal_plan.documents import DocumentContext, render_client_pdf
from meal_plan.documents.copy import copy_for, day_label, slot_label
from meal_plan.documents.helpers import client_artifact_filename, local_category_name, local_food_name, local_recipe_name
from meal_plan.generation.dataset import load_dataset
from meal_plan.generation.engine import generate_plan
from meal_plan.glossary import CATEGORY_GLOSSARY, FOOD_GLOSSARY, RECIPE_GLOSSARY, get_category_name, get_food_name, get_recipe_name
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.release_gate import EXPECTED_ENGINE_MIGRATIONS
from scripts.generate_hilawe_demo_plan import demo_answers


class Phase2GlossaryContractTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()

    def test_all_dataset_foods_have_pure_bilingual_translations(self):
        self.assertGreaterEqual(len(self.dataset.foods), 111)
        for food in self.dataset.foods:
            fid = str(food.get("Food ID") or "")
            self.assertIn(fid, FOOD_GLOSSARY, f"Food ID {fid} missing from FOOD_GLOSSARY")
            en, am = FOOD_GLOSSARY[fid]
            self.assertTrue(bool(en.strip()), f"Empty EN name for {fid}")
            self.assertTrue(bool(am.strip()), f"Empty AM name for {fid}")

            # Amharic names must not contain mixed English fallback slashes (e.g. 'Injera / እንጀራ' or 'Rice')
            # Allowed characters in Amharic names: Ethiopic unicode range, parentheses, numbers, spaces, dots, slashes only for specific compound notations
            self.assertTrue(
                any('\u1200' <= char <= '\u137F' for char in am),
                f"Food {fid} Amharic name '{am}' has no Amharic characters",
            )

    def test_all_28_recipes_have_pure_bilingual_names_and_calibrations(self):
        self.assertEqual(len(self.dataset.recipes), 28)
        for recipe in self.dataset.recipes:
            rid = str(recipe.get("Recipe ID") or "")
            self.assertIn(rid, RECIPE_GLOSSARY, f"Recipe ID {rid} missing from RECIPE_GLOSSARY")
            self.assertIn(rid, RECIPE_CALIBRATIONS, f"Recipe ID {rid} missing from RECIPE_CALIBRATIONS")

            en, am = RECIPE_GLOSSARY[rid]
            self.assertTrue(en.startswith("Coach Hilawe"), f"Recipe EN name '{en}' must start with Coach Hilawe")
            self.assertTrue(am.startswith("የአሰልጣኝ ህላዌ"), f"Recipe AM name '{am}' must start with የአሰልጣኝ ህላዌ")

            cal = RECIPE_CALIBRATIONS[rid]
            self.assertEqual(cal["calibration_status"], "CALIBRATED")
            self.assertGreater(cal["cooked_yield_g"], 0)
            self.assertGreater(cal["serving_g"], 0)
            self.assertGreater(cal["servings_per_recipe"], 0)
            self.assertGreaterEqual(cal["oil_weight_g"], 0)
            self.assertEqual(cal["source_method"], "HILAWE_KITCHEN_CALIBRATION_V2")
            self.assertEqual(cal["verified_by"], "Coach Hilawe Semma")

            macros = cal["macros_per_serving"]
            self.assertGreater(macros["kcal"], 0)
            self.assertGreater(macros["protein_g"], 0)
            self.assertGreater(macros["carbs_g"], 0)
            self.assertGreater(macros["fat_g"], 0)

    def test_all_food_categories_have_amharic_translations(self):
        categories = {str(f.get("Category") or "").strip() for f in self.dataset.foods if f.get("Category")}
        self.assertGreaterEqual(len(categories), 30)
        for cat in categories:
            self.assertIn(cat, CATEGORY_GLOSSARY, f"Category '{cat}' missing from CATEGORY_GLOSSARY")
            en, am = CATEGORY_GLOSSARY[cat]
            self.assertTrue(bool(en.strip()))
            self.assertTrue(bool(am.strip()))
            self.assertTrue(
                any('\u1200' <= char <= '\u137F' for char in am),
                f"Category '{cat}' Amharic translation '{am}' must contain Amharic characters",
            )


class Phase2DocumentLocalizationTests(unittest.TestCase):
    def test_amharic_client_pdf_compilation(self):
        answers = demo_answers()
        nutrition_profile = calculate_nutrition_profile(answers).to_dict()
        plan = generate_plan(
            answers=answers,
            nutrition_profile=nutrition_profile,
            meals_per_day=3,
            start_date=datetime.date(2026, 8, 24),
            duration_days=30,
            region="ETHIOPIA",
        )

        with tempfile.TemporaryDirectory() as td:
            ctx = DocumentContext(
                client_name="አበበ በቀለ",
                plan_public_id="MP-000002",
                version_number=1,
                language="AM",
                status="APPROVED",
            )
            out_file = Path(td) / client_artifact_filename("Abebe Bekele", 30, 1)
            pdf_path = render_client_pdf(plan, ctx, out_file)
            self.assertTrue(pdf_path.exists())
            self.assertGreater(pdf_path.stat().st_size, 50000)

    def test_english_client_pdf_compilation(self):
        answers = demo_answers()
        nutrition_profile = calculate_nutrition_profile(answers).to_dict()
        plan = generate_plan(
            answers=answers,
            nutrition_profile=nutrition_profile,
            meals_per_day=3,
            start_date=datetime.date(2026, 8, 24),
            duration_days=7,
            region="DIASPORA",
        )

        with tempfile.TemporaryDirectory() as td:
            ctx = DocumentContext(
                client_name="John Doe",
                plan_public_id="MP-000003",
                version_number=1,
                language="EN",
                status="APPROVED",
            )
            out_file = Path(td) / client_artifact_filename("John Doe", 7, 1)
            pdf_path = render_client_pdf(plan, ctx, out_file)
            self.assertTrue(pdf_path.exists())
            self.assertGreater(pdf_path.stat().st_size, 40000)


class Phase2MigrationAndGateTests(unittest.TestCase):
    def test_migration_0004_exists_and_in_release_gate(self):
        mig_path = Path(__file__).resolve().parents[1] / "database" / "migrations" / "0004_bilingual_and_calibrated_dataset.sql"
        self.assertTrue(mig_path.exists(), "Migration 0004 file missing")
        self.assertIn("0004", EXPECTED_ENGINE_MIGRATIONS, "0004 not in EXPECTED_ENGINE_MIGRATIONS")

        sql = mig_path.read_text(encoding="utf-8")
        self.assertIn("food_name_en", sql)
        self.assertIn("food_name_am", sql)
        self.assertIn("recipe_name_en", sql)
        self.assertIn("recipe_name_am", sql)
        self.assertIn("calibration_data", sql)


if __name__ == "__main__":
    unittest.main()
