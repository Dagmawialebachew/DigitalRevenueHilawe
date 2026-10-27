import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
repo_root = Path(r"d:\The hobby 2\DigitalRevenueHilawe")
sys.path.insert(0, str(repo_root))
from datetime import date
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan
from meal_plan.documents.html_pdf_renderer import render_html_document
from meal_plan.documents.models import DocumentContext

answers = {
    "full_name": "Yohannes",
    "calculation_sex": "MALE",
    "age": 19,
    "current_weight_kg": 71.0,
    "target_weight_kg": 83.0,
    "height_cm": 189,
    "activity_level": "HEAVY_5DAYS",
    "primary_goal": "MUSCLE_GAIN",
    "meals_per_day": 4,
    "cuisine_style": "INTERNATIONAL",
    "dietary_pattern": "OMNIVORE",
    "grocery_budget": "BALANCED",
    "orthodox_fasting": "WED_FRI_AND_SEASONAL",
    "training_days_per_week": 5,
    "training_type": "GYM_STRENGTH",
    "region": "EUROPE",
    "country_name": "Germany",
    "liked_foods": [
        "EGGS", "AVOCADO", "FRUIT", "CHICKPEAS", "OATS",
        "POTATO", "PASTA", "RICE", "MILK_YOGURT", "FISH", "MISIR", "CHICKEN"
    ]
}

profile = calculate_nutrition_profile(answers)
plan = generate_plan(
    answers=answers,
    nutrition_profile=profile.to_dict(),
    meals_per_day=4,
    start_date=date(2026, 10, 26),
    duration_days=7,
    region="EUROPE",
    country_name="Germany",
)

context = DocumentContext(
    client_name="Yohannes",
    language="EN",
    plan_public_id="YOH-2026-001",
    version_number=1,
    client_profile=answers,
)

html = render_html_document(plan, context)

output_html_path = repo_root / "Yohannes-7days-plan-FINAL.html"
with open(output_html_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Rendered HTML length: {len(html)} characters to {output_html_path}")

# Verify key phrases
checks = [
    ("Muscle Gain (71.0 kg ➔ 83.0 kg)", "Cover Goal Label"),
    ("83.0 kg (Phase 1: 74.5 kg)", "Section 01 Target Metric Card"),
    ("Phase 1 Gate: 74.5 kg", "Section 01 Summary Row"),
    ("1 carton (10–12 eggs)", "Grocery Egg Packaging"),
    ("1 bottle (500 ml)", "Cooking Oil Packaging"),
    ("1 fresh loaf (~500 g)", "Sourdough Bread Packaging"),
    ("Milk, low-fat", "Milk, low-fat"),
    ("Soy milk (unsweetened)", "Soy milk (unsweetened)"),
    ("Garlic (Raw)", "Garlic (Raw)"),
    ("Onion (Raw)", "Onion (Raw)"),
    ("Tomato (Raw)", "Tomato (Raw)"),
]

all_passed = True
for needle, label in checks:
    if needle in html:
        print(f"  [PASS] {label}: found '{needle}'")
    else:
        print(f"  [FAIL] {label}: '{needle}' NOT found!")
        all_passed = False

import re
pages = re.findall(r'<div class="page(?: [^"]*)?"', html)
print(f"\nTotal page count in HTML: {len(pages)}")

titles = re.findall(r'<(?:h1|div)[^>]*class="(?:page-title|cover-main-title)[^"]*">([^<]+)<', html)
for i, t in enumerate(titles, 1):
    print(f"  Page {i:2d}: {t.strip()}")
