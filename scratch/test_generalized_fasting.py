import sys, json, os, asyncio, math
from dotenv import load_dotenv
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')
from meal_plan.generation.engine import MealItem, food_macros, MacroTotals
from meal_plan.generation.dataset import load_dataset
from database.db import Database
load_dotenv(r'd:\The hobby 2\DigitalRevenueHilawe\.env')

dataset = load_dataset()

def _recalculate_meal_macros(meal, dataset):
    tot = MacroTotals()
    for it in meal.items:
        f_obj = dataset.food_by_id.get(it.food_id) if it.food_id else None
        r_obj = dataset.recipe_by_id.get(it.recipe_id) if it.recipe_id else None
        if f_obj:
            tot = tot.plus(food_macros(f_obj, it.grams))
        elif r_obj:
            std_g = float(r_obj.get("standard_portion_grams") or 250.0)
            scale = it.grams / std_g if std_g > 0 else 1.0
            tot = tot.plus(MacroTotals(
                kcal=float(r_obj.get("kcal") or 0.0) * scale,
                protein=float(r_obj.get("protein_g") or 0.0) * scale,
                carbs=float(r_obj.get("carbs_g") or 0.0) * scale,
                fat=float(r_obj.get("fat_g") or 0.0) * scale,
                fibre=float(r_obj.get("fibre_g") or 0.0) * scale,
            ))
        elif it.macros:
            tot = tot.plus(it.macros)
    return tot

def _add_or_scale_food(meal, food_obj, grams, familiar, weekly_food_grams):
    fid = food_obj.id if hasattr(food_obj, "id") else food_obj.get("id")
    fname = food_obj.name if hasattr(food_obj, "name") else food_obj.get("name", "Food")
    existing = next((it for it in meal.items if it.food_id == fid), None)
    if existing:
        diff_g = max(0.0, grams - existing.grams)
        existing.grams = max(existing.grams, grams)
        existing.familiar = familiar
        weekly_food_grams[fid] = weekly_food_grams.get(fid, 0.0) + diff_g
    else:
        m_macros = food_macros(food_obj, grams)
        meal.items.append(MealItem(
            food_id=fid,
            food_name=fname,
            grams=grams,
            source="food",
            familiar=familiar,
            exchange_group="Fasting protein",
            macros=m_macros,
        ))
        weekly_food_grams[fid] = weekly_food_grams.get(fid, 0.0) + grams

def _calibrate_fasting_day(meals, targets, answers, dataset, weekly_food_grams):
    target_p = float(targets.get("protein") or targets.get("protein_g") or 140.0)
    protein_floor = max(target_p * 0.80, min(target_p, 112.0))
    allergies = [str(a).upper() for a in answers.get("food_allergies", [])]
    soya_allowed = "SOY" not in allergies
    soya_food = dataset.food_by_id.get("P009") if soya_allowed else None
    soymilk_food = dataset.food_by_id.get("P014") if soya_allowed else None

    breakfast_m = next((m for m in meals if m.source_slot == "Breakfast"), None)
    lunch_m = next((m for m in meals if m.source_slot == "Lunch"), None)
    dinner_m = next((m for m in meals if m.source_slot == "Dinner"), None)
    savory_meals = [m for m in meals if m.source_slot in ("Lunch", "Dinner")]

    # 1. Breakfast liquid balance
    if breakfast_m:
        oat_it = next((it for it in breakfast_m.items if it.food_id == "C007"), None)
        pb_it = next((it for it in breakfast_m.items if it.food_id == "T004"), None)
        has_milk = any(it.food_id in ("P014", "A015") for it in breakfast_m.items)
        if oat_it and pb_it:
            if pb_it.grams > 20.0:
                diff_pb = pb_it.grams - 15.0
                pb_it.grams = 15.0
                weekly_food_grams["T004"] = max(0.0, weekly_food_grams.get("T004", 0.0) - diff_pb)
            if not has_milk and soymilk_food:
                sm_m = food_macros(soymilk_food, 250.0)
                breakfast_m.items.append(MealItem(
                    food_id="P014",
                    food_name="Soy milk (unsweetened)",
                    grams=250.0,
                    source="food",
                    familiar="about 1 large glass",
                    exchange_group="Plant milk",
                    macros=sm_m,
                ))
                weekly_food_grams["P014"] = weekly_food_grams.get("P014", 0.0) + 250.0
            oat_it.grams = 50.0
            oat_it.familiar = "about 0.5 cup dry"

    # 2. Stew portion normalization & legume stacking cleanup
    for m in savory_meals:
        has_legume_stew = any(it.recipe_id in ("R001", "R002", "R003") for it in m.items)
        if has_legume_stew:
            stacked = [it for it in m.items if it.food_id in ("P001", "P007")]
            for st in stacked:
                m.items.remove(st)
                weekly_food_grams[st.food_id] = max(0.0, weekly_food_grams.get(st.food_id, 0.0) - st.grams)
        
        atkilt_it = next((it for it in m.items if it.recipe_id == "R004"), None)
        if atkilt_it:
            atkilt_it.grams = 80.0
            atkilt_it.familiar = "ሲሶ / 1/3 መካከለኛ ጭልፋ"
        
        misir_it = next((it for it in m.items if it.recipe_id == "R002"), None)
        if misir_it:
            misir_it.grams = 200.0
            misir_it.familiar = "1 መካከለኛ ጭልፋ"

        ful_it = next((it for it in m.items if it.recipe_id in ("R018", "R025") or "ful" in str(it.food_name).lower()), None)
        if ful_it:
            ful_it.grams = 220.0
            ful_it.familiar = "1 መካከለኛ ሳህን"

    # 3. Recalculate intermediate macros
    for m in meals:
        m.macros = _recalculate_meal_macros(m, dataset)
    
    current_p = sum(m.macros.protein for m in meals)
    if current_p < protein_floor and soya_food and savory_meals:
        diff_p = protein_floor - current_p
        needed_g = float(math.ceil((diff_p / 0.52) / 5.0) * 5.0)
        
        if needed_g > 60.0 and lunch_m and dinner_m:
            g_lunch = float(math.ceil((needed_g / 2.0) / 5.0) * 5.0)
            g_din = needed_g - g_lunch
            _add_or_scale_food(lunch_m, soya_food, g_lunch, "በግምት 1 ከግማሽ ሲኒ የተዘፈቀ", weekly_food_grams)
            _add_or_scale_food(dinner_m, soya_food, g_din, "በግምት 1 ከግማሽ ሲኒ የተዘፈቀ", weekly_food_grams)
        else:
            target_m = dinner_m or lunch_m or savory_meals[0]
            _add_or_scale_food(target_m, soya_food, needed_g, "በግምት 1 ከግማሽ ሲኒ የተዘፈቀ", weekly_food_grams)

    # 4. Final totals
    totals = MacroTotals()
    for m in meals:
        m.macros = _recalculate_meal_macros(m, dataset)
        totals = totals.plus(m.macros)
    return totals

print("Generalized function parsed cleanly!")
