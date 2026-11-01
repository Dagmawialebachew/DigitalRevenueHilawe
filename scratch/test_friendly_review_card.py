import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from meal_plan.review_logic import review_card_text

mock_version = {
    "full_name": "Bezawit Nigusse",
    "username": "bezawit_n",
    "user_id": 12345678,
    "order_id": 105,
    "order_public_id": "MP-000105",
    "version_number": 1,
    "source": "GENERATED",
    "duration_days": 7,
    "meals_per_day": 3,
    "service_type": "Personalized 7-Day Plan",
    "start_date": "2026-11-02",
    "ends_on": "2026-11-08",
    "country_name": "Ethiopia",
    "amount": 2500,
    "currency": "ETB",
    "engine_version": "v2.5-fasting-aligned",
    "dataset_version": "v1.8-ethiopian-stews",
    "nutrition_profile": {
        "target_kcal": 2100,
        "protein_g": 120,
        "carbs_g": 240,
        "fat_g": 60,
    },
    "plan_json": {
        "profile_summary": {"goal": "Weight Loss"},
        "review": {"practical_warnings": [], "uncalibrated_recipes": []},
        "lint_report": {
            "score": 9.9,
            "passed": True,
            "errors_count": 0,
            "warnings_count": 1,
        },
        "ai_audit": {
            "score": 9.8,
            "culinary_cohesion": "EXCELLENT",
            "coach_briefing": "Clean fasting day balance with soy milk at breakfast and steady protein throughout.",
        }
    }
}

card_output = review_card_text(mock_version)
print("=== GENERATED REVIEW CARD OUTPUT ===")
print(card_output)
print("====================================")

# Assertions
assert "Pre-Flight" not in card_output, "Found robotic 'Pre-Flight' in card!"
assert "Linter" not in card_output, "Found robotic 'Linter' in card!"
assert "Quality Check: <b>9.9/10</b> (Passed)" in card_output, "Missing Quality Check line!"
assert "AI Coach: <b>Approved</b> · <i>Clean fasting day balance with soy milk" in card_output, "Missing AI Coach line!"

print("\nSUCCESS: All plain-language card checks passed with zero robotic AI jargon!")
