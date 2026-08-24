from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from aiohttp import web

from database.db import _encode_json, _init_connection
from meal_plan.api import _authenticate
from meal_plan.release_gate import collect_release_findings, release_report
from meal_plan.runtime import demo_bot_id, demo_mode
from scripts.meal_plan_acceptance import collect_acceptance

ROOT = Path(__file__).resolve().parents[1]


class Phase10DatabaseJsonCodecTests(unittest.IsolatedAsyncioTestCase):
    async def test_pool_codec_decodes_json_and_jsonb_to_python_values(self):
        calls = []

        class Connection:
            async def set_type_codec(self, type_name, **kwargs):
                calls.append((type_name, kwargs))

        await _init_connection(Connection())
        self.assertEqual([name for name, _kwargs in calls], ["json", "jsonb"])
        for _name, kwargs in calls:
            self.assertEqual(kwargs["decoder"]('{"answers":{"age":30}}'), {"answers": {"age": 30}})
            self.assertEqual(kwargs["format"], "text")

    def test_json_encoder_preserves_existing_serialized_repository_writes(self):
        serialized = '{"age":30}'
        self.assertEqual(_encode_json(serialized), serialized)
        self.assertEqual(json.loads(_encode_json({"age": 30})), {"age": 30})


class Phase10PublicAccessGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_admin_receives_structured_coming_soon_response(self):
        request = SimpleNamespace(app={"bot": SimpleNamespace(token="placeholder")})
        identity = SimpleNamespace(telegram_id=303)
        env = {
            "MEAL_PLAN_ENABLED": "true",
            "MEAL_PLAN_PUBLIC_ACCESS": "false",
            "ADMIN_IDS": "101,202",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "meal_plan.api.validate_telegram_init_data",
            return_value=identity,
        ):
            with self.assertRaises(web.HTTPForbidden) as raised:
                await _authenticate(request, {"init_data": "signed"})
        payload = json.loads(raised.exception.text)
        self.assertEqual(payload["error"]["code"], "MEAL_PLAN_COMING_SOON")

    async def test_admin_continues_through_the_existing_authenticated_path(self):
        request = SimpleNamespace(app={"bot": SimpleNamespace(token="placeholder")})
        identity = SimpleNamespace(telegram_id=202)
        env = {
            "MEAL_PLAN_ENABLED": "true",
            "MEAL_PLAN_PUBLIC_ACCESS": "false",
            "ADMIN_IDS": "101,202",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "meal_plan.api.validate_telegram_init_data",
            return_value=identity,
        ):
            result = await _authenticate(request, {"init_data": "signed"})
        self.assertIs(result, identity)


