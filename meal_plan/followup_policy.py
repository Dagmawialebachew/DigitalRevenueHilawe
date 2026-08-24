from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class CheckinValidationError(ValueError):
    pass


ALLOWED_RATINGS = {1, 2, 3, 4, 5}


def _number(name: str, value: Any, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CheckinValidationError(f"{name} must be a number")
    value = float(value)
    if value < minimum or value > maximum:
        raise CheckinValidationError(f"{name} must be between {minimum:g} and {maximum:g}")
    return round(value, 2)


def _rating(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in ALLOWED_RATINGS:
        raise CheckinValidationError(f"{name} must be an integer from 1 to 5")
    return value


def _text(name: str, value: Any, limit: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise CheckinValidationError(f"{name} must be text")
    value = " ".join(value.strip().split())
    if len(value) > limit:
        raise CheckinValidationError(f"{name} must be {limit} characters or fewer")
    return value


def validate_checkin_answers(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise CheckinValidationError("check-in answers must be an object")

    health_change = raw.get("health_change")
    if not isinstance(health_change, bool):
        raise CheckinValidationError("health_change must be true or false")

    answers: dict[str, Any] = {
        "current_weight_kg": _number("current_weight_kg", raw.get("current_weight_kg"), 30, 300),
        "adherence_percent": int(_number("adherence_percent", raw.get("adherence_percent"), 0, 100)),
        "hunger_rating": _rating("hunger_rating", raw.get("hunger_rating")),
        "energy_rating": _rating("energy_rating", raw.get("energy_rating")),
        "digestion_rating": _rating("digestion_rating", raw.get("digestion_rating")),
        "training_rating": _rating("training_rating", raw.get("training_rating")),
        "health_change": health_change,
        "health_change_notes": _text("health_change_notes", raw.get("health_change_notes"), 700),
        "foods_to_avoid": _text("foods_to_avoid", raw.get("foods_to_avoid"), 300),
        "foods_to_prioritize": _text("foods_to_prioritize", raw.get("foods_to_prioritize"), 300),
        "notes": _text("notes", raw.get("notes"), 1000),
    }
    if health_change and len(answers["health_change_notes"]) < 3:
        raise CheckinValidationError("Describe the health change before submitting")
    return answers


@dataclass(frozen=True)
class RevisionDecision:
    action: str
    kcal_delta: int
    reasons: tuple[str, ...]
    answer_patch: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "kcal_delta": self.kcal_delta,
            "reasons": list(self.reasons),
            "answer_patch": dict(self.answer_patch),
        }


def _merge_food_text(existing: Any, incoming: str) -> str:
    incoming = incoming.strip()
    if not incoming:
        return str(existing or "").strip()
    current = str(existing or "").strip()
    if not current:
        return incoming
    existing_parts = {part.strip().lower() for part in current.replace(";", ",").split(",") if part.strip()}
    if incoming.lower() in existing_parts:
        return current
    return f"{current}, {incoming}"


def decide_revision(
    *,
    baseline_answers: dict[str, Any],
    checkin_answers: dict[str, Any],
) -> RevisionDecision:
    """Conservative, deterministic revision suggestion.

    It never bypasses Coach review. Health changes always stop automation. Calorie
    deltas are limited to +/-100 kcal per weekly revision and protein/fat are not
    reduced by this policy; the generator applies the energy delta primarily to
    carbohydrate. Free-text food preferences are treated only as exact preference
    / exclusion phrases by the Phase 6 safety layer.
    """
    if bool(checkin_answers.get("health_change")):
        return RevisionDecision(
            action="HEALTH_REVIEW_REQUIRED",
            kcal_delta=0,
            reasons=("Client reported a health/medication/symptom change; automated revision is blocked.",),
            answer_patch={},
        )

    adherence = int(checkin_answers.get("adherence_percent") or 0)
    hunger = int(checkin_answers.get("hunger_rating") or 3)
    energy = int(checkin_answers.get("energy_rating") or 3)
    current = float(checkin_answers.get("current_weight_kg") or 0)
    baseline = float(baseline_answers.get("current_weight_kg") or current or 1)
    goal = str(baseline_answers.get("primary_goal") or "").upper()
    delta_pct = ((current - baseline) / max(baseline, 1.0)) * 100.0

    answer_patch: dict[str, Any] = {}
    avoid = str(checkin_answers.get("foods_to_avoid") or "").strip()
    prefer = str(checkin_answers.get("foods_to_prioritize") or "").strip()
    if avoid:
        answer_patch["disliked_foods_other"] = _merge_food_text(baseline_answers.get("disliked_foods_other"), avoid)
    if prefer:
        answer_patch["liked_foods_other"] = _merge_food_text(baseline_answers.get("liked_foods_other"), prefer)

    reasons: list[str] = []
    kcal_delta = 0

    if adherence < 70:
        reasons.append("Adherence is below 70%; calories are not changed from one low-adherence week.")
    elif goal == "FAT_LOSS":
        if delta_pct > -0.20:
            kcal_delta = -100
            reasons.append("High adherence with minimal weekly weight decrease: conservative -100 kcal suggestion.")
        elif delta_pct < -1.25 or energy <= 2 or hunger >= 5:
            kcal_delta = 100
            reasons.append("Weight fell quickly or recovery/hunger signal is poor: conservative +100 kcal suggestion.")
    elif goal == "MUSCLE_GAIN":
        if delta_pct < 0.10:
            kcal_delta = 100
            reasons.append("High adherence with minimal weekly weight increase: conservative +100 kcal suggestion.")
        elif delta_pct > 0.75:
            kcal_delta = -100
            reasons.append("Weekly weight increase is relatively fast: conservative -100 kcal suggestion.")
    elif goal == "MAINTAIN":
        if delta_pct > 0.75:
            kcal_delta = -100
            reasons.append("Weight drifted upward despite high adherence: conservative -100 kcal suggestion.")
        elif delta_pct < -0.75:
            kcal_delta = 100
            reasons.append("Weight drifted downward despite high adherence: conservative +100 kcal suggestion.")
    elif goal in {"RECOMPOSITION", "PERFORMANCE"}:
        if energy <= 2 and adherence >= 80:
            kcal_delta = 100
            reasons.append("Low energy with high adherence: conservative +100 kcal suggestion for Coach review.")

    if answer_patch:
        reasons.append("Client requested food preference changes; safe exact-phrase filters will be applied.")

    if kcal_delta or answer_patch:
        return RevisionDecision("QUEUE_REVISION", kcal_delta, tuple(reasons), answer_patch)

    if not reasons:
        reasons.append("No conservative plan change threshold was reached this week.")
    return RevisionDecision("NO_REVISION", 0, tuple(reasons), {})


def apply_revision_payload(
    *,
    answers: dict[str, Any],
    nutrition_profile: dict[str, Any],
    payload: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    payload = dict(payload or {})
    revision = payload.get("revision")
    if not isinstance(revision, dict):
        return dict(answers), dict(nutrition_profile), None

    merged_answers = dict(answers)
    patch = revision.get("answer_patch")
    if isinstance(patch, dict):
        for key in ("disliked_foods_other", "liked_foods_other"):
            if key in patch and isinstance(patch[key], str):
                merged_answers[key] = patch[key][:600]

    profile = dict(nutrition_profile)
    try:
        kcal_delta = int(revision.get("kcal_delta") or 0)
    except (TypeError, ValueError):
        kcal_delta = 0
    kcal_delta = max(-150, min(150, kcal_delta))
    if kcal_delta:
        target = float(profile.get("target_kcal") or 0)
        carbs = float(profile.get("carbs_g") or 0)
        if target > 0 and carbs > 0:
            new_target = max(1200.0, min(4500.0, target + kcal_delta))
            effective = new_target - target
            profile["target_kcal"] = round(new_target, 1)
            profile["carbs_g"] = round(max(40.0, carbs + effective / 4.0), 1)
            kcal_delta = int(round(effective))
        else:
            kcal_delta = 0

    context = {
        "checkin_id": revision.get("checkin_id"),
        "week_number": revision.get("week_number"),
        "kcal_delta": kcal_delta,
        "reasons": list(revision.get("reasons") or []),
        "current_weight_kg": revision.get("current_weight_kg"),
    }
    return merged_answers, profile, context
