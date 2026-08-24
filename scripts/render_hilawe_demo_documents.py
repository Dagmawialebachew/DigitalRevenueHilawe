"""Render premium local Phase 7 DOCX/PDF artifacts from a structured plan JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from meal_plan.documents import DocumentContext, render_plan_artifacts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, help="Structured Phase 6 plan JSON")
    parser.add_argument("--output-root", default="artifacts/meal_plans")
    parser.add_argument("--client", default="Demo Client")
    parser.add_argument("--plan-id", default="MP-DEMO-0001")
    parser.add_argument("--language", choices=("AM", "EN"), default="AM")
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--weight", type=float, default=75.4)
    parser.add_argument("--target-weight", type=float, default=72.0)
    parser.add_argument("--hydration", type=float, default=2.6)
    parser.add_argument("--coach-image", default=None)
    args = parser.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    context = DocumentContext(
        client_name=args.client,
        plan_public_id=args.plan_id,
        version_number=args.version,
        language=args.language,
        client_profile={
            "current_weight_kg": args.weight,
            "target_weight_kg": args.target_weight,
        },
        hydration_target_l=args.hydration,
        coach_image_path=args.coach_image,
    )
    result = render_plan_artifacts(plan, context, output_root=args.output_root)
    print(f"DOCX: {result.docx.path}")
    print(f"PDF:  {result.pdf.path}")
    print(f"Manifest: {result.manifest_path}")
    print(f"DOCX SHA256: {result.docx.sha256}")
    print(f"PDF SHA256:  {result.pdf.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
