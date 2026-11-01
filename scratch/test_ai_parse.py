"""Test AI Feedback Synthesis with Gemini 3.8 Flash."""

import json
import sys
from dotenv import load_dotenv

sys.path.insert(0, '.')
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv(r'd:\The hobby 2\DigitalRevenueHilawe\.env')

from meal_plan.ai.gemini_coach import get_gemini_coach
from meal_plan.generation.feedback_store import get_feedback_store

def main():
    coach = get_gemini_coach()
    store = get_feedback_store()
    
    critique = "Fasting clients get bloated from 250g evening ful. Please cap dinner ful portions at 160g."
    print(f"Coach Boss Critique: '{critique}'")
    print("Calling Gemini 3.8 Flash to synthesize catalog rule...")
    
    rule = coach.synthesize_feedback_rule(critique, author="Coach Boss")
    print("\n✅ Successfully Synthesized Rule:")
    print(f"  ID: {rule.id}")
    print(f"  Type: {rule.type}")
    print(f"  Name: {rule.name}")
    print(f"  Description: {rule.description}")
    print(f"  Severity: {rule.severity}")
    print(f"  Metadata: {json.dumps(rule.metadata, ensure_ascii=False, indent=2)}")

    # Assert rule is in catalog
    fetched = store.get_rule(rule.id)
    assert fetched is not None, "Rule was not saved to catalog!"
    print(f"\nVerified rule is persisted in {store.catalog_path}")

    # Clean up test rule
    store.remove_rule(rule.id)
    print(f"Cleaned up test rule '{rule.id}' from catalog.")

if __name__ == "__main__":
    main()
