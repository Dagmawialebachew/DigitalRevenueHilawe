from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.meal_plan_readiness import collect_checks

from meal_plan.followup_policy import (
    CheckinValidationError,
    apply_revision_payload,
    decide_revision,
    validate_checkin_answers,
)
from meal_plan.runtime import (
    checkin_hour,
    checkin_missed_after_hours,
    delivery_retry_limit,
    followup_auto_revision_enabled,
    lifecycle_interval_seconds,
    renewal_lead_days,
    stale_job_minutes,
)

ROOT = Path(__file__).parents[1]


def valid_checkin(**updates):
    data = {
        "current_weight_kg": 80.0,
        "adherence_percent": 90,
        "hunger_rating": 3,
        "energy_rating": 3,
        "digestion_rating": 3,
        "training_rating": 3,
        "health_change": False,
        "health_change_notes": "",
        "foods_to_avoid": "",
        "foods_to_prioritize": "",
        "notes": "",
    }
    data.update(updates)
    return data


class Phase9FollowUpPolicyTests(unittest.TestCase):
    def test_checkin_validation_accepts_bounded_values(self):
        result = validate_checkin_answers(valid_checkin(current_weight_kg=79.4, adherence_percent=85))
        self.assertEqual(result["current_weight_kg"], 79.4)
        self.assertEqual(result["adherence_percent"], 85)

    def test_health_change_requires_notes(self):
        with self.assertRaises(CheckinValidationError):
            validate_checkin_answers(valid_checkin(health_change=True, health_change_notes=""))

    def test_rating_is_fail_closed(self):
        with self.assertRaises(CheckinValidationError):
            validate_checkin_answers(valid_checkin(energy_rating=6))

    def test_health_change_blocks_automation(self):
        decision = decide_revision(
            baseline_answers={"current_weight_kg": 80, "primary_goal": "FAT_LOSS"},
            checkin_answers=valid_checkin(health_change=True, health_change_notes="new medication"),
        )
        self.assertEqual(decision.action, "HEALTH_REVIEW_REQUIRED")
        self.assertEqual(decision.kcal_delta, 0)
        self.assertEqual(decision.answer_patch, {})

    def test_low_adherence_does_not_cut_calories(self):
        decision = decide_revision(
            baseline_answers={"current_weight_kg": 80, "primary_goal": "FAT_LOSS"},
            checkin_answers=valid_checkin(current_weight_kg=80.5, adherence_percent=50),
        )
        self.assertEqual(decision.action, "NO_REVISION")
        self.assertEqual(decision.kcal_delta, 0)

    def test_fat_loss_stall_is_conservative_minus_100(self):
        decision = decide_revision(
            baseline_answers={"current_weight_kg": 80, "primary_goal": "FAT_LOSS"},
            checkin_answers=valid_checkin(current_weight_kg=80.0, adherence_percent=90),
        )
        self.assertEqual(decision.action, "QUEUE_REVISION")
        self.assertEqual(decision.kcal_delta, -100)

    def test_fat_loss_fast_drop_can_restore_100(self):
        decision = decide_revision(
            baseline_answers={"current_weight_kg": 80, "primary_goal": "FAT_LOSS"},
            checkin_answers=valid_checkin(current_weight_kg=78.8, adherence_percent=90),
        )
        self.assertEqual(decision.kcal_delta, 100)

    def test_muscle_gain_stall_is_plus_100(self):
        decision = decide_revision(
            baseline_answers={"current_weight_kg": 80, "primary_goal": "MUSCLE_GAIN"},
            checkin_answers=valid_checkin(current_weight_kg=80.0, adherence_percent=90),
        )
        self.assertEqual(decision.kcal_delta, 100)

    def test_food_feedback_queues_revision_without_calorie_change(self):
        decision = decide_revision(
            baseline_answers={"current_weight_kg": 80, "primary_goal": "RECOMPOSITION", "disliked_foods_other": "okra"},
            checkin_answers=valid_checkin(foods_to_avoid="tuna"),
        )
        self.assertEqual(decision.action, "QUEUE_REVISION")
        self.assertEqual(decision.kcal_delta, 0)
        self.assertIn("tuna", decision.answer_patch["disliked_foods_other"])
        self.assertIn("okra", decision.answer_patch["disliked_foods_other"])

    def test_revision_payload_changes_carbs_not_protein_or_fat(self):
        answers, profile, context = apply_revision_payload(
            answers={"liked_foods_other": "injera"},
            nutrition_profile={"target_kcal": 2000, "protein_g": 150, "fat_g": 60, "carbs_g": 215},
            payload={"revision": {"kcal_delta": -100, "answer_patch": {"liked_foods_other": "injera, rice"}, "week_number": 2}},
        )
        self.assertEqual(profile["target_kcal"], 1900.0)
        self.assertEqual(profile["carbs_g"], 190.0)
        self.assertEqual(profile["protein_g"], 150)
        self.assertEqual(profile["fat_g"], 60)
        self.assertEqual(answers["liked_foods_other"], "injera, rice")
        self.assertEqual(context["week_number"], 2)

    def test_revision_payload_caps_untrusted_delta(self):
        _answers, profile, context = apply_revision_payload(
            answers={},
            nutrition_profile={"target_kcal": 2000, "protein_g": 150, "fat_g": 60, "carbs_g": 215},
            payload={"revision": {"kcal_delta": -9999}},
        )
        self.assertEqual(profile["target_kcal"], 1850.0)
        self.assertEqual(context["kcal_delta"], -150)


