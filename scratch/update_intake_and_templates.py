import os, sys, asyncio, json
from dotenv import load_dotenv
import asyncpg

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv(r'd:\The hobby 2\DigitalRevenueHilawe\.env')

async def main():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    try:
        # Check intake 186
        intake = await conn.fetchrow('SELECT id, answers FROM meal_intakes WHERE id = 186')
        ans = intake['answers'] if isinstance(intake['answers'], dict) else json.loads(intake['answers'])
        print("Intake 186 food_intolerances now:", ans.get('food_intolerances'))

        # Update MN-B02 budget to Value
        t = await conn.fetchrow("SELECT template_id, budget, source_payload FROM nutrition_templates WHERE template_id = 'MN-B02'")
        if t:
            p = json.loads(t['source_payload']) if isinstance(t['source_payload'], str) else dict(t['source_payload'])
            p["Budget"] = "Value"
            await conn.execute("UPDATE nutrition_templates SET budget = 'Value', source_payload = $1 WHERE template_id = 'MN-B02'", json.dumps(p, ensure_ascii=False))
            print("Updated MN-B02 budget and source_payload to Value")

    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
