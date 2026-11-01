import sys, os, json
from datetime import date
from dotenv import load_dotenv

sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv(r'd:\The hobby 2\DigitalRevenueHilawe\.env')

from meal_plan.generation.dataset import load_dataset
from meal_plan.generation.engine import generate_plan

dataset = load_dataset()

def test_persona(name, answers, nutrition_profile, meals_per_day=3, duration_days=7):
    print(f"\n========================================================")
    print(f"Testing Persona: {name}")
    print(f"Targets: {nutrition_profile.get('target_kcal')} kcal, {nutrition_profile.get('protein_g')}g Protein")
    
    plan = generate_plan(
        answers=answers,
        nutrition_profile=nutrition_profile,
        meals_per_day=meals_per_day,
        start_date=date(2026, 11, 2), # Monday
        duration_days=duration_days,
        region="ADDIS_ABABA",
        country_name="Ethiopia",
        dataset=dataset,
    )
    
    days = plan.get("core_week", [])
    print(f"Generated {len(days)} days in core_week.")
    for d in days:
        day_name = d.get("day_name")
        fasting = d.get("fasting", False)
        tot = d.get("totals", {})
        kcal = tot.get("kcal", 0.0)
        p = tot.get("protein", 0.0)
        c = tot.get("carbs", 0.0)
        f = tot.get("fat", 0.0)
        f_badge = " [FASTING]" if fasting else ""
        print(f"  {day_name:<10}{f_badge:<11}: {kcal:>6.1f} kcal | P: {p:>5.1f}g | C: {c:>5.1f}g | F: {f:>4.1f}g")
        
        # Check Injera portions
        for m in d.get("meals", []):
            for it in m.get("items", []):
                if it.get("food_id") == "C001":
                    g = it.get("grams", 0.0)
                    if g % 60.0 != 0.0:
                        print(f"    ⚠️ WARNING: Non-standard Injera {g}g in {m.get('slot')}")
                # Check for double parentheses in familiar
                fam = str(it.get("familiar") or "")
                if "((" in fam or "))" in fam:
                    print(f"    ⚠️ WARNING: Double parentheses in {it.get('food_name')}: {fam}")
    return plan

# Persona 1: Bezawit Nigusse (Female Fat Loss, Wed/Fri fasting, 1675 kcal, 140g P)
bezawit_answers = {
    "gender": "FEMALE",
    "primary_goal": "FAT_LOSS",
    "dietary_pattern": "OMNIVORE",
    "orthodox_fasting": "WED_FRI",
    "food_allergies": ["SHELLFISH"],
    "disliked_foods": ["PASTA", "RICE"],
    "current_weight_kg": 72.0,
    "target_weight_kg": 62.0,
}
bezawit_targets = {
    "target_kcal": 1675.0,
    "protein_g": 140.0,
    "carbs_g": 160.0,
    "fat_g": 45.0,
    "fibre_g": 28.0,
}

# Persona 2: Yohannes (Male Hardgainer, Non-fasting, 3075 kcal, 145g P, 4 meals)
yohannes_answers = {
    "gender": "MALE",
    "primary_goal": "MUSCLE_GAIN",
    "dietary_pattern": "OMNIVORE",
    "fasting_preference": "NONE",
    "food_allergies": [],
    "disliked_foods": [],
    "current_weight_kg": 64.0,
    "target_weight_kg": 72.0,
}
yohannes_targets = {
    "target_kcal": 3075.0,
    "protein_g": 145.0,
    "carbs_g": 420.0,
    "fat_g": 75.0,
    "fibre_g": 35.0,
}

p1 = test_persona("Bezawit Nigusse", bezawit_answers, bezawit_targets, meals_per_day=3)
p2 = test_persona("Yohannes Hardgainer", yohannes_answers, yohannes_targets, meals_per_day=4)

print("\nEngine test complete!")
