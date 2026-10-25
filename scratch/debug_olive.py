import sys
from pathlib import Path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from datetime import date
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan

answers = {
    'calculation_sex': 'MALE', 'age': 25, 'current_weight_kg': 45.0, 'target_weight_kg': 60.0,
    'height_cm': 170, 'activity_level': 'LIGHTLY_ACTIVE', 'primary_goal': 'MUSCLE_GAIN',
    'meals_per_day': 3, 'cuisine_style': 'ETHIOPIAN', 'dietary_pattern': 'OMNIVORE',
    'grocery_budget': 'SAVE', 'orthodox_fasting': 'NONE', 'fish_during_fast': False,
    'training_days_per_week': 3, 'training_type': 'HOME_WORKOUT',
}
profile = calculate_nutrition_profile(answers)
plan = generate_plan(answers=answers, nutrition_profile=profile.to_dict(), meals_per_day=3, start_date=date(2026, 10, 26), duration_days=14, region='ETHIOPIA')

for d_idx, day in enumerate(plan['core_week']):
    for m in day['meals']:
        for it in m['items']:
            if 'olive' in it.get('food_name', '').lower() or it.get('food_id') == 'T001':
                print(f"Day {d_idx+1} Meal {m.get('slot')} ({m.get('meal_name')} / template={m.get('template_id')} / recipe={it.get('recipe_id')}): {it}")

for g in plan['grocery']:
    if 'olive' in g.get('buy_item', '').lower():
        print('Grocery item:', g)
