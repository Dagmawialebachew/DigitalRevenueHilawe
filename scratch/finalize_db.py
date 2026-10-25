import asyncio, os
from dotenv import load_dotenv
import asyncpg

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")

async def finalize():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    await conn.execute("""
        UPDATE meal_plan_versions 
        SET status = 'REVIEW_PENDING', review_chat_id = -5592866261, review_message_id = 431123, updated_at = NOW() 
        WHERE id = 10
    """)
    await conn.execute("""
        UPDATE meal_orders 
        SET state = 'REVIEW_PENDING', current_plan_version_id = 10, updated_at = NOW() 
        WHERE id = 19
    """)
    await conn.execute("""
        UPDATE meal_generation_jobs 
        SET status = 'SUCCEEDED', stage = 'COMPLETE', plan_version_id = 10, finished_at = NOW(), updated_at = NOW() 
        WHERE order_id = 19
    """)
    print("Finalized DB state for Order 19 & Version 10!")
    await conn.close()

asyncio.run(finalize())
