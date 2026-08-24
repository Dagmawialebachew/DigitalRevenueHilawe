from __future__ import annotations

import unittest
from pathlib import Path

from database.migrations.runner import discover_migrations
from meal_plan.constants import ServiceType
from meal_plan.pricing import Money, PriceKey, requires_manual_quote
from meal_plan.schema import REQUIRED_TABLES
from meal_plan.state_machine import InvalidTransition, UnauthorizedTransition, allowed_targets, require_transition
from meal_plan.states import ActorRole, IntakeState, OrderState


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "database" / "migrations"


class Phase1MigrationTests(unittest.TestCase):
    def test_first_migration_discovered(self):
        migrations = discover_migrations(MIGRATIONS)
        self.assertIn("0001", [m.version for m in migrations])

    def test_migration_is_additive_to_legacy_domain(self):
        sql = (MIGRATIONS / "0001_meal_plan_core.sql").read_text(encoding="utf-8").upper()
        forbidden = (
            "DROP TABLE",
            "TRUNCATE ",
            "DELETE FROM USERS",
            "DELETE FROM PAYMENTS",
            "ALTER TABLE USERS",
            "ALTER TABLE PAYMENTS",
            "ALTER TABLE PRODUCTS",
        )
        for token in forbidden:
            self.assertNotIn(token, sql)

    def test_required_tables_are_created(self):
        sql = (MIGRATIONS / "0001_meal_plan_core.sql").read_text(encoding="utf-8").lower()
        for table in REQUIRED_TABLES:
            self.assertIn(f"create table if not exists {table}", sql)

    def test_payment_model_supports_display_vs_bank_settlement(self):
        sql = (MIGRATIONS / "0001_meal_plan_core.sql").read_text(encoding="utf-8").lower()
        self.assertIn("expected_currency", sql)
        self.assertIn("settlement_currency", sql)
        self.assertIn("exchange_rate", sql)

    def test_intake_can_store_calculated_profile_separately_from_answers(self):
        sql = (MIGRATIONS / "0001_meal_plan_core.sql").read_text(encoding="utf-8").lower()
        self.assertIn("nutrition_profile jsonb", sql)


class Phase1StateMachineTests(unittest.TestCase):
    def test_health_review_stops_checkout(self):
        self.assertNotIn(IntakeState.CHECKOUT_READY, allowed_targets("intake", IntakeState.HEALTH_REVIEW_REQUIRED))
        require_transition("intake", IntakeState.HEALTH_REVIEW_REQUIRED, IntakeState.HEALTH_APPROVED, ActorRole.REVIEWER)
        with self.assertRaises(UnauthorizedTransition):
            require_transition("intake", IntakeState.HEALTH_REVIEW_REQUIRED, IntakeState.HEALTH_APPROVED, ActorRole.USER)

    def test_user_cannot_approve_plan(self):
        with self.assertRaises(UnauthorizedTransition):
            require_transition("order", OrderState.REVIEW_PENDING, OrderState.APPROVED, ActorRole.USER)
        require_transition("order", OrderState.REVIEW_PENDING, OrderState.APPROVED, ActorRole.REVIEWER)

    def test_invalid_skip_to_active_is_blocked(self):
        with self.assertRaises(InvalidTransition):
            require_transition("order", OrderState.PAYMENT_APPROVED, OrderState.ACTIVE, ActorRole.SYSTEM)

    def test_generation_failure_can_retry(self):
        require_transition("order", OrderState.GENERATION_FAILED, OrderState.GENERATION_QUEUED, ActorRole.SYSTEM)


class Phase1PricingTests(unittest.TestCase):
    def test_follow_up_only_30_days(self):
        PriceKey.build("ETHIOPIA", 30, ServiceType.FOLLOW_UP)
        with self.assertRaises(ValueError):
            PriceKey.build("ETHIOPIA", 14, ServiceType.FOLLOW_UP)

    def test_other_requires_manual_quote(self):
        self.assertTrue(requires_manual_quote("OTHER"))
        self.assertFalse(requires_manual_quote("UAE"))

    def test_money_validation(self):
        money = Money.build("29.00", "usd")
        self.assertEqual(money.currency, "USD")
        with self.assertRaises(ValueError):
            Money.build(-1, "ETB")


if __name__ == "__main__":
    unittest.main()


class Phase1StartupWiringTests(unittest.TestCase):
    def test_bot_runs_migrations_after_legacy_setup(self):
        bot_text = (ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertIn("await run_meal_plan_migrations()", bot_text)
        self.assertIn("MEAL_PLAN_RUN_MIGRATIONS", bot_text)

    def test_customer_meal_routes_are_feature_flagged_when_later_phases_wire_them(self):
        # Phase 1 established the storage layer. Later phases may wire routes, but
        # the public feature must remain guarded by MEAL_PLAN_ENABLED.
        runtime_text = (ROOT / "meal_plan" / "runtime.py").read_text(encoding="utf-8") if (ROOT / "meal_plan" / "runtime.py").exists() else ""
        bot_text = (ROOT / "bot.py").read_text(encoding="utf-8")
        if "setup_meal_plan_routes(app)" in bot_text:
            self.assertIn("MEAL_PLAN_ENABLED", runtime_text)
        else:
            self.assertNotIn("meal_plan_router", bot_text)
