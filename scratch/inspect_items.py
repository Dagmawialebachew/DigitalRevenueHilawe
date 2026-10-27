import sys
sys.path.insert(0, '.')
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan
from datetime import date

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
for idx, day in enumerate(plan['core_week']):
    print(f"=== Day {idx+1} ===")
    for m in day['meals']:
        mname = m['meal_name']
        for it in m['items']:
            fid = it.get('food_id')
            rid = it.get('recipe_id')
            fn = it.get('food_name')
            g = it.get('grams')
            print(f"   [{mname}] fid={fid}, rid={rid}, name={fn}, g={g}")

print("\n=== GROCERY ITEMS ===")
for item in plan['grocery']:
    print(f"   - {item.get('buy_item')} ({item.get('category')}) | Planned: {item.get('planned_grams')}g | Buy: {item.get('buy_weight_g')}g | Qty: {item.get('purchase_quantity_en')}")
