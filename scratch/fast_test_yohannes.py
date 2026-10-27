import sys
from datetime import date
from pathlib import Path

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path(r"d:\The hobby 2\DigitalRevenueHilawe")
sys.path.insert(0, str(repo_root))

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
    ],
}

print("=== 1. CALCULATING NUTRITION PROFILE ===")
profile = calculate_nutrition_profile(answers)
print(f"Target Kcal: {profile.target_kcal}")
print(f"Protein: {profile.protein_g} g")
print(f"Fat: {profile.fat_g} g")
print(f"Carbs: {profile.carbs_g} g")

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
print(f"Generated {len(days)} days.")

errors = []
print("\n=== 3. AUDITING MEAL PLAN ACCORDING TO SHOWSTOPPERS ===")
for day in days:
    d_num = day.get("day_number")
    d_name = day.get("day_name")
    totals = day.get("totals", {})
    kcal = totals.get("kcal", 0)
    prot = totals.get("protein", 0)
    carbs = totals.get("carbs", 0)
    fat = totals.get("fat", 0)
    print(f"Day {d_num} ({d_name}): {kcal:.1f} kcal, {prot:.1f}g P, {carbs:.1f}g C, {fat:.1f}g F")
    if kcal < 2980 or kcal > 3170:
        errors.append(f"Day {d_num} kcal {kcal:.1f} out of range [2980, 3170]")
    if prot < 135 or prot > 155:
        errors.append(f"Day {d_num} protein {prot:.1f} out of range [135, 155]")

    for meal in day.get("meals", []):
        slot = meal.get("slot") or meal.get("slot_name")
        fids = [it.get("food_id") for it in meal.get("items", []) if it.get("food_id")]
        
        # 1. Check rice cakes <= 40g
        for it in meal.get("items", []):
            if it.get("food_id") == "C020":
                g = it.get("grams", 0)
                if g > 40.0:
                    errors.append(f"Day {d_num} {slot} Rice cakes C020 exceeded 40g: {g:.1f}g!")
                else:
                    print(f"  Day {d_num} {slot} Rice cakes C020: {g:.1f}g (Comfortable)")

        # 2. Check dual oils
        has_t001 = "T001" in fids
        has_t002 = "T002" in fids
        if has_t001 and has_t002:
            errors.append(f"Day {d_num} {slot} has BOTH T001 (olive) and T002 (sunflower) oils!")

        # 3. Check snack swaps
        if "snack" in slot.lower():
            for ex in meal.get("exchange_options", []):
                for opt in ex.get("options", []):
                    opt_fid = opt.get("food_id", "")
                    if opt_fid in ("C005", "C006", "C003", "C004"):
                        errors.append(f"Day {d_num} Snack swap prescribed {opt.get('food_name')} ({opt.get('grams')}g)!")

# 4. Grocery egg audit
grocery = plan.get("grocery", [])
egg_row = next((g for g in grocery if g.get("food_id") == "A011" or "egg" in g.get("buy_item", "").lower()), None)
if egg_row:
    print(f"\nGrocery Egg purchase quantity: {egg_row.get('purchase_quantity')}")
    if "10–12" not in egg_row.get("purchase_quantity", "") and "12" not in egg_row.get("purchase_quantity", ""):
        errors.append(f"Grocery Egg quantity not 10-12 eggs: {egg_row.get('purchase_quantity')}")
else:
    errors.append("No Egg row found in grocery!")

# 5. HTML rendering & string checks
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
Path("Yohannes-7days-plan-FINAL.html").write_text(html_content, encoding="utf-8")
print(f"Saved Yohannes-7days-plan-FINAL.html ({len(html_content)} bytes)")

# Search for typos / glitches in HTML
typos = [
    "Dimer", "dimer", "gig keal", "gig kcal", "about 1 approx", "about I approx",
    "Cooked broccoli — g", "Cooked broccoli   g", "Teff injera"
]
for typo in typos:
    if typo in html_content:
        errors.append(f"Found typo '{typo}' in HTML!")

if errors:
    print("\n--- ERRORS FOUND ---")
    for err in errors:
        print("ERROR:", err)
else:
    print("\n>>> ALL 6 SHOWSTOPPERS RESOLVED & VERIFIED 100% PERFECTLY! <<<")
