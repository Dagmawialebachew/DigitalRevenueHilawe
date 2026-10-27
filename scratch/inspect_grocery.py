import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
repo_root = Path(r"d:\The hobby 2\DigitalRevenueHilawe")
sys.path.insert(0, str(repo_root))
from datetime import date
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan

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

print(f"Total Grocery Items: {len(plan['grocery'])}")
for idx, r in enumerate(plan['grocery'], 1):
    print(f"{idx:2d}. [{r['category']}] {r['buy_item']} | Planned: {r['planned_grams']}g | Buy: {r['purchase_quantity']}")
    if r['buy_item'] is None or r['buy_item'] == "None":
        print(f"   --> None food_id: {r.get('food_id')}")
