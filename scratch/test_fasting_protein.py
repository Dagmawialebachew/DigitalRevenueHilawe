import asyncio, os, json, sys
from dotenv import load_dotenv
load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")
from database.db import Database
from meal_plan.generation.dataset import load_dataset
from meal_plan.generation.solver import food_macros
from meal_plan.generation.models import MacroTotals

dataset = load_dataset()
soya = dataset.food_by_id["P009"]
print("P009 (100g dry soy chunks):", soya)
m10 = food_macros(soya, 10.0)
print("10g dry soy chunks macros:", m10)

misir = dataset.recipe_by_id.get("R002", {})
print("R002 Misir wot:", misir)

ful = dataset.recipe_by_id.get("R018", {})
print("R018 Fasting ful:", ful)
