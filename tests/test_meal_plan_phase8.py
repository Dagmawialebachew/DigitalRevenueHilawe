from __future__ import annotations

import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from meal_plan.plan_access import plan_payload, safe_local_pdf_path
from meal_plan.review_logic import parse_review_callback, review_card_text
from meal_plan.review_files import ReviewFileError, classify_review_filename, validate_review_file
from meal_plan.runtime import coach_username, generation_worker_interval_seconds, review_upload_max_bytes


class Phase8ReviewDeliveryTests(unittest.TestCase):
    def test_callback_parser_accepts_supported_actions(self):
        for action in ("approve", "regen", "replace", "client", "deliver"):
            self.assertEqual(parse_review_callback(f"mealreview:{action}:17"), (action, 17))

    def test_callback_parser_rejects_bad_payload(self):
        for value in ("", "mealreview:nope:1", "mealreview:approve:0", "other:approve:1", "mealreview:approve:x"):
            with self.assertRaises(ValueError):
                parse_review_callback(value)

    def test_review_keyboard_has_required_four_actions(self):
        source = (Path(__file__).parents[1] / "meal_plan" / "review_card.py").read_text(encoding="utf-8")
        for action in ("approve", "regen", "replace", "client"):
            self.assertIn(f"mealreview:{action}:{{plan_version_id}}", source)

    def test_review_card_escapes_client_html(self):
        row = {
            "plan_json": {"nutrition_targets": {"target_kcal": 2000, "protein_g": 150, "carbs_g": 220, "fat_g": 60}, "profile_summary": {"goal": "FAT_LOSS"}, "review": {}},
            "full_name": "A <B>", "username": "a_user", "user_id": 1, "order_id": 2,
            "order_public_id": "ord", "version_number": 1, "duration_days": 30, "meals_per_day": 4,
            "service_type": "PLAN", "start_date": "2026-08-24", "ends_on": "2026-09-22",
            "region": "ETHIOPIA", "country_name": None, "currency": "ETB", "amount": "1000",
            "source": "GENERATED", "detail_source": "STRUCTURED", "engine_version": "ENGINE", "dataset_version": "DATA",
        }
        text = review_card_text(row)
        self.assertIn("A &lt;B&gt;", text)
        self.assertNotIn("A <B>", text)
        self.assertIn("Nothing is sent to the client before approval", text)

    def test_manual_override_card_is_explicit(self):
        row = {
            "plan_json": {"nutrition_targets": {}, "profile_summary": {}, "review": {}}, "full_name": "Demo",
            "username": None, "user_id": 1, "order_id": 2, "order_public_id": "ord", "version_number": 2,
            "duration_days": 7, "meals_per_day": 3, "service_type": "PLAN", "start_date": "2026-08-24",
            "ends_on": "2026-08-30", "region": "ETHIOPIA", "country_name": None, "currency": "ETB", "amount": "1",
            "source": "MANUAL_REPLACEMENT", "detail_source": "DOCUMENT_OVERRIDE", "engine_version": "E", "dataset_version": "D",
        }
        self.assertIn("DOCUMENT OVERRIDE", review_card_text(row))

    def test_classifies_pdf_and_docx(self):
        self.assertEqual(classify_review_filename("plan.PDF", None), "PDF")
        self.assertEqual(classify_review_filename("plan.docx", None), "DOCX")
        self.assertEqual(classify_review_filename("upload.bin", "application/pdf"), "PDF")

    def test_rejects_other_replacement_types(self):
        with self.assertRaises(ReviewFileError):
            classify_review_filename("plan.exe", "application/octet-stream")

    def test_validates_pdf_signature(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "plan.pdf"
            path.write_bytes(b"%PDF-1.4\n%%EOF")
            result = validate_review_file(path, filename="plan.pdf")
            self.assertEqual(result.artifact_type, "PDF")
            self.assertEqual(len(result.sha256), 64)

    def test_rejects_fake_pdf(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "plan.pdf"
            path.write_bytes(b"not a pdf")
            with self.assertRaises(ReviewFileError):
                validate_review_file(path, filename="plan.pdf")

    def test_validates_minimal_docx_structure(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "plan.docx"
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("[Content_Types].xml", "<Types/>")
                zf.writestr("word/document.xml", "<document/>")
            result = validate_review_file(path, filename="plan.docx")
            self.assertEqual(result.artifact_type, "DOCX")

    def test_rejects_zip_that_is_not_docx(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "plan.docx"
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("random.txt", "x")
            with self.assertRaises(ReviewFileError):
                validate_review_file(path, filename="plan.docx")

    def test_replacement_size_limit_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "plan.pdf"
            path.write_bytes(b"%PDF-" + b"x" * 100)
            with self.assertRaises(ReviewFileError):
                validate_review_file(path, filename="plan.pdf", max_bytes=10)

    def test_worker_interval_is_bounded(self):
        with patch.dict(os.environ, {"MEAL_PLAN_GENERATION_WORKER_INTERVAL_SECONDS": "0"}):
            self.assertEqual(generation_worker_interval_seconds(), 1)
        with patch.dict(os.environ, {"MEAL_PLAN_GENERATION_WORKER_INTERVAL_SECONDS": "999"}):
            self.assertEqual(generation_worker_interval_seconds(), 60)

    def test_review_upload_limit_is_bounded(self):
        with patch.dict(os.environ, {"MEAL_PLAN_REVIEW_UPLOAD_MAX_MB": "999"}):
            self.assertEqual(review_upload_max_bytes(), 50 * 1024 * 1024)

    def test_coach_username_normalization(self):
        with patch.dict(os.environ, {"MEAL_PLAN_COACH_USERNAME": "CoachExample"}):
            self.assertEqual(coach_username(), "@CoachExample")

    def test_pdf_download_path_cannot_escape_artifact_root(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            root = Path(td)
            inside = root / "MP" / "v1" / "plan.pdf"
            inside.parent.mkdir(parents=True)
            inside.write_bytes(b"%PDF-1.4")
            out = Path(outside) / "secret.pdf"
            out.write_bytes(b"%PDF-1.4")
            with patch.dict(os.environ, {"MEAL_PLAN_ARTIFACT_ROOT": str(root)}):
                self.assertEqual(safe_local_pdf_path(str(inside)), inside.resolve())
                self.assertIsNone(safe_local_pdf_path(str(out)))

    def testplan_payload_does_not_expose_storage_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pdf = root / "plan.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            with patch.dict(os.environ, {"MEAL_PLAN_ARTIFACT_ROOT": str(root), "MEAL_PLAN_COACH_USERNAME": "coach"}):
                payload = plan_payload({
                    "version_number": 1, "status": "DELIVERED", "detail_source": "STRUCTURED",
                    "approved_at": None, "delivered_at": None, "pdf_storage_key": str(pdf),
                    "docx_artifact_id": 4,
                })
            self.assertTrue(payload["pdf_available"])
            self.assertNotIn("pdf_storage_key", payload)
            self.assertEqual(payload["coach_username"], "@coach")

    def test_review_repository_uses_skip_locked_and_idempotency(self):
        source = (Path(__file__).parents[1] / "meal_plan" / "review_repository.py").read_text(encoding="utf-8")
        self.assertIn("FOR UPDATE SKIP LOCKED", source)
        self.assertIn("idempotency_key", source)
        self.assertIn("MANUAL_REPLACEMENT", source)
        self.assertIn("DOCUMENT_OVERRIDE", source)

    def test_approval_requires_both_review_artifacts(self):
        source = (Path(__file__).parents[1] / "meal_plan" / "review_repository.py").read_text(encoding="utf-8")
        self.assertIn("Both DOCX and PDF artifacts are required before approval", source)

    def test_second_replacement_cannot_start_while_one_is_in_review(self):
        source = (Path(__file__).parents[1] / "meal_plan" / "review_repository.py").read_text(encoding="utf-8")
        self.assertIn("A replacement version is already waiting for Coach review", source)

    def test_mini_app_unlock_is_recorded_before_telegram_send(self):
        source = (Path(__file__).parents[1] / "meal_plan" / "delivery.py").read_text(encoding="utf-8")
        mini_pos = source.index('mark_delivery_sent(plan_version_id, "MINI_APP")')
        telegram_pos = source.index('bot.send_document(order["user_id"]')
        self.assertLess(mini_pos, telegram_pos)

    def test_delivery_requires_both_channels_before_active(self):
        source = (Path(__file__).parents[1] / "meal_plan" / "review_repository.py").read_text(encoding="utf-8")
        self.assertIn('by_channel.get("TELEGRAM_DOCUMENT") != "SENT"', source)
        self.assertIn('by_channel.get("MINI_APP") != "SENT"', source)
        self.assertIn("state='ACTIVE'", source)


if __name__ == "__main__":
    unittest.main()
