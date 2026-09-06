import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with open("meal_plan/data/hilawe_v1_3_dataset.json", "r", encoding="utf-8") as f:
    d = json.load(f)

print("=== CANONICAL DATASET FOODS P001-P015 ===")
for food in d["foods"]:
    fid = food.get("Food ID")
    if fid and fid.startswith("P"):
        print(f"{fid:5} | Name: {food.get('Food Name'):35} | Local: {food.get('Local / Amharic'):25} | kcal: {food.get('kcal / 100 g')}")

print("\n=== CANONICAL RECIPES (FIRST 10) ===")
for r in d["recipes"][:10]:
    print(f"{r.get('Recipe ID'):5} | Name: {r.get('Recipe Name'):30} | Local: {r.get('Local Name'):30}")
