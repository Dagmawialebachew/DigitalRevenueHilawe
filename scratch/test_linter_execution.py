import sys
from datetime import date
from dotenv import load_dotenv

sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')
load_dotenv(r'd:\The hobby 2\DigitalRevenueHilawe\.env')

from meal_plan.generation.dataset import load_dataset
from meal_plan.generation.engine import generate_plan
from meal_plan.generation.linter import MealPlanLinter
from scratch.test_plan_engine_personas import bezawit_answers, bezawit_targets

dataset = load_dataset()
linter = MealPlanLinter(strict=True)

print("=== 1. GENERATING BEZAWIT PLAN ===")
plan = generate_plan(
    answers=bezawit_answers,
    nutrition_profile=bezawit_targets,
    meals_per_day=3,
    start_date=date(2026, 11, 2),
    duration_days=7,
    region="ADDIS_ABABA",
    country_name="Ethiopia",
    dataset=dataset,
)

print("\n=== 2. RUNNING PRE-FLIGHT LINTER ===")
report = linter.lint_plan(plan, answers=bezawit_answers, nutrition_profile=bezawit_targets)

print(f"\nAudit Result: Score = {report.score} / 10.0 | Passed = {report.passed}")
print(f"Errors = {report.errors_count} | Warnings = {report.warnings_count}")
print("\n" + report.summary_markdown)
