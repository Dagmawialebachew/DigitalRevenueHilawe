"""Tests for admin-only /reset meal plan state management."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from meal_plan.admin_reset import (
    handle_admin_reset_command,
    is_admin_user,
    reset_user_meal_plan_data,
)


class FakeConnection:
    def __init__(self, fetchval_map=None):
        self.fetchval_map = fetchval_map or {
            "meal_intakes": 1,
            "meal_orders": 1,
            "meal_payments": 2,
            "meal_checkins": 0,
        }
        self.executed_sqls = []

    async def fetchval(self, query: str, *args):
        for table, count in self.fetchval_map.items():
            if f"FROM {table}" in query:
                return count
        return 0

    async def execute(self, query: str, *args):
        self.executed_sqls.append((query.strip(), args))


class FakeTransactionContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        pass


class FakeAcquireContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        pass


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return FakeAcquireContext(self.conn)


class FakeDatabase:
    def __init__(self, pool):
        self._pool = pool


class TestAdminReset(unittest.IsolatedAsyncioTestCase):
    def test_is_admin_user_detection(self):
        fake_settings = MagicMock()
        fake_settings.ADMIN_IDS = [111, 222]

        with patch("meal_plan.admin_reset.settings", fake_settings), patch(
            "meal_plan.admin_reset.admin_ids", return_value=(333,)
        ):
            self.assertTrue(is_admin_user(111))
            self.assertTrue(is_admin_user(222))
            self.assertTrue(is_admin_user("333"))
            self.assertFalse(is_admin_user(999))
            self.assertFalse(is_admin_user(None))
            self.assertFalse(is_admin_user("invalid"))

    async def test_reset_user_meal_plan_data_queries(self):
        fake_conn = FakeConnection(
            fetchval_map={
                "meal_intakes": 2,
                "meal_orders": 1,
                "meal_payments": 3,
                "meal_checkins": 1,
            }
        )
        fake_conn.transaction = lambda: FakeTransactionContext(fake_conn)
        pool = FakePool(fake_conn)

        user_id = 555001
        counts = await reset_user_meal_plan_data(pool, user_id)

        self.assertEqual(counts["intakes"], 2)
        self.assertEqual(counts["orders"], 1)
        self.assertEqual(counts["payments"], 3)
        self.assertEqual(counts["checkins"], 1)

        # Check all expected tables were targeted with user_id
        executed = " ".join(sql for sql, _ in fake_conn.executed_sqls)
        self.assertIn("UPDATE meal_orders SET current_plan_version_id = NULL", executed)
        self.assertIn("DELETE FROM meal_revision_requests", executed)
        self.assertIn("DELETE FROM meal_checkins", executed)
        self.assertIn("DELETE FROM meal_deliveries", executed)
        self.assertIn("DELETE FROM meal_plan_reviews", executed)
        self.assertIn("DELETE FROM meal_plan_artifacts", executed)
        self.assertIn("DELETE FROM meal_generation_jobs", executed)
        self.assertIn("DELETE FROM meal_plan_versions", executed)
        self.assertIn("DELETE FROM meal_payments", executed)
        self.assertIn("DELETE FROM meal_orders", executed)
        self.assertIn("DELETE FROM meal_quotes", executed)
        self.assertIn("DELETE FROM meal_health_reviews", executed)
        self.assertIn("DELETE FROM meal_intakes", executed)
        self.assertIn("DELETE FROM meal_audit_events", executed)

    async def test_handle_admin_reset_blocks_unauthorized_user(self):
        message = AsyncMock()
        message.from_user = MagicMock(id=999999)
        message.text = "/reset"

        state = AsyncMock()
        db = FakeDatabase(None)

        fake_settings = MagicMock()
        fake_settings.ADMIN_IDS = [111]

        with patch("meal_plan.admin_reset.settings", fake_settings), patch(
            "meal_plan.admin_reset.admin_ids", return_value=()
        ):
            await handle_admin_reset_command(message, state, db)

        state.clear.assert_not_called()
        message.answer.assert_not_called()

    async def test_handle_admin_reset_executes_for_authorized_admin(self):
        admin_id = 777123
        message = AsyncMock()
        message.from_user = MagicMock(id=admin_id, full_name="Admin Coach")
        message.text = "/reset"

        state = AsyncMock()

        fake_conn = FakeConnection(
            fetchval_map={
                "meal_intakes": 1,
                "meal_orders": 1,
                "meal_payments": 1,
                "meal_checkins": 0,
            }
        )
        fake_conn.transaction = lambda: FakeTransactionContext(fake_conn)
        pool = FakePool(fake_conn)
        db = FakeDatabase(pool)

        fake_settings = MagicMock()
        fake_settings.ADMIN_IDS = [admin_id]

        with patch("meal_plan.admin_reset.settings", fake_settings), patch(
            "meal_plan.admin_reset.admin_ids", return_value=()
        ):
            await handle_admin_reset_command(message, state, db)

        state.clear.assert_awaited_once()
        message.answer.assert_awaited_once()
        sent_text = message.answer.call_args[0][0]
        self.assertIn("Meal Plan Test State Reset Complete!", sent_text)
        self.assertIn(str(admin_id), sent_text)
        self.assertIn("Intakes Cleared:</b> 1", sent_text)
        self.assertIn("Orders Cleared:</b> 1", sent_text)
        self.assertIn("Payments Cleared:</b> 1", sent_text)

    async def test_handle_admin_reset_executes_for_explicit_target_id(self):
        admin_id = 777123
        target_id = 888456
        message = AsyncMock()
        message.from_user = MagicMock(id=admin_id, full_name="Admin Coach")
        message.text = f"/reset {target_id}"

        state = AsyncMock()

        fake_conn = FakeConnection(
            fetchval_map={
                "meal_intakes": 3,
                "meal_orders": 2,
                "meal_payments": 2,
                "meal_checkins": 1,
            }
        )
        fake_conn.transaction = lambda: FakeTransactionContext(fake_conn)
        pool = FakePool(fake_conn)
        db = FakeDatabase(pool)

        fake_settings = MagicMock()
        fake_settings.ADMIN_IDS = [admin_id]

        with patch("meal_plan.admin_reset.settings", fake_settings), patch(
            "meal_plan.admin_reset.admin_ids", return_value=()
        ):
            await handle_admin_reset_command(message, state, db)

        # Admin reset another target: caller's own state shouldn't be cleared
        state.clear.assert_not_called()
        message.answer.assert_awaited_once()
        sent_text = message.answer.call_args[0][0]
        self.assertIn("Meal Plan Test State Reset Complete!", sent_text)
        self.assertIn(str(target_id), sent_text)
        self.assertIn("Intakes Cleared:</b> 3", sent_text)


if __name__ == "__main__":
    unittest.main()
