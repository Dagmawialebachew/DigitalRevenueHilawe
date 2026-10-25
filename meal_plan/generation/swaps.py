from __future__ import annotations

import math
from typing import Any

from meal_plan.generation.dataset import HilaweDataset
from meal_plan.generation.safety import food_is_safe
from meal_plan.glossary import get_food_name


def build_exchange_options(
    food_id: str,
    dataset: HilaweDataset,
    answers: dict[str, Any],
    *,
    fasting: bool,
    base_grams: float = 100.0,
    meal_food_ids: set[str] | list[str] | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    food = dataset.food_by_id.get(food_id)
    if not food:
        return []
    group = str(food.get("Exchange Group") or "").strip()
    if not group:
        return []
    # Swap Attachment Guard:
    # Swaps must ONLY attach to primary carb anchors (food_id.startswith("C") or tubers)
    # or primary protein anchors (food_id.startswith("A") or legumes P001-P008).
    # NEVER attach a meal swap to low-calorie vegetable garnishes (cucumber V012, lettuce V013, onions V001).
    if food_id.startswith("V") or food_id in ("V012", "V013", "V001", "V002", "V003", "V004", "V005", "V006", "V007", "V008", "V009", "V010", "V011"):
        return []

    cat = str(food.get("Category") or "").lower()

    if food_id.startswith("C") or any(k in cat for k in ("grain", "starch", "tuber", "bread", "cereal")):
        swap_type = "carb"
    elif food_id.startswith(("A", "P")) or any(k in cat for k in ("protein", "meat", "poultry", "dairy", "egg", "legume", "fish")):
        swap_type = "protein"
    elif food_id.startswith("T") or any(k in cat for k in ("fat", "oil", "nut", "seed")):
        swap_type = "fat"
    else:
        return []

    is_save_budget = str(answers.get("grocery_budget") or "").upper() in ("SAVE", "VALUE")

    base_carbs_per_g = float(food.get("Carbs / 100 g") or 0) / 100.0
    base_prot_per_g = float(food.get("Protein / 100 g") or 0) / 100.0
    base_kcal_per_g = float(food.get("kcal / 100 g") or 0) / 100.0

    target_carbs_g = base_grams * base_carbs_per_g
    target_prot_g = base_grams * base_prot_per_g
    target_kcal = base_grams * base_kcal_per_g

    forbidden: set[str] = set(meal_food_ids or [])
    forbidden.add(food_id)

    def _calc_swap_grams_and_familiar(cand_id: str, cand_obj: dict[str, Any]) -> tuple[float, str, str]:
        c_cat = str(cand_obj.get("Category") or "").lower()
        if swap_type == "carb":
            c_carbs_per_g = float(cand_obj.get("Carbs / 100 g") or 0) / 100.0
            if c_carbs_per_g >= 0.05:
                sg = round((target_carbs_g / c_carbs_per_g) / 10.0) * 10.0
            else:
                sg = float(cand_obj.get("Standard Portion g") or 100.0)
            sg = max(30.0, sg)
        elif swap_type == "protein":
            c_prot_per_g = float(cand_obj.get("Protein / 100 g") or 0) / 100.0
            if c_prot_per_g >= 0.05:
                sg = round((target_prot_g / c_prot_per_g) / 10.0) * 10.0
            else:
                sg = float(cand_obj.get("Standard Portion g") or 100.0)
            if cand_id == "A011":
                # Whole eggs: discrete 50g steps
                sg = max(50.0, round(sg / 50.0) * 50.0)
            else:
                sg = max(30.0, sg)
        else:
            sg = float(cand_obj.get("Standard Portion g") or 30.0)

        # Dynamic familiar portion
        if cand_id == "C001":
            rolls = sg / 120.0
            if rolls <= 0.5:
                fam_am, fam_en = "ግማሽ መካከለኛ የተጠቀለለ እንጀራ", "½ medium rolled piece"
            elif rolls <= 1.0:
                fam_am, fam_en = "1 መካከለኛ የተጠቀለለ እንጀራ", "1 medium rolled piece"
            elif rolls <= 1.5:
                fam_am, fam_en = "1 ከግማሽ መካከለኛ የተጠቀለለ እንጀራ", "1 ½ medium rolled piece"
            elif rolls <= 2.0:
                fam_am, fam_en = "2 መካከለኛ የተጠቀለለ እንጀራ", "2 medium rolled pieces"
            else:
                fam_am, fam_en = f"{int(rolls)} መካከለኛ የተጠቀለለ እንጀራ", f"{int(rolls)} medium rolled pieces"
        elif cand_id == "A011":
            cnt = max(1, int(round(sg / 50.0)))
            fam_am, fam_en = f"{cnt} ፍሬ", f"{cnt} whole eggs"
        elif cand_id == "C011":
            if sg >= 280:
                fam_am, fam_en = "በግምት 2 መካከለኛ ስኳር ድንች", "approx. 2 medium sweet potatoes"
            elif sg >= 140:
                fam_am, fam_en = "በግምት 1 መካከለኛ ስኳር ድንች", "approx. 1 medium sweet potato"
            else:
                fam_am, fam_en = "በግምት ግማሽ ስኳር ድንች", "approx. ½ medium sweet potato"
        elif cand_id in ("C003", "C004"):
            cups = round((sg / 150.0) * 2) / 2
            fam_am, fam_en = f"በግምት {cups:g} ሲኒ የበሰለ ሩዝ", f"approx. {cups:g} cups cooked rice"
        elif cand_id in ("C005", "C006"):
            cups = round((sg / 140.0) * 2) / 2
            fam_am, fam_en = f"በግምት {cups:g} ሲኒ የበሰለ ፓስታ", f"approx. {cups:g} cups cooked pasta"
        elif cand_id == "A008":
            fam_am, fam_en = "በግምት ግማሽ ጣሳ", "approx. ½ can"
        elif cand_id == "A018":
            fam_am, fam_en = f"በግምት {round(sg)} ግ", f"approx. {round(sg)} g"
        else:
            fam_am, fam_en = f"{round(sg)} ግ", f"{round(sg)} g"

        return sg, fam_am, fam_en

    rows: list[dict[str, Any]] = []
    seen_fids: set[str] = set()

    for x in dataset.active_exchanges:
        if str(x.get("Exchange Group") or "") != group:
            continue
        fid = str(x.get("Food ID") or "")
        if not fid or fid in forbidden or fid in seen_fids:
            continue
        # Enforce budget guardrails (no imported cottage cheese A016, olive oil T001, Greek yogurt A013 for Save budget)
        if is_save_budget and fid in {"A013", "A016", "T001", "A009"}:
            continue

        candidate = dataset.food_by_id.get(fid)
        if not candidate:
            continue
        c_cat = str(candidate.get("Category") or "").lower()

        # Strict like-for-like macro guardrails:
        # Never swap protein for peanuts (T003) or oils (T001, T002)
        if swap_type == "protein":
            if fid.startswith("T") or any(k in c_cat for k in ("nut", "seed", "fat", "oil")):
                continue
        elif swap_type == "carb":
            if not fid.startswith("C") and not any(k in c_cat for k in ("grain", "starch", "tuber", "bread")):
                continue

        base_name = str(food.get("Food Name") or "").lower()
        cand_name = str(candidate.get("Food Name") or "").lower()

        # Redundant swap guard: Never swap a food for a variation of itself!
        if "pasta" in base_name and "pasta" in cand_name:
            continue
        if "rice" in base_name and "rice" in cand_name:
            continue
        if "injera" in base_name and "injera" in cand_name:
            continue

        # Fruit snack sanity:
        has_fruit = any(str(mid).startswith("F") for mid in (meal_food_ids or []))
        if has_fruit or food_id in ("T004", "T003"):
            # Never offer raw liquid oils (T001 Olive oil, T002 Canola/Veg oil) as a fruit dip or peanut butter swap
            if fid in ("T001", "T002", "T005", "T006"):
                continue
            # Never offer raw tofu with fruit
            if "tofu" in cand_name or fid in ("P005", "P006", "P010"):
                continue

        safe, _ = food_is_safe(candidate, answers, fasting=fasting)
        if not safe:
            continue

        sg, fam_am, fam_en = _calc_swap_grams_and_familiar(fid, candidate)
        cand_macros = {
            "kcal": float(candidate.get("kcal / 100 g") or 0) * (sg / 100.0),
            "protein": float(candidate.get("Protein / 100 g") or 0) * (sg / 100.0),
            "carbs": float(candidate.get("Carbs / 100 g") or 0) * (sg / 100.0),
            "fat": float(candidate.get("Fat / 100 g") or 0) * (sg / 100.0),
            "fibre": float(candidate.get("Fibre / 100 g") or 0) * (sg / 100.0),
        }

        f_name_en = get_food_name(fid, str(candidate.get("Food Name") or x.get("Food") or ""), language="EN")
        f_name_am = get_food_name(fid, str(candidate.get("Food Name") or x.get("Food") or ""), language="AM")
        seen_fids.add(fid)

        rows.append({
            "food_id": fid,
            "food_name": f_name_en,
            "food_name_am": f_name_am,
            "category": c_cat,
            "grams": sg,
            "exchange_weight_g": sg,
            "familiar": fam_en,
            "familiar_am": fam_am,
            "familiar_guidance": fam_am,
            "coach_note": x.get("Coach Note") or "Like-for-like nutritional swap",
            "exchange_group": group,
            "swap_type": swap_type,
            "macros": cand_macros,
        })

    # Direct curated fallbacks for core foods when exchange table has gaps:
    # 1. Swapping Ayib (A018) -> must be lean protein: Boiled whole eggs (A011) or Canned tuna (A008)
    if food_id == "A018":
        for fallback_fid in ("A011", "A008", "A012"):
            if fallback_fid not in forbidden and fallback_fid not in seen_fids:
                if is_save_budget and fallback_fid == "A008":
                    continue
                cand = dataset.food_by_id.get(fallback_fid)
                if cand:
                    safe, _ = food_is_safe(cand, answers, fasting=fasting)
                    if safe:
                        sg, fam_am, fam_en = _calc_swap_grams_and_familiar(fallback_fid, cand)
                        cand_macros = {
                            "kcal": float(cand.get("kcal / 100 g") or 0) * (sg / 100.0),
                            "protein": float(cand.get("Protein / 100 g") or 0) * (sg / 100.0),
                            "carbs": float(cand.get("Carbs / 100 g") or 0) * (sg / 100.0),
                            "fat": float(cand.get("Fat / 100 g") or 0) * (sg / 100.0),
                            "fibre": float(cand.get("Fibre / 100 g") or 0) * (sg / 100.0),
                        }
                        f_name_en = get_food_name(fallback_fid, str(cand.get("Food Name") or ""), language="EN")
                        f_name_am = get_food_name(fallback_fid, str(cand.get("Food Name") or ""), language="AM")
                        seen_fids.add(fallback_fid)
                        rows.append({
                            "food_id": fallback_fid,
                            "food_name": f_name_en,
                            "food_name_am": f_name_am,
                            "category": str(cand.get("Category") or "").lower(),
                            "grams": sg,
                            "exchange_weight_g": sg,
                            "familiar": fam_en,
                            "familiar_am": fam_am,
                            "familiar_guidance": fam_am,
                            "coach_note": "Lean protein alternative",
                            "exchange_group": group,
                            "swap_type": "protein",
                            "macros": cand_macros,
                        })

    # 2. Swapping Boiled Whole Eggs (A011) -> must be lean protein: Ayib (A018) or Tuna (A008), NEVER self-swap!
    elif food_id == "A011":
        for fallback_fid in ("A018", "A008", "A012"):
            if fallback_fid not in forbidden and fallback_fid not in seen_fids:
                if is_save_budget and fallback_fid == "A008":
                    continue
                cand = dataset.food_by_id.get(fallback_fid)
                if cand:
                    safe, _ = food_is_safe(cand, answers, fasting=fasting)
                    if safe:
                        sg, fam_am, fam_en = _calc_swap_grams_and_familiar(fallback_fid, cand)
                        cand_macros = {
                            "kcal": float(cand.get("kcal / 100 g") or 0) * (sg / 100.0),
                            "protein": float(cand.get("Protein / 100 g") or 0) * (sg / 100.0),
                            "carbs": float(cand.get("Carbs / 100 g") or 0) * (sg / 100.0),
                            "fat": float(cand.get("Fat / 100 g") or 0) * (sg / 100.0),
                            "fibre": float(cand.get("Fibre / 100 g") or 0) * (sg / 100.0),
                        }
                        f_name_en = get_food_name(fallback_fid, str(cand.get("Food Name") or ""), language="EN")
                        f_name_am = get_food_name(fallback_fid, str(cand.get("Food Name") or ""), language="AM")
                        seen_fids.add(fallback_fid)
                        rows.append({
                            "food_id": fallback_fid,
                            "food_name": f_name_en,
                            "food_name_am": f_name_am,
                            "category": str(cand.get("Category") or "").lower(),
                            "grams": sg,
                            "exchange_weight_g": sg,
                            "familiar": fam_en,
                            "familiar_am": fam_am,
                            "familiar_guidance": fam_am,
                            "coach_note": "Protein swap alternative",
                            "exchange_group": group,
                            "swap_type": "protein",
                            "macros": cand_macros,
                        })

    # 3. Swapping Injera (C001) -> Sweet potato (C011), Cooked rice (C003), Cooked pasta (C005)
    elif food_id == "C001":
        for fallback_fid in ("C011", "C003", "C005"):
            if fallback_fid not in forbidden and fallback_fid not in seen_fids:
                cand = dataset.food_by_id.get(fallback_fid)
                if cand:
                    safe, _ = food_is_safe(cand, answers, fasting=fasting)
                    if safe:
                        sg, fam_am, fam_en = _calc_swap_grams_and_familiar(fallback_fid, cand)
                        cand_macros = {
                            "kcal": float(cand.get("kcal / 100 g") or 0) * (sg / 100.0),
                            "protein": float(cand.get("Protein / 100 g") or 0) * (sg / 100.0),
                            "carbs": float(cand.get("Carbs / 100 g") or 0) * (sg / 100.0),
                            "fat": float(cand.get("Fat / 100 g") or 0) * (sg / 100.0),
                            "fibre": float(cand.get("Fibre / 100 g") or 0) * (sg / 100.0),
                        }
                        f_name_en = get_food_name(fallback_fid, str(cand.get("Food Name") or ""), language="EN")
                        f_name_am = get_food_name(fallback_fid, str(cand.get("Food Name") or ""), language="AM")
                        seen_fids.add(fallback_fid)
                        rows.append({
                            "food_id": fallback_fid,
                            "food_name": f_name_en,
                            "food_name_am": f_name_am,
                            "category": str(cand.get("Category") or "").lower(),
                            "grams": sg,
                            "exchange_weight_g": sg,
                            "familiar": fam_en,
                            "familiar_am": fam_am,
                            "familiar_guidance": fam_am,
                            "coach_note": "Iso-carb grain/tuber alternative",
                            "exchange_group": group,
                            "swap_type": "carb",
                            "macros": cand_macros,
                        })

    # 4. Swapping Boiled Potato (C010) -> Cooked pasta (C005), Injera (C001), Cooked rice (C003)
    elif food_id == "C010":
        for fallback_fid in ("C005", "C001", "C003"):
            if fallback_fid not in forbidden and fallback_fid not in seen_fids:
                cand = dataset.food_by_id.get(fallback_fid)
                if cand:
                    safe, _ = food_is_safe(cand, answers, fasting=fasting)
                    if safe:
                        sg, fam_am, fam_en = _calc_swap_grams_and_familiar(fallback_fid, cand)
                        cand_macros = {
                            "kcal": float(cand.get("kcal / 100 g") or 0) * (sg / 100.0),
                            "protein": float(cand.get("Protein / 100 g") or 0) * (sg / 100.0),
                            "carbs": float(cand.get("Carbs / 100 g") or 0) * (sg / 100.0),
                            "fat": float(cand.get("Fat / 100 g") or 0) * (sg / 100.0),
                            "fibre": float(cand.get("Fibre / 100 g") or 0) * (sg / 100.0),
                        }
                        f_name_en = get_food_name(fallback_fid, str(cand.get("Food Name") or ""), language="EN")
                        f_name_am = get_food_name(fallback_fid, str(cand.get("Food Name") or ""), language="AM")
                        seen_fids.add(fallback_fid)
                        rows.append({
                            "food_id": fallback_fid,
                            "food_name": f_name_en,
                            "food_name_am": f_name_am,
                            "category": str(cand.get("Category") or "").lower(),
                            "grams": sg,
                            "exchange_weight_g": sg,
                            "familiar": fam_en,
                            "familiar_am": fam_am,
                            "familiar_guidance": fam_am,
                            "coach_note": "Iso-carb starch alternative",
                            "exchange_group": group,
                            "swap_type": "carb",
                            "macros": cand_macros,
                        })

    # 5. Swapping Pasta (C005 / C006) -> Cooked Brown Rice (C003), Boiled Potato (C010), Sweet Potato (C011)
    elif food_id in ("C005", "C006"):
        for fallback_fid in ("C003", "C010", "C011"):
            if fallback_fid not in forbidden and fallback_fid not in seen_fids:
                cand = dataset.food_by_id.get(fallback_fid)
                if cand:
                    safe, _ = food_is_safe(cand, answers, fasting=fasting)
                    if safe:
                        sg, fam_am, fam_en = _calc_swap_grams_and_familiar(fallback_fid, cand)
                        cand_macros = {
                            "kcal": float(cand.get("kcal / 100 g") or 0) * (sg / 100.0),
                            "protein": float(cand.get("Protein / 100 g") or 0) * (sg / 100.0),
                            "carbs": float(cand.get("Carbs / 100 g") or 0) * (sg / 100.0),
                            "fat": float(cand.get("Fat / 100 g") or 0) * (sg / 100.0),
                            "fibre": float(cand.get("Fibre / 100 g") or 0) * (sg / 100.0),
                        }
                        f_name_en = get_food_name(fallback_fid, str(cand.get("Food Name") or ""), language="EN")
                        f_name_am = get_food_name(fallback_fid, str(cand.get("Food Name") or ""), language="AM")
                        seen_fids.add(fallback_fid)
                        rows.append({
                            "food_id": fallback_fid,
                            "food_name": f_name_en,
                            "food_name_am": f_name_am,
                            "category": str(cand.get("Category") or "").lower(),
                            "grams": sg,
                            "exchange_weight_g": sg,
                            "familiar": fam_en,
                            "familiar_am": fam_am,
                            "familiar_guidance": fam_am,
                            "coach_note": "Cooked brown rice or boiled potato alternative",
                            "exchange_group": group,
                            "swap_type": "carb",
                            "macros": cand_macros,
                        })

    # 6. Swapping Peanut butter (T004) -> Roasted peanuts (T003)
    elif food_id == "T004":
        for fallback_fid in ("T003",):
            if fallback_fid not in forbidden and fallback_fid not in seen_fids:
                cand = dataset.food_by_id.get(fallback_fid)
                if cand:
                    safe, _ = food_is_safe(cand, answers, fasting=fasting)
                    if safe:
                        sg = 25.0
                        fam_am, fam_en = "በግምት 1 አነስተኛ ጭብጥ / እፍኝ", "approx. 1 small handful (25g)"
                        cand_macros = {
                            "kcal": float(cand.get("kcal / 100 g") or 0) * (sg / 100.0),
                            "protein": float(cand.get("Protein / 100 g") or 0) * (sg / 100.0),
                            "carbs": float(cand.get("Carbs / 100 g") or 0) * (sg / 100.0),
                            "fat": float(cand.get("Fat / 100 g") or 0) * (sg / 100.0),
                            "fibre": float(cand.get("Fibre / 100 g") or 0) * (sg / 100.0),
                        }
                        f_name_en = get_food_name(fallback_fid, str(cand.get("Food Name") or ""), language="EN")
                        f_name_am = get_food_name(fallback_fid, str(cand.get("Food Name") or ""), language="AM")
                        seen_fids.add(fallback_fid)
                        rows.append({
                            "food_id": fallback_fid,
                            "food_name": f_name_en,
                            "food_name_am": f_name_am,
                            "category": "nuts",
                            "grams": sg,
                            "exchange_weight_g": sg,
                            "familiar": fam_en,
                            "familiar_am": fam_am,
                            "familiar_guidance": fam_am,
                            "coach_note": "Roasted peanuts alternative",
                            "exchange_group": group,
                            "swap_type": "fat",
                            "macros": cand_macros,
                        })

    # Curated preferred swap order for staple foods:
    preferred_order = {
        "C001": ["C011", "C003", "C005", "C013", "C018"],  # Injera -> Sweet potato (320g), Rice (240g), Pasta (220g)
        "C010": ["C005", "C011", "C001", "C003"],          # Boiled potato -> Cooked pasta (260g), Sweet potato, Injera
        "C005": ["C003", "C010", "C011"],                  # Whole-wheat pasta -> Cooked rice, Boiled potato, Sweet potato
        "C006": ["C003", "C010", "C011"],                  # White pasta -> Cooked rice, Boiled potato, Sweet potato
        "T004": ["T003"],                                  # Peanut butter -> Roasted peanuts
        "A018": ["A011", "A008", "A012"],                  # Ayib -> Whole eggs (50g discrete units), Tuna, Egg whites
        "A011": ["A018", "A008", "A012"],                  # Whole eggs -> Ayib, Tuna, Egg whites
        "A007": ["A001", "A002", "A003", "A011"],          # Fish -> Chicken, Lean beef, Eggs
        "A001": ["A007", "A002", "A003", "A011"],          # Chicken -> Fish, Lean beef, Eggs
        "A003": ["A001", "A007", "A002", "A011"],          # Beef -> Chicken, Fish, Eggs
    }.get(food_id, [])

    def _sort_key(r: dict[str, Any]):
        fid = r["food_id"]
        pref_idx = preferred_order.index(fid) if fid in preferred_order else 999
        return (pref_idx, abs(r["macros"]["kcal"] - target_kcal), fid)

    rows.sort(key=_sort_key)
    return rows[:limit]
