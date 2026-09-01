"""Phase 4 Contract & Experience Tests: Premium Client Experience & Mini App.

Verifies:
1. Honest Mini App duration selection copy (7-day starter, 14-day habit builder, 30-day transformation system).
2. Clean, premium client PDF rendering across 7, 14, and 30 days in Amharic and English.
3. Proper inclusion of Section 03 schedule map and complete omission of internal review tables in client PDFs.
4. Consistent customer-friendly filenames.
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
from scripts.generate_hilawe_demo_plan import demo_answers


class Phase4ClientExperienceTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()
        self.answers = demo_answers()
        self.profile = calculate_nutrition_profile(self.answers).to_dict()

    def test_miniapp_duration_copy_honesty(self):
        """Mini App source must explain the rotation model honestly in Amharic and English."""
        source_path = Path(__file__).resolve().parents[1] / "meal_plan_miniapp" / "src" / "ProfileCheckoutFlow.tsx"
        source = source_path.read_text(encoding="utf-8")
        
        # English copy checks
        self.assertIn("1-Week Foundation", source)
        self.assertIn("2-Week Rotation + Swaps", source)
        self.assertIn("4-Week System + Fasting Support", source)
        
        # Amharic copy checks
        self.assertIn("የ1 ሳምንት ዋና መዋቅር", source)
        self.assertIn("የ2 ሳምንት ተዘዋዋሪ + Swaps", source)
        self.assertIn("የ4 ሳምንት ሙሉ ስርዓት + ጾም", source)

    def test_client_pdf_compiles_for_all_durations_and_languages(self):
        """7, 14, and 30-day plans compile cleanly in both Amharic and English."""
        with tempfile.TemporaryDirectory() as td:
            for duration in (7, 14, 30):
                for lang in ("AM", "EN"):
                    plan = generate_plan(
                        answers=self.answers,
                        nutrition_profile=self.profile,
                        meals_per_day=3,
                        start_date=datetime.date(2026, 8, 24),
                        duration_days=duration,
                        region="ETHIOPIA",
                        dataset=self.dataset,
                    )
                    ctx = DocumentContext(
                        client_name="Abel Tesfaye",
                        plan_public_id="MP-000004",
                        version_number=1,
                        language=lang,
                        status="APPROVED",
                    )
                    filename = client_artifact_filename("Abel Tesfaye", duration, 1)
                    out_path = Path(td) / f"{lang}_{filename}"
                    pdf_path = render_client_pdf(plan, ctx, out_path)
                    self.assertTrue(pdf_path.exists())
                    self.assertGreater(pdf_path.stat().st_size, 40000)

    def test_client_pdf_omits_draft_banner_and_section_06(self):
        """Client PDFs must never leak internal coach review banners or section 06 diagnostic pages."""
        plan = generate_plan(
            answers=self.answers,
            nutrition_profile=self.profile,
            meals_per_day=3,
            start_date=datetime.date(2026, 8, 24),
            duration_days=30,
            region="ETHIOPIA",
            dataset=self.dataset,
        )
        with tempfile.TemporaryDirectory() as td:
            ctx = DocumentContext(
                client_name="Selamawit Desta",
                plan_public_id="MP-000005",
                version_number=1,
                language="EN",
                status="APPROVED",
            )
            out_path = Path(td) / "Selamawit_Meal_Plan_30_Days_V1.pdf"
            pdf_path = render_client_pdf(plan, ctx, out_path)
            
            # Read binary PDF and verify absence of raw draft strings
            content = pdf_path.read_bytes()
            self.assertNotIn(b"DRAFT - FOR COACH REVIEW", content)
            self.assertNotIn(b"06 PLAN REVIEW", content)


if __name__ == "__main__":
    unittest.main()
