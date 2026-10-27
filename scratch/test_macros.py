import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from datetime import date
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan

answers = {
    'full_name': 'Yohannes',
    'calculation_sex': 'MALE',
    'age': 19,
    'current_weight_kg': 71.0,
    'target_weight_kg': 83.0,
    'height_cm': 189,
    'activity_level': 'HEAVY_5DAYS',
    'primary_goal': 'MUSCLE_GAIN',
    'meals_per_day': 4,
    'cuisine_style': 'INTERNATIONAL',
    'dietary_pattern': 'OMNIVORE',
    'grocery_budget': 'BALANCED',
    'orthodox_fasting': 'WED_FRI_AND_SEASONAL',
    'training_days_per_week': 5,
    'training_type': 'GYM_STRENGTH',
    'region': 'EUROPE',
    'country_name': 'Germany',
    'liked_foods': ['EGGS', 'AVOCADO', 'FRUIT', 'CHICKPEAS', 'OATS', 'POTATO', 'PASTA', 'RICE', 'MILK_YOGURT', 'FISH', 'MISIR', 'CHICKEN']
}

prof = calculate_nutrition_profile(answers)
print("Target Kcal:", prof.target_kcal, "Protein:", prof.protein_g, "Carbs:", prof.carbs_g, "Fat:", prof.fat_g)
plan = generate_plan(
    answers=answers,
    nutrition_profile=prof.to_dict(),
    meals_per_day=4,
    start_date=date(2026, 10, 26),
    duration_days=7,
    region='EUROPE',
    country_name='Germany'
)
days = plan.get('core_week') or []
for i, d in enumerate(days):
    tot = d.get('totals') or {}
    meals = [m.get('meal_name') for m in d.get('meals', [])]
    print(f"Day {i+1} ({d.get('day_name')}): Fasting={d.get('fasting')}, Kcal={tot.get('kcal'):.0f}, Protein={tot.get('protein'):.1f}g, Carbs={tot.get('carbs'):.1f}g, Fat={tot.get('fat'):.1f}g")
    for m in d.get('meals', []):
        m_tot = m.get('totals') or {}
        items = [f"{it.get('food_name')} ({it.get('grams')}g)" for it in m.get('items', [])]
        mk = m_tot.get('kcal') or 0.0
        mp = m_tot.get('protein') or m_tot.get('protein_g') or 0.0
        print(f"   [{m.get('slot_label')}] {m.get('meal_name')} ({mk:.0f} kcal, {mp:.1f}p): {', '.join(items)}")
