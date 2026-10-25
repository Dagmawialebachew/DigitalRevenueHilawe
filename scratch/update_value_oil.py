import json
import asyncio
import os
from pathlib import Path
import dotenv
import asyncpg

repo_root = Path(__file__).resolve().parent.parent
dotenv.load_dotenv(repo_root / ".env")

# 1. Update hilawe_v1_3_dataset.json
json_path = repo_root / "meal_plan" / "data" / "hilawe_v1_3_dataset.json"
with open(json_path, encoding="utf-8") as f:
    data = json.load(f)

for c in data["template_components"]:
    if c.get("Template ID") in ("MN-D09", "MF-L08", "MF-D08") and c.get("Item ID") == "T001":
        c["Item ID"] = "T002"
        c["Item Name"] = "Sunflower oil"
        if "Olive oil" in str(c.get("Exact Instruction") or ""):
            c["Exact Instruction"] = c["Exact Instruction"].replace("Olive oil", "Sunflower oil")

with open(json_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print("Updated hilawe_v1_3_dataset.json")

# 2. Update PostgreSQL nutrition_template_components
async def update_db():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    await conn.execute("""
        UPDATE nutrition_template_components
        SET item_id = 'T002', item_name = 'Sunflower oil'
        WHERE template_id IN ('MN-D09', 'MF-L08', 'MF-D08') AND item_id = 'T001'
    """)
    rows = await conn.fetch("""
        SELECT template_id, item_id, item_name 
        FROM nutrition_template_components
        WHERE template_id IN ('MN-D09', 'MF-L08', 'MF-D08') AND item_id = 'T002'
    """)
    print("DB Updated rows count:", len(rows))
    await conn.close()

asyncio.run(update_db())
