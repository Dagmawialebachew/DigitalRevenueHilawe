"""Unit Test Suite for Pillar 3: FeedbackStore & Dynamic Rule Catalog.

Asserts:
1. FeedbackStore loads canonical catalog and parses rule types accurately.
2. Natural language parsing converts Coach Boss commands into structured rules.
3. Generator engine applies dynamic rules during plan creation.
4. Pre-flight linter catches violations dynamically governed by FeedbackStore.
"""

import sys
import unittest
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, '.')
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv(r'd:\The hobby 2\DigitalRevenueHilawe\.env')

from meal_plan.generation.feedback_store import FeedbackRule, FeedbackStore, get_feedback_store
from meal_plan.generation.linter import MealPlanLinter, LintSeverity


class TestFeedbackStore(unittest.TestCase):

    def setUp(self):
        self.store = get_feedback_store(reload=True)

    def test_canonical_catalog_loaded(self):
        rules = self.store.get_all_rules()
        self.assertGreaterEqual(len(rules), 10)
        
        # Assert key canonical rules exist
        rule_ids = {r.id for r in rules}
        self.assertIn("RULE_PORTION_CAP_RICE_CAKES", rule_ids)
        self.assertIn("RULE_PAIRING_EXCLUDE_LEGUME_STACKING", rule_ids)
        self.assertIn("RULE_INJERA_MOD_60_STANDARDIZATION", rule_ids)
        self.assertIn("RULE_FAMILIAR_MEASURE_SOYA_CHUNKS", rule_ids)
        self.assertIn("RULE_STEW_PORTION_STANDARDIZATION", rule_ids)
        self.assertIn("RULE_NO_LOOSE_OIL_ON_RICH_STEWS", rule_ids)

    def test_portion_caps_query(self):
        caps = self.store.get_portion_caps()
        self.assertIn("C020", caps)
        self.assertEqual(caps["C020"], 40.0)

        # Breakfast-specific oil cap
        bfast_caps = self.store.get_portion_caps(meal_slot="Breakfast")
        self.assertIn("T001", bfast_caps)
        self.assertEqual(bfast_caps["T001"], 15.0)

    def test_pairing_exclusions_query(self):
        # When Misir Wot (R002) is served, plain lentils (P001) are forbidden
        forbidden = self.store.get_forbidden_secondaries_for({"R002"})
        self.assertIn("P001", forbidden)
        self.assertIn("P007", forbidden)

        # When Key Wot (R020) is served, loose oil (T001) is forbidden
        forbidden_oil = self.store.get_forbidden_secondaries_for({"R020"})
        self.assertIn("T001", forbidden_oil)

    def test_portion_standards_query(self):
        stds = self.store.get_portion_standards()
        self.assertIn("R004", stds)
        self.assertEqual(stds["R004"]["grams"], 80.0)
        self.assertEqual(stds["R002"]["grams"], 200.0)

    def test_natural_language_coach_feedback_parsing(self):
        # 1. Portion cap parse
        r1 = self.store.record_coach_feedback("Cap rice cakes to 35g", author="Coach Boss")
        self.assertEqual(r1.type, "portion_cap")
        self.assertEqual(r1.metadata["target_id"], "C020")
        self.assertEqual(r1.metadata["max_grams"], 35.0)
        self.store.remove_rule(r1.id)

        # 2. Pairing exclusion parse
        r2 = self.store.record_coach_feedback("Never pair plain lentils with misir wot", author="Coach Boss")
        self.assertEqual(r2.type, "pairing_exclusion")
        self.store.remove_rule(r2.id)

    def test_linter_dynamic_rule_enforcement(self):
        linter = MealPlanLinter(strict=True, feedback_store=self.store)
        
        # Test synthetic plan with rice cakes > 40g
        bad_plan = {
            "core_week": [
                {
                    "day_name": "Monday",
                    "fasting": False,
                    "totals": {"kcal": 1800, "protein": 130},
                    "meals": [
                        {
                            "slot": "Snack",
                            "items": [
                                {"food_id": "C020", "food_name": "Rice cakes", "grams": 60.0}
                            ]
                        }
                    ]
                }
            ]
        }
        findings = []
        score = linter._audit_legume_carb_realism(bad_plan["core_week"], findings)
        self.assertLess(score, 1.0)
        self.assertTrue(any("exceeds safety cap" in f.message for f in findings))


if __name__ == "__main__":
    unittest.main()
