import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with open("meal_plan/data/hilawe_v1_3_dataset.json", "r", encoding="utf-8") as f:
    d = json.load(f)

for r in d["recipes"]:
    print(f"=== {r.get('Recipe ID')} | {r.get('Recipe Name')} ===")
    print(f"Summary: {r.get('Ingredients Summary')}")
    print(f"Method: {r.get('Method')}\n")
