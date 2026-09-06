import json
import sys
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")

with open("meal_plan/data/hilawe_v1_3_dataset.json", "r", encoding="utf-8") as f:
    d = json.load(f)

templates = d.get("templates", [])
print(f"Total templates: {len(templates)}")
for t in templates:
    print(f"{t['Template ID']:8} | {t['Meal Slot']:10} | {t['Meal Name']}")
