from __future__ import annotations

import re
from typing import Any

from meal_plan.generation.dataset import HilaweDataset


SUPPLEMENT_FOOD_IDS = {"A017", "P015"}  # whey / plant protein powders; V1 product decision: food-first.

ALLERGY_TERMS: dict[str, set[str]] = {
    "PEANUTS": {"peanut", "peanuts", "peanut butter"},
    "TREE_NUTS": {"almond", "almonds", "cashew", "cashews", "walnut", "walnuts", "tree nut", "tree nuts"},
    "MILK": {"milk", "dairy", "yogurt", "cheese", "ayib", "whey"},
    "EGGS": {"egg", "eggs", "egg white", "egg whites"},
    "FISH": {"fish", "tilapia", "tuna", "salmon", "sardine", "sardines"},
    "SHELLFISH": {"shellfish", "shrimp", "prawn", "prawns", "crab", "lobster"},
    "WHEAT": {"wheat", "gluten", "bread", "pasta", "wrap"},
    "SOY": {"soy", "soya", "tofu", "tempeh"},
    "SESAME": {"sesame", "tahini"},
}

DISLIKE_TERMS: dict[str, set[str]] = {
    # 16 Core Staples
    "INJERA": {"injera"},
    "SHIRO": {"shiro"},
    "MISIR": {"misir", "lentil", "lentils"},
    "EGGS": {"egg", "eggs"},
    "CHICKEN": {"chicken"},
    "BEEF": {"beef", "tibs"},
    "FISH": ALLERGY_TERMS["FISH"],
    "MILK_YOGURT": {"milk", "dairy", "yogurt", "ayib", "cheese"},
    "RICE": {"rice"},
    "OATS": {"oat", "oats"},
    "POTATO": {"potato", "potatoes"},
    "AVOCADO": {"avocado"},
    "GOMEN": {"gomen", "collard"},
    "PASTA": {"pasta", "spaghetti", "macaroni"},
    "CHICKPEAS": {"chickpea", "chickpeas"},
    "FRUIT": {"fruit", "banana", "apple", "orange", "papaya", "mango"},
    # Extended database foods
    "TEFF": {"teff"},
    "SWEET_POTATO": {"sweet potato"},
    "BREAD": {"bread", "toast", "whole-wheat bread", "dabo"},
    "CORN": {"corn", "maize"},
    "BARLEY": {"barley", "kinche"},
    "BULGUR": {"bulgur"},
    "QUINOA": {"quinoa"},
    "KOCHO": {"kocho"},
    "KITA": {"kita"},
    "SPLIT_PEAS": {"split peas", "kik"},
    "FAVA_BEANS": {"fava", "ful", "fava beans", "bakela"},
    "KIDNEY_BEANS": {"kidney beans", "red beans", "kidney bean"},
    "BLACK_BEANS": {"black beans", "black bean"},
    "WHITE_BEANS": {"white beans", "white bean"},
    "GREEN_PEAS": {"peas", "green peas", "ater"},
    "SOY_CHUNKS": {"soy chunks", "soya chunks", "soy meat", "soya"},
    "TOFU": {"tofu"},
    "TEMPEH": {"tempeh"},
    "KOLO": {"kolo"},
    "EGG_WHITES": {"egg white", "egg whites"},
    "TUNA": {"tuna"},
    "SALMON": {"salmon"},
    "SARDINES": {"sardine", "sardines"},
    "GOAT_MEAT": {"goat", "goat meat"},
    "LAMB": {"lamb", "mutton"},
    "TURKEY": {"turkey"},
    "GREEK_YOGURT": {"greek yogurt"},
    "AYIB": {"ayib", "cottage cheese"},
    "COTTAGE_CHEESE": {"cottage cheese"},
    "CABBAGE": {"cabbage", "tikil gomen"},
    "CARROT": {"carrot", "carrots"},
    "GREEN_BEANS": {"green beans", "fosolia", "string beans"},
    "BELL_PEPPER": {"bell pepper", "pepper", "karia"},
    "BROCCOLI": {"broccoli"},
    "SPINACH": {"spinach"},
    "CUCUMBER": {"cucumber", "kiyar"},
    "LETTUCE": {"lettuce", "salad"},
    "ZUCCHINI": {"zucchini"},
    "MUSHROOMS": {"mushroom", "mushrooms", "enguday"},
    "BEETROOT": {"beetroot", "beet", "key sir"},
    "CAULIFLOWER": {"cauliflower"},
    "EGGPLANT": {"eggplant", "deberjan", "aubergine"},
    "OKRA": {"okra", "bamiya"},
    "TOMATO": {"tomato", "tomatoes"},
    "ONION": {"onion", "onions"},
    "GARLIC": {"garlic"},
    "BANANA": {"banana", "bananas", "muz"},
    "APPLE": {"apple", "apples", "pom"},
    "ORANGE": {"orange", "oranges"},
    "MANGO": {"mango", "mangoes"},
    "PAPAYA": {"papaya"},
    "PINEAPPLE": {"pineapple", "ananas"},
    "GUAVA": {"guava", "zeytun"},
    "STRAWBERRIES": {"strawberry", "strawberries"},
    "BLUEBERRIES": {"blueberry", "blueberries"},
    "GRAPES": {"grape", "grapes", "woyn"},
    "WATERMELON": {"watermelon", "habhab"},
    "DATES": {"date", "dates", "temir"},
    "PEACH": {"peach", "peaches"},
    "PEANUTS": {"peanut", "peanuts", "peanut butter", "lewz"},
    "PEANUT_BUTTER": {"peanut butter"},
    "ALMONDS": {"almond", "almonds"},
    "WALNUTS": {"walnut", "walnuts"},
    "SESAME": {"sesame", "selit", "tahini"},
    "CHIA_SEEDS": {"chia", "chia seeds"},
    "FLAXSEED": {"flaxseed", "flax", "telba"},
    "OLIVE_OIL": {"olive oil"},
    "BUTTER": {"butter", "kibbeh", "niter kibbeh"},
}


