import asyncio
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aiogram import Bot
from config import settings
from database.db import Database
from meal_plan.review_repository import MealPlanReviewRepository
from meal_plan.generation.pipeline import process_generation_job

async def test_order_72():
    db = Database(settings.DATABASE_URL)
    await db.connect()
    bot = Bot(token=settings.BOT_TOKEN)

    review_repo = MealPlanReviewRepository(db._pool)

    # 1. Reset order 72 and job 13 so it can be claimed or run
    print("Resetting Order #72 and Job #13...")
    await db.execute("""
        UPDATE meal_orders
        SET state = 'GENERATING', updated_at = NOW()
        WHERE id = 72;
    """)
    await db.execute("""
        UPDATE meal_generation_jobs
        SET status = 'RUNNING', stage = 'TARGETS', attempt_count = 1,
            last_error_code = NULL, last_error_message = NULL,
            locked_at = NOW(), locked_by = 'manual-test', updated_at = NOW()
        WHERE id = 13;
    """)

    job = await db.fetchrow("SELECT * FROM meal_generation_jobs WHERE id = 13;")
    print("Job before execution:", dict(job))

    print("\nStarting process_generation_job for Order #72...")
    try:
        version_id = await process_generation_job(bot, db, review_repo, job)
        print(f"\n🎉 SUCCESS! Order #72 generated as version_id: {version_id}")
    except Exception as e:
        print("\n❌ GENERATION FAILED WITH ERROR:", e)
        import traceback
        traceback.print_exc()

    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_order_72())

