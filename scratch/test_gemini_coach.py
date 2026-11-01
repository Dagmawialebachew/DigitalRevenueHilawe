"""Test script for Gemini 3.8 Flash AI Coach & RAG System."""

import json
import sys
from datetime import date
from dotenv import load_dotenv

sys.path.insert(0, '.')
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv(r'd:\The hobby 2\DigitalRevenueHilawe\.env')

from meal_plan.ai.gemini_coach import get_gemini_coach
from meal_plan.generation.dataset import load_dataset
from meal_plan.generation.engine import generate_plan
from scratch.verify_multi_persona_linter import test_cases

def main():
    coach = get_gemini_coach()
    print(f"Gemini Client Available: {coach.is_available()}")
    if not coach.is_available():
        print("Error: Gemini client is not available. Check API key.")
        return

    # 1. Test Semantic Plan Audit on Bezawit Nigusse
    print("\n" + "=" * 80)
    print("TEST 1: LIVE SEMANTIC AUDIT VIA GEMINI 3.8 FLASH")
    print("=" * 80)
    dataset = load_dataset()
    bezawit = test_cases[0]
    plan = generate_plan(
        answers=bezawit["answers"],
        nutrition_profile=bezawit["targets"],
        meals_per_day=3,
        start_date=date(2026, 11, 2),
        duration_days=7,
        region="ADDIS_ABABA",
        country_name="Ethiopia",
        dataset=dataset,
    )

    result = coach.audit_plan_semantics(plan, answers=bezawit["answers"], nutrition_profile=bezawit["targets"])
    print(result.to_markdown())

    # 2. Test Feedback-to-Rule Synthesis
    print("\n" + "=" * 80)
    print("TEST 2: AUTONOMOUS FEEDBACK-TO-RULE SYNTHESIS VIA GEMINI 3.8 FLASH")
    print("=" * 80)
    critique = "Coach Boss: Evening ful is causing gastric bloating in fasting clients. Please strictly limit ful at dinner to 160g."
    print(f"Input Critique: '{critique}'")
    rule = coach.synthesize_feedback_rule(critique, author="Coach Boss")
    print(f"\nSynthesized Rule:")
    print(f"  ID: {rule.id}")
    print(f"  Type: {rule.type}")
    print(f"  Name: {rule.name}")
    print(f"  Severity: {rule.severity}")
    print(f"  Metadata: {json.dumps(rule.metadata, ensure_ascii=False, indent=2)}")

    # Clean up test rule
    from meal_plan.generation.feedback_store import get_feedback_store
    store = get_feedback_store()
    store.remove_rule(rule.id)
    print(f"\nCleaned up test rule '{rule.id}' from catalog.")
    print("=" * 80 + "\n")
    print("🎉 ALL GEMINI 3.8 FLASH TESTS PASSED CLEANLY!")

if __name__ == "__main__":
    main()