class Phase9RuntimeTests(unittest.TestCase):
    def test_lifecycle_interval_is_bounded(self):
        with patch.dict(os.environ, {"MEAL_PLAN_LIFECYCLE_INTERVAL_SECONDS": "1"}):
            self.assertEqual(lifecycle_interval_seconds(), 15)
        with patch.dict(os.environ, {"MEAL_PLAN_LIFECYCLE_INTERVAL_SECONDS": "99999"}):
            self.assertEqual(lifecycle_interval_seconds(), 3600)

    def test_checkin_hour_is_bounded(self):
        with patch.dict(os.environ, {"MEAL_PLAN_CHECKIN_HOUR": "99"}):
            self.assertEqual(checkin_hour(), 23)

    def test_missed_window_is_at_least_one_day(self):
        with patch.dict(os.environ, {"MEAL_PLAN_CHECKIN_MISSED_AFTER_HOURS": "1"}):
            self.assertEqual(checkin_missed_after_hours(), 24)

    def test_renewal_lead_is_bounded(self):
        with patch.dict(os.environ, {"MEAL_PLAN_RENEWAL_LEAD_DAYS": "90"}):
            self.assertEqual(renewal_lead_days(), 14)

    def test_stale_job_recovery_window_is_bounded(self):
        with patch.dict(os.environ, {"MEAL_PLAN_STALE_JOB_MINUTES": "1"}):
            self.assertEqual(stale_job_minutes(), 10)

    def test_delivery_retry_limit_is_bounded(self):
        with patch.dict(os.environ, {"MEAL_PLAN_DELIVERY_RETRY_LIMIT": "99"}):
            self.assertEqual(delivery_retry_limit(), 25)

    def test_auto_revision_defaults_true_but_is_switchable(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MEAL_PLAN_FOLLOWUP_AUTO_REVISION_ENABLED", None)
            self.assertTrue(followup_auto_revision_enabled())
        with patch.dict(os.environ, {"MEAL_PLAN_FOLLOWUP_AUTO_REVISION_ENABLED": "false"}):
            self.assertFalse(followup_auto_revision_enabled())


class Phase9ReadinessTests(unittest.TestCase):
    def test_demo_readiness_never_requires_production_workers(self):
        with patch.dict(os.environ, {
            "BOT_TOKEN": "x",
            "DATABASE_URL": "postgresql://example",
            "MEAL_PLAN_ENABLED": "false",
            "MEAL_PLAN_REVIEW_GROUP_ID": "-1001",
            "MEAL_PLAN_REVIEWER_IDS": "123",
            "MEAL_PLAN_GENERATION_WORKER_ENABLED": "false",
            "MEAL_PLAN_LIFECYCLE_WORKER_ENABLED": "false",
        }, clear=False):
            statuses = {c.code: c.status for c in collect_checks("demo")}
        self.assertEqual(statuses["FEATURE_FLAG"], "WARN")
        self.assertEqual(statuses["GENERATION_WORKER"], "WARN")
        self.assertEqual(statuses["LIFECYCLE_WORKER"], "WARN")

    def test_production_readiness_blocks_legacy_verify_fallback(self):
        env = {
            "BOT_TOKEN": "x",
            "DATABASE_URL": "postgresql://example",
            "MEAL_PLAN_ENABLED": "true",
            "MEAL_PLAN_FRONTEND_URL": "https://example.com",
            "MEAL_PLAN_REVIEW_GROUP_ID": "-1001",
            "MEAL_PLAN_REVIEWER_IDS": "123",
            "MEAL_PLAN_GENERATION_WORKER_ENABLED": "true",
            "MEAL_PLAN_LIFECYCLE_WORKER_ENABLED": "true",
            "MEAL_PLAN_AUTO_APPROVE_PAYMENTS": "false",
            "VERIFY_API": "",
        }
        with patch.dict(os.environ, env, clear=False):
            checks = {c.code: c for c in collect_checks("production")}
        self.assertEqual(checks["VERIFY_API_ENV"].status, "BLOCK")
        self.assertNotIn("secret", checks["VERIFY_API_ENV"].message.lower())


class Phase9SurfaceAndSafetyTests(unittest.TestCase):
    def test_phase9_api_has_followup_and_renewal_routes(self):
        source = (ROOT / "meal_plan" / "api.py").read_text(encoding="utf-8")
        self.assertIn('/api/meal/followup/checkin', source)
        self.assertIn('/api/meal/renewal/start', source)
        self.assertRegex(source, r'"phase"\s*:\s*(?:9|[1-9][0-9]+)')

    def test_renewal_intake_is_fresh_not_prefilled(self):
        source = (ROOT / "meal_plan" / "followup_repository.py").read_text(encoding="utf-8")
        insert = "INSERT INTO meal_intakes(public_id,user_id,language,state,source,current_step)"
        self.assertIn(insert, source)
        self.assertNotIn("previous_answers", source)
        self.assertIn("RENEWAL:", source)

    def test_followup_creates_four_weekly_checkins_idempotently(self):
        source = (ROOT / "meal_plan" / "followup_repository.py").read_text(encoding="utf-8")
        self.assertIn("for week in range(1, 5)", source)
        self.assertIn("ON CONFLICT(order_id,week_number) DO NOTHING", source)
        self.assertIn("week * 7 - 1", source)

    def test_revision_generation_does_not_take_active_order_offline(self):
        source = (ROOT / "meal_plan" / "review_repository.py").read_text(encoding="utf-8")
        self.assertIn('if job["job_type"] == "REVISION"', source)
        self.assertIn('{"ACTIVE", "RENEWAL_DUE"}', source)
        self.assertIn("already-approved plan remains ACTIVE/RENEWAL_DUE", source)

    def test_revision_still_requires_coach_review(self):
        source = (ROOT / "meal_plan" / "generation" / "pipeline.py").read_text(encoding="utf-8")
        self.assertIn("review_keyboard(version[\"id\"])", source)
        review = (ROOT / "meal_plan" / "review_repository.py").read_text(encoding="utf-8")
        self.assertIn("Both DOCX and PDF artifacts are required before approval", review)

    def test_health_change_card_says_automation_blocked(self):
        source = (ROOT / "meal_plan" / "followup.py").read_text(encoding="utf-8")
        self.assertIn("AUTOMATION BLOCKED", source)
        self.assertIn("No automatic revision is queued", source)

    def test_stale_jobs_use_skip_locked_recovery(self):
        source = (ROOT / "meal_plan" / "followup_repository.py").read_text(encoding="utf-8")
        self.assertIn("FOR UPDATE SKIP LOCKED", source)
        self.assertIn("STALE_WORKER_RECOVERY", source)

    def test_delivery_retry_only_targets_current_approved_versions(self):
        source = (ROOT / "meal_plan" / "review_repository.py").read_text(encoding="utf-8")
        self.assertIn("list_delivery_retry_versions", source)
        self.assertIn("o.current_plan_version_id=v.id", source)
        self.assertIn("d.status IN ('PENDING','FAILED')", source)

    def test_bot_starts_lifecycle_worker_only_by_flag(self):
        source = (ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertIn("lifecycle_worker_enabled", source)
        self.assertIn("meal_plan_lifecycle_worker_loop", source)

    def test_frontend_has_weekly_checkin_and_renewal_ui(self):
        source = (ROOT / "meal_plan_miniapp" / "src" / "App.tsx").read_text(encoding="utf-8")
        self.assertIn("FollowUpCheckinCard", source)
        self.assertIn("startRenewal", source)
        self.assertIn("healthChange", source)

    def test_generation_pipeline_applies_revision_payload_before_engine(self):
        source = (ROOT / "meal_plan" / "generation" / "pipeline.py").read_text(encoding="utf-8")
        apply_pos = source.index("apply_revision_payload")
        generate_pos = source.index("plan = generate_plan")
        self.assertLess(apply_pos, generate_pos)
        self.assertIn('plan["revision_context"]', source)

    def test_approved_pdf_has_telegram_durable_fallback(self):
        source = (ROOT / "meal_plan" / "api.py").read_text(encoding="utf-8")
        self.assertIn('pdf_telegram_file_id', source)
        self.assertIn('download_file(telegram_file.file_path', source)
        self.assertIn('body.startswith(b"%PDF")', source)

    def test_plan_access_reports_telegram_archived_pdf_available(self):
        source = (ROOT / "meal_plan" / "plan_access.py").read_text(encoding="utf-8")
        self.assertIn('pdf_path or plan_row.get("pdf_telegram_file_id")', source)

    def test_artifact_is_marked_local_telegram_after_upload(self):
        source = (ROOT / "meal_plan" / "review_repository.py").read_text(encoding="utf-8")
        self.assertIn("LOCAL_TELEGRAM", source)


if __name__ == "__main__":
    unittest.main()
