import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.path.insert(0, ".")
from database.db import Database

async def main():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    version_id = 15
    target_group = -5592866261
    message_id = 431164

    async with db._pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE meal_plan_versions
            SET status = 'REVIEW_PENDING', review_chat_id = $2, review_message_id = $3, updated_at = NOW()
            WHERE id = $1
            """,
            version_id, target_group, message_id
        )
        await conn.execute(
            """
            UPDATE meal_orders
            SET state = 'REVIEW_PENDING', current_plan_version_id = $1, updated_at = NOW()
            WHERE id = 19
            """,
            version_id
        )
        await conn.execute(
            """
            UPDATE meal_generation_jobs
            SET status = 'SUCCEEDED', stage = 'COMPLETE', plan_version_id = $1, finished_at = NOW(), updated_at = NOW()
            WHERE order_id = 19
            """,
            version_id
        )

        v = await conn.fetchrow("SELECT id, order_id, version_number, status, review_chat_id, review_message_id FROM meal_plan_versions WHERE id = $1", version_id)
        o = await conn.fetchrow("SELECT id, state, current_plan_version_id FROM meal_orders WHERE id = 19")
        print("Updated meal_plan_versions:", dict(v))
        print("Updated meal_orders:", dict(o))

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
