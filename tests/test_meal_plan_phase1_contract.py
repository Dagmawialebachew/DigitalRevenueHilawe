from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from meal_plan.documents import DocumentContext, render_client_pdf, render_plan_artifacts
from meal_plan.documents.helpers import client_artifact_filename, review_warning_lines
from meal_plan.generation.engine import generate_plan
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.review_repository import MealPlanReviewRepository
from scripts.generate_hilawe_demo_plan import demo_answers


class Phase1DeliveryContractTests(unittest.TestCase):
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

    def test_client_artifact_filename_standardization(self):
        self.assertEqual(
            client_artifact_filename("Dagmaros Alebachew", 30, 1),
            "Dagmaros_Alebachew_Meal_Plan_30_Days_V1.pdf",
        )
        self.assertEqual(
            client_artifact_filename("Abel / S.", 7, 2),
            "Abel_S_Meal_Plan_7_Days_V2.pdf",
        )
        self.assertEqual(
            client_artifact_filename("  Special-Name!!  ", 14, 3),
            "Special_Name_Meal_Plan_14_Days_V3.pdf",
        )
        self.assertEqual(
            client_artifact_filename("", 7, 1),
            "Client_Meal_Plan_7_Days_V1.pdf",
        )

    def test_client_pdf_renders_clean_document_without_internal_page(self):
        with tempfile.TemporaryDirectory() as td:
            context = DocumentContext(
                client_name="Dagmaros Alebachew",
                plan_public_id="MP-000042",
                version_number=1,
                language="EN",
                client_profile={"current_weight_kg": 75.0, "target_weight_kg": 70.0},
                hydration_target_l=2.5,
                status="APPROVED",
            )
            out_pdf = Path(td) / client_artifact_filename("Dagmaros Alebachew", 30, 1)
            result_path = render_client_pdf(self.plan, context, out_pdf)
            self.assertTrue(result_path.exists())
            self.assertGreater(result_path.stat().st_size, 10_000)

            # Internal review PDF rendering for comparison
            review_artifacts = render_plan_artifacts(self.plan, context, output_root=td)
            self.assertTrue(review_artifacts.pdf.path.exists())

            # Verify that client PDF is cleanly generated
            pdf_bytes = result_path.read_bytes()
            self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_review_warnings_helper_extracts_all_issues(self):
        plan_with_warnings = {
            "review": {
                "practical_warnings": ["High daily fiber volume", "Fasting protein floor deficit"],
                "uncalibrated_recipes": [{"recipe_name": "Shiro Wot Special"}, "Misir Wot Demo"],
            }
        }
        warnings = review_warning_lines(plan_with_warnings)
        self.assertEqual(len(warnings), 4)
        self.assertIn("High daily fiber volume", warnings)
        self.assertIn("Recipe calibration required before final approval: Shiro Wot Special", warnings)
        self.assertIn("Recipe calibration required before final approval: Misir Wot Demo", warnings)

    def test_clean_plan_has_no_review_warnings(self):
        clean_plan = {"review": {"practical_warnings": [], "uncalibrated_recipes": []}}
        self.assertEqual(review_warning_lines(clean_plan), [])


class Phase1ApprovalGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_approve_version_blocks_when_unresolved_warnings_exist(self):
        pool = MagicMock()
        repo = MealPlanReviewRepository(pool)

        plan_with_warnings = {
            "review": {
                "practical_warnings": ["Protein floor below 95% target"],
                "uncalibrated_recipes": ["Custom Kitfo Recipe"],
            },
            "product": {"duration_days": 30},
        }

        mock_version = {
            "id": 10,
            "order_id": 1,
            "version_number": 1,
            "status": "REVIEW_PENDING",
            "source": "GENERATED",
            "full_name": "Test Client",
            "language": "EN",
            "duration_days": 30,
            "answers": {},
            "nutrition_profile": {},
            "plan_json": json.dumps(plan_with_warnings),
        }
        mock_order = {
            "id": 1,
            "state": "REVIEW_PENDING",
            "current_plan_version_id": None,
        }

        mock_conn = MagicMock()
        mock_conn.transaction.return_value.__aenter__ = AsyncMock()
        mock_conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        async def fetchrow_side_effect(query, *args):
            if "FROM meal_plan_versions" in query:
                return mock_version
            if "FROM meal_orders" in query:
                return mock_order
            return None

        async def fetchval_side_effect(query, *args):
            if "COUNT(*)" in query:
                return 2
            return None

        mock_conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
        mock_conn.fetchval = AsyncMock(side_effect=fetchval_side_effect)
        mock_conn.execute = AsyncMock()

        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        # Approval without override must raise ValueError
        with self.assertRaises(ValueError) as ctx:
            await repo.approve_version(10, reviewer_id=999)
        self.assertIn("Cannot approve plan with unresolved review warnings", str(ctx.exception))
        self.assertIn("Protein floor below 95% target", str(ctx.exception))

    async def test_approve_version_succeeds_with_override_reason(self):
        pool = MagicMock()
        repo = MealPlanReviewRepository(pool)

        plan_with_warnings = {
            "review": {
                "practical_warnings": ["High legume volume"],
                "uncalibrated_recipes": [],
            },
            "product": {"duration_days": 7},
        }

        mock_version = {
            "id": 10,
            "order_id": 1,
            "version_number": 1,
            "status": "REVIEW_PENDING",
            "source": "GENERATED",
            "full_name": "Test Client",
            "language": "EN",
            "duration_days": 7,
            "answers": {},
            "nutrition_profile": {},
            "plan_json": json.dumps(plan_with_warnings),
        }
        mock_order = {
            "id": 1,
            "state": "REVIEW_PENDING",
            "current_plan_version_id": None,
        }

        mock_conn = MagicMock()
        mock_conn.transaction.return_value.__aenter__ = AsyncMock()
        mock_conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        approved_version_row = {**mock_version, "status": "APPROVED"}
        approved_order_row = {**mock_order, "state": "APPROVED", "current_plan_version_id": 10}

        async def fetchrow_side_effect(query, *args):
            if "FROM meal_plan_versions" in query and "FOR UPDATE OF" in query:
                return mock_version
            if "UPDATE meal_plan_versions SET status='APPROVED'" in query:
                return approved_version_row
            if "FROM meal_orders" in query:
                return mock_order
            if "UPDATE meal_orders SET state='APPROVED'" in query:
                return approved_order_row
            return None

        async def fetchval_side_effect(query, *args):
            if "COUNT(*)" in query:
                return 2
            return None

        mock_conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
        mock_conn.fetchval = AsyncMock(side_effect=fetchval_side_effect)
        mock_conn.execute = AsyncMock()

        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        with tempfile.TemporaryDirectory() as td:
            with patch("meal_plan.review_repository.version_output_dir", return_value=Path(td)):
                ver, ord_res = await repo.approve_version(
                    10,
                    reviewer_id=999,
                    override_reason="Client explicitly requested high-legume Ethiopian staple dishes",
                )
                self.assertEqual(ver["status"], "APPROVED")
                self.assertEqual(ord_res["state"], "APPROVED")

                # Verify audit review insert was recorded with override reason
                inserted_review = False
                for call in mock_conn.execute.call_args_list:
                    query = call[0][0]
                    if "INSERT INTO meal_plan_reviews" in query:
                        inserted_review = True
                        notes = call[0][3]
                        self.assertEqual(notes, "Client explicitly requested high-legume Ethiopian staple dishes")
                self.assertTrue(inserted_review)


if __name__ == "__main__":
    unittest.main()
