import sys
from datetime import date
from pathlib import Path
from pypdf import PdfReader

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

print("=== 1. CALCULATING NUTRITION PROFILE ===")
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

print("\n=== 2. GENERATING 7-DAY MEAL PLAN ===")
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

print("\n--- 3. DAILY MACRO & NUTRITION AUDIT ---")
injera_count = 0
for idx, day in enumerate(days):
    day_name = day.get("day_name")
    is_fasting = bool(day.get("fasting"))
    totals = day.get("totals") or {}
    k = totals.get("kcal") or 0.0
    p = totals.get("protein") or totals.get("protein_g") or 0.0
    
    # Assert fasting rule
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
        mname = m.get("meal_name") or ""
        # Check Day 6 Breakfast title
        if idx == 5 and m.get("slot") == "Breakfast":
            assert "Boiled eggs, bread and orange" in mname, f"Day 6 Breakfast title incorrect: {mname}"
            
        for it in m.get("items") or []:
            fn = it.get("food_name", "").lower()
            if "injera" in fn or "እንጀራ" in fn or it.get("food_id") == "C001":
                injera_count += 1
            assert "coach hilawe" not in fn, f"Found 'Coach Hilawe' in food name: {fn}"
            # Ensure no papaya or peanuts in Tuna Pasta
            if "tuna pasta" in mname.lower():
                assert "papaya" not in fn, f"Found papaya in Tuna Pasta: {fn}"
                assert "peanuts" not in fn, f"Found peanuts in Tuna Pasta: {fn}"
            # Ensure no white rice in snacks
            if m.get("slot") == "Snack":
                assert "white rice" not in fn, f"Found white rice in snack: {fn}"
    
    tag = "FASTING" if is_fasting else "OMNIVORE"
    print(f"Day {idx+1} ({day_name[:3]}) [{tag}]: {k:.0f} kcal, {p:.1f}g protein | Meals: {meal_names}")

print(f"\nTotal Injera occurrences across 7 days: {injera_count}")
assert injera_count <= 1, f"Injera appeared {injera_count} times (> 1 time) in International mode!"

print("\n=== 4. RENDERING HTML AND PDF ARTIFACTS ===")
ctx = DocumentContext(
    client_name="Yohannes",
    client_profile=answers,
    plan_public_id="MP-000016",
    version_number=2,
    language="EN",
    status="APPROVED",
    hydration_target_l=profile.water_target_l,
)

html_content = render_html_document(plan, ctx, is_client_delivery=True)

# Check HTML text content for corrupt strings or bugs
broken_strings = [
    "114/2", "4/2 cup", "14.5 cup", "Yoharmes", "Protein   g",
    "Coach Hilawe Chicken", "Coach Hilawe Beef", " 1.25 g", "/2 large avocado"
]
for b in broken_strings:
    assert b not in html_content, f"Corrupt string '{b}' found in HTML!"

print("✓ Zero broken fraction strings (no 114/2, 4/2 cup, 14.5 cups, no 1.25 g, no /2 large avocado)")
print("✓ Client name spelled 'Yohannes' (zero 'Yoharmes')")
print("✓ Zero 'Coach Hilawe' inside meals/foods")
print("✓ Day 2 protein banner renders valid numeric macro")

# Output PDFs
pdf_v2_path = repo_root / "Yohannes-7days-plan-V2.pdf"
pdf_final_path = repo_root / "Yohannes-7days-plan-FINAL.pdf"
html_v2_path = repo_root / "Yohannes-7days-plan-V2.html"

html_v2_path.write_text(html_content, encoding="utf-8")
print(f"✓ Wrote HTML to {html_v2_path}")

render_plan_to_pdf(plan, pdf_v2_path, client_name="Yohannes", language="EN")
render_plan_to_pdf(plan, pdf_final_path, client_name="Yohannes", language="EN")

print(f"✓ Generated {pdf_v2_path} ({pdf_v2_path.stat().st_size:,} bytes)")
print(f"✓ Generated {pdf_final_path} ({pdf_final_path.stat().st_size:,} bytes)")

print("\n=== 5. STRICT PDF STRUCTURE & CONTENT ASSERTIONS ===")
reader = PdfReader(str(pdf_v2_path))
num_pages = len(reader.pages)
print(f"Total PDF pages: {num_pages}")
assert num_pages == 15, f"Expected exactly 15 pages in PDF, got {num_pages}!"

page1_clean = " ".join((reader.pages[0].extract_text() or "").split())
page2_clean = " ".join((reader.pages[1].extract_text() or "").split())

# Check Muscle Gain on pages 1 and 2
assert "Muscle Gain" in page1_clean, f"Page 1 missing 'Muscle Gain': {page1_clean}"
assert "Muscle Gain" in page2_clean, f"Page 2 missing 'Muscle Gain': {page2_clean}"
assert "71" in page2_clean and "83" in page2_clean, f"Page 2 missing weights: {page2_clean}"
print("✓ Primary Goal is 'Muscle Gain' on Pages 1 & 2")
print("✓ Biometric weights 71 kg and 83 kg present on Page 2")

# Check odd page footers on Pages 6, 8, 10 (0-indexed: 5, 7, 9)
for p_num in (6, 8, 10):
    p_clean = " ".join((reader.pages[p_num - 1].extract_text() or "").split())
    assert "3.5 L" in p_clean, f"Page {p_num} footer missing hydration target '3.5 L': {p_clean}"
    assert f"Page {p_num}" in p_clean and "15" in p_clean, f"Page {p_num} footer missing page number 'Page {p_num} / 15': {p_clean}"
print("✓ Pages 6, 8, 10 footers intact with '3.5 L/day' and 'Page X/15'")

# Check Grocery List on pages 13 & 14 (0-indexed: 12, 13)
grocery_text = (reader.pages[12].extract_text() or "") + " " + (reader.pages[13].extract_text() or "")
assert "Chicken" in grocery_text or "chicken" in grocery_text, "Grocery list missing Chicken!"
assert "Tilapia" in grocery_text or "tilapia" in grocery_text, "Grocery list missing Tilapia!"
assert "Chickpeas" in grocery_text or "chickpeas" in grocery_text, "Grocery list missing Chickpeas!"
assert "266" not in grocery_text and "256" not in grocery_text, "Found glyph corruption '266' or '256' in grocery list!"
assert "ፍሬ" not in grocery_text, "Found Amharic 'ፍሬ' in English grocery list!"
assert "eggs" in grocery_text.lower(), "Grocery list missing English 'eggs' count!"

print("✓ Grocery list includes unpacked Chicken, Tilapia, Chickpeas")
print("✓ Zero glyph corruption (no '266', '256', or 'ፍሬ' in grocery list)")
print("✓ English egg count formatted with 'eggs'")

print("\n=======================================================")
print("  ALL 100% OF VALIDATION ASSERTIONS PASSED PERFECTLY!  ")
print("=======================================================")
