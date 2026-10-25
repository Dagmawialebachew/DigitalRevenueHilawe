import asyncio
import os
import json
import sys
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

DATASET_PATH = "meal_plan/data/hilawe_v1_3_dataset.json"

def update_dataset_json():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Update recipes
    for r in data.get("recipes", []):
        if r.get("Recipe ID") == "R023":
            r["Recipe Name"] = "Beef Key Wot"
            r["Local Name"] = "ቀይ ወጥ"
        # Fix any 'ፋል' typo
        for k, v in r.items():
            if isinstance(v, str) and "ፋል" in v:
                r[k] = v.replace("ፋል", "ፉል")

    # 2. Update templates
    for t in data.get("templates", []):
        tid = t.get("Template ID")
        if tid == "MN-L07":
            t["Meal Name"] = "Beef key wot and injera"
            t["Budget"] = "Value"
            if "Meal Name AM" in t:
                t["Meal Name AM"] = "ቀይ ወጥ ከእንጀራ ጋር"
        elif tid in ("MN-L02", "MN-D02", "MF-L01", "MF-L02", "MN-L04", "MN-L06"):
            t["Budget"] = "Value"

        for k, v in t.items():
            if isinstance(v, str) and "ፋል" in v:
                t[k] = v.replace("ፋል", "ፉል")

    # 3. Update template components item names
    for c in data.get("template_components", []):
        if c.get("Item ID") == "R023":
            c["Item Name"] = "Beef Key Wot"
            c["Exact Instruction"] = "Beef Key Wot — 320 g"

    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Updated meal_plan/data/hilawe_v1_3_dataset.json successfully!")

async def update_database():
    from database.db import Database
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("No DATABASE_URL found; skipping DB sync.")
        return
    db = Database(db_url)
    await db.connect()
    
    # Update R023
    await db.execute("""
        UPDATE nutrition_recipes 
        SET recipe_name = 'Beef Key Wot', 
            local_name = 'ቀይ ወጥ', 
            recipe_name_en = 'Beef Key Wot', 
            recipe_name_am = 'ቀይ ወጥ' 
        WHERE recipe_id = 'R023'
    """)
    print("Database: Updated nutrition_recipes R023 to 'ቀይ ወጥ'")

    # Update MN-L07
    await db.execute("""
        UPDATE nutrition_templates 
        SET meal_name = 'Beef key wot and injera', 
            meal_name_am = 'ቀይ ወጥ ከእንጀራ ጋር', 
            budget = 'Value' 
        WHERE template_id = 'MN-L07'
    """)
    print("Database: Updated nutrition_templates MN-L07 to 'ቀይ ወጥ ከእንጀራ ጋር'")

    # Update budgets for lunch rotation
    await db.execute("""
        UPDATE nutrition_templates 
        SET budget = 'Value' 
        WHERE template_id IN ('MN-L02', 'MN-D02', 'MF-L01', 'MF-L02', 'MN-L04', 'MN-L06')
    """)
    print("Database: Set Value budget on MN-L02, MN-D02, MF-L01, MF-L02, MN-L04, MN-L06")

    # Fix any 'ፋል' in nutrition_recipes and nutrition_templates
    await db.execute("""
        UPDATE nutrition_recipes 
        SET recipe_name = REPLACE(recipe_name, 'ፋል', 'ፉል'),
            local_name = REPLACE(local_name, 'ፋል', 'ፉል'),
            recipe_name_am = REPLACE(recipe_name_am, 'ፋል', 'ፉል')
        WHERE recipe_name LIKE '%ፋል%' OR local_name LIKE '%ፋል%' OR recipe_name_am LIKE '%ፋል%'
    """)
    await db.execute("""
        UPDATE nutrition_templates 
        SET meal_name = REPLACE(meal_name, 'ፋል', 'ፉል'),
            meal_name_am = REPLACE(meal_name_am, 'ፋል', 'ፉል')
        WHERE meal_name LIKE '%ፋል%' OR meal_name_am LIKE '%ፋል%'
    """)
    print("Database: Fixed any ፋል typos")

    await db.disconnect()

if __name__ == "__main__":
    update_dataset_json()
    asyncio.run(update_database())
