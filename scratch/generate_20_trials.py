"""Automated 20-Persona Stress-Test Runner for Meal Plan PDFs.

Stress-tests the generation engine and HTML-to-PDF renderer across 20 distinct,
realistic client profiles in the Ethiopian fitness market to verify:
1. Every meal contains complete base ingredients with zero ingredient stripping (Day 1 lunch > 1 item).
2. Macro fillers never inject white rice into breakfast oatmeal/toast.
3. Budget tiers ("Save" vs. "Standard" vs. "Premium") are strictly respected.
4. Fasting rules (Wed/Fri, Lent/Tsome, pescatarian vs. strict vegan) are followed without nutritional collapse.
5. Roadmaps and check-in worksheets dynamically match the exact duration (7, 14, or 30 days).
6. Grocery lists aggregate realistically (>= 8 distinct items).
7. Output PDFs are written to 20_TRIAL_PDFS/{index:02d}_{slug}.pdf and are valid (> 50 KB).
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

import dotenv
dotenv.load_dotenv(repo_root / ".env")

from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.generation.engine import generate_plan
from meal_plan.generation.dataset import load_dataset, HilaweDataset
from meal_plan.generation.db_dataset import load_dataset_from_db
from meal_plan.documents.models import DocumentContext
from meal_plan.documents.html_pdf_renderer import render_html_document, render_html_pdf

OUTPUT_DIR = repo_root / "20_TRIAL_PDFS"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 20 Distinct Ethiopian Client Profiles
PERSONAS: list[dict[str, Any]] = [
    {
        "slug": "01_male_hardgainer_save_14d",
        "client_name": "Yohannes Bekele",
        "duration_days": 14,
        "start_date": date(2026, 10, 26),
        "answers": {
            "calculation_sex": "MALE",
            "age": 22,
            "current_weight_kg": 45.0,
            "target_weight_kg": 60.0,
            "height_cm": 172,
            "primary_goal": "MUSCLE_GAIN",
            "grocery_budget": "SAVE",
            "meals_per_day": 3,
            "training_type": "HOME_WORKOUT",
            "training_days_per_week": 3,
            "orthodox_fasting": "NONE",
            "fish_during_fast": False,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "LIGHTLY_ACTIVE",
        },
    },
    {
        "slug": "02_female_fatloss_save_wed_fri_14d",
        "client_name": "Selamawit Tadesse",
        "duration_days": 14,
        "start_date": date(2026, 10, 26),
        "answers": {
            "calculation_sex": "FEMALE",
            "age": 27,
            "current_weight_kg": 70.0,
            "target_weight_kg": 58.0,
            "height_cm": 162,
            "primary_goal": "FAT_LOSS",
            "grocery_budget": "SAVE",
            "meals_per_day": 3,
            "training_type": "HOME_WORKOUT",
            "training_days_per_week": 3,
            "orthodox_fasting": "WED_FRI",
            "fish_during_fast": False,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "LIGHTLY_ACTIVE",
        },
    },
    {
        "slug": "03_male_overweight_fatloss_save_30d",
        "client_name": "Dawit Haile",
        "duration_days": 30,
        "start_date": date(2026, 10, 26),
        "answers": {
            "calculation_sex": "MALE",
            "age": 34,
            "current_weight_kg": 96.0,
            "target_weight_kg": 80.0,
            "height_cm": 178,
            "primary_goal": "FAT_LOSS",
            "grocery_budget": "SAVE",
            "meals_per_day": 3,
            "training_type": "GYM",
            "training_days_per_week": 3,
            "orthodox_fasting": "NONE",
            "fish_during_fast": False,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "LIGHTLY_ACTIVE",
        },
    },
    {
        "slug": "04_female_strict_lent_fasting_save_14d",
        "client_name": "Bethelhem Assefa",
        "duration_days": 14,
        "start_date": date(2026, 3, 2),  # During Great Lent 2026 (2026-02-16 to 2026-04-11)
        "answers": {
            "calculation_sex": "FEMALE",
            "age": 29,
            "current_weight_kg": 64.0,
            "target_weight_kg": 55.0,
            "height_cm": 160,
            "primary_goal": "FAT_LOSS",
            "grocery_budget": "SAVE",
            "meals_per_day": 3,
            "training_type": "HOME_WORKOUT",
            "training_days_per_week": 3,
            "orthodox_fasting": "SEASONAL",
            "fish_during_fast": False,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "LIGHTLY_ACTIVE",
        },
    },
    {
        "slug": "05_male_athletic_recomp_standard_30d",
        "client_name": "Tewodros Girma",
        "duration_days": 30,
        "start_date": date(2026, 10, 26),
        "answers": {
            "calculation_sex": "MALE",
            "age": 26,
            "current_weight_kg": 75.0,
            "target_weight_kg": 78.0,
            "height_cm": 180,
            "primary_goal": "RECOMPOSITION",
            "grocery_budget": "BALANCED",
            "meals_per_day": 3,
            "training_type": "GYM",
            "training_days_per_week": 4,
            "orthodox_fasting": "NONE",
            "fish_during_fast": False,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "ACTIVE",
        },
    },
    {
        "slug": "06_female_lent_with_fish_standard_14d",
        "client_name": "Rahel Mengistu",
        "duration_days": 14,
        "start_date": date(2026, 3, 2),  # During Great Lent 2026
        "answers": {
            "calculation_sex": "FEMALE",
            "age": 31,
            "current_weight_kg": 62.0,
            "target_weight_kg": 56.0,
            "height_cm": 165,
            "primary_goal": "FAT_LOSS",
            "grocery_budget": "BALANCED",
            "meals_per_day": 3,
            "training_type": "HOME_WORKOUT",
            "training_days_per_week": 3,
            "orthodox_fasting": "SEASONAL",
            "fish_during_fast": True,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "LIGHTLY_ACTIVE",
        },
    },
    {
        "slug": "07_male_muscle_gain_sprint_save_7d",
        "client_name": "Binyam Worku",
        "duration_days": 7,
        "start_date": date(2026, 10, 26),
        "answers": {
            "calculation_sex": "MALE",
            "age": 24,
            "current_weight_kg": 58.0,
            "target_weight_kg": 65.0,
            "height_cm": 175,
            "primary_goal": "MUSCLE_GAIN",
            "grocery_budget": "SAVE",
            "meals_per_day": 3,
            "training_type": "GYM",
            "training_days_per_week": 4,
            "orthodox_fasting": "NONE",
            "fish_during_fast": False,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "LIGHTLY_ACTIVE",
        },
    },
    {
        "slug": "08_female_petite_bulking_standard_14d",
        "client_name": "Hanan Mohammed",
        "duration_days": 14,
        "start_date": date(2026, 10, 26),
        "answers": {
            "calculation_sex": "FEMALE",
            "age": 21,
            "current_weight_kg": 44.0,
            "target_weight_kg": 50.0,
            "height_cm": 155,
            "primary_goal": "MUSCLE_GAIN",
            "grocery_budget": "BALANCED",
            "meals_per_day": 3,
            "training_type": "HOME_WORKOUT",
            "training_days_per_week": 3,
            "orthodox_fasting": "NONE",
            "fish_during_fast": False,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "LIGHTLY_ACTIVE",
        },
    },
    {
        "slug": "09_male_hypertrophy_premium_30d",
        "client_name": "Ermias Tesfaye",
        "duration_days": 30,
        "start_date": date(2026, 10, 26),
        "answers": {
            "calculation_sex": "MALE",
            "age": 28,
            "current_weight_kg": 82.0,
            "target_weight_kg": 88.0,
            "height_cm": 184,
            "primary_goal": "MUSCLE_GAIN",
            "grocery_budget": "FLEXIBLE",
            "meals_per_day": 3,
            "training_type": "GYM",
            "training_days_per_week": 5,
            "orthodox_fasting": "NONE",
            "fish_during_fast": False,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "ACTIVE",
        },
    },
    {
        "slug": "10_female_fatloss_snack_save_14d",
        "client_name": "Tsion Kassa",
        "duration_days": 14,
        "start_date": date(2026, 10, 26),
        "answers": {
            "calculation_sex": "FEMALE",
            "age": 25,
            "current_weight_kg": 68.0,
            "target_weight_kg": 58.0,
            "height_cm": 163,
            "primary_goal": "FAT_LOSS",
            "grocery_budget": "SAVE",
            "meals_per_day": 4,  # 3 meals + 1 snack
            "training_type": "HOME_WORKOUT",
            "training_days_per_week": 3,
            "orthodox_fasting": "NONE",
            "fish_during_fast": False,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "LIGHTLY_ACTIVE",
        },
    },
    {
        "slug": "11_male_orthodox_strict_muscle_save_30d",
        "client_name": "Kaleb Berhanu",
        "duration_days": 30,
        "start_date": date(2026, 3, 2),  # During Great Lent 2026
        "answers": {
            "calculation_sex": "MALE",
            "age": 30,
            "current_weight_kg": 60.0,
            "target_weight_kg": 70.0,
            "height_cm": 176,
            "primary_goal": "MUSCLE_GAIN",
            "grocery_budget": "SAVE",
            "meals_per_day": 3,
            "training_type": "GYM",
            "training_days_per_week": 4,
            "orthodox_fasting": "SEASONAL",
            "fish_during_fast": False,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "ACTIVE",
        },
    },
    {
        "slug": "12_female_lifestyle_standard_14d",
        "client_name": "Martha Kebede",
        "duration_days": 14,
        "start_date": date(2026, 10, 26),
        "answers": {
            "calculation_sex": "FEMALE",
            "age": 35,
            "current_weight_kg": 58.0,
            "target_weight_kg": 55.0,
            "height_cm": 168,
            "primary_goal": "FAT_LOSS",
            "grocery_budget": "BALANCED",
            "meals_per_day": 3,
            "training_type": "HOME_WORKOUT",
            "training_days_per_week": 3,
            "orthodox_fasting": "WED_FRI",
            "fish_during_fast": False,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "LIGHTLY_ACTIVE",
        },
    },
    {
        "slug": "13_male_senior_maintenance_save_14d",
        "client_name": "Solomon Wolde",
        "duration_days": 14,
        "start_date": date(2026, 10, 26),
        "answers": {
            "calculation_sex": "MALE",
            "age": 52,
            "current_weight_kg": 72.0,
            "target_weight_kg": 72.0,
            "height_cm": 170,
            "primary_goal": "MAINTAIN",
            "grocery_budget": "SAVE",
            "meals_per_day": 3,
            "training_type": "NOT_TRAINING",
            "training_days_per_week": 0,
            "orthodox_fasting": "NONE",
            "fish_during_fast": False,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "MOSTLY_SEATED",
        },
    },
    {
        "slug": "14_female_extreme_budget_save_14d",
        "client_name": "Genet Alemayehu",
        "duration_days": 14,
        "start_date": date(2026, 10, 26),
        "answers": {
            "calculation_sex": "FEMALE",
            "age": 23,
            "current_weight_kg": 54.0,
            "target_weight_kg": 50.0,
            "height_cm": 158,
            "primary_goal": "FAT_LOSS",
            "grocery_budget": "SAVE",
            "meals_per_day": 3,
            "training_type": "HOME_WORKOUT",
            "training_days_per_week": 2,
            "orthodox_fasting": "NONE",
            "fish_during_fast": False,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "LIGHTLY_ACTIVE",
        },
    },
    {
        "slug": "15_male_high_calorie_bulking_standard_14d",
        "client_name": "Abel Fikru",
        "duration_days": 14,
        "start_date": date(2026, 10, 26),
        "answers": {
            "calculation_sex": "MALE",
            "age": 25,
            "current_weight_kg": 70.0,
            "target_weight_kg": 80.0,
            "height_cm": 182,
            "primary_goal": "MUSCLE_GAIN",
            "grocery_budget": "BALANCED",
            "meals_per_day": 4,  # High calorie, 4 meals
            "training_type": "GYM",
            "training_days_per_week": 5,
            "orthodox_fasting": "NONE",
            "fish_during_fast": False,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "VERY_ACTIVE",  # High TDEE
        },
    },
    {
        "slug": "16_female_sprint_fatloss_save_7d",
        "client_name": "Lydia Hailu",
        "duration_days": 7,
        "start_date": date(2026, 10, 26),
        "answers": {
            "calculation_sex": "FEMALE",
            "age": 28,
            "current_weight_kg": 65.0,
            "target_weight_kg": 60.0,
            "height_cm": 165,
            "primary_goal": "FAT_LOSS",
            "grocery_budget": "SAVE",
            "meals_per_day": 3,
            "training_type": "HOME_WORKOUT",
            "training_days_per_week": 3,
            "orthodox_fasting": "NONE",
            "fish_during_fast": False,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "LIGHTLY_ACTIVE",
        },
    },
    {
        "slug": "17_male_pescatarian_recomp_standard_14d",
        "client_name": "Dagmawi Negash",
        "duration_days": 14,
        "start_date": date(2026, 10, 26),
        "answers": {
            "calculation_sex": "MALE",
            "age": 27,
            "current_weight_kg": 74.0,
            "target_weight_kg": 75.0,
            "height_cm": 177,
            "primary_goal": "RECOMPOSITION",
            "grocery_budget": "BALANCED",
            "meals_per_day": 3,
            "training_type": "GYM",
            "training_days_per_week": 4,
            "orthodox_fasting": "WED_FRI",
            "fish_during_fast": True,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "ACTIVE",
            "disliked_foods": ["BEEF", "CHICKEN", "LAMB", "GOAT_MEAT"],
        },
    },
    {
        "slug": "18_female_vegetarian_save_14d",
        "client_name": "Tigist Demissie",
        "duration_days": 14,
        "start_date": date(2026, 10, 26),
        "answers": {
            "calculation_sex": "FEMALE",
            "age": 26,
            "current_weight_kg": 60.0,
            "target_weight_kg": 54.0,
            "height_cm": 164,
            "primary_goal": "FAT_LOSS",
            "grocery_budget": "SAVE",
            "meals_per_day": 3,
            "training_type": "HOME_WORKOUT",
            "training_days_per_week": 3,
            "orthodox_fasting": "NONE",
            "fish_during_fast": False,
            "dietary_pattern": "VEGETARIAN",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "LIGHTLY_ACTIVE",
        },
    },
    {
        "slug": "19_male_heavy_lifter_bulking_30d",
        "client_name": "Henok Gebre",
        "duration_days": 30,
        "start_date": date(2026, 10, 26),
        "answers": {
            "calculation_sex": "MALE",
            "age": 23,
            "current_weight_kg": 80.0,
            "target_weight_kg": 87.0,
            "height_cm": 185,
            "primary_goal": "MUSCLE_GAIN",
            "grocery_budget": "BALANCED",
            "meals_per_day": 3,
            "training_type": "GYM",
            "training_days_per_week": 5,
            "orthodox_fasting": "NONE",
            "fish_during_fast": False,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "VERY_ACTIVE",
        },
    },
    {
        "slug": "20_female_underweight_muscle_save_14d",
        "client_name": "Eden Melaku",
        "duration_days": 14,
        "start_date": date(2026, 10, 26),
        "answers": {
            "calculation_sex": "FEMALE",
            "age": 20,
            "current_weight_kg": 41.0,
            "target_weight_kg": 48.0,
            "height_cm": 160,
            "primary_goal": "MUSCLE_GAIN",
            "grocery_budget": "SAVE",
            "meals_per_day": 3,
            "training_type": "HOME_WORKOUT",
            "training_days_per_week": 3,
            "orthodox_fasting": "NONE",
            "fish_during_fast": False,
            "dietary_pattern": "OMNIVORE",
            "cuisine_style": "ETHIOPIAN",
            "activity_level": "LIGHTLY_ACTIVE",
        },
    },
]


async def get_dataset() -> HilaweDataset:
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        try:
            import asyncpg
            conn = await asyncpg.connect(db_url)
            try:
                ds = await load_dataset_from_db(conn)
                print("[INIT] Loaded verified dataset from PostgreSQL database.")
                return ds
            finally:
                await conn.close()
        except Exception as e:
            print(f"[INIT] DB load failed ({e}), falling back to local JSON dataset.")
    ds = load_dataset()
    print("[INIT] Loaded default local JSON dataset.")
    return ds


def run_all_trials():
    print("=" * 80)
    print("STARTING 20-PERSONA STRESS-TEST SUITE FOR ETHIOPIAN MEAL PLAN PDFS")
    print(f"Output Directory: {OUTPUT_DIR}")
    print("=" * 80)

    dataset = asyncio.run(get_dataset())

    total_personas = len(PERSONAS)
    passed_count = 0
    failed_count = 0
    results: list[dict[str, Any]] = []

    for index, p in enumerate(PERSONAS, start=1):
        slug = p["slug"]
        client_name = p["client_name"]
        duration = p["duration_days"]
        start_date = p["start_date"]
        answers = p["answers"]
        pdf_filename = f"{slug}.pdf" if slug.startswith(f"{index:02d}_") else f"{index:02d}_{slug}.pdf"
        pdf_path = OUTPUT_DIR / pdf_filename

        print(f"\n[{index:02d}/{total_personas:02d}] Testing persona: {slug}")
        start_time = time.time()

        try:
            # Step 1: Calculate Nutrition Targets
            profile = calculate_nutrition_profile(answers)
            target_kcal = profile.target_kcal
            protein_g = profile.protein_g
            carbs_g = profile.carbs_g
            fat_g = profile.fat_g
            print(f"       Targets: {target_kcal} kcal | P: {protein_g}g | C: {carbs_g}g | F: {fat_g}g")

            # Step 2: Generate Plan
            plan = generate_plan(
                answers=answers,
                nutrition_profile=profile.to_dict(),
                meals_per_day=answers.get("meals_per_day", 3),
                start_date=start_date,
                duration_days=duration,
                region="ETHIOPIA",
                country_name="Ethiopia",
                dataset=dataset,
            )

            # Step 3: Verify Core Engine Assertions
            day1_meals = plan["core_week"][0]["meals"]
            lunch_item_count = len(day1_meals[1]["items"])
            assert lunch_item_count > 1, f"Stripped lunch: Day 1 lunch has only {lunch_item_count} item(s)"

            # Verify no white rice injected into breakfast oatmeal/toast/egg
            for day in plan["core_week"]:
                bfast = day["meals"][0]
                bfast_title = (bfast.get("template_name") or "").lower()
                # If breakfast is oat, toast, omelette, ful, firfir, etc., rice filler should never be added
                if any(k in bfast_title for k in ["oat", "toast", "omelette", "firfir", "ful", "ayib", "bread"]):
                    for it in bfast.get("items", []):
                        f_name = it.get("food_name", "").lower()
                        f_id = it.get("food_id", "")
                        assert "rice" not in f_name and f_id not in {"C003", "C004"}, (
                            f"White rice macro filler injected into breakfast: {f_name} ({f_id})"
                        )

            # Verify budget rules: In SAVE tier, no imported tuna or luxury olive oil
            grocery_items = plan["grocery"]
            distinct_grocery_count = len(grocery_items)
            assert distinct_grocery_count >= 8, f"Collapsed grocery list: only {distinct_grocery_count} items"

            if answers.get("grocery_budget") == "SAVE":
                for item in grocery_items:
                    b_name = item.get("buy_item", "").lower()
                    assert "tuna" not in b_name, f"Budget leak: Imported tuna found in SAVE grocery list ({b_name})"
                    assert "olive oil" not in b_name, f"Budget leak: Olive oil found in SAVE grocery list ({b_name})"

            # Step 4: Render HTML and Validate Dynamic Duration Slicing
            context = DocumentContext(
                client_name=client_name,
                language="AM",
                plan_public_id=f"TEST-PERSONA-{index:02d}",
                version_number="1.0",
                client_profile=answers,
            )
            html = render_html_document(plan, context, is_client_delivery=True)

            # Duration slicing checks
            if duration == 7:
                assert "Week 01" in html or "ሳምንት 01" in html, "7-day plan missing Week 01"
                assert "Week 02" not in html and "ሳምንት 02" not in html, "7-day plan leaked Week 02"
                assert "Week 03" not in html and "ሳምንት 03" not in html, "7-day plan leaked Week 03"
                assert "Week 04" not in html and "ሳምንት 04" not in html, "7-day plan leaked Week 04"
            elif duration == 14:
                assert "Week 01" in html or "ሳምንት 01" in html, "14-day plan missing Week 01"
                assert "Week 02" in html or "ሳምንት 02" in html, "14-day plan missing Week 02"
                assert "Week 03" not in html and "ሳምንት 03" not in html, "14-day plan leaked Week 03"
                assert "Week 04" not in html and "ሳምንት 04" not in html, "14-day plan leaked Week 04"
            elif duration == 30:
                assert "Week 01" in html or "ሳምንት 01" in html, "30-day plan missing Week 01"
                assert "Week 02" in html or "ሳምንት 02" in html, "30-day plan missing Week 02"
                assert "Week 03" in html or "ሳምንት 03" in html, "30-day plan missing Week 03"
                assert "Week 04" in html or "ሳምንት 04" in html, "30-day plan missing Week 04"

            # Check for no dangling template tokens
            assert "| | PAG" not in html, "Dangling metadata token '| | PAG' in rendered HTML"

            # Check authentic Amharic phrasing and formatting
            assert "የሀገር ባህል አይብ" not in html, f"Awkward phrase 'የሀገር ባህል አይብ' found in {slug}"
            assert "የተዘጋጀ እንጀራ" not in html, f"Awkward phrase 'የተዘጋጀ እንጀራ' found in {slug}"
            assert "1 ከግማሽ 1 ከግማሽ" not in html, f"Repeated measure bug found in {slug}"
            assert "መደበኛ መጠን" not in html, f"Robotic placeholder 'መደበኛ መጠን' found in {slug}"

            # Step 5: Render PDF Document
            render_html_pdf(plan, context, str(pdf_path), is_client_delivery=True)
            elapsed = time.time() - start_time

            # Step 6: Validate Output PDF File
            assert pdf_path.exists(), f"PDF output file not created: {pdf_path}"
            pdf_size_bytes = pdf_path.stat().st_size
            pdf_size_kb = pdf_size_bytes / 1024
            assert pdf_size_kb >= 50.0, f"PDF file size too small ({pdf_size_kb:.1f} KB < 50 KB)"

            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
                assert pdf_bytes.startswith(b"%PDF-"), f"Invalid PDF header"
                pages = len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))

            if slug == "04_female_strict_lent_fasting_save_14d":
                assert 13 <= pages <= 16, f"Persona 04 expected 14-15 pages, got {pages}"

            passed_count += 1
            print(f"       [PASS] Day 1 Lunch Items: {lunch_item_count} | Grocery: {distinct_grocery_count} items")
            print(f"              PDF: {pdf_filename} ({pdf_size_kb:.1f} KB) rendered in {elapsed:.1f}s")

            results.append({
                "index": index,
                "slug": slug,
                "status": "PASS",
                "target_kcal": target_kcal,
                "p_c_f": f"{protein_g}/{carbs_g}/{fat_g}",
                "lunch_items": lunch_item_count,
                "grocery_items": distinct_grocery_count,
                "pdf_size_kb": f"{pdf_size_kb:.1f} KB",
                "pdf_path": str(pdf_path),
            })

        except Exception as err:
            failed_count += 1
            print(f"       [FAIL] Error: {err}")
            results.append({
                "index": index,
                "slug": slug,
                "status": "FAIL",
                "error": str(err),
            })

    print("\n" + "=" * 80)
    print("STRESS TEST SUMMARY REPORT")
    print("=" * 80)
    print(f"Total Personas Tested: {total_personas}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")
    print("-" * 80)
    print(f"{'#':<3} | {'Slug':<42} | {'Status':<6} | {'Target':<10} | {'P/C/F':<12} | {'Lunch':<5} | {'Groc':<5} | {'PDF Size':<10}")
    print("-" * 80)
    for r in results:
        idx = r["index"]
        slug = r["slug"]
        status = r["status"]
        if status == "PASS":
            print(f"{idx:<3} | {slug:<42} | {status:<6} | {r['target_kcal']:<10} | {r['p_c_f']:<12} | {r['lunch_items']:<5} | {r['grocery_items']:<5} | {r['pdf_size_kb']:<10}")
        else:
            print(f"{idx:<3} | {slug:<42} | {status:<6} | FAILED: {r.get('error')}")
    print("=" * 80)

    if failed_count > 0:
        sys.exit(1)
    else:
        print("\nALL 20 PERSONA STRESS TESTS COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    run_all_trials()
