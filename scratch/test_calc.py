import asyncio, os, json, sys
from dotenv import load_dotenv
load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")
from database.db import Database
from meal_plan.generation.dataset import load_dataset
from meal_plan.generation.solver import food_macros
from meal_plan.generation.models import MacroTotals, MealItem
from meal_plan.generation.engine import generate_plan
from datetime import date

dataset = load_dataset()
soya_food = dataset.food_by_id["P009"]

# Let's inspect Day 3 adjustment:
# Currently Day 3: Lunch has 30g soya chunks. Dinner has Misir Wot 250g, Atkilt Wot 200g, Injera 60g.
# If Lunch soya chunks is 50g (+20g -> +10.4g protein, +69 kcal)
# If Dinner has 55g soya chunks (+55g -> +28.6g protein, +190 kcal)
# And Dinner Atkilt Wot is 100g (-100g -> -60 kcal) and Misir Wot is 200g (-50g -> -57 kcal, -3.3g protein)
# Total protein = 77.6 + 10.4 + 28.6 - 3.3 = 113.3g!
# Total kcal = 1586 + 69 + 190 - 60 - 57 = 1728 kcal (just 1 kcal over 1727).
# If Dinner Atkilt Wot is 80g (-120g -> -72 kcal): Kcal = 1716 kcal!

# Let's inspect Day 5 adjustment:
# Currently Day 5: 1672 kcal, P: 78.4g.
# Lunch: Misir Wot 325g, Gomen 175g, Injera 120g.
# Dinner: Fasting Ful 330g, Injera 120g, Tomato 160g.
# If Lunch: Misir Wot 200g (-125g -> -142 kcal, -8.3g protein) + Soya Chunks 50g (+50g -> +172.5 kcal, +26.0g protein).
# If Dinner: Fasting Ful 220g (-110g -> -120 kcal, -8.8g protein) + Soya Chunks 50g (+50g -> +172.5 kcal, +26.0g protein).
# Breakfast Oats: 50g instead of 60g (-10g -> -38 kcal, -1.3g protein).
# Total Day 5 Protein: 78.4 - 8.3 + 26.0 - 8.8 + 26.0 - 1.3 = 112.0g!
# Total Day 5 Kcal: 1672 - 142 + 172.5 - 120 + 172.5 - 38 = 1717 kcal!

print("Testing exact calculations...")
soya_50 = food_macros(soya_food, 50.0)
soya_55 = food_macros(soya_food, 55.0)
print("50g soya:", soya_50)
print("55g soya:", soya_55)
