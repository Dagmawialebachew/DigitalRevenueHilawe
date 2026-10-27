import sys
from datetime import date
from pathlib import Path

repo_root = Path(r"d:\The hobby 2\DigitalRevenueHilawe")
sys.path.insert(0, str(repo_root))

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

for d_idx in (2, 3, 5):  # Day 3, 4, 6
    day = plan["core_week"][d_idx]
    m = day.get("totals", {})
    name = day.get("day_name")
    print(f"=== Day {d_idx+1} ({name}): {m.get('kcal',0):.1f} kcal, {m.get('protein',0):.1f}g P, {m.get('carbs',0):.1f}g C, {m.get('fat',0):.1f}g F ===")
    for meal in day.get("meals", []):
        mm = meal.get("macros", {})
        print(f"  -- {meal.get('slot')}: {meal.get('meal_name')} ({mm.get('kcal',0):.1f} kcal, {mm.get('protein',0):.1f}g P)")
        for it in meal.get("items", []):
            im = it.get("macros", {})
            print(f"     {it.get('food_name')} ({it.get('food_id') or it.get('recipe_id')}): {it.get('grams',0):.1f}g -> {im.get('kcal',0):.1f} kcal, {im.get('protein',0):.1f}g P")
