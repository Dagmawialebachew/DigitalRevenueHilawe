from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from meal_plan.generation.dataset import HilaweDataset
from meal_plan.generation.models import MacroTotals, SlotSpec
from meal_plan.generation.safety import food_is_safe


def n(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def food_macros(food: dict[str, Any], grams: float) -> MacroTotals:
    factor = grams / 100.0
    return MacroTotals(
        n(food.get("kcal / 100 g")) * factor,
        n(food.get("Protein / 100 g")) * factor,
        n(food.get("Carbs / 100 g")) * factor,
        n(food.get("Fat / 100 g")) * factor,
        n(food.get("Fibre / 100 g")) * factor,
    )


def template_macros(t: dict[str, Any]) -> MacroTotals:
    return MacroTotals(n(t.get("kcal")), n(t.get("Protein g")), n(t.get("Carbs g")), n(t.get("Fat g")), n(t.get("Fibre g")))


def practical_group(food_id: str) -> str:
    if food_id.startswith("F") and food_id[1:].isdigit(): return "fruit"
    if food_id in {"C003", "C004"}: return "rice"
    if food_id == "C001": return "injera"
    if food_id == "C007": return "oats"
    if food_id in {"C005", "C006"}: return "pasta"
    if food_id in {"C008", "C009", "C016"}: return "bread"
    if food_id in {"C010", "C011"}: return "potato"
    if food_id in {"C013", "C014", "C015"}: return "grain"
    if food_id in {"T001", "T002"}: return "oil"
    return food_id


def practical_cap(group: str, settings: dict[str, Any]) -> float:
    mapping = {
        "fruit": ("MAX_FRUIT_MEAL_G", 300), "rice": ("MAX_RICE_MEAL_G", 300),
        "injera": ("MAX_INJERA_MEAL_G", 240), "oats": ("MAX_OATS_MEAL_G", 80),
        "pasta": ("MAX_PASTA_MEAL_G", 350), "bread": ("MAX_BREAD_MEAL_G", 100),
        "potato": ("MAX_POTATO_MEAL_G", 400), "grain": ("MAX_OTHER_GRAIN_MEAL_G", 350),
        "oil": ("MAX_OIL_MEAL_G", 14),
    }
    if group not in mapping:
        return math.inf
    key, default = mapping[group]
    return n(settings.get(key)) or float(default)


def minimum_addition(food_id: str) -> float:
    if food_id in {"T001", "T002"}: return 2
    if food_id.startswith("F") and food_id[1:].isdigit(): return 50
    if food_id == "P010": return 75
    if food_id == "P014": return 100
    if food_id == "P001": return 50
    if food_id.startswith("A") and food_id[1:].isdigit(): return 60
    return 15


@dataclass
class DaySolution:
    scale: float
    extras: dict[str, list[dict[str, float]]]
    warnings: list[str]
    totals: MacroTotals
    food_by_slot: dict[str, dict[str, float]]
    mass_by_slot: dict[str, float]


class DaySolver:
    def __init__(self, dataset: HilaweDataset, answers: dict[str, Any]):
        self.dataset = dataset
        self.answers = answers
        self.foods = dataset.food_by_id
        self.recipes = dataset.recipe_by_id
        self.ingredients = dataset.ingredients_by_recipe
        self.components = dataset.components_by_template
        self.settings = dataset.settings

    def solve(self, selected: list[tuple[SlotSpec, dict[str, Any]]], targets: dict[str, float], *, fasting: bool) -> DaySolution:
        target = {
            "kcal": n(targets.get("target_kcal") or targets.get("kcal")),
            "protein": n(targets.get("protein_g") or targets.get("protein")),
            "carbs": n(targets.get("carbs_g") or targets.get("carbs")),
            "fat": n(targets.get("fat_g") or targets.get("fat")),
        }
        if min(target.values()) <= 0:
            raise ValueError("Generation requires nonzero calorie, protein, carbohydrate and fat targets")

        base = MacroTotals()
        for _, t in selected:
            base = base.plus(template_macros(t))
        ratios = [1.0]
        if base.protein > 0: ratios.append(target["protein"] * 0.90 / base.protein)
        if base.carbs > 0: ratios.append(target["carbs"] / base.carbs)
        if base.fat > 0: ratios.append(target["fat"] / base.fat)
        scale = max(0.5, min(ratios))

        extras: dict[str, list[dict[str, float]]] = {spec.label: [] for spec, _ in selected}
        meal_state: dict[str, dict[str, float]] = {}
        food_by_slot: dict[str, dict[str, float]] = {}
        mass_by_slot: dict[str, float] = {}
        slot_specs = {spec.label: spec for spec, _ in selected}
        totals = {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fibre": 0.0}

        for spec, t in selected:
            m = template_macros(t).scale(scale)
            meal_state[spec.label] = m.to_dict()
            food_by_slot[spec.label] = {}
            mass_by_slot[spec.label] = 0.0
            for c in self.components.get(str(t.get("Template ID")), []):
                amount = n(c.get("Portion g")) * scale
                mass_by_slot[spec.label] += amount
                if str(c.get("Item Type")) == "Food":
                    fid = str(c.get("Item ID"))
                    food_by_slot[spec.label][fid] = food_by_slot[spec.label].get(fid, 0.0) + amount
                else:
                    rid = str(c.get("Item ID"))
                    recipe = self.recipes.get(rid, {})
                    fraction = amount / max(1.0, n(recipe.get("Yield g")))
                    for ingredient in self.ingredients.get(rid, []):
                        fid = str(ingredient.get("Food ID"))
                        food_by_slot[spec.label][fid] = food_by_slot[spec.label].get(fid, 0.0) + n(ingredient.get("Weight g")) * fraction
            for key, value in meal_state[spec.label].items(): totals[key] += value

        upper = {"kcal": target["kcal"]*1.03, "protein": target["protein"]*1.10, "carbs": target["carbs"]*1.10, "fat": target["fat"]*1.15}

        def candidate(fid: str, cap: float, daily_cap: float = math.inf) -> dict[str, float | str]:
            return {"id": fid, "cap": cap, "daily_cap": daily_cap}

        ethiopian_count = sum(1 for _, t in selected if "ethiopian" in str(t.get("Cuisine") or "").lower())
        primary_carb = "C001" if ethiopian_count >= max(2, len(selected)//2) else "C003"

        def preferred_carb(slot: str) -> str:
            options = ["C001","C003","C004","C005","C006","C007","C008","C009","C010","C011","C013","C014","C015","C016"]
            best, best_g = primary_carb, 0.0
            for fid in options:
                grams = food_by_slot[slot].get(fid, 0.0)
                if grams > best_g:
                    best, best_g = fid, grams
            return best

        fish_slots = {spec.label for spec, t in selected if str(t.get("Fish Required")) == "Yes"}
        dietary = str(self.answers.get("dietary_pattern") or "").upper()
        plant_based = fasting or dietary == "VEGAN"
        def proteins(spec: SlotSpec):
            if plant_based:
                if spec.source_slot == "Breakfast": return [candidate("P010",150),candidate("P014",250),candidate("P009",35)]
                if spec.source_slot == "Snack": return [candidate("P013",40),candidate("P014",250),candidate("P010",100)]
                base = [candidate("P001",180),candidate("P010",150),candidate("P009",50)]
                if spec.label in fish_slots:
                    return [candidate("A007",180),candidate("A020",180)] + base
                return base
            if spec.source_slot == "Breakfast": return [candidate("A013",200),candidate("A012",200)]
            if spec.source_slot == "Snack": return [candidate("A013",200),candidate("A012",120)]
            return [candidate("A001",120),candidate("A012",200)]

        protein_candidates = {spec.label: proteins(spec) for spec, _ in selected}
        carb_candidates = {}
        fat_candidates = {}
        for spec, _ in selected:
            if spec.source_slot == "Breakfast": carb_candidates[spec.label] = [candidate(preferred_carb(spec.label),300),candidate("F001",120)]
            elif spec.source_slot == "Snack": carb_candidates[spec.label] = [candidate("F001",120),candidate("F002",180),candidate("C020",36)]
            else: carb_candidates[spec.label] = [candidate(preferred_carb(spec.label),300)]
            if spec.source_slot == "Breakfast": fat_candidates[spec.label] = [candidate("V020",100),candidate("T004",30),candidate("T001",14)]
            elif spec.source_slot == "Snack": fat_candidates[spec.label] = [candidate("T004",30),candidate("T003",30),candidate("V020",100)]
            else: fat_candidates[spec.label] = [candidate("T001",14),candidate("V020",100),candidate("T003",30)]

        def group_used(slot: str, group: str) -> float:
            return sum(g for fid,g in food_by_slot[slot].items() if practical_group(fid)==group)
        def daily_used(fid: str) -> float:
            return sum(v.get(fid,0.0) for v in food_by_slot.values())

        macro_per = {"kcal":"kcal", "protein":"protein", "carbs":"carbs", "fat":"fat"}
        def add_candidate(slot: str, spec: dict[str, Any], macro: str, need: float) -> float:
            if need <= 0: return 0.0
            fid = str(spec["id"])
            food = self.foods.get(fid)
            safe, _ = food_is_safe(food or {}, self.answers, fasting=fasting)
            if not safe: return 0.0
            per_total = food_macros(food, 1.0)
            per = getattr(per_total, macro_per[macro])
            if per <= 0: return 0.0
            existing_extra = sum(x["grams"] for x in extras[slot] if x["id"]==fid)
            grams = need / per
            grams = min(grams, n(spec["cap"])-existing_extra, n(spec["daily_cap"])-daily_used(fid))
            group = practical_group(fid)
            grams = min(grams, practical_cap(group, self.settings)-group_used(slot,group))
            grams = min(grams, slot_specs[slot].mass_cap_g-mass_by_slot[slot])
            grams = min(grams, (target["kcal"]*slot_specs[slot].kcal_cap_fraction-meal_state[slot]["kcal"]) / max(0.01,per_total.kcal))
            for key in ("kcal","protein","carbs","fat"):
                p = getattr(per_total,key)
                if p > 0: grams = min(grams,(upper[key]-totals[key])/p)
            if not math.isfinite(grams) or grams < minimum_addition(fid): return 0.0
            grams = max(0.0, grams)
            found = next((x for x in extras[slot] if x["id"]==fid),None)
            if found: found["grams"] += grams
            else: extras[slot].append({"id":fid,"grams":grams})
            food_by_slot[slot][fid]=food_by_slot[slot].get(fid,0.0)+grams
            mass_by_slot[slot]+=grams
            delta=food_macros(food,grams)
            for key in totals:
                dv=getattr(delta,key); totals[key]+=dv; meal_state[slot][key]+=dv
            return getattr(delta,macro)

        ordered_slots=[spec.label for spec,_ in selected]
        shares={spec.label:spec.target_share for spec,_ in selected}
        def fill(macro: str, candidates: dict[str,list[dict[str,Any]]], factor: float=1.0):
            goal=target[macro]*factor
            for slot in ordered_slots:
                if totals[macro] >= goal*0.99: break
                need=min(max(0.0,goal*shares[slot]-meal_state[slot][macro]),max(0.0,goal-totals[macro]))
                for cand in candidates[slot]: need-=add_candidate(slot,cand,macro,need)
            for _ in range(3):
                if totals[macro] >= goal*0.99: break
                order=sorted(ordered_slots,key=lambda s: meal_state[s]["kcal"]/max(1.0,target["kcal"]*shares[s]))
                for slot in order:
                    need=max(0.0,goal-totals[macro])
                    for cand in candidates[slot]: need-=add_candidate(slot,cand,macro,need)

        fill("protein",protein_candidates,0.90)
        fill("carbs",carb_candidates,0.95)
        fill("fat",fat_candidates,1.0)
        fill("protein",protein_candidates,1.0)
        fill("carbs",carb_candidates,1.0)
        if totals["kcal"] < target["kcal"]*0.97:
            energy={}
            for spec,_ in selected:
                energy[spec.label]=[candidate("T004",30),candidate("T003",30)] if spec.source_slot=="Snack" else [candidate("T001",14),candidate("V020",100)]
            fill("kcal",energy,1.0)

        warnings=[]
        variances={
            "kcal":(totals["kcal"]-target["kcal"])/target["kcal"],
            "protein":(totals["protein"]-target["protein"])/target["protein"],
            "carbs":(totals["carbs"]-target["carbs"])/target["carbs"],
            "fat":(totals["fat"]-target["fat"])/target["fat"],
        }
        if not (abs(variances["kcal"])<=0.03 and abs(variances["protein"])<=0.10 and abs(variances["carbs"])<=0.10 and abs(variances["fat"])<=0.15):
            warnings.append("Daily targets were not reached within practical portion caps; coach review/tuning required.")
        for spec,_ in selected:
            if meal_state[spec.label]["kcal"] > target["kcal"]*spec.kcal_cap_fraction+1:
                warnings.append(f"{spec.label} exceeds the practical energy cap.")
            if mass_by_slot[spec.label] > spec.mass_cap_g+1:
                warnings.append(f"{spec.label} exceeds the practical food-volume cap.")
        return DaySolution(
            scale=scale, extras=extras, warnings=list(dict.fromkeys(warnings)),
            totals=MacroTotals(**totals), food_by_slot=food_by_slot, mass_by_slot=mass_by_slot,
        )
