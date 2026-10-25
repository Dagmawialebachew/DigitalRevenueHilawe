import sys
from datetime import date, timedelta
from pathlib import Path

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path(r"d:\The hobby 2\DigitalRevenueHilawe")
sys.path.insert(0, str(repo_root))

from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan
from meal_plan.documents.html_pdf_renderer import render_plan_to_pdf, render_html_document
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
    ],
}

print("=== CALCULATING NUTRITION PROFILE ===")
profile = calculate_nutrition_profile(answers)
print(f"Target Kcal: {profile.target_kcal}")
print(f"Protein: {profile.protein_g} g")
print(f"Fat: {profile.fat_g} g")
print(f"Carbs: {profile.carbs_g} g")
print(f"Water: {profile.water_target_l} L/day ({profile.water_glasses} glasses)")

assert profile.target_kcal >= 2850, f"Target kcal too low: {profile.target_kcal}"
assert 135 <= profile.protein_g <= 150, f"Protein outside 135-150g: {profile.protein_g}"
assert profile.water_target_l == 3.5, f"Water target not 3.5: {profile.water_target_l}"
assert profile.water_glasses == 14, f"Water glasses not 14: {profile.water_glasses}"

print("\n=== GENERATING 7-DAY MEAL PLAN ===")
plan = generate_plan(
    answers=answers,
    nutrition_profile=profile.to_dict(),
    meals_per_day=4,
    start_date=date(2026, 10, 26),
    duration_days=7,
    region="EUROPE",
    country_name="Germany",
)

days = plan.get("core_week") or []
assert len(days) == 7, f"Expected 7 days, got {len(days)}"

print("\n--- DAILY AUDIT ---")
injera_count = 0
for idx, day in enumerate(days):
    day_name = day.get("day_name")
    is_fasting = bool(day.get("fasting"))
    totals = day.get("totals") or {}
    k = totals.get("kcal") or 0.0
    p = totals.get("protein") or totals.get("protein_g") or 0.0
    
    # Assert fasting rule
    # Day 1: Monday, Day 2: Tuesday, Day 3: Wednesday, Day 4: Thursday, Day 5: Friday, Day 6: Saturday, Day 7: Sunday
    if idx in (0, 1, 3, 5, 6): # Mon, Tue, Thu, Sat, Sun
        assert not is_fasting, f"Day {idx+1} ({day_name}) must NOT be fasting!"
    else: # Wed, Fri
        assert is_fasting, f"Day {idx+1} ({day_name}) MUST be fasting!"
    
    # Assert calorie and protein bounds
    assert k >= 2850.0, f"Day {idx+1} ({day_name}) kcal too low ({k:.0f} < 2850)"
    assert 135.0 <= p <= 150.0, f"Day {idx+1} ({day_name}) protein out of bounds [135, 150]: {p:.1f}g"
    
    # Check foods
    day_meals = day.get("meals") or []
    meal_names = [m.get("meal_name") for m in day_meals]
    for m in day_meals:
        for it in m.get("items") or []:
            fn = it.get("food_name", "").lower()
            if "injera" in fn or "እንጀራ" in fn or it.get("food_id") == "C001":
                injera_count += 1
            assert "coach hilawe" not in fn, f"Found 'Coach Hilawe' in food name: {fn}"
    
    tag = "FASTING" if is_fasting else "OMNIVORE"
    print(f"Day {idx+1} ({day_name[:3]}) [{tag}]: {k:.0f} kcal, {p:.1f}g protein | Meals: {meal_names}")

print(f"\nTotal Injera occurrences across 7 days: {injera_count}")
assert injera_count <= 1, f"Injera appeared {injera_count} times (> 1 time) in International mode!"

print("\n=== RENDERING HTML AND PDF ARTIFACTS ===")
# Context
ctx = DocumentContext(
    client_name="Yohannes",
    plan_public_id="MP-000016",
    version_number=2,
    language="EN",
    status="APPROVED",
    hydration_target_l=profile.water_target_l,
)

html_content = render_html_document(plan, ctx, is_client_delivery=True)

# Check HTML text content for corrupt strings or bugs
broken_strings = ["114/2", "4/2 cup", "14.5 cup", "Yoharmes", "Protein   g", "Coach Hilawe Chicken", "Coach Hilawe Beef"]
for b in broken_strings:
    assert b not in html_content, f"Corrupt string '{b}' found in HTML!"

print("✓ Zero broken fraction strings (no 114/2, 4/2 cup, 14.5 cups)")
print("✓ Client name spelled 'Yohannes' (zero 'Yoharmes')")
print("✓ Zero 'Coach Hilawe' inside meals/foods")
print("✓ Day 2 protein banner renders valid numeric macro")

# Output PDFs
pdf_v2_path = repo_root / "Yohannes-7days-plan-V2.pdf"
pdf_main_path = repo_root / "Yohannes-7days-plan.pdf"

render_plan_to_pdf(plan, pdf_v2_path, client_name="Yohannes", language="EN")
render_plan_to_pdf(plan, pdf_main_path, client_name="Yohannes", language="EN")

print(f"\nSUCCESS: Generated {pdf_v2_path} ({pdf_v2_path.stat().st_size:,} bytes)")
print(f"SUCCESS: Generated {pdf_main_path} ({pdf_main_path.stat().st_size:,} bytes)")
