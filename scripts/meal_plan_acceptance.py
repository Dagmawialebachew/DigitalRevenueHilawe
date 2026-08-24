"""Final offline acceptance harness for the Meal Plan release candidate.

It exercises the locked engine matrix and document pipeline without touching
Telegram or PostgreSQL. Optionally it can also ping a running API health URL.
"""
from __future__ import annotations

import argparse
import json
import tempfile
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from meal_plan.documents import DocumentContext, render_plan_artifacts
from meal_plan.generation.engine import generate_plan
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.release_gate import release_report
from scripts.generate_hilawe_demo_plan import demo_answers


@dataclass(frozen=True)
class AcceptanceCheck:
    code: str
    status: str
    message: str


def _scenario(name: str, *, meals: int, days: int, overrides: dict) -> AcceptanceCheck:
    answers = demo_answers()
    answers.update(overrides)
    profile = calculate_nutrition_profile(answers).to_dict()
    plan = generate_plan(
        answers=answers,
        nutrition_profile=profile,
        meals_per_day=meals,
        start_date=date(2026, 8, 24),
        duration_days=days,
        region="ETHIOPIA",
    )
    meal_counts_ok = all(len(day["meals"]) == meals for day in plan["core_week"])
    rotation_ok = len(plan["rotation"]) == days
    review_ok = bool(plan["review"]["required"]) and not bool(plan["policy"]["auto_delivery"])
    if not (meal_counts_ok and rotation_ok and review_ok):
        return AcceptanceCheck(name, "BLOCK", "Engine contract failed for acceptance scenario.")
    return AcceptanceCheck(name, "PASS", f"{meals}-meal / {days}-day deterministic plan generated and remains Coach-gated.")


def _document_smoke(language: str) -> AcceptanceCheck:
    answers = demo_answers()
    profile = calculate_nutrition_profile(answers).to_dict()
    plan = generate_plan(
        answers=answers,
        nutrition_profile=profile,
        meals_per_day=4,
        start_date=date(2026, 8, 24),
        duration_days=30,
        region="ETHIOPIA",
    )
    with tempfile.TemporaryDirectory(prefix="hilawe_acceptance_") as tmp:
        context = DocumentContext(
            client_name="Acceptance Demo",
            plan_public_id=f"MP-RC-{language}",
            version_number=1,
            language=language,
            client_profile={"current_weight_kg": 75.4, "target_weight_kg": 72.0},
            hydration_target_l=2.6,
        )
        result = render_plan_artifacts(plan, context, output_root=tmp)
        docx = Path(result.docx.path)
        pdf = Path(result.pdf.path)
        manifest = Path(result.manifest_path)
        if not docx.exists() or docx.stat().st_size < 10_000:
            return AcceptanceCheck(f"DOCUMENT_{language}", "BLOCK", "DOCX smoke artifact missing or too small.")
        if not pdf.exists() or pdf.stat().st_size < 10_000 or not pdf.read_bytes().startswith(b"%PDF"):
            return AcceptanceCheck(f"DOCUMENT_{language}", "BLOCK", "PDF smoke artifact missing/invalid.")
        if not manifest.exists():
            return AcceptanceCheck(f"DOCUMENT_{language}", "BLOCK", "Artifact manifest missing.")
    return AcceptanceCheck(f"DOCUMENT_{language}", "PASS", f"{language} DOCX/PDF + manifest render smoke passed.")


def _api_health(api_url: str) -> AcceptanceCheck:
    url = api_url.rstrip("/") + "/api/meal/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return AcceptanceCheck("API_HEALTH", "BLOCK", f"Running Meal Plan API health check failed ({type(exc).__name__}).")
    ok = payload.get("ok") is True and payload.get("service") == "meal-plan" and int(payload.get("phase", 0)) >= 10
    return AcceptanceCheck(
        "API_HEALTH",
        "PASS" if ok else "BLOCK",
        "Running Meal Plan API reports Phase 10 health." if ok else "Running API health payload is not the Phase 10 Meal Plan service.",
    )


def collect_acceptance(*, mode: str, full_demo: bool, documents: bool, api_url: str | None) -> list[AcceptanceCheck]:
    checks: list[AcceptanceCheck] = []
    gate = release_report(mode, full_demo=full_demo)
    checks.append(AcceptanceCheck(
        "RELEASE_GATE",
        "PASS" if gate.ready else "BLOCK",
        f"Release gate has {gate.blockers} blocker(s) and {gate.warnings} warning(s).",
    ))

    checks.extend([
        _scenario("ENGINE_3X7", meals=3, days=7, overrides={"orthodox_fasting": "NONE", "fish_during_fast": False}),
        _scenario("ENGINE_4X14_VEGETARIAN", meals=4, days=14, overrides={"dietary_pattern": "VEGETARIAN", "orthodox_fasting": "NONE", "fish_during_fast": False}),
        _scenario("ENGINE_5X30_FASTING", meals=5, days=30, overrides={"orthodox_fasting": "WED_FRI", "fish_during_fast": True}),
        _scenario("ENGINE_ALLERGY_PATH", meals=4, days=7, overrides={"orthodox_fasting": "NONE", "fish_during_fast": False, "food_allergies": ["PEANUTS"]}),
    ])

    if documents:
        checks.append(_document_smoke("AM"))
        checks.append(_document_smoke("EN"))
    if api_url:
        checks.append(_api_health(api_url))
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coach Hilawe Meal Plan final acceptance harness")
    parser.add_argument("--mode", choices=("demo", "production"), default="demo")
    parser.add_argument("--full-demo", action="store_true", help="Upgrade demo HTTPS/worker requirements to blockers")
    parser.add_argument("--skip-documents", action="store_true")
    parser.add_argument("--api-url", default="")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    checks = collect_acceptance(
        mode=args.mode,
        full_demo=args.full_demo,
        documents=not args.skip_documents,
        api_url=args.api_url.strip() or None,
    )
    blockers = sum(item.status == "BLOCK" for item in checks)
    warnings = sum(item.status == "WARN" for item in checks)

    if args.as_json:
        print(json.dumps({
            "ready": blockers == 0,
            "blockers": blockers,
            "warnings": warnings,
            "checks": [asdict(item) for item in checks],
        }, indent=2))
    else:
        print("Coach Hilawe Meal Plan - FINAL ACCEPTANCE")
        for item in checks:
            print(f"[{item.status:5}] {item.code}: {item.message}")
        print(f"Summary: {blockers} blocker(s), {warnings} warning(s)")
        print("RELEASE CANDIDATE ACCEPTED" if blockers == 0 else "RELEASE CANDIDATE NOT READY")
    return 0 if blockers == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
