import json
import sys
sys.path.insert(0, '.')

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from meal_plan.glossary import FOOD_GLOSSARY, RECIPE_GLOSSARY, CATEGORY_GLOSSARY

with open("meal_plan/data/hilawe_v1_3_dataset.json", "r", encoding="utf-8") as f:
    d = json.load(f)

foods = d["foods"]
print(f"Total dataset foods: {len(foods)}")

missing = []
for f in foods:
    fid = f.get("Food ID")
    if fid not in FOOD_GLOSSARY:
        missing.append((fid, f.get("Food Name"), f.get("Local / Amharic")))

print(f"Missing from FOOD_GLOSSARY: {len(missing)}")
for m in missing:
    print(f"  {m[0]}: {m[1]} (Local: {m[2]})")

print("\nChecking Recipes:")
recipes = d["recipes"]
print(f"Total dataset recipes: {len(recipes)}")
missing_rec = []
for r in recipes:
    rid = r.get("Recipe ID")
    if rid not in RECIPE_GLOSSARY:
        missing_rec.append((rid, r.get("Recipe Name"), r.get("Local Name")))
print(f"Missing from RECIPE_GLOSSARY: {len(missing_rec)}")
for m in missing_rec:
    print(f"  {m[0]}: {m[1]} (Local: {m[2]})")

print("\nChecking Categories:")
cats = set(f.get("Category") for f in foods if f.get("Category"))
missing_cat = []
for c in cats:
    if c not in CATEGORY_GLOSSARY:
        missing_cat.append(c)
print(f"Missing categories: {missing_cat}")
