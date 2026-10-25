import asyncio
import os
import json
from pathlib import Path
import dotenv
import asyncpg

dotenv.load_dotenv(Path(__file__).resolve().parent.parent / ".env")

async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    row = await conn.fetchrow("SELECT food_id, kcal_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g, source_payload FROM nutrition_foods WHERE food_id = 'C001'")
    print("Before:", row["food_id"], row["kcal_per_100g"], row["protein_per_100g"], row["carbs_per_100g"], row["fat_per_100g"])
    
    # Update columns
    await conn.execute("""
        UPDATE nutrition_foods
        SET kcal_per_100g = 142,
            protein_per_100g = 4.2,
            carbs_per_100g = 28.0,
            fat_per_100g = 0.6
        WHERE food_id = 'C001'
    """)
    
    # If source_payload has json, update that too
    if row and row["source_payload"]:
        payload = dict(row["source_payload"]) if isinstance(row["source_payload"], dict) else json.loads(row["source_payload"])
        payload["kcal / 100 g"] = 142
        payload["Protein / 100 g"] = 4.2
        payload["Carbs / 100 g"] = 28.0
        payload["Fat / 100 g"] = 0.6
        await conn.execute("UPDATE nutrition_foods SET source_payload = $1 WHERE food_id = 'C001'", json.dumps(payload))
    
    row_after = await conn.fetchrow("SELECT food_id, kcal_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g FROM nutrition_foods WHERE food_id = 'C001'")
    print("After:", row_after["food_id"], row_after["kcal_per_100g"], row_after["protein_per_100g"], row_after["carbs_per_100g"], row_after["fat_per_100g"])
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