def _tokens(text: str) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9]+", text.lower()) if x}


def _contains_phrase(haystack: str, terms: set[str]) -> bool:
    h = " " + re.sub(r"\s+", " ", haystack.lower()) + " "
    words = _tokens(haystack)
    for term in terms:
        if " " in term:
            if f" {term.lower()} " in h:
                return True
        elif term.lower() in words:
            return True
    return False


def profile_exclusion_terms(answers: dict[str, Any]) -> list[tuple[str, set[str]]]:
    result: list[tuple[str, set[str]]] = []
    for key in answers.get("food_allergies") or []:
        terms = ALLERGY_TERMS.get(str(key).upper())
        if terms:
            result.append((f"allergy:{key}", terms))
    for key in answers.get("food_intolerances") or []:
        terms = ALLERGY_TERMS.get(str(key).upper())
        if terms:
            result.append((f"intolerance:{key}", terms))
    for key in answers.get("disliked_foods") or []:
        terms = DISLIKE_TERMS.get(str(key).upper())
        if terms:
            result.append((f"dislike:{key}", terms))
    # Optional free text is intentionally conservative: exact phrase/word matching only.
    for field, prefix in (
        ("allergy_other", "allergy"), ("intolerance_other", "intolerance"), ("disliked_foods_other", "dislike")
    ):
        raw = str(answers.get(field) or "").strip().lower()
        if raw:
            for part in re.split(r"[,;|\n]+", raw):
                part = part.strip()
                if len(part) >= 3:
                    result.append((f"{prefix}:custom", {part}))
    return result


def food_haystack(food: dict[str, Any]) -> str:
    return " ".join(str(food.get(k) or "") for k in (
        "Food Name", "Local / Amharic", "Category", "Allergen Tags", "Exchange Group"
    ))


