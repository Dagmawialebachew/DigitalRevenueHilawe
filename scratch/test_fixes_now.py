import sys
import os
import re
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
from meal_plan.documents.html_pdf_renderer import render_html_document, render_html_pdf

def run():
    ds = load_dataset()
    test_cases = [
        (
            "01_male_hardgainer_save_14d",
            "Yohannes Bekele",
            14,
            date(2026, 10, 26),
            {
                'calculation_sex': 'MALE', 'age': 22, 'current_weight_kg': 45.0, 'target_weight_kg': 60.0,
                'height_cm': 172, 'primary_goal': 'MUSCLE_GAIN', 'grocery_budget': 'SAVE', 'meals_per_day': 3,
                'training_type': 'HOME_WORKOUT', 'training_days_per_week': 3, 'orthodox_fasting': 'NONE',
                'fish_during_fast': False, 'dietary_pattern': 'OMNIVORE', 'cuisine_style': 'ETHIOPIAN',
                'activity_level': 'LIGHTLY_ACTIVE'
            }
        ),
        (
            "02_female_fatloss_save_wed_fri_14d",
            "Selamawit Tadesse",
            14,
            date(2026, 10, 26),
            {
                'calculation_sex': 'FEMALE', 'age': 27, 'current_weight_kg': 70.0, 'target_weight_kg': 58.0,
                'height_cm': 162, 'primary_goal': 'FAT_LOSS', 'grocery_budget': 'SAVE', 'meals_per_day': 3,
                'training_type': 'HOME_WORKOUT', 'training_days_per_week': 3, 'orthodox_fasting': 'WED_FRI',
                'fish_during_fast': False, 'dietary_pattern': 'OMNIVORE', 'cuisine_style': 'ETHIOPIAN',
                'activity_level': 'LIGHTLY_ACTIVE'
            }
        ),
        (
            "04_female_strict_lent_fasting_save_14d",
            "Bethelhem Assefa",
            14,
            date(2026, 3, 2),
            {
                'calculation_sex': 'FEMALE', 'age': 29, 'current_weight_kg': 64.0, 'target_weight_kg': 55.0,
                'height_cm': 160, 'primary_goal': 'FAT_LOSS', 'grocery_budget': 'SAVE', 'meals_per_day': 3,
                'training_type': 'HOME_WORKOUT', 'training_days_per_week': 3, 'orthodox_fasting': 'LENT',
                'fish_during_fast': False, 'dietary_pattern': 'OMNIVORE', 'cuisine_style': 'ETHIOPIAN',
                'activity_level': 'LIGHTLY_ACTIVE'
            }
        ),
    ]

    for slug, client_name, duration, start_d, answers in test_cases:
        print(f"\n--- Testing {slug} ---")
        profile = calculate_nutrition_profile(answers).to_dict()
        plan = generate_plan(
            answers=answers,
            nutrition_profile=profile,
            meals_per_day=answers.get("meals_per_day", 3),
            start_date=start_d,
            duration_days=duration,
            region='ETHIOPIA',
            dataset=ds
        )

        # Check Greek Yogurt strictly excluded in SAVE budget
        for day in plan["core_week"]:
            for meal in day["meals"]:
                for it in meal["items"]:
                    fid = str(it.get("food_id") or "")
                    fname = str(it.get("food_name") or "").lower()
                    assert fid != "A013" and "greek yogurt" not in fname, f"Greek yogurt leaked into {slug}: {fname}"

        ctx = DocumentContext(
            client_name=client_name,
            language="AM",
            plan_public_id=f"TEST-{slug[:2]}",
            version_number="1.0",
            client_profile=answers
        )
        html = render_html_document(plan, ctx, is_client_delivery=True)

        assert "የሀገር ባህል አይብ" not in html, f"Found awkward phrase 'የሀገር ባህል አይብ' in {slug}"
        assert "የተዘጋጀ እንጀራ" not in html, f"Found awkward phrase 'የተዘጋጀ እንጀራ' in {slug}"
        assert "1 ከግማሽ 1 ከግማሽ" not in html, f"Found double string in {slug}"
        assert "መደበኛ መጠን" not in html, f"Found 'መደበኛ መጠን' in {slug}"
        
        # Check swap role labels
        assert "🔄" in html, f"No swap symbol found in {slug}"
        assert ("የእንጀራ / የእህል ተቀያሪ፦" in html or "የስጋ / የፕሮቲን ተቀያሪ፦" in html or "የምግብ ተቀያሪ አማራጭ፦" in html or "የቅባት ተቀያሪ፦" in html), f"Swap role labels missing in {slug}"

        pdf_out = Path(f"scratch/test_{slug}.pdf")
        render_html_pdf(plan, ctx, str(pdf_out), is_client_delivery=True)
        with open(pdf_out, "rb") as f:
            pdf_bytes = f.read()
        pages = len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))
        print(f"[PASS] {slug}: {pdf_out.stat().st_size / 1024:.1f} KB, {pages} pages")
        if slug == "04_female_strict_lent_fasting_save_14d":
            assert 13 <= pages <= 16, f"Expected 14-15 pages, got {pages}"

    print("\nALL VERIFICATIONS (01, 02, 04) PASSED PERFECTLY!")

if __name__ == "__main__":
    run()
