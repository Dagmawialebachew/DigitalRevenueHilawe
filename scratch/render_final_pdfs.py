import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
repo_root = Path(r"d:\The hobby 2\DigitalRevenueHilawe")
sys.path.insert(0, str(repo_root))

from datetime import date
from pypdf import PdfReader
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan
from meal_plan.documents.html_pdf_renderer import render_plan_to_pdf

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

print("1. Calculating nutrition profile...")
profile = calculate_nutrition_profile(answers)
print(f"   Target: {profile.target_kcal} kcal | {profile.protein_g}g P")

print("2. Generating 7-day meal plan...")
plan = generate_plan(
    answers=answers,
    nutrition_profile=profile.to_dict(),
    meals_per_day=4,
    start_date=date(2026, 10, 26),
    duration_days=7,
    region="EUROPE",
    country_name="Germany",
)
print(f"   Plan days: {len(plan.get('core_week', []))}")
print(f"   Grocery items: {len(plan.get('grocery', []))}")

pdf_targets = [
    repo_root / "Yohannes-7days-plan-FINAL.pdf",
    repo_root / "Yohannes-7days-plan-V2.pdf",
    repo_root / "Yohannes-7days-plan-PERFECT.pdf",
]

for pdf_path in pdf_targets:
    print(f"\n3. Compiling PDF: {pdf_path.name}...")
    actual_path = render_plan_to_pdf(
        plan=plan,
        output_pdf_path=pdf_path,
        language="EN",
        client_name="Yohannes",
    )
    
    reader = PdfReader(str(actual_path))
    page_count = len(reader.pages)
    file_size_kb = actual_path.stat().st_size / 1024.0
    print(f"   --> Success! {actual_path.name}: {page_count} pages ({file_size_kb:.1f} KB)")
    assert page_count == 15, f"Expected 15 pages, got {page_count}"

print("\n=== ALL PDFs COMPILED AND VERIFIED (EXACTLY 15 PAGES) ===")
