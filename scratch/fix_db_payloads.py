import asyncio
import os
import json
import sys
from dotenv import load_dotenv
import asyncpg

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    
    # 1. Update MN-L07 in nutrition_templates
    row_t = await conn.fetchrow("SELECT source_payload FROM nutrition_templates WHERE template_id = 'MN-L07'")
    if row_t:
        p = json.loads(row_t["source_payload"]) if isinstance(row_t["source_payload"], str) else dict(row_t["source_payload"])
        p["Meal Name"] = "Beef key wot and injera"
        p["Meal Name AM"] = "ቀይ ወጥ ከእንጀራ ጋር"
        p["Budget"] = "Value"
        p_json = json.dumps(p, ensure_ascii=False)
        await conn.execute("UPDATE nutrition_templates SET meal_name = 'Beef key wot and injera', meal_name_am = 'ቀይ ወጥ ከእንጀራ ጋር', budget = 'Value', source_payload = $1 WHERE template_id = 'MN-L07'", p_json)
        print("Updated MN-L07 source_payload and columns.")

    # 2. Update R023 in nutrition_recipes
    row_r = await conn.fetchrow("SELECT source_payload FROM nutrition_recipes WHERE recipe_id = 'R023'")
    if row_r:
        p = json.loads(row_r["source_payload"]) if isinstance(row_r["source_payload"], str) else dict(row_r["source_payload"])
        p["Recipe Name"] = "Beef Key Wot"
        p["Local Name"] = "ቀይ ወጥ"
        p["Recipe Name AM"] = "ቀይ ወጥ"
        p_json = json.dumps(p, ensure_ascii=False)
        await conn.execute("UPDATE nutrition_recipes SET recipe_name = 'Beef Key Wot', local_name = 'ቀይ ወጥ', recipe_name_en = 'Beef Key Wot', recipe_name_am = 'ቀይ ወጥ', source_payload = $1 WHERE recipe_id = 'R023'", p_json)
        print("Updated R023 source_payload and columns.")

    # 3. Update R023 in nutrition_template_components
    await conn.execute("""
        UPDATE nutrition_template_components 
        SET item_name = 'Beef Key Wot', exact_instruction = 'Beef Key Wot — 320 g'
        WHERE item_id = 'R023'
    """)
    print("Updated nutrition_template_components for R023.")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
