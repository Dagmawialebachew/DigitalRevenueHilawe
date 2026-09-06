import sys
sys.path.insert(0, ".")
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
from meal_plan.generation.formatting import familiar_portion, grams_text

print(familiar_portion(1.0, 'about 1 cup cooked', 'AM'))
print(familiar_portion(1.0, '1 palm-and-a-half', 'AM'))
print(familiar_portion(1.5, 'about 2 large eggs', 'AM'))
print(familiar_portion(1.0, '1 medium rolled piece', 'AM'))
print(grams_text(150, 'AM'))
