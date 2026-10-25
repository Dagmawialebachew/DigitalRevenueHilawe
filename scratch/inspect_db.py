import asyncio
import os
import json
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, ".")
from database.db import Database

async def inspect():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    
    order = await db.fetchrow("""
        SELECT o.*, i.answers, i.nutrition_profile
        FROM meal_orders o
        LEFT JOIN meal_intakes i ON o.intake_id = i.id
        WHERE o.id = 47
    """)
    ans = order["answers"]
    if isinstance(ans, str): ans = json.loads(ans)
    print("Order 47 user_id:", order["user_id"])
    print("Order 47 duration_days:", order["duration_days"])
    print("Order 47 answers:")
    for k, v in ans.items():
        print(f"  {k}: {v}")
    
    # check user
    u = await db.fetchrow(f"SELECT * FROM users WHERE telegram_id = {order['user_id']}")
    if u:
        print("User:", dict(u))
        
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(inspect())
