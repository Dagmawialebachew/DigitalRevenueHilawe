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
    
    tids = ('MN-L02', 'MN-D02', 'MF-L01', 'MF-L02', 'MN-L04', 'MN-L06', 'MN-L07')
    rows = await conn.fetch("SELECT template_id, budget, source_payload FROM nutrition_templates WHERE template_id = ANY($1::text[])", list(tids))
    for r in rows:
        tid = r['template_id']
        p = json.loads(r['source_payload']) if isinstance(r['source_payload'], str) else dict(r['source_payload'])
        p["Budget"] = "Value"
        p_json = json.dumps(p, ensure_ascii=False)
        await conn.execute("UPDATE nutrition_templates SET budget = 'Value', source_payload = $1 WHERE template_id = $2", p_json, tid)
        print(f"Updated {tid} source_payload Budget -> Value")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
