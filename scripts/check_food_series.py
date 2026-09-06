import sys
import json
sys.path.insert(0, '.')
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
from meal_plan.glossary import FOOD_GLOSSARY

with open('meal_plan/data/hilawe_v1_3_dataset.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

print("=== TEMPLATES SAMPLE ===")
for t in d['templates'][:20]:
    print(f"{t['Template ID']:8} | {t['Meal Name']:45} | Slot: {t['Meal Slot']}")