def food_is_safe(food: dict[str, Any], answers: dict[str, Any], *, fasting: bool) -> tuple[bool, str | None]:
    if str(food.get("Active") or "").lower() != "yes":
        return False, "inactive food"
    fid = str(food.get("Food ID") or "")
    category = str(food.get("Category") or "").lower()
    if fid in SUPPLEMENT_FOOD_IDS or "supplement" in category:
        return False, "supplements disabled in V1"

    dietary = str(answers.get("dietary_pattern") or "").upper()
    if dietary not in {"OMNIVORE", "VEGETARIAN", "VEGAN"}:
        return False, "dietary pattern is missing or unsupported"
    if dietary == "VEGAN":
        if str(food.get("Fasting Allowed") or "") != "Yes" or str(food.get("Fish Item") or "") == "Yes":
            return False, "not vegan-compatible"
    elif dietary == "VEGETARIAN":
        if str(food.get("Fish Item") or "") == "Yes" or "animal protein" in category or "fish protein" in category:
            return False, "not lacto-ovo vegetarian compatible"

    if fasting:
        if str(food.get("Fasting Allowed") or "") != "Yes":
            return False, "not fasting-compatible"
        if str(food.get("Fish Item") or "") == "Yes" and not bool(answers.get("fish_during_fast")):
            return False, "fish not allowed for this client during fast"
    haystack = food_haystack(food)
    for reason, terms in profile_exclusion_terms(answers):
        if _contains_phrase(haystack, terms):
            return False, reason
    return True, None


def template_is_safe(template: dict[str, Any], dataset: HilaweDataset, answers: dict[str, Any], *, fasting: bool) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if str(template.get("Active") or "") != "Yes":
        return False, ["inactive template"]
    if str(template.get("Fasting") or "") != ("Yes" if fasting else "No"):
        return False, ["fasting mode mismatch"]
    if fasting and str(template.get("Fish Required") or "") == "Yes" and not bool(answers.get("fish_during_fast")):
        return False, ["fish not allowed during fast"]

    food_by_id = dataset.food_by_id
    recipe_by_id = dataset.recipe_by_id
    ingredients = dataset.ingredients_by_recipe
    for component in dataset.components_by_template.get(str(template.get("Template ID")), []):
        if str(component.get("Item Type")) == "Food":
            food = food_by_id.get(str(component.get("Item ID")))
            safe, reason = food_is_safe(food or {}, answers, fasting=fasting)
            if not safe:
                reasons.append(f"{component.get('Item Name')}: {reason}")
        else:
            rid = str(component.get("Item ID") or "")
            recipe = recipe_by_id.get(rid)
            if not recipe:
                reasons.append(f"missing recipe {rid}")
                continue
            for ingredient in ingredients.get(rid, []):
                food = food_by_id.get(str(ingredient.get("Food ID")))
                safe, reason = food_is_safe(food or {}, answers, fasting=fasting)
                if not safe:
                    reasons.append(f"{ingredient.get('Ingredient')}: {reason}")
    return not reasons, reasons


def preference_score(template: dict[str, Any], dataset: HilaweDataset, answers: dict[str, Any]) -> float:
    score = 0.0
    cuisine = str(answers.get("cuisine_style") or "MIXED").upper()
    tcuisine = str(template.get("Cuisine") or "").lower()
    if cuisine == "ETHIOPIAN":
        score += 4 if "ethiopian" in tcuisine else (1 if "hybrid" in tcuisine else 0)
    elif cuisine == "INTERNATIONAL":
        score += 4 if any(x in tcuisine for x in ("diaspora", "international")) else (2 if "hybrid" in tcuisine else 0)
    else:
        score += 2 if "ethiopian" in tcuisine else 1

    haystack_parts = [str(template.get("Meal Name") or ""), str(template.get("Tags") or "")]
    for component in dataset.components_by_template.get(str(template.get("Template ID")), []):
        haystack_parts.extend([str(component.get("Item Name") or ""), str(component.get("Allergens") or "")])
    haystack = " ".join(haystack_parts)
    for key in answers.get("liked_foods") or []:
        terms = DISLIKE_TERMS.get(str(key).upper(), set())
        if terms and _contains_phrase(haystack, terms):
            score += 2.0
    custom_likes = str(answers.get("liked_foods_other") or "").strip().lower()
    if custom_likes:
        for part in re.split(r"[,;|\n]+", custom_likes):
            part = part.strip()
            if len(part) >= 3 and _contains_phrase(haystack, {part}):
                score += 1.5
    return score
