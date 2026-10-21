import datetime
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, ".")

from meal_plan.documents import DocumentContext, render_client_pdf
from meal_plan.generation.dataset import load_dataset
from meal_plan.generation.engine import generate_plan
from meal_plan.nutrition_targets import calculate_nutrition_profile
from scripts.generate_hilawe_demo_plan import demo_answers

def main():
    print("Loading dataset...")
    dataset = load_dataset()
    answers = demo_answers()
    answers.update({
        "dietary_pattern": "OMNIVORE",
        "orthodox_fasting": "WED_FRI",
        "fish_during_fast": True,
        "grocery_budget": "BALANCED",
    })
    
    print("Calculating nutrition profile...")
    profile = calculate_nutrition_profile(answers).to_dict()
    
    print("Generating 7-day meal plan with Hilawe Engine...")
    plan = generate_plan(
        answers=answers,
        nutrition_profile=profile,
        meals_per_day=4,
        start_date=datetime.date(2026, 10, 26),
        duration_days=7,
        region="ETHIOPIA",
        dataset=dataset,
    )
    
    ctx = DocumentContext(
        client_name="Kidus Yohannes (ኪዱስ ዮሐንስ)",
        plan_public_id="MP-HILAWE-2026",
        version_number=1,
        language="AM",
        hydration_target_l=3.2,
        coach_name="Coach Hilawe Semma",
        coach_username="@CoachHilaweBot",
        client_profile=profile,
    )
    
    output_pdf = Path(r"d:\The hobby 2\DigitalRevenueHilawe\sample_hilawe_meal_plan.pdf")
    print(f"Rendering Luxury Headless Chromium PDF with Coach photo & watermark to: {output_pdf}")
    res = render_client_pdf(plan, ctx, output_path=output_pdf)
    print(f"SUCCESS! Rendered PDF at: {res} (Size: {res.stat().st_size:,} bytes)")

if __name__ == "__main__":
    main()
