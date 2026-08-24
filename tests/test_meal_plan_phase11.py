from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from meal_plan.api import _checkout_fasting_context
from meal_plan.fasting_calendar import (
    FastingCalendarCoverageRequired,
    build_overlaps,
    missing_verified_years,
    seasonal_fasting_selected,
)
from meal_plan.generation.dataset import load_dataset
from meal_plan.generation.engine import generate_plan
from meal_plan.generation.fasting import FastingCalendarRequired, fasting_days_for_period
from meal_plan.nutrition_targets import calculate_nutrition_profile
from tests.test_meal_plan_phase6 import base_answers


ROOT = Path(__file__).resolve().parents[1]


def occurrence(rule_id: str, name: str, start: date, end: date) -> dict[str, object]:
    return {
        "Rule ID": rule_id,
        "Fast Name": name,
        "Rule Type": "Annual occurrence",
        "Start Date": start.isoformat(),
        "End Date": end.isoformat(),
        "Verification Status": "VERIFIED_RULESET",
        "Verified For Year": str(start.year),
    }


class FastingCalendarPolicyTests(unittest.TestCase):
    def test_seasonal_patterns_are_explicit(self):
        self.assertTrue(seasonal_fasting_selected("SEASONAL"))
        self.assertTrue(seasonal_fasting_selected("WED_FRI_AND_SEASONAL"))
        self.assertFalse(seasonal_fasting_selected("WED_FRI"))

    def test_missing_coverage_is_not_confused_with_no_overlap(self):
        coverage = [{"calendar_year": 2026, "status": "VERIFIED_COMPLETE"}]
        self.assertEqual(missing_verified_years(date(2026, 12, 20), date(2027, 1, 5), coverage), (2027,))
        complete = coverage + [{"calendar_year": 2027, "status": "VERIFIED_COMPLETE"}]
        self.assertEqual(missing_verified_years(date(2026, 12, 20), date(2027, 1, 5), complete), ())

    def test_overlap_is_clipped_to_purchased_plan(self):
        rows = [{
            "rule_id": "FAST-FILSETA-2026", "fast_name": "Filseta",
            "start_date": date(2026, 8, 7), "end_date": date(2026, 8, 21),
        }]
        result = build_overlaps(date(2026, 8, 18), date(2026, 8, 24), rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].overlap_start, date(2026, 8, 18))
        self.assertEqual(result[0].overlap_end, date(2026, 8, 21))
        self.assertEqual(result[0].overlap_days, 4)

    def test_full_period_requires_every_touched_year(self):
        rows = (occurrence("FAST-NATIVITY-2026", "Nativity", date(2026, 11, 24), date(2027, 1, 6)),)
        with self.assertRaises(FastingCalendarRequired):
            fasting_days_for_period(
                date(2026, 12, 20), 30, "SEASONAL", rows,
                verified_years=[2026],
            )


class CheckoutFastingPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_nonseasonal_checkout_does_not_query_annual_calendar(self):
        class Repo:
            async def get_fasting_calendar_window(self, _start, _end):
                self.fail("Annual calendar must not be queried for weekly-only fasting")

        context = await _checkout_fasting_context(
            Repo(),
            {"answers": {"orthodox_fasting": "WED_FRI"}},
            SimpleNamespace(start_date=date(2026, 8, 24), ends_on=date(2026, 9, 6)),
        )
        self.assertFalse(context["seasonal_selected"])
        self.assertEqual(context["overlaps"], [])

    async def test_seasonal_checkout_fails_closed_when_coverage_is_missing(self):
        class Repo:
            async def get_fasting_calendar_window(self, _start, _end):
                return [], []

        with self.assertRaises(FastingCalendarCoverageRequired):
            await _checkout_fasting_context(
                Repo(),
                {"answers": {"orthodox_fasting": "SEASONAL"}},
                SimpleNamespace(start_date=date(2027, 1, 1), ends_on=date(2027, 1, 30)),
            )

    async def test_verified_no_overlap_is_a_valid_empty_result(self):
        class Repo:
            async def get_fasting_calendar_window(self, _start, _end):
                return [{"calendar_year": 2026, "status": "VERIFIED_COMPLETE"}], []

        context = await _checkout_fasting_context(
            Repo(),
            {"answers": {"orthodox_fasting": "SEASONAL"}},
            SimpleNamespace(start_date=date(2026, 9, 1), ends_on=date(2026, 9, 14)),
        )
        self.assertTrue(context["seasonal_selected"])
        self.assertEqual(context["coverage_years"], [2026])
        self.assertEqual(context["overlaps"], [])


class FastingGenerationTests(unittest.TestCase):
    def test_seasonal_dates_use_a_separate_fasting_safe_core(self):
        source = load_dataset()
        meta = {**source.meta, "verified_fasting_calendar_years": [2026]}
        calendar = source.fasting_calendar + (
            occurrence("FAST-FILSETA-2026", "Filseta", date(2026, 8, 7), date(2026, 8, 21)),
        )
        dataset = replace(source, meta=meta, fasting_calendar=calendar)
        answers = base_answers(orthodox_fasting="SEASONAL", fish_during_fast=False)
        profile = calculate_nutrition_profile(answers).to_dict()
        plan = generate_plan(
            answers=answers, nutrition_profile=profile, meals_per_day=4,
            start_date=date(2026, 8, 5), duration_days=14, region="ETHIOPIA",
            dataset=dataset,
        )
        self.assertTrue(plan["fasting_core_week"])
        self.assertTrue(all(day["fasting"] for day in plan["fasting_core_week"]))
        self.assertTrue(plan["fasting_grocery"])
        by_date = {row["date"]: row for row in plan["rotation"]}
        self.assertEqual(by_date["2026-08-06"]["core_source"], "REGULAR")
        self.assertEqual(by_date["2026-08-07"]["core_source"], "FASTING")
        self.assertEqual(by_date["2026-08-18"]["core_source"], "FASTING")


class FastingFeatureContractTests(unittest.TestCase):
    def test_migration_seeds_rolling_verified_calendar(self):
        sql = (ROOT / "database" / "migrations" / "0003_verified_fasting_calendar.sql").read_text(encoding="utf-8")
        for year in (2026, 2027, 2028, 2029):
            self.assertIn(f"({year},'VERIFIED_COMPLETE'", sql)
            self.assertIn(f"FAST-LENT-{year}", sql)
            self.assertIn(f"FAST-FILSETA-{year}", sql)

    def test_checkout_rechecks_calendar_before_payment(self):
        api = (ROOT / "meal_plan" / "api.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(api.count("_checkout_fasting_context"), 3)
        self.assertIn("FASTING_CALENDAR_NOT_VERIFIED", api)

    def test_miniapp_has_dual_calendar_and_overlap_ui(self):
        source = (ROOT / "meal_plan_miniapp" / "src" / "ProfileCheckoutFlow.tsx").read_text(encoding="utf-8")
        self.assertIn("react-day-picker/ethiopic", source)
        self.assertIn("function CalendarPicker", source)
        self.assertIn("function FastingCalendarPanel", source)
        self.assertIn("formatEthiopian", source)


if __name__ == "__main__":
    unittest.main()
