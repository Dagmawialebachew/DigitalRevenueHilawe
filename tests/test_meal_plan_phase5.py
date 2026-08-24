from __future__ import annotations

import os
import unittest
from decimal import Decimal
from pathlib import Path

from meal_plan.payment_rules import amount_matches, build_settlement
from meal_plan.runtime import auto_approve_payments, payment_review_chat_id, usd_settlement_mode

ROOT = Path(__file__).resolve().parents[1]


class PaymentSettlementTests(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in (
            "MEAL_PLAN_USD_SETTLEMENT_MODE", "MEAL_PLAN_USD_TO_ETB_RATE",
            "MEAL_PLAN_PAYMENT_AMOUNT_TOLERANCE", "MEAL_PLAN_AUTO_APPROVE_PAYMENTS",
            "MEAL_PLAN_PAYMENT_REVIEW_CHAT_ID", "ADMIN_PAYMENT_LOG_ID",
        )}

    def tearDown(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_etb_settlement_is_same_currency(self):
        settlement = build_settlement("1499", "ETB")
        self.assertEqual(settlement.expected_amount, Decimal("1499.00"))
        self.assertEqual(settlement.settlement_amount, Decimal("1499.00"))
        self.assertEqual(settlement.settlement_currency, "ETB")
        self.assertIsNone(settlement.exchange_rate)

    def test_usd_defaults_to_direct_usd_settlement(self):
        os.environ.pop("MEAL_PLAN_USD_SETTLEMENT_MODE", None)
        result = build_settlement("29", "USD")
        self.assertEqual(usd_settlement_mode(), "USD")
        self.assertEqual(result.settlement_amount, Decimal("29.00"))
        self.assertEqual(result.settlement_currency, "USD")

    def test_etb_conversion_requires_explicit_rate(self):
        os.environ["MEAL_PLAN_USD_SETTLEMENT_MODE"] = "ETB"
        os.environ.pop("MEAL_PLAN_USD_TO_ETB_RATE", None)
        with self.assertRaises(ValueError):
            build_settlement("29", "USD")

        os.environ["MEAL_PLAN_USD_TO_ETB_RATE"] = "150"
        result = build_settlement("29", "USD")
        self.assertEqual(result.settlement_amount, Decimal("4350.00"))
        self.assertEqual(result.exchange_rate, Decimal("150"))

    def test_amount_matching_uses_small_configurable_tolerance(self):
        os.environ["MEAL_PLAN_PAYMENT_AMOUNT_TOLERANCE"] = "1.00"
        self.assertTrue(amount_matches("1000", "1000.50"))
        self.assertFalse(amount_matches("1000", "1002.00"))

    def test_auto_approval_is_off_by_default(self):
        os.environ.pop("MEAL_PLAN_AUTO_APPROVE_PAYMENTS", None)
        self.assertFalse(auto_approve_payments())

    def test_payment_review_chat_prefers_dedicated_then_admin_log(self):
        os.environ["MEAL_PLAN_PAYMENT_REVIEW_CHAT_ID"] = "-1001"
        os.environ["ADMIN_PAYMENT_LOG_ID"] = "-1002"
        self.assertEqual(payment_review_chat_id(), -1001)
        os.environ.pop("MEAL_PLAN_PAYMENT_REVIEW_CHAT_ID", None)
        self.assertEqual(payment_review_chat_id(), -1002)


class Phase5SurfaceTests(unittest.TestCase):
    def test_payment_route_is_isolated(self):
        api = (ROOT / "meal_plan" / "api.py").read_text(encoding="utf-8")
        self.assertIn('/api/meal/payment/start', api)
        self.assertRegex(api, r'"phase"\s*:\s*(?:[5-9]|[1-9][0-9]+)')
        payment = (ROOT / "meal_plan" / "payment.py").read_text(encoding="utf-8")
        self.assertIn('MealPaymentState', payment)
        self.assertIn('meal_payments', (ROOT / "database" / "migrations" / "0001_meal_plan_core.sql").read_text(encoding="utf-8"))

    def test_legacy_workout_payment_handler_not_modified_by_phase5_design(self):
        source = (ROOT / "handlers" / "payment.py").read_text(encoding="utf-8")
        self.assertIn('router = Router(name="payment")', source)
        self.assertNotIn('mealpay_', source)

    def test_generation_queue_contract_remains_after_engine_phase(self):
        repo = (ROOT / "meal_plan" / "repository.py").read_text(encoding="utf-8")
        self.assertIn("state='GENERATION_QUEUED'", repo)
        self.assertIn("meal_generation_jobs", repo)
        self.assertTrue((ROOT / "meal_plan" / "generation" / "engine.py").exists())

    def test_payment_router_registered(self):
        bot = (ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertIn("meal_plan_payment_router", bot)
        self.assertIn("include_router(meal_plan_payment_router)", bot)

    def test_no_new_database_migration_required(self):
        migrations = sorted((ROOT / "database" / "migrations").glob("[0-9][0-9][0-9][0-9]_*.sql"))
        names = [p.name for p in migrations]
        self.assertIn("0001_meal_plan_core.sql", names)

    def test_frontend_is_phase5(self):
        import json
        package = json.loads((ROOT / "meal_plan_miniapp" / "package.json").read_text(encoding="utf-8"))
        major, minor, _ = [int(part) for part in package["version"].split(".")]
        self.assertGreaterEqual((major, minor), (0, 5))
        app = (ROOT / "meal_plan_miniapp" / "src" / "App.tsx").read_text(encoding="utf-8")
        self.assertIn("PaymentOrderFlow", app)
        checkout = (ROOT / "meal_plan_miniapp" / "src" / "ProfileCheckoutFlow.tsx").read_text(encoding="utf-8")
        self.assertIn("startPayment", checkout)
        self.assertIn("payment_accounts", checkout)

    def test_bank_surface_is_cbe_and_boa_only(self):
        payment = (ROOT / "meal_plan" / "payment.py").read_text(encoding="utf-8")
        self.assertIn('"code": "CBE"', payment)
        self.assertIn('"code": "BOA"', payment)
        self.assertNotIn('"code": "TELEBIRR"', payment)


if __name__ == "__main__":
    unittest.main()
