from __future__ import annotations

import html
from decimal import Decimal
from typing import Any


def parse_review_callback(data: str) -> tuple[str, int]:
    try:
        prefix, action, raw_id = data.split(":", 2)
        if prefix != "mealreview":
            raise ValueError
        plan_version_id = int(raw_id)
        if action not in {"approve", "regen", "replace", "client", "deliver"} or plan_version_id <= 0:
            raise ValueError
        return action, plan_version_id
    except (ValueError, AttributeError):
        raise ValueError("Invalid Meal Plan review action")


def _money(amount: object, currency: str) -> str:
    value = Decimal(str(amount or 0))
    return f"{value:,.2f} Br" if currency == "ETB" else f"${value:,.2f}"


def review_card_text(version: Any) -> str:
    plan = dict(version.get("plan_json") or {})
    targets = dict(plan.get("nutrition_targets") or version.get("nutrition_profile") or {})
    review = dict(plan.get("review") or {})
    profile = dict(plan.get("profile_summary") or {})
    name = html.escape(str(version.get("full_name") or "Member"))
    username = version.get("username")
    user_line = f"@{html.escape(str(username))}" if username else f"ID <code>{version['user_id']}</code>"
    warnings = list(review.get("practical_warnings") or [])
    uncal = list(review.get("uncalibrated_recipes") or [])
    source = str(version.get("source") or "GENERATED")
    detail = str(version.get("detail_source") or "STRUCTURED")
    override_note = "\n⚠️ <b>DOCUMENT OVERRIDE:</b> uploaded PDF/DOCX are authoritative." if detail == "DOCUMENT_OVERRIDE" else ""
    revision = dict(plan.get("revision_context") or {})
    revision_note = ""
    if revision:
        reasons = "; ".join(str(x) for x in revision.get("reasons") or [])
        revision_note = (
            f"\n🔄 <b>FOLLOW-UP REVISION:</b> Week {html.escape(str(revision.get('week_number') or '—'))}"
            f" · kcal delta {html.escape(str(revision.get('kcal_delta') or 0))}"
            f" · current weight {html.escape(str(revision.get('current_weight_kg') or '—'))} kg"
            + (f"\nReason: {html.escape(reasons)}" if reasons else "")
        )
    warning_line = "None" if not warnings and not uncal else f"{len(warnings)} practical · {len(uncal)} recipe calibration"
    return (
        "🥗 <b>HILAWE MEAL PLAN · COACH REVIEW</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{name}</b> · {user_line}\n"
        f"📦 Order <code>{html.escape(str(version.get('order_public_id') or version.get('order_id')))}</code>\n"
        f"📄 Version <b>V{version['version_number']}</b> · {html.escape(source)}\n"
        f"🗓 {version['duration_days']} days · {version['meals_per_day']} meals/day · {html.escape(str(version['service_type']))}\n"
        f"▶️ {version['start_date']} → {version['ends_on']}\n"
        f"🌍 {html.escape(str(version.get('country_name') or version.get('region') or '—'))}\n"
        f"💰 {_money(version.get('amount'), str(version.get('currency') or 'ETB'))}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Goal: <b>{html.escape(str(profile.get('goal') or '—'))}</b>\n"
        f"🔥 Target: <b>{targets.get('target_kcal', '—')} kcal</b>\n"
        f"🥩 Protein: <b>{targets.get('protein_g', '—')} g</b> · 🍚 Carbs: <b>{targets.get('carbs_g', '—')} g</b> · 🥑 Fat: <b>{targets.get('fat_g', '—')} g</b>\n"
        f"⚕️ Review flags: <b>{html.escape(warning_line)}</b>\n"
        f"⚙️ Engine: <code>{html.escape(str(version.get('engine_version') or '—'))}</code>\n"
        f"🗃 Dataset: <code>{html.escape(str(version.get('dataset_version') or '—'))}</code>"
        f"{override_note}{revision_note}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Approve only after checking the actual attached PDF/DOCX. Nothing is sent to the client before approval."
    )
