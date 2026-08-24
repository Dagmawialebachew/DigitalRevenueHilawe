from __future__ import annotations

from typing import Any

from meal_plan.generation.dataset import HilaweDataset
from meal_plan.generation.safety import food_is_safe


def build_exchange_options(
    food_id: str,
    dataset: HilaweDataset,
    answers: dict[str, Any],
    *,
    fasting: bool,
    limit: int = 3,
) -> list[dict[str, Any]]:
    food=dataset.food_by_id.get(food_id)
    if not food:
        return []
    group=str(food.get("Exchange Group") or "").strip()
    if not group:
        return []
    rows=[]
    for x in dataset.active_exchanges:
        if str(x.get("Exchange Group") or "") != group:
            continue
        fid=str(x.get("Food ID") or "")
        if not fid or fid==food_id:
            continue
        candidate=dataset.food_by_id.get(fid)
        safe,_=food_is_safe(candidate or {},answers,fasting=fasting)
        if not safe:
            continue
        rows.append({
            "food_id":fid,
            "food_name":x.get("Food"),
            "exchange_weight_g":float(x.get("Exchange Weight g") or 0),
            "familiar_guidance":x.get("Familiar Guidance"),
            "coach_note":x.get("Coach Note"),
            "exchange_group":group,
            "macros":{
                "kcal":float(x.get("kcal") or 0),
                "protein":float(x.get("Protein g") or 0),
                "carbs":float(x.get("Carbs g") or 0),
                "fat":float(x.get("Fat g") or 0),
                "fibre":float(x.get("Fibre g") or 0),
            },
        })
    # Exchange rows are already calibrated as roughly like-for-like units; sort by kcal closeness.
    basis=next((x for x in dataset.active_exchanges if str(x.get("Food ID"))==food_id and str(x.get("Exchange Group"))==group),None)
    target=float((basis or {}).get("kcal") or 0)
    rows.sort(key=lambda x:(abs(x["macros"]["kcal"]-target),x["food_id"]))
    return rows[:limit]
