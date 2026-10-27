import sys
from pathlib import Path
sys.path.insert(0, '.')
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan
from datetime import date

answers = {
    'full_name': 'Yohannes', 'calculation_sex': 'MALE', 'age': 19, 'current_weight_kg': 71.0,
    'target_weight_kg': 83.0, 'height_cm': 189, 'activity_level': 'HEAVY_5DAYS',
    'primary_goal': 'MUSCLE_GAIN', 'meals_per_day': 4, 'cuisine_style': 'INTERNATIONAL',
    'dietary_pattern': 'OMNIVORE', 'grocery_budget': 'BALANCED', 'orthodox_fasting': 'WED_FRI_AND_SEASONAL',
    'training_days_per_week': 5, 'training_type': 'GYM_STRENGTH', 'region': 'EUROPE', 'country_name': 'Germany',
    'liked_foods': ['EGGS', 'AVOCADO', 'FRUIT', 'CHICKPEAS', 'OATS', 'POTATO', 'PASTA', 'RICE', 'MILK_YOGURT', 'FISH', 'MISIR', 'CHICKEN'],
}
profile = calculate_nutrition_profile(answers)
plan = generate_plan(answers=answers, nutrition_profile=profile.to_dict(), meals_per_day=4, start_date=date(2026, 10, 26), duration_days=7, region='EUROPE', country_name='Germany')
for idx, day in enumerate(plan['core_week']):
    totals = day['totals']
    dname = day['day_name']
    k = totals['kcal']
    p = totals['protein']
    c = totals['carbs']
    f = totals['fat']
    print(f"Day {idx+1} ({dname}): {k:.0f} kcal, {p:.1f}g prot, {c:.0f}g carbs, {f:.0f}g fat")
    for m in day['meals']:
        slot = m['slot']
        mname = m['meal_name']
        mk = m['macros']['kcal']
        items_str = ', '.join([f"{it['food_name']} ({it['grams']:.0f}g)" for it in m['items']])
        print(f"   {slot}: {mname} ({mk:.0f} kcal) -> {items_str}")
