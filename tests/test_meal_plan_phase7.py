from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from meal_plan.documents import DocumentContext, render_plan_artifacts
from meal_plan.documents.helpers import artifact_basename, safe_slug
from meal_plan.generation.engine import generate_plan
from meal_plan.nutrition_targets import calculate_nutrition_profile
from scripts.generate_hilawe_demo_plan import demo_answers


class Phase7DocumentsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        answers = demo_answers()
        cls.plan = generate_plan(
            answers=answers,
            nutrition_profile=calculate_nutrition_profile(answers).to_dict(),
            meals_per_day=3,
            start_date=__import__("datetime").date(2026, 8, 24),
            duration_days=7,
            region="ETHIOPIA",
        )

    def test_safe_filename_does_not_leak_path_chars(self):
        self.assertEqual(safe_slug("../A/B\\C"), "A-B-C")
        name = artifact_basename("MP-001", "Demo / Client", 2)
        self.assertEqual(name, "MP-001-Demo-Client-V2")

    def test_render_artifact_pair_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            context = DocumentContext(
                client_name="Abel Demo",
                plan_public_id="MP-TEST-0001",
                version_number=1,
                language="AM",
                client_profile={"current_weight_kg": 75.4, "target_weight_kg": 72.0},
                hydration_target_l=2.6,
            )
            result = render_plan_artifacts(self.plan, context, output_root=td)
            self.assertTrue(result.docx.path.exists())
            self.assertTrue(result.pdf.path.exists())
            self.assertTrue(result.manifest_path.exists())
            self.assertGreater(result.docx.byte_size, 10_000)
            self.assertGreater(result.pdf.byte_size, 10_000)
            self.assertEqual(len(result.docx.sha256), 64)
            self.assertEqual(len(result.pdf.sha256), 64)
            self.assertTrue(result.pdf.path.read_bytes().startswith(b"%PDF"))
            self.assertTrue(zipfile.is_zipfile(result.docx.path))

            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["plan_public_id"], "MP-TEST-0001")
            self.assertEqual(manifest["version_number"], 1)
            self.assertEqual(manifest["status"], "DRAFT_FOR_REVIEW")
            self.assertEqual(manifest["artifacts"]["PDF"]["sha256"], result.pdf.sha256)

    def test_docx_contains_amharic_and_review_language(self):
        with tempfile.TemporaryDirectory() as td:
            context = DocumentContext(
                client_name="Abel Demo",
                plan_public_id="MP-AM-0001",
                language="AM",
            )
            result = render_plan_artifacts(self.plan, context, output_root=td)
            with zipfile.ZipFile(result.docx.path) as zf:
                xml = zf.read("word/document.xml").decode("utf-8")
            self.assertIn("የግል የምግብ ፕላን", xml)
            self.assertIn("ረቂቅ", xml)
            self.assertIn("እንጀራ", xml)

    def test_document_generation_never_marks_auto_delivery(self):
        self.assertFalse(bool((self.plan.get("policy") or {}).get("auto_delivery")))
        self.assertTrue(bool((self.plan.get("review") or {}).get("required")))


if __name__ == "__main__":
    unittest.main()
