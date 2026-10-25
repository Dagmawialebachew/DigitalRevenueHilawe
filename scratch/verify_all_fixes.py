import sys
import os
from pathlib import Path
from datetime import date

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

import dotenv
dotenv.load_dotenv(repo_root / ".env")

from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan
from meal_plan.generation.dataset import load_dataset
from meal_plan.documents.models import DocumentContext
from meal_plan.documents.html_pdf_renderer import render_html_document, render_html_pdf

answers = {
    'calculation_sex': 'MALE',
    'age': 25,
    'current_weight_kg': 45.0,
    'target_weight_kg': 60.0,
    'height_cm': 170,
    'activity_level': 'LIGHTLY_ACTIVE',
    'primary_goal': 'MUSCLE_GAIN',
    'meals_per_day': 3,
    'cuisine_style': 'ETHIOPIAN',
    'dietary_pattern': 'OMNIVORE',
    'grocery_budget': 'SAVE',
    'orthodox_fasting': 'NONE',
    'fish_during_fast': False,
    'training_days_per_week': 3,
    'training_type': 'HOME_WORKOUT',
}

profile = calculate_nutrition_profile(answers)
print("Target Calories:", profile.target_kcal)
assert profile.target_kcal >= 2000, f"Calorie surplus too low: {profile.target_kcal}"

# Generate a 14-day plan
plan = generate_plan(
    answers=answers,
    nutrition_profile=profile.to_dict(),
    meals_per_day=3,
    start_date=date(2026, 10, 26),
    duration_days=14,
    region='ETHIOPIA',
    country_name='Ethiopia',
)

# Assertions to confirm fixes
day1_meals = plan['core_week'][0]['meals']
print("Day 1 Lunch Items:", [it['food_name'] for it in day1_meals[1]['items']])
assert len(day1_meals[1]['items']) > 1, "FAILED: Lunch still only has 1 ingredient!"

# Check breakfast carbs: Ensure no rice in breakfast
for day in plan['core_week']:
    bfast = day['meals'][0]
    for it in bfast.get('items', []):
        f_name = it.get('food_name', '').lower()
        f_id = it.get('food_id', '')
        assert 'rice' not in f_name and f_id not in {'C003', 'C004'}, f"FAILED: Injected rice {f_name} into breakfast!"

grocery_items = plan['grocery']
print("Total Grocery Items Count:", len(grocery_items))
assert len(grocery_items) > 8, f"FAILED: Grocery list collapsed, only {len(grocery_items)} items!"

for item in grocery_items:
    name = item['buy_item'].lower()
    assert 'tuna' not in name, "FAILED: Imported tuna in Save budget!"
    assert 'olive oil' not in name, "FAILED: Premium olive oil in Save budget!"

# Verify HTML and PDF Rendering
context = DocumentContext(
    client_name="Kirubel Tadesse",
    language="AM",
    plan_public_id="PLAN-2026-TEST",
    version_number="1.0",
    client_profile=answers,
)

html = render_html_document(plan, context, is_client_delivery=True)

# Slicing checks: 14-day plan must have Week 01 and Week 02, but NOT Week 03 or Week 04 in roadmap and checkin
assert "Week 01" in html or "ሳምንት 01" in html, "Week 01 missing!"
assert "Week 02" in html or "ሳምንት 02" in html, "Week 02 missing!"
assert "Week 03" not in html and "ሳምንት 03" not in html, "FAILED: Week 03 leaked into 14-day plan!"
assert "Week 04" not in html and "ሳምንት 04" not in html, "FAILED: Week 04 leaked into 14-day plan!"

# Token check: no dangling | | PAG
assert "| | PAG" not in html, "FAILED: Hanging metadata label | | PAG found in HTML!"

# Render actual PDF
output_pdf = Path(__file__).resolve().parent / "test_14day_plan.pdf"
render_html_pdf(plan, context, str(output_pdf), is_client_delivery=True)
assert output_pdf.exists() and output_pdf.stat().st_size > 10000, "PDF rendering failed or output file is empty!"
print(f"PDF generated successfully at {output_pdf} (size: {output_pdf.stat().st_size} bytes)")

print("ALL VERIFICATIONS PASSED SUCCESSFULLY!")
