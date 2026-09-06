import json
import sys
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")

with open("meal_plan/data/hilawe_v1_3_dataset.json", "r", encoding="utf-8") as f:
    d = json.load(f)

measures = set()
for food in d["foods"]:
    m = food.get("Familiar Measure")
    if m:
        measures.add(m)

print(f"Total unique familiar measures: {len(measures)}")
for m in sorted(measures):
    print(f"  '{m}'")
