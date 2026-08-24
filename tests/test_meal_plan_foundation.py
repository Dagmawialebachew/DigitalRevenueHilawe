from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from database.migrations.runner import discover_migrations
from meal_plan.constants import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    MEAL_COUNTS,
    PLAN_DURATIONS_DAYS,
    PRICING_REGIONS,
    ServiceType,
    service_type_allowed,
)
from meal_plan.states import MealPlanLifecycle


class ProductDecisionTests(unittest.TestCase):
    def test_amharic_is_default_language(self):
        self.assertEqual(DEFAULT_LANGUAGE, "AM")
        self.assertEqual(LANGUAGES, ("AM", "EN"))

    def test_locked_regions(self):
        self.assertEqual(
            PRICING_REGIONS,
            ("ETHIOPIA", "UNITED_STATES", "EUROPE", "UAE", "OTHER"),
        )

    def test_locked_durations_and_meal_counts(self):
        self.assertEqual(PLAN_DURATIONS_DAYS, (7, 14, 30))
        self.assertEqual(MEAL_COUNTS, (3, 4, 5))

    def test_follow_up_is_thirty_day_only(self):
        self.assertFalse(service_type_allowed(7, ServiceType.FOLLOW_UP))
        self.assertFalse(service_type_allowed(14, ServiceType.FOLLOW_UP))
        self.assertTrue(service_type_allowed(30, ServiceType.FOLLOW_UP))
        for duration in PLAN_DURATIONS_DAYS:
            self.assertTrue(service_type_allowed(duration, ServiceType.PLAN))

    def test_lifecycle_contains_review_before_active(self):
        names = [state.value for state in MealPlanLifecycle]
        self.assertIn("HEALTH_REVIEW_REQUIRED", names)
        self.assertIn("REVIEW_PENDING", names)
        self.assertIn("APPROVED", names)
        self.assertIn("ACTIVE", names)
        self.assertLess(names.index("REVIEW_PENDING"), names.index("APPROVED"))
        self.assertLess(names.index("APPROVED"), names.index("ACTIVE"))


class MigrationDiscoveryTests(unittest.TestCase):
    def test_empty_directory_has_no_migrations(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(discover_migrations(Path(tmp)), [])

    def test_migrations_are_sorted_and_hashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "0002_second.sql").write_text("SELECT 2;", encoding="utf-8")
            (root / "0001_first.sql").write_text("SELECT 1;", encoding="utf-8")
            migrations = discover_migrations(root)
            self.assertEqual([m.version for m in migrations], ["0001", "0002"])
            self.assertTrue(all(len(m.checksum) == 64 for m in migrations))

    def test_duplicate_versions_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "0001_first.sql").write_text("SELECT 1;", encoding="utf-8")
            (root / "0001_second.sql").write_text("SELECT 2;", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                discover_migrations(root)


if __name__ == "__main__":
    unittest.main()
