import os
import sys
import time
from pathlib import Path
from datetime import date

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

import dotenv
dotenv.load_dotenv(repo_root / ".env")

from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan
from meal_plan.generation.dataset import load_dataset
from meal_plan.documents.models import DocumentContext
from meal_plan.documents.html_pdf_renderer import render_html_pdf, render_html_document

TEST_PERSONAS = [
    {
        "slug": "01_male_hardgainer_save_14d",
        "client_name": "Yohannes Bekele",
        "answers": {
            "calculation_sex": "MALE", "age": 22, "current_weight_kg": 45.0, "target_weight_kg": 60.0,
            "height_cm": 172, "activity_level": "LIGHTLY_ACTIVE", "primary_goal": "MUSCLE_GAIN",
            "meals_per_day": 3, "cuisine_style": "ETHIOPIAN", "dietary_pattern": "OMNIVORE",
            "grocery_budget": "SAVE", "orthodox_fasting": "NONE", "training_days_per_week": 3,
            "training_type": "HOME_WORKOUT"
        },
        "days": 14
    },
    {
        "slug": "02_female_fatloss_save_wed_fri_14d",
        "client_name": "Selamawit Tadesse",
        "answers": {
            "calculation_sex": "FEMALE", "age": 27, "current_weight_kg": 70.0, "target_weight_kg": 58.0,
            "height_cm": 162, "activity_level": "LIGHTLY_ACTIVE", "primary_goal": "FAT_LOSS",
            "meals_per_day": 3, "cuisine_style": "ETHIOPIAN", "dietary_pattern": "OMNIVORE",
            "grocery_budget": "SAVE", "orthodox_fasting": "WED_FRI", "training_days_per_week": 3,
            "training_type": "HOME_WORKOUT"
        },
        "days": 14
    },
    {
        "slug": "03_male_overweight_fatloss_save_30d",
        "client_name": "Dawit Haile",
        "answers": {
            "calculation_sex": "MALE", "age": 34, "current_weight_kg": 96.0, "target_weight_kg": 80.0,
            "height_cm": 178, "activity_level": "MODERATELY_ACTIVE", "primary_goal": "FAT_LOSS",
            "meals_per_day": 3, "cuisine_style": "ETHIOPIAN", "dietary_pattern": "OMNIVORE",
            "grocery_budget": "SAVE", "orthodox_fasting": "NONE", "training_days_per_week": 4,
            "training_type": "GYM_WORKOUT"
        },
        "days": 30
    },
    {
        "slug": "04_female_strict_lent_fasting_save_14d",
        "client_name": "Bethelhem Assefa",
        "answers": {
            "calculation_sex": "FEMALE", "age": 29, "current_weight_kg": 64.0, "target_weight_kg": 55.0,
            "height_cm": 160, "activity_level": "LIGHTLY_ACTIVE", "primary_goal": "FAT_LOSS",
            "meals_per_day": 3, "cuisine_style": "ETHIOPIAN", "dietary_pattern": "OMNIVORE",
            "grocery_budget": "SAVE", "orthodox_fasting": "LENT", "fish_during_fast": False,
            "training_days_per_week": 3, "training_type": "HOME_WORKOUT"
        },
        "days": 14
    },
    {
        "slug": "05_male_athletic_recomp_standard_30d",
        "client_name": "Ermias Tesfaye",
        "answers": {
            "calculation_sex": "MALE", "age": 26, "current_weight_kg": 75.0, "target_weight_kg": 78.0,
            "height_cm": 180, "activity_level": "MODERATELY_ACTIVE", "primary_goal": "RECOMPOSITION",
            "meals_per_day": 3, "cuisine_style": "ETHIOPIAN", "dietary_pattern": "OMNIVORE",
            "grocery_budget": "BALANCED", "orthodox_fasting": "NONE", "training_days_per_week": 4,
            "training_type": "GYM_WORKOUT"
        },
        "days": 30
    },
    {
        "slug": "06_female_lent_with_fish_standard_14d",
        "client_name": "Rahel Getachew",
        "answers": {
            "calculation_sex": "FEMALE", "age": 31, "current_weight_kg": 62.0, "target_weight_kg": 56.0,
            "height_cm": 165, "activity_level": "LIGHTLY_ACTIVE", "primary_goal": "FAT_LOSS",
            "meals_per_day": 3, "cuisine_style": "ETHIOPIAN", "dietary_pattern": "OMNIVORE",
            "grocery_budget": "BALANCED", "orthodox_fasting": "LENT", "fish_during_fast": True,
            "training_days_per_week": 3, "training_type": "HOME_WORKOUT"
        },
        "days": 14
    },
    {
        "slug": "07_male_orthodox_strict_muscle_save_30d",
        "client_name": "Tewodros Girma",
        "answers": {
            "calculation_sex": "MALE", "age": 30, "current_weight_kg": 60.0, "target_weight_kg": 70.0,
            "height_cm": 176, "activity_level": "MODERATELY_ACTIVE", "primary_goal": "MUSCLE_GAIN",
            "meals_per_day": 3, "cuisine_style": "ETHIOPIAN", "dietary_pattern": "OMNIVORE",
            "grocery_budget": "SAVE", "orthodox_fasting": "LENT", "fish_during_fast": False,
            "training_days_per_week": 4, "training_type": "GYM_WORKOUT"
        },
        "days": 30
    },
    {
        "slug": "08_male_senior_maintenance_save_14d",
        "client_name": "Kebede Worku",
        "answers": {
            "calculation_sex": "MALE", "age": 52, "current_weight_kg": 72.0, "target_weight_kg": 72.0,
            "height_cm": 170, "activity_level": "SEDENTARY", "primary_goal": "MAINTENANCE",
            "meals_per_day": 3, "cuisine_style": "ETHIOPIAN", "dietary_pattern": "OMNIVORE",
            "grocery_budget": "SAVE", "orthodox_fasting": "NONE", "training_days_per_week": 0,
            "training_type": "NONE"
        },
        "days": 14
    },
    {
        "slug": "09_male_pescatarian_recomp_standard_14d",
        "client_name": "Abel Desta",
        "answers": {
            "calculation_sex": "MALE", "age": 27, "current_weight_kg": 74.0, "target_weight_kg": 75.0,
            "height_cm": 177, "activity_level": "MODERATELY_ACTIVE", "primary_goal": "RECOMPOSITION",
            "meals_per_day": 3, "cuisine_style": "ETHIOPIAN", "dietary_pattern": "PESCATARIAN",
            "grocery_budget": "BALANCED", "orthodox_fasting": "WED_FRI", "training_days_per_week": 4,
            "training_type": "GYM_WORKOUT"
        },
        "days": 14
    },
    {
        "slug": "10_female_vegetarian_save_14d",
        "client_name": "Hana Mekonnen",
        "answers": {
            "calculation_sex": "FEMALE", "age": 26, "current_weight_kg": 60.0, "target_weight_kg": 54.0,
            "height_cm": 164, "activity_level": "LIGHTLY_ACTIVE", "primary_goal": "FAT_LOSS",
            "meals_per_day": 3, "cuisine_style": "ETHIOPIAN", "dietary_pattern": "VEGETARIAN",
            "grocery_budget": "SAVE", "orthodox_fasting": "NONE", "training_days_per_week": 3,
            "training_type": "HOME_WORKOUT"
        },
        "days": 14
    }
]

