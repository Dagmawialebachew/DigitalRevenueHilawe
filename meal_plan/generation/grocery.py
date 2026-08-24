from __future__ import annotations

import math
from typing import Any

from meal_plan.generation.dataset import HilaweDataset
from meal_plan.generation.formatting import familiar_portion


DEFAULT_YIELD={
    "C003":3.0,"C004":3.0,"C005":2.4,"C006":2.4,"C013":3.0,"C014":2.5,"C015":3.0,
    "P001":2.5,"P002":2.4,"P003":2.5,"P004":2.5,"P005":2.5,"P006":2.5,"P007":2.5,
}


def _n(v:Any)->float:
    try:return float(v or 0)
    except (TypeError,ValueError):return 0.0


def _dry_name(name:str)->str:
    import re
    base=re.sub(r",?\s*cooked\b","",str(name or ""),flags=re.I).strip(" ,")
    return base+", dry"


def build_grocery(weekly_food_grams:dict[str,float], dataset:HilaweDataset)->list[dict[str,Any]]:
    foods=dataset.food_by_id
    rows=[]
    for fid,planned in sorted(weekly_food_grams.items()):
        food=foods.get(fid)
        if not food or planned<=0:continue
        factor=_n(food.get("Yield Conversion")) or DEFAULT_YIELD.get(fid,1.0)
        planned_rounded=math.ceil(planned/10)*10
        buy=math.ceil((planned/max(0.01,factor))/10)*10
        if factor>1:
            name=_dry_name(str(food.get("Food Name") or ""))
            quantity=f"~{buy/1000:.1f} kg dry" if buy>=1000 else f"~{round(buy)} g dry"
            guide=(f"Plan uses ~{planned_rounded/1000:.1f} kg cooked" if planned_rounded>=1000 else f"Plan uses ~{round(planned_rounded)} g cooked")+f" • estimated {factor:.1f}× cooking yield"
            note="Dry purchase estimate. Cooking water, product, batch method, package size and waste can change purchase need."
        else:
            name=str(food.get("Food Name") or "")
            quantity=f"{buy/1000:.1f} kg" if buy>=1000 else f"{round(buy)} g"
            guide=familiar_portion(planned_rounded/max(1.0,_n(food.get('Standard Portion g'))),str(food.get('Familiar Measure') or 'standard portion'))
            note="Adjust for household waste, package size and client preference."
        rows.append({
            "food_id":fid,"buy_item":name,"category":food.get("Category"),
            "planned_grams":round(planned,1),"buy_weight_g":round(buy,1),"purchase_quantity":quantity,
            "plan_yield_guide":guide,"budget":food.get("Budget Level"),"fasting_allowed":food.get("Fasting Allowed"),
            "data_quality":food.get("Data Quality"),"note":note,
        })
    rows.sort(key=lambda r:(str(r["category"] or ""),str(r["buy_item"])))
    return rows
