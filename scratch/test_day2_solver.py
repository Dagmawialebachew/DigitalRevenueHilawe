import sys
sys.path.insert(0, '.')
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.dataset import HilaweDataset
from meal_plan.generation.solver import DaySolver
from meal_plan.generation.selection import TemplateSelector
from meal_plan.generation.meal_structure import meal_structure

answers = {
    'full_name': 'Yohannes', 'calculation_sex': 'MALE', 'age': 19, 'current_weight_kg': 71.0,
    'target_weight_kg': 83.0, 'height_cm': 189, 'activity_level': 'HEAVY_5DAYS',
    'primary_goal': 'MUSCLE_GAIN', 'meals_per_day': 4, 'cuisine_style': 'INTERNATIONAL',
    'dietary_pattern': 'OMNIVORE', 'grocery_budget': 'BALANCED', 'orthodox_fasting': 'WED_FRI_AND_SEASONAL',
    'training_days_per_week': 5, 'training_type': 'GYM_STRENGTH', 'region': 'EUROPE', 'country_name': 'Germany',
    'liked_foods': ['EGGS', 'AVOCADO', 'FRUIT', 'CHICKPEAS', 'OATS', 'POTATO', 'PASTA', 'RICE', 'MILK_YOGURT', 'FISH', 'MISIR', 'CHICKEN'],
}
profile = calculate_nutrition_profile(answers)
from meal_plan.generation.dataset import load_dataset
dataset = load_dataset()
selector = TemplateSelector(dataset, answers, region="EUROPE", country_name="Germany")
specs = meal_structure(4)
# Day 2 templates:
# Breakfast: MN-B03, Lunch: MN-L01, Dinner: MN-D06, Snack: MN-S01
tmpl_by_id = {str(x.get("Template ID")): x for x in dataset.templates}
selected = [
    (specs[0], tmpl_by_id["MN-B03"]),
    (specs[1], tmpl_by_id["MN-L01"]),
    (specs[2], tmpl_by_id["MN-D06"]),
    (specs[3], tmpl_by_id["MN-S01"]),
]

solver = DaySolver(dataset, answers)
sol = solver.solve(selected, profile.to_dict(), fasting=False)
print("Scale:", sol.scale)
print("Totals:", sol.totals)
print("Extras:", sol.extras)
print("Food by slot:", sol.food_by_slot)