def run():
    out_dir = repo_root / "10_TRIAL_PDFS"
    out_dir.mkdir(parents=True, exist_ok=True)
    dataset = load_dataset()

    print(f"Starting 10-Trial Generation into {out_dir}...\n")
    start_total = time.time()

    for i, p in enumerate(TEST_PERSONAS, 1):
        slug = p["slug"]
        answers = p["answers"]
        days = p["days"]
        client_name = p.get("client_name", f"Client {i}")
        t0 = time.time()
        print(f"[{i:02d}/10] Generating {slug} ({days} days)...")

        profile = calculate_nutrition_profile(answers)
        plan = generate_plan(
            answers=answers,
            nutrition_profile=profile.to_dict(),
            meals_per_day=answers["meals_per_day"],
            start_date=date(2026, 10, 26),
            duration_days=days,
            region="ETHIOPIA",
            country_name="Ethiopia",
            dataset=dataset,
        )

        context = DocumentContext(
            client_name=client_name,
            language="AM",
            plan_public_id=f"HILAWE-{i:02d}",
            version_number="1.0",
            client_profile=answers,
        )

        pdf_path = out_dir / f"{i:02d}_{slug}.pdf"
        render_html_pdf(plan, context, str(pdf_path), is_client_delivery=True)
        pdf_size_kb = pdf_path.stat().st_size / 1024
        elapsed = time.time() - t0
        print(f"       -> [SUCCESS] Rendered {pdf_path.name} ({pdf_size_kb:.1f} KB) in {elapsed:.1f}s")

    print(f"\nCompleted generating all 10 stress-test trial PDFs in {out_dir}/ in {time.time()-start_total:.1f}s!")

if __name__ == "__main__":
    run()
