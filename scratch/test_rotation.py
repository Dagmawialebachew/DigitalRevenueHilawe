import sys
sys.path.insert(0, ".")
from meal_plan.generation.dataset import load_dataset
from meal_plan.generation.selection import TemplateSelector

dataset = load_dataset()
answers = {
    "grocery_budget": "SAVE",
    "dietary_pattern": "OMNIVORE",
    "orthodox_fasting": "WED_FRI",
    "cuisine_style": "ETHIOPIAN",
}
selector = TemplateSelector(dataset, answers, region="ETHIOPIA")
print("\n=== 7-Day Omnivore Wed/Fri Fasting Rotation ===")
fasting_days = [False, False, True, False, True, False, False]
for d in range(7):
    f = fasting_days[d]
    bf = selector.choose(fasting=f, source_slot="Breakfast", day_index=d)
    lu = selector.choose(fasting=f, source_slot="Lunch", day_index=d)
    di = selector.choose(fasting=f, source_slot="Dinner", day_index=d)
    status = "(FASTING)" if f else "(NON-FASTING)"
    print(f"Day {d+1} {status}:")
    print(f"  B: {bf.get('Meal Name')}")
    print(f"  L: {lu.get('Meal Name')}")
    print(f"  D: {di.get('Meal Name')}")
