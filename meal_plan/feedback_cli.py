"""Coach Feedback Management CLI (Pillar 3 Architecture).

Allows developers and operators to list, inspect, add, update, and parse Coach Boss
feedback rules into the persistent rule catalog without touching python code.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from meal_plan.generation.feedback_store import FeedbackRule, get_feedback_store


def cmd_list(args: argparse.Namespace) -> None:
    store = get_feedback_store(reload=True)
    rules = store.get_all_rules()
    if args.type:
        rules = [r for r in rules if r.type == args.type]
    if args.active_only:
        rules = [r for r in rules if r.is_active]

    print("\n" + "=" * 90)
    print(f"📋 COACH FEEDBACK RULE CATALOG ({len(rules)} Rules) | Path: {store.catalog_path}")
    print("=" * 90)
    print(f"{'RULE ID':<35} | {'TYPE':<18} | {'STATUS':<8} | {'AUTHOR':<14} | {'SEV':<7}")
    print("-" * 90)

    for r in sorted(rules, key=lambda x: (not x.is_active, x.type, x.id)):
        status_str = "🟢 ON" if r.is_active else "⚪ OFF"
        sev_str = "ERR" if r.severity == "ERROR" else ("WARN" if r.severity == "WARNING" else "INFO")
        print(f"{r.id:<35} | {r.type:<18} | {status_str:<8} | {r.author:<14} | {sev_str:<7}")
        print(f"  └─ {r.name}: {r.description}")
        if r.metadata:
            meta_brief = json.dumps(r.metadata, ensure_ascii=False)
            if len(meta_brief) > 80:
                meta_brief = meta_brief[:77] + "..."
            print(f"     ⚙️  Metadata: {meta_brief}")
    print("=" * 90 + "\n")


def cmd_add_cap(args: argparse.Namespace) -> None:
    store = get_feedback_store()
    rule_id = args.id or f"RULE_CAP_{args.food_id.upper()}_{int(args.max_grams)}G"
    rule = FeedbackRule(
        id=rule_id,
        type="portion_cap",
        name=args.name or f"Portion Cap on {args.food_id.upper()} ({args.max_grams:.0f}g)",
        description=args.desc or f"Cap {args.food_id.upper()} to maximum {args.max_grams:.0f}g per meal.",
        author=args.author,
        is_active=True,
        severity=args.severity,
        metadata={
            "target_id": args.food_id.upper(),
            "max_grams": float(args.max_grams),
            "enforced_familiar": args.familiar or "",
            "applies_to": "all",
        }
    )
    store.add_rule(rule)
    print(f"✅ Added portion cap rule: {rule.id}")


def cmd_add_exclusion(args: argparse.Namespace) -> None:
    store = get_feedback_store()
    primaries = [p.strip().upper() for p in args.primaries.split(",")]
    forbidden = [f.strip().upper() for f in args.forbidden.split(",")]
    rule_id = args.id or f"RULE_EXCLUDE_{forbidden[0]}_{primaries[0]}"
    rule = FeedbackRule(
        id=rule_id,
        type="pairing_exclusion",
        name=args.name or f"Exclude {', '.join(forbidden)} with {', '.join(primaries)}",
        description=args.desc or f"Forbid {', '.join(forbidden)} when {', '.join(primaries)} are served.",
        author=args.author,
        is_active=True,
        severity=args.severity,
        metadata={
            "primary_ids": primaries,
            "forbidden_secondary_ids": forbidden,
            "action": "remove_secondary",
        }
    )
    store.add_rule(rule)
    print(f"✅ Added pairing exclusion rule: {rule.id}")


def cmd_parse_feedback(args: argparse.Namespace) -> None:
    if getattr(args, "use_ai", False):
        from meal_plan.ai.gemini_coach import get_gemini_coach
        coach = get_gemini_coach()
        print("🤖 Synthesizing rule via Gemini 3.8 Flash & RAG...")
        rule = coach.synthesize_feedback_rule(
            feedback_text=args.text,
            author=args.author,
            context={"submitted_via": "CLI_GEMINI_AI"}
        )
    else:
        store = get_feedback_store()
        rule = store.record_coach_feedback(
            feedback_text=args.text,
            author=args.author,
            context={"submitted_via": "CLI"}
        )
    print(f"🎉 Successfully parsed and stored Coach feedback rule:")
    print(f"  ID: {rule.id}")
    print(f"  Type: {rule.type}")
    print(f"  Name: {rule.name}")
    print(f"  Severity: {rule.severity}")
    print(f"  Metadata: {json.dumps(rule.metadata, ensure_ascii=False, indent=2)}")


def cmd_toggle(args: argparse.Namespace) -> None:
    store = get_feedback_store()
    rule = store.get_rule(args.id)
    if not rule:
        print(f"❌ Error: Rule '{args.id}' not found in catalog.")
        sys.exit(1)
    if rule.is_active:
        store.archive_rule(args.id)
        print(f"⚪ Rule '{args.id}' is now DEACTIVATED (archived).")
    else:
        store.activate_rule(args.id)
        print(f"🟢 Rule '{args.id}' is now ACTIVATED.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Coach Feedback Catalog Management Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List all rules in catalog")
    p_list.add_argument("--type", help="Filter by rule type")
    p_list.add_argument("--active-only", action="store_true", help="Only show active rules")
    p_list.set_defaults(func=cmd_list)

    # add-cap
    p_cap = subparsers.add_parser("add-cap", help="Add portion cap rule")
    p_cap.add_argument("--food-id", required=True, help="Food ID (e.g. C020, T001)")
    p_cap.add_argument("--max-grams", type=float, required=True, help="Max grams allowed")
    p_cap.add_argument("--name", help="Rule title")
    p_cap.add_argument("--desc", help="Detailed description")
    p_cap.add_argument("--familiar", help="Enforced familiar household string")
    p_cap.add_argument("--author", default="Coach Hilawe", help="Author")
    p_cap.add_argument("--severity", default="WARNING", choices=["INFO", "WARNING", "ERROR"])
    p_cap.add_argument("--id", help="Custom rule ID")
    p_cap.set_defaults(func=cmd_add_cap)

    # add-exclusion
    p_ex = subparsers.add_parser("add-exclusion", help="Add pairing exclusion rule")
    p_ex.add_argument("--primaries", required=True, help="Comma-separated primary dish IDs (e.g. R001,R002)")
    p_ex.add_argument("--forbidden", required=True, help="Comma-separated forbidden secondary IDs (e.g. P001,P007)")
    p_ex.add_argument("--name", help="Rule title")
    p_ex.add_argument("--desc", help="Detailed description")
    p_ex.add_argument("--author", default="Coach Hilawe", help="Author")
    p_ex.add_argument("--severity", default="ERROR", choices=["INFO", "WARNING", "ERROR"])
    p_ex.add_argument("--id", help="Custom rule ID")
    p_ex.set_defaults(func=cmd_add_exclusion)

    # parse-feedback
    p_fb = subparsers.add_parser("parse-feedback", help="Parse natural text feedback into structured rule")
    p_fb.add_argument("--text", required=True, help="Coach feedback text")
    p_fb.add_argument("--author", default="Coach Boss", help="Feedback author")
    p_fb.add_argument("--use-ai", action="store_true", help="Use Gemini 3.8 Flash RAG to synthesize rule")
    p_fb.set_defaults(func=cmd_parse_feedback)

    # toggle
    p_tog = subparsers.add_parser("toggle", help="Toggle rule active / inactive")
    p_tog.add_argument("--id", required=True, help="Rule ID to toggle")
    p_tog.set_defaults(func=cmd_toggle)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
