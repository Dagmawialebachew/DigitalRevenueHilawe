import sys
from datetime import date
from dotenv import load_dotenv

sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')
load_dotenv(r'd:\The hobby 2\DigitalRevenueHilawe\.env')

from meal_plan.generation.dataset import load_dataset
from meal_plan.generation.linter import MealPlanLinter

dataset = load_dataset()
linter = MealPlanLinter(strict=True)

# Let's inspect engine.py lines around 750-860
with open('meal_plan/generation/engine.py', 'r', encoding='utf-8') as f:
    text = f.read()

print("File read cleanly, length:", len(text))
