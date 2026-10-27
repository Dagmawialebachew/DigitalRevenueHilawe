import sys
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
print("Target Kcal:", profile.target_kcal, "Target Protein:", profile.protein_g)
