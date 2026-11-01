import asyncio, os, json, sys
from dotenv import load_dotenv
load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")
from database.db import Database
from meal_plan.generation.dataset import load_dataset
from meal_plan.generation.solver import food_macros
from meal_plan.generation.models import MacroTotals, MealItem
from meal_plan.generation.engine import generate_plan
from datetime import date

async def run():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    row = await db._pool.fetchrow("SELECT i.answers, i.nutrition_profile FROM meal_orders o JOIN meal_intakes i ON o.intake_id = i.id WHERE o.id = 26")
    answers = row["answers"] if isinstance(row["answers"], dict) else json.loads(row["answers"])
    stored_p = row["nutrition_profile"] if isinstance(row["nutrition_profile"], dict) else json.loads(row["nutrition_profile"])
    dataset = load_dataset()
    plan = generate_plan(
        answers=answers,
        nutrition_profile=stored_p,
        meals_per_day=3,
        start_date=date(2026, 10, 26),
        duration_days=7,
        region="ETHIOPIA",
        country_name="Ethiopia",
        dataset=dataset,
    )
    core_days = plan["core_week"]
    
    soya_food = dataset.food_by_id.get("P009")

    for d_idx in (2, 4):
        d = core_days[d_idx]
        meals = d["meals"]
        
        # Calibration for Day 3 (Wednesday)
        if d_idx == 2:
            lunch = meals[1]
            dinner = meals[2]
            
            # 1. Scale up Lunch Soya Chunks from 30g to 50g (+20g -> +10.4g P, +69 kcal)
            soya_item = next((it for it in lunch["items"] if it.get("food_id") == "P009"), None)
            if soya_item:
                soya_item["portion_g"] = 50.0
                soya_item["familiar"] = "በግምት 50 ግ ጥሬ (የተዘፈቀ)"
                # update item macros
                m_diff = food_macros(soya_food, 20.0)
                soya_item["macros"]["kcal"] += m_diff.kcal
                soya_item["macros"]["protein"] += m_diff.protein
                soya_item["macros"]["carbs"] += m_diff.carbs
                lunch["macros"]["kcal"] += m_diff.kcal
                lunch["macros"]["protein"] += m_diff.protein
                lunch["macros"]["carbs"] += m_diff.carbs
            
            # 2. Add Soya Chunks 55g to Dinner (+55g -> +28.6g P, +190 kcal)
            soya_din_m = food_macros(soya_food, 55.0)
            dinner["items"].append({
                "food_id": "P009",
                "food_name": "Dry soy chunks",
                "portion_g": 55.0,
                "familiar": "በግምት 55 ግ ጥሬ (የተዘፈቀ)",
                "exchange_group": "Fasting protein",
                "macros": {
                    "kcal": soya_din_m.kcal,
                    "protein": soya_din_m.protein,
                    "carbs": soya_din_m.carbs,
                    "fat": soya_din_m.fat,
                    "fibre": soya_din_m.fibre,
                }
            })
            dinner["macros"]["kcal"] += soya_din_m.kcal
            dinner["macros"]["protein"] += soya_din_m.protein
            dinner["macros"]["carbs"] += soya_din_m.carbs
            dinner["macros"]["fat"] += soya_din_m.fat
            
            # 3. Trim Dinner Atkilt Wot from 200g to 80g (-120g -> -72 kcal)
            atkilt_item = next((it for it in dinner["items"] if it.get("recipe_id") == "R004"), None)
            if atkilt_item:
                atkilt_item["portion_g"] = 80.0
                atkilt_item["familiar"] = "80 ግ (በግምት 1/3 መካከለኛ ጭልፋ)"
                dinner["macros"]["kcal"] -= 72.0
                dinner["macros"]["carbs"] -= 16.0

            # 4. Trim Dinner Misir Wot from 250g to 200g (-50g -> -57 kcal, -3.3g P)
            misir_item = next((it for it in dinner["items"] if it.get("recipe_id") == "R002"), None)
            if misir_item:
                misir_item["portion_g"] = 200.0
                misir_item["familiar"] = "200 ግ (በግምት 1 መካከለኛ ጭልፋ)"
                dinner["macros"]["kcal"] -= 57.0
                dinner["macros"]["protein"] -= 3.3
                dinner["macros"]["carbs"] -= 8.7

        # Calibration for Day 5 (Friday)
        if d_idx == 4:
            b = meals[0]
            lunch = meals[1]
            dinner = meals[2]
            
            # 1. Breakfast oats from 60g to 50g (-10g -> -38 kcal, -1.3g P)
            oat_it = next((it for it in b["items"] if it.get("food_id") == "C007"), None)
            if oat_it:
                oat_it["portion_g"] = 50.0
                oat_it["familiar"] = "50 ግ (በግምት 1/2 ሲኒ ደረቅ አጃ)"
                b["macros"]["kcal"] -= 38.0
                b["macros"]["protein"] -= 1.3
                b["macros"]["carbs"] -= 6.6

            # 2. Lunch Misir Wot from 325g to 200g (-125g -> -142 kcal, -8.3g P)
            # Add 50g dry soy chunks to Lunch (+50g -> +172.5 kcal, +26.0g P)
            misir_l = next((it for it in lunch["items"] if it.get("recipe_id") == "R002"), None)
            if misir_l:
                misir_l["portion_g"] = 200.0
                misir_l["familiar"] = "200 ግ (በግምት 1 መካከለኛ ጭልፋ)"
                lunch["macros"]["kcal"] -= 142.0
                lunch["macros"]["protein"] -= 8.3
                lunch["macros"]["carbs"] -= 21.6

            soya_l_m = food_macros(soya_food, 50.0)
            lunch["items"].append({
                "food_id": "P009",
                "food_name": "Dry soy chunks",
                "portion_g": 50.0,
                "familiar": "በግምት 50 ግ ጥሬ (የተዘፈቀ)",
                "exchange_group": "Fasting protein",
                "macros": {
                    "kcal": soya_l_m.kcal,
                    "protein": soya_l_m.protein,
                    "carbs": soya_l_m.carbs,
                    "fat": soya_l_m.fat,
                    "fibre": soya_l_m.fibre,
                }
            })
            lunch["macros"]["kcal"] += soya_l_m.kcal
            lunch["macros"]["protein"] += soya_l_m.protein
            lunch["macros"]["carbs"] += soya_l_m.carbs

            # 3. Dinner Fasting Ful Bowl from 330g to 220g (-110g -> -120 kcal, -8.8g P)
            # Add 50g dry soy chunks to Dinner (+50g -> +172.5 kcal, +26.0g P)
            ful_d = next((it for it in dinner["items"] if it.get("recipe_id") in ("R018", "R025") or "ful" in str(it.get("food_name") or it.get("name") or "").lower()), None)
            if ful_d:
                ful_d["portion_g"] = 220.0
                ful_d["familiar"] = "220 ግ (በግምት 1 መካከለኛ ሳህን)"
                dinner["macros"]["kcal"] -= 120.0
                dinner["macros"]["protein"] -= 8.8
                dinner["macros"]["carbs"] -= 18.0

            dinner["items"].append({
                "food_id": "P009",
                "food_name": "Dry soy chunks",
                "portion_g": 50.0,
                "familiar": "በግምት 50 ግ ጥሬ (የተዘፈቀ)",
                "exchange_group": "Fasting protein",
                "macros": {
                    "kcal": soya_l_m.kcal,
                    "protein": soya_l_m.protein,
                    "carbs": soya_l_m.carbs,
                    "fat": soya_l_m.fat,
                    "fibre": soya_l_m.fibre,
                }
            })
            dinner["macros"]["kcal"] += soya_l_m.kcal
            dinner["macros"]["protein"] += soya_l_m.protein
            dinner["macros"]["carbs"] += soya_l_m.carbs

        # Recompute totals
        tot_kcal = sum(m["macros"]["kcal"] for m in meals)
        tot_p = sum(m["macros"]["protein"] for m in meals)
        tot_c = sum(m["macros"]["carbs"] for m in meals)
        tot_f = sum(m["macros"]["fat"] for m in meals)
        d["totals"] = {"kcal": tot_kcal, "protein": tot_p, "carbs": tot_c, "fat": tot_f}

        print(f"=== AFTER CALIBRATION Day {d_idx+1} ({d['day_name']}) ===")
        print(f"Total: {tot_kcal:.0f} kcal, P: {tot_p:.1f}g, C: {tot_c:.1f}g, F: {tot_f:.1f}g")
        for m in meals:
            print(f"  {m['slot']}: {m['macros']['kcal']:.0f} kcal, P: {m['macros']['protein']:.1f}g")
            for it in m["items"]:
                print(f"    - {it.get('food_name') or it.get('name')}: {it.get('portion_g') or it.get('grams')}g")

    await db.disconnect()

asyncio.run(run())
