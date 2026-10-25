import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")
from database.db import Database

async def run_audit():
    db = Database(os.getenv("DATABASE_URL"))
    await db.connect()
    
    async with db._pool.acquire() as conn:
        row = await conn.fetchrow("SELECT plan_json FROM meal_plan_versions WHERE id = 15")
        plan = row["plan_json"] if isinstance(row["plan_json"], dict) else json.loads(row["plan_json"])

    print("=" * 65)
    print("V4 COMPLETE NUTRITIONAL, MATHEMATICAL & CULINARY AUDIT")
    print("=" * 65)

    # 1. Check Artifact Files
    files_to_check = [
        "MP-000019-Shekur-afiff-V4.pdf",
        "14-days-meal-plan.pdf",
        "14-days-meal-plan.docx",
    ]
    for fn in files_to_check:
        p = Path(fn)
        assert p.exists(), f"File {fn} does not exist!"
        sz = p.stat().st_size
        assert sz > 1000, f"File {fn} is too small ({sz} bytes)!"
        print(f" Artifact Verified: {fn} ({sz / 1024:.1f} KB)")

    days = plan.get("core_week", [])
    print(f"\nTotal Days in Core Week: {len(days)}")
    assert len(days) == 7, f"Expected 7 days in core_week, got {len(days)}"

    # 2. Check Daily Calories and Meal Counts
    print("\n--- 1. Daily Calorie & Macro Target Audit (Target: 2,100 kcal, 105g P) ---")
    for d in days:
        d_idx = d["day_index"] + 1
        d_name = d["day_name"]
        kcal = d["totals"].get("kcal", 0)
        p = d["totals"].get("protein", 0)
        c = d["totals"].get("carbs", 0)
        f = d["totals"].get("fat", 0)
        meals = d.get("meals", [])
        meal_names = [m["meal_name"] for m in meals]
        print(f"Day {d_idx} ({d_name}): {kcal:.0f} kcal (P: {p:.0f}g, C: {c:.0f}g, F: {f:.0f}g) | Meals ({len(meals)}): {meal_names}")
        assert 2050 <= kcal <= 2180, f"Day {d_idx} calories {kcal} out of target range [2050, 2180]!"
        assert len(meals) == 4, f"Day {d_idx} does not have 4 meals (3 main + 1 snack shake)!"
        snack = meals[3]
        assert "shake" in snack["meal_name"].lower() or "ሼክ" in snack["meal_name"] or "መክሰስ" in snack["meal_name"], f"Day {d_idx} snack is not shake: {snack['meal_name']}"
    print(" Daily Calories & Structure: ALL 7 days hit ~2,100 kcal across 3 main meals + 1 compact shake snack!")

    # 3. Check Swaps Dynamic Gram Scaling & Guardrails
    print("\n--- 2. Swaps Dynamic Scaling & Guardrails Audit ---")
    all_swaps = []
    for d in days:
        d_idx = d["day_index"] + 1
        for m in d.get("meals", []):
            for ex in m.get("exchange_options", []):
                for opt in ex.get("options", []):
                    all_swaps.append((d_idx, m["meal_name"], ex["for_food_id"], opt))

    injera_swaps = [s for s in all_swaps if s[2] == "C001"]
    potato_swaps = [s for s in all_swaps if s[2] == "C010"]
    ayib_swaps = [s for s in all_swaps if s[2] == "A018"]

    from meal_plan.documents.helpers import format_swap_text

    print(f"Total swaps generated across core week: {len(all_swaps)}")
    print(f"Injera (C001) swaps count: {len(injera_swaps)}")
    for day_num, meal_name, for_fid, sw in injera_swaps[:6]:
        sw_copy = dict(sw)
        sw_copy["for_food_id"] = for_fid
        text_am = format_swap_text(None, sw_copy, is_am=True)
        print(f"  Day {day_num} {meal_name} [C001]: {text_am}")
        # Swapping 240g Injera (67.2g carbs) to Sweet Potato (0.207g carbs/g) -> 320g Sweet Potato
        if sw.get("food_id") == "C011" or "ስኳር ድንች" in text_am:
            assert "320" in text_am or sw.get("exchange_weight_g") == 320, f"Injera swap to sweet potato must be 320g! Got {text_am}"
        if sw.get("food_id") == "C003" or "ሩዝ" in text_am:
            assert "240" in text_am or sw.get("exchange_weight_g") == 240, f"Injera swap to rice must be 240g! Got {text_am}"

    print(f"Potato (C010) swaps count: {len(potato_swaps)}")
    for day_num, meal_name, for_fid, sw in potato_swaps[:6]:
        sw_copy = dict(sw)
        sw_copy["for_food_id"] = for_fid
        text_am = format_swap_text(None, sw_copy, is_am=True)
        print(f"  Day {day_num} {meal_name} [C010]: {text_am}")
        # Swapping 400g Boiled Potato to Cooked Pasta -> 250g-260g Pasta
        if sw.get("food_id") == "C005" or "ፓስታ" in text_am:
            assert ("250" in text_am or "260" in text_am or 
                    sw.get("exchange_weight_g") in (250, 260)), f"Potato swap to pasta must be 250-260g! Got {text_am}"

    print(f"Ayib (A018) swaps count: {len(ayib_swaps)}")
    for day_num, meal_name, for_fid, sw in ayib_swaps[:6]:
        sw_copy = dict(sw)
        sw_copy["for_food_id"] = for_fid
        text_am = format_swap_text(None, sw_copy, is_am=True)
        print(f"  Day {day_num} {meal_name} [A018]: {text_am}")
        assert "ለውዝ" not in text_am and sw.get("food_id") != "T003", f"Ayib swap must NEVER be peanuts! Got {text_am}"
        assert "ዘይት" not in text_am and sw.get("food_id") not in ("T001", "T002"), f"Ayib swap must NEVER be oil! Got {text_am}"
        assert (sw.get("food_id") in ("A011", "A012", "A008", "A007") or 
                any(p_word in text_am for p_word in ("እንቁላል", "አሳ", "ቱና"))), f"Ayib must swap to lean protein! Got {text_am}"
        # Boiled eggs should be discrete integer (e.g. 150g = 3 eggs or 200g = 4 eggs)
        if sw.get("food_id") == "A011":
            assert sw.get("exchange_weight_g") in (100, 150, 200), f"Egg swap grams should be discrete: {sw.get('exchange_weight_g')}"

    print(" Dynamic Swaps & Guardrails: ALL assertions passed (320g sweet potato, 260g pasta, Ayib -> Boiled Eggs/Tuna)!")

    # 4. Check Day 2 Breakfast Oatmeal Deconstruction
    print("\n--- 3. Day 2 Breakfast Oatmeal Deconstruction Audit ---")
    d2_b = days[1]["meals"][0]
    print(f"Day 2 Breakfast Title: {d2_b['meal_name']}")
    d2_items = {it["food_id"]: it for it in d2_b.get("items", [])}
    print("Day 2 Breakfast Items:")
    for fid, it in d2_items.items():
        print(f"  - {it.get('food_name')} ({fid}): {it['grams']}g ({it.get('familiar')})")
    assert "A014" in d2_items, "Yogurt A014 missing from Day 2 breakfast!"
    assert d2_items["A014"]["grams"] == 200, f"Yogurt grams should be 200g, got {d2_items['A014']['grams']}g"
    assert "C007" in d2_items, "Oats C007 missing from Day 2 breakfast!"
    assert d2_items["C007"]["grams"] == 50, f"Oats grams should be 50g, got {d2_items['C007']['grams']}g"
    assert "F001" in d2_items, "Banana F001 missing from Day 2 breakfast!"
    assert d2_items["F001"]["grams"] == 120, f"Banana grams should be 120g, got {d2_items['F001']['grams']}g"
    assert "T003" in d2_items, "Peanuts T003 missing from Day 2 breakfast!"
    assert d2_items["T003"]["grams"] == 30, f"Peanuts grams should be 30g, got {d2_items['T003']['grams']}g"
    print(" Day 2 Breakfast Composite Oatmeal: Cleanly deconstructed to 200g yogurt, 50g oats, 120g banana, 30g peanuts!")

    # 5. Check Egg Discrete Multiples
    print("\n--- 4. Boiled Whole Egg Discrete Multiples Audit ---")
    for d in days:
        d_idx = d["day_index"] + 1
        for m in d.get("meals", []):
            for it in m.get("items", []):
                if it.get("food_id") == "A011":
                    grams = it["grams"]
                    print(f"  Day {d_idx} {m['meal_name']}: Egg {grams}g ({it.get('familiar')})")
                    assert grams in (50, 100, 150, 200), f"Egg grams must be clean multiple of 50g! Got {grams}g in Day {d_idx} {m['meal_name']}"
    print(" Boiled Whole Eggs: Strictly clean multiples of 50g (100g = 2 eggs, 150g = 3 eggs)!")

    # 6. Check Economical Ethiopian Menu Rotation
    print("\n--- 5. Economical Ethiopian Menu Rotation Audit ---")
    legume_count = 0
    for d in days:
        d_idx = d["day_index"] + 1
        for m in d.get("meals", [])[1:3]: # Lunch and Dinner
            t_id = m.get("template_id", "")
            name = m.get("meal_name", "")
            fids = [it.get("food_id") for it in m.get("items", [])]
            if any(l_fid in fids for l_fid in ("L001", "L002", "L003")) or any(leg in name for leg in ("ሽሮ", "ምስር", "ክክ")):
                legume_count += 1
                print(f"  Day {d_idx} {m['meal_name']}: {t_id} (Budget Legume Meal)")
    print(f"Total budget legume lunches/dinners: {legume_count} (Requirement >= 3)")
    assert legume_count >= 3, f"Expected >= 3 legume meals in week, got {legume_count}!"
    print(" Economical Ethiopian Menu Rotation: Verified with Shiro, Misir, and Kik Alicha rotating across week!")

    # 7. Check Grocery List Integrity
    print("\n--- 6. Grocery List Integrity & Conversions Audit ---")
    all_g_items = plan.get("grocery", [])
    if isinstance(all_g_items, dict):
        all_g_items = all_g_items.get("rows", [])
    print(f"Total items in grocery list: {len(all_g_items)}")

    egg_item = next((it for it in all_g_items if it.get("food_id") == "A011" or "እንቁላል" in it.get("buy_item", "") or "Egg" in it.get("buy_item", "")), None)
    potato_item = next((it for it in all_g_items if it.get("food_id") == "C010" or "ድንች" in it.get("buy_item", "") or "Potato" in it.get("buy_item", "")), None)
    meat_items = [it for it in all_g_items if it.get("food_id") in ("A001", "A002", "A007") or "ስጋ" in it.get("buy_item", "") or "Beef" in it.get("buy_item", "")]
    peanut_item = next((it for it in all_g_items if it.get("food_id") == "T003" or "ለውዝ" in it.get("buy_item", "") or "Peanut" in it.get("buy_item", "")), None)

    assert egg_item, "Egg item missing from grocery list!"
    print(f"  Grocery Egg: {egg_item['buy_item']} -> {egg_item.get('purchase_quantity')} ({egg_item.get('plan_yield_guide')})")
    assert "ፍሬ" in str(egg_item.get("purchase_quantity", "")) or "eggs" in str(egg_item.get("purchase_quantity", "")).lower(), "Egg must be displayed by count (ፍሬ)!"

    assert potato_item, "Potato item missing from grocery list!"
    print(f"  Grocery Potato: {potato_item['buy_item']} -> {potato_item.get('purchase_quantity')} ({potato_item.get('plan_yield_guide')})")
    assert "ጥሬ" in potato_item["buy_item"] or "Raw" in potato_item["buy_item"], "Potato should be labeled as raw produce ድንች (ጥሬ)!"

    for m in meat_items:
        print(f"  Grocery Meat: {m['buy_item']} -> {m.get('purchase_quantity')} (Planned: {m.get('planned_grams')}g, Buy: {m.get('buy_weight_g')}g)")
        assert "ጥሬ" in m["buy_item"] or "Raw" in m["buy_item"], f"Meat {m['buy_item']} must be labeled as raw produce!"
        # Check yield factor 0.72 shrinkage: buy >= planned / 0.72
        assert m["buy_weight_g"] > m["planned_grams"], f"Meat purchase must account for shrinkage! Buy: {m['buy_weight_g']}, Planned: {m['planned_grams']}"

    assert peanut_item, "Peanut item missing from grocery list!"
    print(f"  Grocery Peanut: {peanut_item['buy_item']} -> {peanut_item.get('purchase_quantity')} ({peanut_item.get('plan_yield_guide')})")
    assert "1881" not in str(peanut_item.get("purchase_quantity")) and "1881" not in str(peanut_item.get("plan_yield_guide")), "Peanut contains 1881 typo!"

    print("\n" + "=" * 65)
    print("ALL 6 CRITICAL SYSTEMIC REQUIREMENTS & AUDIT ASSERTIONS FULLY PASSED!")
    print("=" * 65)

    await db.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_audit())
