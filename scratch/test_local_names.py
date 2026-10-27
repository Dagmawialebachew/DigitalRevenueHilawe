import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
repo_root = Path(r"d:\The hobby 2\DigitalRevenueHilawe")
sys.path.insert(0, str(repo_root))

from meal_plan.documents.helpers import local_food_name

items = [
    ("A015", "Low-fat fresh milk"),
    ("P014", "Fortified soy milk (unsweetened)"),
    ("V003", "Fresh garlic"),
    ("V001", "Fresh red/yellow onions"),
    ("V002", "Fresh tomatoes"),
]

for fid, name in items:
    en_res = local_food_name(fid, name, "EN")
    am_res = local_food_name(fid, name, "AM")
    print(f"{fid}: '{name}' -> EN='{en_res}' | AM='{am_res}'")
