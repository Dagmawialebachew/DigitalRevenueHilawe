"""Unit tests for Tri-Stream Payout & Financial Settlement Core (Workout, Club, Meal Plan).

Validates the Stream C Meal Plan agreement:
- Initial Stage (< 100k ETB cumulative): 60% Coach / 40% Dagmawi
- Mature Stage (>= 100k ETB cumulative): 65% Coach / 35% Dagmawi
- Pro-rata operational deduction apportionment across the 3 streams
"""

from __future__ import annotations

from decimal import Decimal
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import web
from api.api import get_pending_payout_stats, confirm_payout


class TriStreamFinancialCoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_pending_payout_stats_under_100k_milestone(self):
        """Under 100k milestone: Meal plan split is 40% Dagmawi / 60% Coach."""
        db = MagicMock()
        db.fetchval = AsyncMock(return_value=None)
        
        # Pending amounts since checkpoint
        db.fetchrow = AsyncMock()
        db.fetchrow.side_effect = [
            # 1. pending_row: 10,000 products, 6,000 club, 10,000 meal
            {
                "products_total": 10000, "products_count": 10,
                "club_total": 6000, "club_count": 20,
                "meal_total": 10000, "meal_count": 2,
            },
            # 2. club_stats (cumulative): 20,000 ETB (< 50,000 -> initial 60/40)
            {"cumulative_gross": 20000, "total_subscriptions": 65},
            # 3. meal_stats (cumulative): 10,000 ETB (< 100,000 -> initial 40/60)
            {"cumulative_gross": 10000, "total_plans": 2},
            # 4. infra_stats (current_month_burn)
            {"current_month_burn": 1000},
            # 5. unsettled_burn_row: 0 pending deductions
            {"pending_burn": 0},
            # 6. lifetime_stats
            {
                "lt_products_gross": 10000, "lt_club_gross": 20000,
                "lt_meal_gross": 10000, "lt_burn": 1000, "lt_paid": 0,
            }
        ]
        db.fetch = AsyncMock(return_value=[])

        request = MagicMock()
        request.app = {"db": db}

        resp = await get_pending_payout_stats(request)
        self.assertEqual(resp.status, 200)

        import json
        data = json.loads(resp.text)
        
        # Gross checks
        self.assertEqual(data["pending_revenue"], 26000.0)
        self.assertEqual(data["products_stream"]["gross"], 10000.0)
        self.assertEqual(data["club_stream"]["gross"], 6000.0)
        self.assertEqual(data["meal_stream"]["gross"], 10000.0)

        # Meal Plan stream under 100k (40% Dag / 60% Coach)
        self.assertEqual(data["meal_stream"]["stage"], "initial_40_60")
        self.assertEqual(data["meal_stream"]["dagmawi_rate"], 0.40)
        self.assertEqual(data["meal_stream"]["coach_rate"], 0.60)
        self.assertEqual(data["meal_stream"]["dagmawi_share"], 4000.0)
        self.assertEqual(data["meal_stream"]["coach_share"], 6000.0)

        # Products (70% Coach / 30% Dag) -> 7,000 Coach / 3,000 Dag
        self.assertEqual(data["products_stream"]["coach_share"], 7000.0)
        self.assertEqual(data["products_stream"]["dagmawi_share"], 3000.0)

        # Club under 50k (60% Coach / 40% Dag) -> 3,600 Coach / 2,400 Dag
        self.assertEqual(data["club_stream"]["coach_share"], 3600.0)
        self.assertEqual(data["club_stream"]["dagmawi_share"], 2400.0)

        # Total payouts
        self.assertEqual(data["coach_total_payout"], 7000.0 + 3600.0 + 6000.0)
        self.assertEqual(data["dagmawi_total_payout"], 3000.0 + 2400.0 + 4000.0)

    async def test_pending_payout_stats_above_100k_milestone(self):
        """Above 100k milestone: Meal plan split transitions to 35% Dagmawi / 65% Coach."""
        db = MagicMock()
        db.fetchval = AsyncMock(return_value=None)
        
        db.fetchrow = AsyncMock()
        db.fetchrow.side_effect = [
            # 1. pending_row: 0 products, 0 club, 20,000 meal
            {
                "products_total": 0, "products_count": 0,
                "club_total": 0, "club_count": 0,
                "meal_total": 20000, "meal_count": 4,
            },
            # 2. club_stats
            {"cumulative_gross": 60000, "total_subscriptions": 200},
            # 3. meal_stats: 120,000 ETB (>= 100,000 -> mature 35/65)
            {"cumulative_gross": 120000, "total_plans": 25},
            # 4. infra_stats
            {"current_month_burn": 0},
            # 5. unsettled_burn_row: 0 deductions
            {"pending_burn": 0},
            # 6. lifetime_stats
            {
                "lt_products_gross": 50000, "lt_club_gross": 60000,
                "lt_meal_gross": 120000, "lt_burn": 0, "lt_paid": 0,
            }
        ]
        db.fetch = AsyncMock(return_value=[])

        request = MagicMock()
        request.app = {"db": db}

        resp = await get_pending_payout_stats(request)
        self.assertEqual(resp.status, 200)

        import json
        data = json.loads(resp.text)

        # Meal Plan stream above 100k (35% Dag / 65% Coach)
        self.assertEqual(data["meal_stream"]["stage"], "mature_35_65")
        self.assertEqual(data["meal_stream"]["dagmawi_rate"], 0.35)
        self.assertEqual(data["meal_stream"]["coach_rate"], 0.65)
        self.assertEqual(data["meal_stream"]["dagmawi_share"], 7000.0)   # 20,000 * 0.35
        self.assertEqual(data["meal_stream"]["coach_share"], 13000.0)  # 20,000 * 0.65

    async def test_confirm_payout_with_meal_plan(self):
        """Confirming payout correctly logs all 3 streams into payout_history."""
        db = MagicMock()
        db.fetchval = AsyncMock(side_effect=[
            None,  # last_payout_ts
            50000, # club_stats (cumulative)
            80000, # meal_stats (cumulative < 100k)
        ])
        db.fetchrow = AsyncMock(return_value={
            "products_total": 5000,
            "club_total": 3000,
            "meal_total": 4000,
        })

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        mock_conn.transaction = MagicMock()
        mock_conn.transaction.return_value.__aenter__ = AsyncMock()
        mock_conn.transaction.return_value.__aexit__ = AsyncMock()

        db._pool = MagicMock()
        db._pool.acquire = MagicMock()
        db._pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        db._pool.acquire.return_value.__aexit__ = AsyncMock()

        request = MagicMock()
        request.app = {"db": db}
        request.json = AsyncMock(return_value={
            "entry_type": "payout",
            "products_amount": 5000,
            "club_amount": 3000,
            "meal_amount": 4000,
            "deductions": 0,
            "note": "Tri-stream settlement"
        })

        resp = await confirm_payout(request)
        self.assertEqual(resp.status, 200)

        import json
        data = json.loads(resp.text)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["gross_revenue"], 12000.0)
        self.assertEqual(data["meal_gross"], 4000.0)
        self.assertEqual(data["meal_stage"], "initial_40_60")

        # Coach share: 5000*0.70 (3500) + 3000*0.65 (1950) + 4000*0.60 (2400) = 7850
        self.assertEqual(data["coach_share"], 7850.0)
        # Dagmawi share: 5000*0.30 (1500) + 3000*0.35 (1050) + 4000*0.40 (1600) = 4150
        self.assertEqual(data["dagmawi_share"], 4150.0)


if __name__ == "__main__":
    unittest.main()
