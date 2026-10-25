import asyncio, os, sys
from dotenv import load_dotenv
import asyncpg

load_dotenv(r'd:\The hobby 2\DigitalRevenueHilawe\.env')
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    target_group = -5592866261
    card_message_id = 431139
    version_id = 14
    
    # Update meal_plan_versions
    await conn.execute("""
        UPDATE meal_plan_versions 
        SET status = 'REVIEW_PENDING', 
            review_chat_id = $1, 
            review_message_id = $2, 
            updated_at = NOW() 
        WHERE id = $3
    """, target_group, card_message_id, version_id)
    print("Updated meal_plan_versions 14!")

    # Update meal_orders
    await conn.execute("""
        UPDATE meal_orders 
        SET state = 'REVIEW_PENDING', 
            current_plan_version_id = $1, 
            updated_at = NOW() 
        WHERE id = 19
    """, version_id)
    print("Updated meal_orders 19 to REVIEW_PENDING!")

    row = await conn.fetchrow("SELECT id, order_id, version_number, status, review_chat_id, review_message_id FROM meal_plan_versions WHERE id = 14")
    print("Version row:", dict(row))

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
