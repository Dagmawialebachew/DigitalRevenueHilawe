"""Tests for 5-client pilot capacity gating and payment approval enforcement."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from meal_plan.repository import (
    ConcurrentUpdate,
    MealPlanRepository,
    PilotCapReached,
    RecordNotFound,
)
from meal_plan.runtime import pilot_cap, pilot_cap_enabled
from meal_plan.states import OrderState


class FakeConnection:
    def __init__(self, fetchrow_map=None, fetchval_map=None):
        self.fetchrow_map = fetchrow_map or {}
        self.fetchval_map = fetchval_map or {}
        self.executed_sqls = []

    async def fetchrow(self, query: str, *args):
        for pattern, res in self.fetchrow_map.items():
            if pattern in query:
                if callable(res):
                    return res(query, *args)
                return res
        return None

    async def fetchval(self, query: str, *args):
        for pattern, res in self.fetchval_map.items():
            if pattern in query:
                if callable(res):
                    return res(query, *args)
                return res
        return None

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


class PilotCapRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_pilot_cap_helpers_read_env(self):
        with patch.dict("os.environ", {"MEAL_PLAN_PILOT_CAP": "5", "MEAL_PLAN_PILOT_CAP_ENABLED": "true"}):
            self.assertEqual(pilot_cap(), 5)
            self.assertTrue(pilot_cap_enabled())

        with patch.dict("os.environ", {"MEAL_PLAN_PILOT_CAP": "10", "MEAL_PLAN_PILOT_CAP_ENABLED": "0"}):
            self.assertEqual(pilot_cap(), 10)
            self.assertFalse(pilot_cap_enabled())

    async def test_get_approved_paid_user_count(self):
        conn = FakeConnection(fetchval_map={"SELECT COUNT(DISTINCT user_id)": 4})
        conn.transaction = lambda: FakeTransactionContext(conn)
        repo = MealPlanRepository(FakePool(conn))

        count = await repo.get_approved_paid_user_count()
        self.assertEqual(count, 4)

    async def test_is_user_pilot_approved(self):
        conn = FakeConnection(fetchval_map={"SELECT 1 FROM meal_orders": 1})
        conn.transaction = lambda: FakeTransactionContext(conn)
        repo = MealPlanRepository(FakePool(conn))

        self.assertTrue(await repo.is_user_pilot_approved(12345))

    async def test_approve_payment_under_cap_succeeds(self):
        payment_row = {"id": 1, "order_id": 10, "status": "VERIFYING", "user_id": 1001}
        order_row = {"id": 10, "user_id": 1001, "state": OrderState.PAYMENT_REVIEW.value}

        fetchrow_map = {
            "FROM meal_payments WHERE id=$1 FOR UPDATE": payment_row,
            "FROM meal_orders WHERE id=$1 FOR UPDATE": order_row,
            "UPDATE meal_payments": {**payment_row, "status": "APPROVED"},
            "UPDATE meal_orders": {**order_row, "state": OrderState.GENERATION_QUEUED.value},
            "INSERT INTO meal_generation_jobs": {"id": 99, "status": "PENDING"},
        }
        fetchval_map = {
            # user not already approved on other orders:
            "SELECT 1 FROM meal_orders": None,
            # current count is 4 (cap is 5):
            "SELECT COUNT(DISTINCT user_id)": 4,
        }
        conn = FakeConnection(fetchrow_map=fetchrow_map, fetchval_map=fetchval_map)
        conn.transaction = lambda: FakeTransactionContext(conn)
        repo = MealPlanRepository(FakePool(conn))

        with patch.dict("os.environ", {"MEAL_PLAN_PILOT_CAP": "5", "MEAL_PLAN_PILOT_CAP_ENABLED": "true"}):
            result = await repo.approve_payment_and_queue_generation(1, processed_by=999)
            self.assertEqual(result["payment"]["status"], "APPROVED")
            self.assertEqual(result["order"]["state"], OrderState.GENERATION_QUEUED.value)

    async def test_approve_payment_at_cap_raises_pilot_cap_reached(self):
        payment_row = {"id": 2, "order_id": 20, "status": "VERIFYING", "user_id": 2002}
        order_row = {"id": 20, "user_id": 2002, "state": OrderState.PAYMENT_REVIEW.value}

        fetchrow_map = {
            "FROM meal_payments WHERE id=$1 FOR UPDATE": payment_row,
            "FROM meal_orders WHERE id=$1 FOR UPDATE": order_row,
        }
        fetchval_map = {
            # user not already approved:
            "SELECT 1 FROM meal_orders": None,
            # current count is ALREADY 5 (cap is 5):
            "SELECT COUNT(DISTINCT user_id)": 5,
        }
        conn = FakeConnection(fetchrow_map=fetchrow_map, fetchval_map=fetchval_map)
        conn.transaction = lambda: FakeTransactionContext(conn)
        repo = MealPlanRepository(FakePool(conn))

        with patch.dict("os.environ", {"MEAL_PLAN_PILOT_CAP": "5", "MEAL_PLAN_PILOT_CAP_ENABLED": "true"}):
            with self.assertRaises(PilotCapReached) as ctx:
                await repo.approve_payment_and_queue_generation(2, processed_by=999)
            self.assertIn("Pilot cap reached (5/5 approved clients)", str(ctx.exception))

    async def test_approve_payment_for_already_approved_user_bypasses_cap(self):
        # A user who was already approved in another order (e.g. renewal or reorder)
        payment_row = {"id": 3, "order_id": 30, "status": "VERIFYING", "user_id": 3003}
        order_row = {"id": 30, "user_id": 3003, "state": OrderState.PAYMENT_REVIEW.value}

        fetchrow_map = {
            "FROM meal_payments WHERE id=$1 FOR UPDATE": payment_row,
            "FROM meal_orders WHERE id=$1 FOR UPDATE": order_row,
            "UPDATE meal_payments": {**payment_row, "status": "APPROVED"},
            "UPDATE meal_orders": {**order_row, "state": OrderState.GENERATION_QUEUED.value},
            "INSERT INTO meal_generation_jobs": {"id": 100, "status": "PENDING"},
        }
        fetchval_map = {
            # user IS already approved:
            "SELECT 1 FROM meal_orders": 1,
            # even if total count is 5:
            "SELECT COUNT(DISTINCT user_id)": 5,
        }
        conn = FakeConnection(fetchrow_map=fetchrow_map, fetchval_map=fetchval_map)
        conn.transaction = lambda: FakeTransactionContext(conn)
        repo = MealPlanRepository(FakePool(conn))

        with patch.dict("os.environ", {"MEAL_PLAN_PILOT_CAP": "5", "MEAL_PLAN_PILOT_CAP_ENABLED": "true"}):
            result = await repo.approve_payment_and_queue_generation(3, processed_by=999)
            self.assertEqual(result["payment"]["status"], "APPROVED")


class TelegramEntryPilotCapTests(unittest.IsolatedAsyncioTestCase):
    async def test_telegram_entry_blocks_new_user_when_pilot_is_full(self):
        from meal_plan.entry import open_meal_plan_entry

        message = MagicMock()
        message.text = "🥗 Meal Plan"
        message.from_user.id = 55555
        message.answer = AsyncMock()

        state = MagicMock()
        state.clear = AsyncMock()

        db = MagicMock()
        db.get_user = AsyncMock(return_value={"language": "EN"})

        repo = MagicMock()
        repo.get_current_order_for_user = AsyncMock(return_value=None)
        repo.is_user_pilot_approved = AsyncMock(return_value=False)
        repo.get_approved_paid_user_count = AsyncMock(return_value=5)

        with patch("meal_plan.entry.meal_plan_enabled", return_value=True), \
             patch("meal_plan.entry.get_meal_plan_repository", return_value=repo), \
             patch.dict("os.environ", {"MEAL_PLAN_PILOT_CAP": "5", "MEAL_PLAN_PILOT_CAP_ENABLED": "true", "ADMIN_IDS": "999"}):
            await open_meal_plan_entry(message, state, db)

        message.answer.assert_called_once()
        sent_text = message.answer.call_args[0][0]
        self.assertIn("Round 1 Meal Plan Pilot is Full!", sent_text)
        self.assertIn("strictly capped at <b>5 clients</b>", sent_text)

    async def test_telegram_entry_allows_admin_when_pilot_is_full(self):
        from meal_plan.entry import open_meal_plan_entry

        message = MagicMock()
        message.text = "🥗 Meal Plan"
        message.from_user.id = 999  # Admin ID
        message.answer = AsyncMock()

        state = MagicMock()
        state.clear = AsyncMock()

        db = MagicMock()
        db.get_user = AsyncMock(return_value={"language": "AM"})

        repo = MagicMock()
        repo.get_current_order_for_user = AsyncMock(return_value=None)
        repo.create_or_resume_intake = AsyncMock(return_value={"id": 1, "country_region": None})

        with patch("meal_plan.entry.meal_plan_enabled", return_value=True), \
             patch("meal_plan.entry.get_meal_plan_repository", return_value=repo), \
             patch.dict("os.environ", {"MEAL_PLAN_PILOT_CAP": "5", "MEAL_PLAN_PILOT_CAP_ENABLED": "true", "ADMIN_IDS": "999"}):
            await open_meal_plan_entry(message, state, db)

        message.answer.assert_called_once()
        repo.create_or_resume_intake.assert_called_once()


class ApiPilotCapTests(unittest.IsolatedAsyncioTestCase):
    async def test_bootstrap_returns_pilot_status_payload(self):
        import json
        from meal_plan.api import bootstrap

        request = MagicMock()
        request.json = AsyncMock(return_value={"init_data": "valid_token"})

        identity = MagicMock()
        identity.telegram_id = 777
        identity.first_name = "Test"
        identity.username = "testuser"

        db = MagicMock()
        db.get_user = AsyncMock(return_value={"language": "EN"})
        request.app = {"db": db}

        repo = MagicMock()
        repo.get_open_intake_for_user = AsyncMock(return_value=None)
        repo.create_or_resume_intake = AsyncMock(return_value={
            "id": 1,
            "public_id": "test-uuid",
            "state": "INTAKE_IN_PROGRESS",
            "current_step": "WELCOME",
            "version": 1,
            "answers": {},
            "country_region": "ETHIOPIA",
            "country_name": None,
            "updated_at": None,
            "closed_at": None,
        })
        repo.get_current_order_for_user = AsyncMock(return_value=None)
        repo.is_user_pilot_approved = AsyncMock(return_value=False)
        repo.get_approved_paid_user_count = AsyncMock(return_value=3)

        followup_repo = MagicMock()
        followup_repo.latest_order_for_user = AsyncMock(return_value=None)

        with patch("meal_plan.api._authenticate", return_value=identity), \
             patch("meal_plan.api.get_meal_plan_repository", return_value=repo), \
             patch("meal_plan.api._followup_repo", return_value=followup_repo), \
             patch.dict("os.environ", {"MEAL_PLAN_PILOT_CAP": "5", "MEAL_PLAN_PILOT_CAP_ENABLED": "true"}):
            resp = await bootstrap(request)

        data = json.loads(resp.text)
        self.assertTrue(data["ok"])
        self.assertIn("pilot", data)
        self.assertEqual(data["pilot"]["cap"], 5)
        self.assertEqual(data["pilot"]["approved_count"], 3)
        self.assertEqual(data["pilot"]["spots_remaining"], 2)
        self.assertFalse(data["pilot"]["is_full"])

    async def test_checkout_returns_403_when_pilot_is_full(self):
        import json
        from meal_plan.api import start_payment

        request = MagicMock()
        request.json = AsyncMock(return_value={
            "init_data": "valid_token",
            "meals_per_day": 3,
            "duration_days": 7,
            "service_type": "PLAN",
            "start_date": "2026-10-05",
        })

        identity = MagicMock()
        identity.telegram_id = 888

        db = MagicMock()
        db.get_user = AsyncMock(return_value={"language": "EN"})
        request.app = {"db": db}

        repo = MagicMock()
        repo.get_current_order_for_user = AsyncMock(return_value=None)
        repo.get_open_intake_for_user = AsyncMock(return_value={
            "id": 1,
            "state": "CHECKOUT_READY",
            "country_region": "ETHIOPIA",
            "country_name": None,
            "answers": {},
        })
        repo.is_user_pilot_approved = AsyncMock(return_value=False)
        repo.get_approved_paid_user_count = AsyncMock(return_value=5)

        with patch("meal_plan.api._authenticate", return_value=identity), \
             patch("meal_plan.api.get_meal_plan_repository", return_value=repo), \
             patch.dict("os.environ", {"MEAL_PLAN_PILOT_CAP": "5", "MEAL_PLAN_PILOT_CAP_ENABLED": "true", "ADMIN_IDS": "999"}):
            resp = await start_payment(request)

        self.assertEqual(resp.status, 403)
        data = json.loads(resp.text)
        self.assertEqual(data["error"]["code"], "PILOT_CAP_REACHED")
        self.assertIn("Round 1 Pilot is full", data["error"]["message"])


if __name__ == "__main__":
    unittest.main()