class Phase10RuntimeSafetyTests(unittest.TestCase):
    def test_demo_mode_is_explicit_and_defaults_off(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MEAL_PLAN_DEMO_MODE", None)
            self.assertFalse(demo_mode())
        with patch.dict(os.environ, {"MEAL_PLAN_DEMO_MODE": "true"}):
            self.assertTrue(demo_mode())

    def test_demo_bot_id_is_optional_and_validated(self):
        with patch.dict(os.environ, {"MEAL_PLAN_DEMO_BOT_ID": "abc"}):
            self.assertEqual(demo_bot_id(), 0)
        with patch.dict(os.environ, {"MEAL_PLAN_DEMO_BOT_ID": "123456"}):
            self.assertEqual(demo_bot_id(), 123456)

    def test_local_runner_requires_demo_mode_before_side_effects(self):
        source = (ROOT / "scripts" / "run_meal_plan_demo.py").read_text(encoding="utf-8")
        self.assertIn("if not demo_mode()", source)
        self.assertLess(source.index("if not demo_mode()"), source.index("await bot.get_me()"))
        self.assertLess(source.index("await bot.get_me()"), source.index("await bot.delete_webhook"))

    def test_local_runner_starts_both_workers(self):
        source = (ROOT / "scripts" / "run_meal_plan_demo.py").read_text(encoding="utf-8")
        self.assertIn("generation_worker_loop", source)
        self.assertIn("meal_plan_lifecycle_worker_loop", source)
        self.assertIn("lifecycle_worker_enabled()", source)

    def test_demo_bot_id_guard_happens_before_webhook_delete(self):
        source = (ROOT / "scripts" / "run_meal_plan_demo.py").read_text(encoding="utf-8")
        self.assertLess(source.index("does not match MEAL_PLAN_DEMO_BOT_ID"), source.index("await bot.delete_webhook"))

    def test_powershell_launcher_prefers_project_virtualenv(self):
        source = (ROOT / "run_full_demo.ps1").read_text(encoding="utf-8")
        self.assertIn('env\\Scripts\\python.exe', source)
        self.assertIn("Test-Path -LiteralPath $projectPython", source)


class Phase10ReleaseGateTests(unittest.TestCase):
    def base_env(self):
        return {
            "BOT_TOKEN": "placeholder",
            "DATABASE_URL": "postgresql://placeholder/db",
            "MEAL_PLAN_ENABLED": "true",
            "MEAL_PLAN_FRONTEND_URL": "https://meal.example.com",
            "FRONTEND_ORIGIN": "https://meal.example.com",
            "MEAL_PLAN_REVIEW_GROUP_ID": "-1001234567890",
            "MEAL_PLAN_REVIEWER_IDS": "123456",
            "MEAL_PLAN_GENERATION_WORKER_ENABLED": "true",
            "MEAL_PLAN_LIFECYCLE_WORKER_ENABLED": "true",
            "MEAL_PLAN_AUTO_APPROVE_PAYMENTS": "false",
            "MEAL_PLAN_DEMO_MODE": "true",
            "MEAL_PLAN_LOCAL_DEV_AUTH": "false",
            "VERIFY_API": "placeholder",
        }

    def test_full_demo_gate_can_be_ready_except_known_recipe_warning(self):
        with patch.dict(os.environ, self.base_env(), clear=False):
            report = release_report("demo", full_demo=True)
        blocking_codes = [item.code for item in report.findings if item.status == "BLOCK"]
        self.assertEqual(blocking_codes, [])
        self.assertTrue(report.ready)

    def test_production_blocks_demo_mode(self):
        env = self.base_env()
        with patch.dict(os.environ, env, clear=False):
            findings = {item.code: item for item in collect_release_findings("production")}
        self.assertEqual(findings["DEMO_MODE_OFF"].status, "BLOCK")

    def test_production_blocks_unapproved_recipe_calibration(self):
        env = self.base_env()
        env["MEAL_PLAN_DEMO_MODE"] = "false"
        with patch.dict(os.environ, env, clear=False):
            findings = {item.code: item for item in collect_release_findings("production")}
        self.assertEqual(findings["RECIPE_CALIBRATION"].status, "BLOCK")

    def test_positive_review_chat_id_is_blocked(self):
        env = self.base_env()
        env["MEAL_PLAN_REVIEW_GROUP_ID"] = "1234"
        with patch.dict(os.environ, env, clear=False):
            findings = {item.code: item for item in collect_release_findings("demo", full_demo=True)}
        self.assertEqual(findings["PRIVATE_GROUP_SHAPE"].status, "BLOCK")

    def test_release_gate_does_not_expose_secret_values(self):
        env = self.base_env()
        env["BOT_TOKEN"] = "ULTRA_SECRET_TOKEN_SHOULD_NEVER_APPEAR"
        with patch.dict(os.environ, env, clear=False):
            text = "\n".join(item.message for item in collect_release_findings("demo"))
        self.assertNotIn("ULTRA_SECRET_TOKEN_SHOULD_NEVER_APPEAR", text)

    def frontend_finding(self, *, mode="demo", demo="false", local_dev="false", url="", origin=None):
        env = self.base_env()
        env.update({
            "MEAL_PLAN_DEMO_MODE": demo,
            "MEAL_PLAN_LOCAL_DEV_AUTH": local_dev,
            "MEAL_PLAN_FRONTEND_URL": url,
            "FRONTEND_ORIGIN": url if origin is None else origin,
        })
        with patch.dict(os.environ, env, clear=True):
            findings = collect_release_findings(mode, full_demo=True)
        return {item.code: item for item in findings}

    def test_production_localhost_frontend_is_blocked(self):
        findings = self.frontend_finding(
            mode="production",
            demo="true",
            local_dev="true",
            url="http://127.0.0.1:5173",
        )
        self.assertEqual(findings["PUBLIC_FRONTEND"].status, "BLOCK")

    def test_demo_without_local_dev_auth_localhost_is_blocked(self):
        findings = self.frontend_finding(demo="true", url="http://localhost:5173")
        self.assertEqual(findings["PUBLIC_FRONTEND"].status, "BLOCK")

    def test_guarded_local_dev_accepts_127_loopback(self):
        findings = self.frontend_finding(demo="true", local_dev="true", url="http://127.0.0.1:5173")
        self.assertEqual(findings["LOCAL_DEV_FRONTEND"].status, "PASS")

    def test_guarded_local_dev_accepts_localhost(self):
        findings = self.frontend_finding(demo="true", local_dev="true", url="http://localhost:5173")
        self.assertEqual(findings["LOCAL_DEV_FRONTEND"].status, "PASS")

    def test_guarded_local_dev_rejects_arbitrary_http_host(self):
        findings = self.frontend_finding(demo="true", local_dev="true", url="http://some-public-host.com:5173")
        self.assertEqual(findings["LOCAL_DEV_FRONTEND"].status, "BLOCK")

    def test_hosted_https_demo_still_passes(self):
        findings = self.frontend_finding(demo="true", url="https://meal.example.com")
        self.assertEqual(findings["PUBLIC_FRONTEND"].status, "PASS")

    def test_local_dev_auth_without_demo_mode_is_blocked(self):
        findings = self.frontend_finding(local_dev="true", url="https://meal.example.com")
        self.assertEqual(findings["P9_LOCAL_DEV_AUTH_GUARD"].status, "BLOCK")

    def test_guarded_local_dev_rejects_non_loopback_cors_origin(self):
        findings = self.frontend_finding(
            demo="true",
            local_dev="true",
            url="http://127.0.0.1:5173",
            origin="http://some-public-host.com:5173",
        )
        self.assertEqual(findings["LOCAL_DEV_FRONTEND"].status, "BLOCK")


class Phase10AcceptanceAndSurfaceTests(unittest.TestCase):
    def test_acceptance_matrix_runs_without_documents(self):
        env = {
            "BOT_TOKEN": "placeholder",
            "DATABASE_URL": "postgresql://placeholder/db",
            "MEAL_PLAN_ENABLED": "true",
            "MEAL_PLAN_FRONTEND_URL": "https://meal.example.com",
            "MEAL_PLAN_REVIEW_GROUP_ID": "-1001234567890",
            "MEAL_PLAN_REVIEWER_IDS": "123456",
            "MEAL_PLAN_GENERATION_WORKER_ENABLED": "true",
            "MEAL_PLAN_LIFECYCLE_WORKER_ENABLED": "true",
            "MEAL_PLAN_AUTO_APPROVE_PAYMENTS": "false",
            "MEAL_PLAN_DEMO_MODE": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            checks = collect_acceptance(mode="demo", full_demo=True, documents=False, api_url=None)
        self.assertTrue(checks)
        self.assertFalse([c for c in checks if c.status == "BLOCK"])
        codes = {c.code for c in checks}
        self.assertTrue({"ENGINE_3X7", "ENGINE_4X14_VEGETARIAN", "ENGINE_5X30_FASTING", "ENGINE_ALLERGY_PATH"}.issubset(codes))

    def test_api_health_reports_phase10(self):
        source = (ROOT / "meal_plan" / "api.py").read_text(encoding="utf-8")
        self.assertIn('"phase": 10', source)

    def test_public_access_gate_runs_after_telegram_validation(self):
        source = (ROOT / "meal_plan" / "api.py").read_text(encoding="utf-8")
        authenticate = source[source.index("async def _authenticate"):source.index("async def _identity_user_intake")]
        self.assertLess(authenticate.index("validate_telegram_init_data"), authenticate.index("meal_plan_access_allowed"))
        self.assertIn("MEAL_PLAN_COMING_SOON", authenticate)

    def test_frontend_is_marked_one_point_zero(self):
        package = (ROOT / "meal_plan_miniapp" / "package.json").read_text(encoding="utf-8")
        self.assertIn('"version": "1.0.0"', package)

    def test_phase10_adds_no_database_migration(self):
        versions = sorted(path.name for path in (ROOT / "database" / "migrations").glob("[0-9][0-9][0-9][0-9]_*.sql"))
        self.assertEqual(versions, ["0001_meal_plan_core.sql", "0002_hilawe_nutrition_dataset.sql"])

    def test_acceptance_script_never_writes_database(self):
        source = (ROOT / "scripts" / "meal_plan_acceptance.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("asyncpg", source)
        self.assertNotIn("database_url", source)
        self.assertNotIn("insert into", source)


if __name__ == "__main__":
    unittest.main()
