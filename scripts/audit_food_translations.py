import asyncio
import os
import sys
from dotenv import load_dotenv
import asyncpg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

async def main():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"), statement_cache_size=0)
    foods = await conn.fetch("""
        SELECT 
            food_id, food_name_en, food_name_am, category, category_am, 
            familiar_measure, standard_portion_g, unit,
            kcal_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g, fibre_per_100g,
            fasting_allowed, fish_item
        FROM nutrition_foods
        ORDER BY food_id ASC
    """)
    
    with open("artifacts/all_111_foods_audit.txt", "w", encoding="utf-8") as f:
        f.write(f"=== FULL AUDIT OF ALL {len(foods)} NUTRITION FOODS ===\n\n")
        current_cat = None
        for r in foods:
            cat = r["category"]
            if cat != current_cat:
                current_cat = cat
                f.write(f"\n=======================================================\n")
                f.write(f"CATEGORY: {cat} (AM: {r['category_am']})\n")
                f.write(f"=======================================================\n")
            
            f.write(f"[{r['food_id']}] EN: {r['food_name_en']}\n")
            f.write(f"       AM: {r['food_name_am']}\n")
            f.write(f"       PORTION: {r['standard_portion_g']}{r['unit']} | FAMILIAR: {r['familiar_measure']}\n")
            f.write(f"       MACROS/100g: {float(r['kcal_per_100g']):.1f} kcal | P: {float(r['protein_per_100g']):.1f}g | C: {float(r['carbs_per_100g']):.1f}g | F: {float(r['fat_per_100g']):.1f}g | Fib: {float(r['fibre_per_100g']):.1f}g\n")
            f.write(f"       FASTING: {r['fasting_allowed']} | FISH: {r['fish_item']}\n")
            f.write("-------------------------------------------------------\n")
            
    print(f"Dumped {len(foods)} foods to artifacts/all_111_foods_audit.txt")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
