import asyncio
import os
import json
import sys
from datetime import date
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

from database.db import Database
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan
from meal_plan.generation.db_dataset import load_dataset_from_db

async def test_generation():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    
    query = """
        SELECT o.id as order_id, o.public_id, o.user_id, o.duration_days, o.meals_per_day, o.start_date,
               i.answers, i.language, u.full_name
        FROM meal_orders o
        JOIN meal_intakes i ON o.intake_id = i.id
        LEFT JOIN users u ON o.user_id = u.telegram_id
        WHERE o.id = 19
    """
    row = await db.fetchrow(query)
    answers = row["answers"]
    if isinstance(answers, str):
        answers = json.loads(answers)

    duration = row["duration_days"] or 14
    meals_per_day = row["meals_per_day"] or 3
    start_date = row["start_date"] or date(2026, 10, 26)

    async with db._pool.acquire() as conn:
        dataset = await load_dataset_from_db(conn)

    profile = calculate_nutrition_profile(answers)
    print(f"Target kcal: {profile.target_kcal}")

    plan = generate_plan(
        answers=answers,
        nutrition_profile=profile.to_dict(),
        meals_per_day=meals_per_day,
        start_date=start_date,
        duration_days=duration,
        region="ETHIOPIA",
        country_name="Ethiopia",
        dataset=dataset,
    )

    core_days = plan.get("core_week", [])
    rotation = plan.get("rotation", [])
    print(f"\nCore days count: {len(core_days)}, Rotation entries: {len(rotation)}")

    egg_days = 0
    oil_with_papaya_days = []
    cottage_cheese_swaps = []
    low_cal_days = []

    for d_idx, day in enumerate(core_days):
        day_cal = day.get("totals", {}).get("kcal", 0)
        meals = day.get("meals", [])
        b_meal = meals[0] if meals else {}
        b_name = b_meal.get("meal_name") or "Unknown"
        b_tid = b_meal.get("template_id") or ""
        b_items = b_meal.get("items", [])
        
        has_egg = any(
            str(it.get("food_id")) in ("A011", "A012") or "egg" in str(it.get("food_name", "")).lower() or "እንቁላል" in str(it.get("food_name", "")) or "firfir" in str(it.get("food_name", "")).lower() or b_tid in ("MN-B01", "MN-B04", "MN-B07")
            for it in b_items
        ) or b_tid in ("MN-B01", "MN-B04", "MN-B07")
        if has_egg:
            egg_days += 1

        # Check raw oil with fresh papaya
        has_papaya = any("papaya" in str(it.get("food_name", "")).lower() or "ፓፓያ" in str(it.get("food_name", "")) or str(it.get("food_id")) == "F005" for it in b_items)
        has_oil = any(str(it.get("food_id")) in ("T001", "T002", "T012") for it in b_items)
        if has_papaya and has_oil:
            oil_with_papaya_days.append(d_idx + 1)

        # Check swaps across all meals
        for m in meals:
            exchanges = m.get("exchange_options") or []
            for ex in exchanges:
                for opt in ex.get("options", []):
                    opt_name = str(opt.get("food_name", "")).lower() + " " + str(opt.get("food_name_am", ""))
                    if "cottage" in opt_name or "ኮቴጅ" in opt_name or str(opt.get("food_id")) == "A016":
                        cottage_cheese_swaps.append((d_idx + 1, opt))

        if day_cal < 2050:
            low_cal_days.append((d_idx + 1, day_cal))

        print(f"Day {d_idx+1:02d}: {day_cal:4.0f} kcal | {b_tid} {b_name} (Egg: {has_egg})")

    print("\n=== VERIFICATION SUMMARY ===")
    print(f"1. Daily Calories >= 2050 kcal: {'PASS' if not low_cal_days else f'FAIL ({low_cal_days})'}")
    print(f"2. Egg Breakfasts in 7-day core week: {egg_days}/7 days: {'PASS' if egg_days >= 2 else 'FAIL'}")
    print(f"3. Cooking Oil paired with Papaya: {'FAIL on days ' + str(oil_with_papaya_days) if oil_with_papaya_days else 'PASS (0 instances)'}")
    print(f"4. Cottage Cheese Swaps: {'FAIL: ' + str(cottage_cheese_swaps) if cottage_cheese_swaps else 'PASS (0 instances)'}")

    # Check grocery list for eggs
    grocery = plan.get("grocery", [])
    egg_in_grocery = any(
        "egg" in str(it.get("food_name", "")).lower() or "እንቁላል" in str(it.get("food_name", "")) or str(it.get("food_id")) in ("A011", "A012")
        for it in grocery
    )
    print(f"5. Eggs on Grocery List: {'PASS' if egg_in_grocery else 'FAIL'}")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(test_generation())
