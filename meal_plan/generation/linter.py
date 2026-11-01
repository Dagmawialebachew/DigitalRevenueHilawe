"""Pre-Flight Programmatic Meal Plan Linter (Pillar 2 Architecture)

Executes a 10-point rigorous audit on generated meal plans before PDF rendering,
database persistence, or Telegram review group handoff. Acts as an automated
"Coach Boss" catching macro defects, fasting contamination, formatting glitches,
and physical print budget overflows in sub-second execution time.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from meal_plan.generation.feedback_store import FeedbackStore, get_feedback_store
from meal_plan.generation.safety import ALLERGY_TERMS, DISLIKE_TERMS, profile_exclusion_terms


class LintSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class LintFinding:
    rule_id: str
    rule_name: str
    severity: LintSeverity
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class LintReport:
    score: float
    passed: bool
    findings: list[LintFinding]
    errors_count: int
    warnings_count: int
    rule_scores: dict[str, float]
    summary_markdown: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 2),
            "passed": self.passed,
            "errors_count": self.errors_count,
            "warnings_count": self.warnings_count,
            "rule_scores": {k: round(v, 2) for k, v in self.rule_scores.items()},
            "findings": [
                {
                    "rule_id": f.rule_id,
                    "rule_name": f.rule_name,
                    "severity": f.severity.value,
                    "message": f.message,
                    "details": f.details,
                }
                for f in self.findings
            ],
            "summary_markdown": self.summary_markdown,
        }


class MealPlanLinter:
    """10-Point Programmatic Pre-Flight Meal Plan Auditor."""

    def __init__(self, strict: bool = True, feedback_store: Optional[FeedbackStore] = None):
        self.strict = strict
        self.feedback_store = feedback_store or get_feedback_store()

    def lint_plan(
        self,
        plan: dict[str, Any],
        answers: dict[str, Any] | None = None,
        nutrition_profile: dict[str, Any] | None = None,
        pdf_path: str | Path | None = None,
    ) -> LintReport:
        answers = answers or plan.get("answers") or plan.get("client_profile") or {}
        nutrition_targets = (
            nutrition_profile
            or plan.get("nutrition_targets")
            or plan.get("nutrition_profile")
            or {}
        )
        core_week = plan.get("core_week") or []
        grocery = plan.get("grocery") or {}

        findings: list[LintFinding] = []
        rule_scores: dict[str, float] = {}

        # Run 10 Programmatic Audits
        rule_scores["RULE_1_CALORIE_BOUNDS"] = self._audit_calorie_bounds(core_week, nutrition_targets, answers, findings)
        rule_scores["RULE_2_PROTEIN_FLOORS"] = self._audit_protein_floors(core_week, nutrition_targets, answers, findings)
        rule_scores["RULE_3_ORTHODOX_FASTING"] = self._audit_orthodox_fasting(core_week, answers, findings)
        rule_scores["RULE_4_ALLERGIES_AND_DISLIKES"] = self._audit_allergies_and_dislikes(core_week, answers, findings)
        rule_scores["RULE_5_LEGUME_CARB_REALISM"] = self._audit_legume_carb_realism(core_week, findings)
        rule_scores["RULE_6_OIL_AND_FAT_BALANCE"] = self._audit_oil_and_fat_balance(core_week, findings)
        rule_scores["RULE_7_KITCHEN_ROUNDING"] = self._audit_kitchen_rounding(core_week, findings)
        rule_scores["RULE_8_HOUSEHOLD_MEASURES"] = self._audit_household_measures(core_week, findings)
        rule_scores["RULE_9_GROCERY_PROCUREMENT"] = self._audit_grocery_procurement(core_week, grocery, findings)
        rule_scores["RULE_10_PHYSICAL_PAGE_BUDGET"] = self._audit_physical_page_budget(plan, pdf_path, findings)

        errors_count = sum(1 for f in findings if f.severity == LintSeverity.ERROR)
        warnings_count = sum(1 for f in findings if f.severity == LintSeverity.WARNING)

        total_score = sum(rule_scores.values())
        overall_score = round(max(0.0, min(10.0, total_score)), 1)
        passed = (errors_count == 0) and (overall_score >= (9.5 if self.strict else 9.0))

        summary_md = self._build_summary_markdown(overall_score, passed, errors_count, warnings_count, rule_scores, findings)

        return LintReport(
            score=overall_score,
            passed=passed,
            findings=findings,
            errors_count=errors_count,
            warnings_count=warnings_count,
            rule_scores=rule_scores,
            summary_markdown=summary_md,
        )

    # -------------------------------------------------------------------------
    # RULE 1: CALORIE BOUNDS
    # -------------------------------------------------------------------------
    def _audit_calorie_bounds(
        self,
        core_week: list[dict[str, Any]],
        targets: dict[str, Any],
        answers: dict[str, Any],
        findings: list[LintFinding],
    ) -> float:
        score = 1.0
        target_kcal = float(targets.get("target_kcal") or targets.get("kcal") or 0.0)
        if target_kcal <= 0:
            findings.append(LintFinding("RULE_1", "Calorie Bounds", LintSeverity.ERROR, "Missing target_kcal in nutrition profile"))
            return 0.0

        is_hardgainer = target_kcal >= 2800.0
        week_kcals = []

        for day in core_week:
            day_name = day.get("day_name", "Unknown Day")
            kcal = float(day.get("totals", {}).get("kcal", 0.0))
            week_kcals.append(kcal)

            if is_hardgainer:
                if kcal < 2980.0 or kcal > 3085.0:
                    findings.append(LintFinding(
                        "RULE_1", "Calorie Bounds", LintSeverity.ERROR,
                        f"{day_name} calories {kcal:.1f} kcal outside strict hardgainer bounds [2,980, 3,085] kcal",
                        {"day": day_name, "kcal": kcal, "expected": "[2980, 3085]"}
                    ))
                    score = max(0.0, score - 0.3)
            else:
                lower = target_kcal * 0.94
                upper = target_kcal * 1.06
                soft_lower = target_kcal * 0.96
                soft_upper = target_kcal * 1.04

                if kcal < lower or kcal > upper:
                    findings.append(LintFinding(
                        "RULE_1", "Calorie Bounds", LintSeverity.ERROR,
                        f"{day_name} calories {kcal:.1f} kcal outside safe tolerance bounds [{lower:.0f}, {upper:.0f}] kcal",
                        {"day": day_name, "kcal": kcal, "target": target_kcal}
                    ))
                    score = max(0.0, score - 0.3)
                elif kcal < soft_lower or kcal > soft_upper:
                    findings.append(LintFinding(
                        "RULE_1", "Calorie Bounds", LintSeverity.WARNING,
                        f"{day_name} calories {kcal:.1f} kcal deviates slightly from target {target_kcal:.0f} kcal",
                        {"day": day_name, "kcal": kcal, "target": target_kcal}
                    ))
                    score = max(0.0, score - 0.05)

        if week_kcals:
            avg_kcal = sum(week_kcals) / len(week_kcals)
            diff_pct = abs(avg_kcal - target_kcal) / target_kcal
            if diff_pct > 0.04:
                findings.append(LintFinding(
                    "RULE_1", "Calorie Bounds", LintSeverity.WARNING,
                    f"Weekly average calories {avg_kcal:.1f} kcal deviates by {diff_pct*100:.1f}% from target {target_kcal:.0f} kcal",
                    {"average_kcal": avg_kcal, "target": target_kcal}
                ))
                score = max(0.0, score - 0.1)

        return max(0.0, round(score, 2))

    # -------------------------------------------------------------------------
    # RULE 2: PROTEIN FLOORS
    # -------------------------------------------------------------------------
    def _audit_protein_floors(
        self,
        core_week: list[dict[str, Any]],
        targets: dict[str, Any],
        answers: dict[str, Any],
        findings: list[LintFinding],
    ) -> float:
        score = 1.0
        target_p = float(targets.get("protein_g") or targets.get("protein") or 0.0)
        target_kcal = float(targets.get("target_kcal") or targets.get("kcal") or 0.0)
        if target_p <= 0:
            findings.append(LintFinding("RULE_2", "Protein Floors", LintSeverity.ERROR, "Missing target protein_g in targets"))
            return 0.0

        is_hardgainer = target_kcal >= 2800.0
        fasting_floor = 135.0 if is_hardgainer else max(target_p * 0.78, 90.0)
        regular_floor = 138.0 if is_hardgainer else max(target_p * 0.84, 100.0)

        for day in core_week:
            day_name = day.get("day_name", "Unknown Day")
            fasting = bool(day.get("fasting", False))
            p_val = float(day.get("totals", {}).get("protein", 0.0))
            required_floor = fasting_floor if fasting else regular_floor

            if p_val < required_floor:
                findings.append(LintFinding(
                    "RULE_2", "Protein Floors", LintSeverity.ERROR,
                    f"{day_name} ({'Fasting' if fasting else 'Regular'}) protein {p_val:.1f}g below minimum floor {required_floor:.1f}g (Target: {target_p:.0f}g)",
                    {"day": day_name, "fasting": fasting, "protein": p_val, "required_floor": required_floor}
                ))
                score = max(0.0, score - 0.3)
            elif not fasting and p_val < target_p * 0.90:
                findings.append(LintFinding(
                    "RULE_2", "Protein Floors", LintSeverity.WARNING,
                    f"{day_name} protein {p_val:.1f}g is slightly below 90% of target {target_p:.0f}g",
                    {"day": day_name, "protein": p_val, "target": target_p}
                ))
                score = max(0.0, score - 0.05)
            elif fasting and p_val < target_p * 0.80:
                findings.append(LintFinding(
                    "RULE_2", "Protein Floors", LintSeverity.WARNING,
                    f"{day_name} (Fasting) protein {p_val:.1f}g is slightly below 80% of target {target_p:.0f}g",
                    {"day": day_name, "protein": p_val, "target": target_p}
                ))
                score = max(0.0, score - 0.05)

        return max(0.0, round(score, 2))

    # -------------------------------------------------------------------------
    # RULE 3: ORTHODOX FASTING STRICTNESS
    # -------------------------------------------------------------------------
    def _audit_orthodox_fasting(
        self,
        core_week: list[dict[str, Any]],
        answers: dict[str, Any],
        findings: list[LintFinding],
    ) -> float:
        score = 1.0
        fish_allowed = bool(answers.get("fish_during_fast", False))
        
        meat_dairy_tokens = {
            "beef", "chicken", "meat", "poultry", "doro", "minchet", "key wot", "tibs",
            "egg", "eggs", "boiled egg", "egg white", "omelet",
            "milk", "cow milk", "cheese", "ayib", "butter", "niter kibbeh", "whey", "yogurt"
        }
        fish_tokens = {"fish", "tilapia", "tuna", "salmon", "sardine"}

        for day in core_week:
            day_name = day.get("day_name", "Unknown Day")
            fasting = bool(day.get("fasting", False))
            if not fasting:
                continue

            for meal in day.get("meals", []):
                slot = meal.get("slot", "Meal")
                for item in meal.get("items", []):
                    food_id = str(item.get("food_id") or "")
                    recipe_id = str(item.get("recipe_id") or "")
                    name = str(item.get("food_name") or "").lower()

                    # Animal food IDs
                    if food_id.startswith("A") and food_id not in ("A015", "A017", "A018"):
                        findings.append(LintFinding(
                            "RULE_3", "Orthodox Fasting Strictness", LintSeverity.ERROR,
                            f"Animal product '{item.get('food_name')}' ({food_id}) present on fasting day {day_name} in {slot}",
                            {"day": day_name, "slot": slot, "food_id": food_id, "name": item.get("food_name")}
                        ))
                        score = max(0.0, score - 0.4)
                    elif any(tok in name for tok in meat_dairy_tokens):
                        # Verify it's not soy meat, plant milk, or peanut butter
                        if "soy" not in name and "plant" not in name and "peanut" not in name and "tofu" not in name:
                            findings.append(LintFinding(
                                "RULE_3", "Orthodox Fasting Strictness", LintSeverity.ERROR,
                                f"Forbidden animal product '{item.get('food_name')}' found on fasting {day_name} in {slot}",
                                {"day": day_name, "slot": slot, "item": item.get("food_name")}
                            ))
                            score = max(0.0, score - 0.4)

                    # Fish check
                    if not fish_allowed and any(ft in name for ft in fish_tokens):
                        findings.append(LintFinding(
                            "RULE_3", "Orthodox Fasting Strictness", LintSeverity.ERROR,
                            f"Fish item '{item.get('food_name')}' present on fasting {day_name} when fish_during_fast=False",
                            {"day": day_name, "slot": slot, "item": item.get("food_name")}
                        ))
                        score = max(0.0, score - 0.3)

        return max(0.0, round(score, 2))

    # -------------------------------------------------------------------------
    # RULE 4: ALLERGIES AND DISLIKES
    # -------------------------------------------------------------------------
    def _audit_allergies_and_dislikes(
        self,
        core_week: list[dict[str, Any]],
        answers: dict[str, Any],
        findings: list[LintFinding],
    ) -> float:
        score = 1.0
        exclusions = profile_exclusion_terms(answers)

        for day in core_week:
            day_name = day.get("day_name", "Unknown Day")
            for meal in day.get("meals", []):
                slot = meal.get("slot", "Meal")
                for item in meal.get("items", []):
                    name = str(item.get("food_name") or "").lower()
                    for prefix_key, terms in exclusions:
                        is_allergy = prefix_key.startswith("allergy") or prefix_key.startswith("intolerance")
                        matched = [t for t in terms if t.lower() in name]
                        if matched:
                            sev = LintSeverity.ERROR if is_allergy else LintSeverity.WARNING
                            findings.append(LintFinding(
                                "RULE_4", "Allergies & Dislikes", sev,
                                f"Item '{item.get('food_name')}' violates {prefix_key} (matched term: '{matched[0]}') in {day_name} {slot}",
                                {"day": day_name, "slot": slot, "item": item.get("food_name"), "matched": matched}
                            ))
                            score = max(0.0, score - (0.5 if is_allergy else 0.1))

        return max(0.0, round(score, 2))

    # -------------------------------------------------------------------------
    # RULE 5: LEGUME AND CARB REALISM
    # -------------------------------------------------------------------------
    def _audit_legume_carb_realism(
        self,
        core_week: list[dict[str, Any]],
        findings: list[LintFinding],
    ) -> float:
        score = 1.0
        forbidden_rules = self.feedback_store.get_forbidden_pairings() if hasattr(self, "feedback_store") else []
        portion_caps = self.feedback_store.get_portion_caps() if hasattr(self, "feedback_store") else {"C020": 40.0}
        legume_stew_rids = {"R001", "R002", "R003"}  # Kik, Misir, Shiro baseline

        for day in core_week:
            day_name = day.get("day_name", "Unknown Day")
            for meal in day.get("meals", []):
                slot = meal.get("slot", "Meal")
                items = meal.get("items", [])
                active_ids = {it.get("recipe_id") for it in items if it.get("recipe_id")} | {it.get("food_id") for it in items if it.get("food_id")}

                # 1. Dynamic pairing exclusion checks from Feedback Catalog
                for rule in forbidden_rules:
                    if rule["primary_ids"].intersection(active_ids):
                        bad_items = [it for it in items if it.get("food_id") in rule["forbidden_secondary_ids"] or it.get("recipe_id") in rule["forbidden_secondary_ids"]]
                        for bi in bad_items:
                            sev = LintSeverity.ERROR if rule.get("severity") == "ERROR" else LintSeverity.WARNING
                            findings.append(LintFinding(
                                "RULE_5", "Legume & Carb Realism", sev,
                                f"Forbidden pairing '{bi.get('food_name')}' stacked on composite stew ({rule.get('name')}) in {day_name} {slot}",
                                {"day": day_name, "slot": slot, "item": bi.get("food_name"), "rule_id": rule.get("rule_id")}
                            ))
                            score = max(0.0, score - 0.25)

                # Fallback baseline check for composite legume stews
                if not forbidden_rules:
                    has_legume_stew = any(it.get("recipe_id") in legume_stew_rids for it in items)
                    loose_legumes = [it for it in items if it.get("food_id") in ("P001", "P007")]
                    if has_legume_stew and loose_legumes:
                        for ll in loose_legumes:
                            findings.append(LintFinding(
                                "RULE_5", "Legume & Carb Realism", LintSeverity.ERROR,
                                f"Duplicate loose legume '{ll.get('food_name')}' stacked on composite stew in {day_name} {slot}",
                                {"day": day_name, "slot": slot, "loose_legume": ll.get("food_name")}
                            ))
                            score = max(0.0, score - 0.25)

                # 2. Dynamic portion caps checks from Feedback Catalog
                for it in items:
                    fid = it.get("food_id")
                    if fid in portion_caps:
                        g = float(it.get("grams") or 0.0)
                        max_g = portion_caps[fid]
                        if g > max_g:
                            findings.append(LintFinding(
                                "RULE_5", "Legume & Carb Realism", LintSeverity.ERROR,
                                f"Portion for '{it.get('food_name')}' ({g:.0f}g) exceeds safety cap of {max_g:.0f}g in {day_name} {slot}",
                                {"day": day_name, "slot": slot, "food_id": fid, "grams": g, "cap": max_g}
                            ))
                            score = max(0.0, score - 0.3)

        return max(0.0, round(score, 2))

    # -------------------------------------------------------------------------
    # RULE 6: OIL AND FAT REALISM
    # -------------------------------------------------------------------------
    def _audit_oil_and_fat_balance(
        self,
        core_week: list[dict[str, Any]],
        findings: list[LintFinding],
    ) -> float:
        score = 1.0
        already_oiled_stews = {"R007", "R008", "R020", "R023"}  # Key Wot, Minchet Abish

        for day in core_week:
            day_name = day.get("day_name", "Unknown Day")
            for meal in day.get("meals", []):
                slot = meal.get("slot", "Meal")
                items = meal.get("items", [])

                has_oiled_stew = any(it.get("recipe_id") in already_oiled_stews for it in items)
                oil_items = [it for it in items if it.get("food_id") in ("T001", "T002")]

                if has_oiled_stew and oil_items:
                    for oi in oil_items:
                        findings.append(LintFinding(
                            "RULE_6", "Oil & Fat Balance", LintSeverity.WARNING,
                            f"Stray cooking oil ({oi.get('grams')}g) added to naturally oil-rich stew in {day_name} {slot}",
                            {"day": day_name, "slot": slot, "oil_grams": oi.get("grams")}
                        ))
                        score = max(0.0, score - 0.1)

                # Breakfast oil check
                if meal.get("source_slot") == "Breakfast" and oil_items:
                    for oi in oil_items:
                        if float(oi.get("grams") or 0.0) > 15.0:
                            findings.append(LintFinding(
                                "RULE_6", "Oil & Fat Balance", LintSeverity.WARNING,
                                f"Heavy oil portion ({oi.get('grams')}g) in breakfast on {day_name}",
                                {"day": day_name, "grams": oi.get("grams")}
                            ))
                            score = max(0.0, score - 0.1)

        return max(0.0, round(score, 2))

    # -------------------------------------------------------------------------
    # RULE 7: KITCHEN ROUNDING STANDARDS
    # -------------------------------------------------------------------------
    def _audit_kitchen_rounding(
        self,
        core_week: list[dict[str, Any]],
        findings: list[LintFinding],
    ) -> float:
        score = 1.0
        allowed_injera = {60.0, 120.0, 180.0, 240.0}

        for day in core_week:
            day_name = day.get("day_name", "Unknown Day")
            for meal in day.get("meals", []):
                slot = meal.get("slot", "Meal")
                for it in meal.get("items", []):
                    fid = str(it.get("food_id") or "")
                    g = float(it.get("grams") or 0.0)

                    # Injera 60g increments check
                    if fid == "C001":
                        if round(g, 1) not in allowed_injera:
                            findings.append(LintFinding(
                                "RULE_7", "Kitchen Rounding", LintSeverity.ERROR,
                                f"Injera portion {g:.1f}g on {day_name} {slot} is not a clean multiple of 60g (must be 60g, 120g, 180g, or 240g)",
                                {"day": day_name, "slot": slot, "grams": g}
                            ))
                            score = max(0.0, score - 0.25)

                    # Decimal check on solid food
                    if fid not in ("T001", "T002") and not fid.startswith("V"):
                        if abs(g - round(g)) > 0.01:
                            findings.append(LintFinding(
                                "RULE_7", "Kitchen Rounding", LintSeverity.WARNING,
                                f"Unrounded continuous decimal {g:.2f}g for '{it.get('food_name')}' on {day_name} {slot}",
                                {"day": day_name, "slot": slot, "food": it.get("food_name"), "grams": g}
                            ))
                            score = max(0.0, score - 0.05)

        return max(0.0, round(score, 2))

    # -------------------------------------------------------------------------
    # RULE 8: HOUSEHOLD MEASURES & TYPOGRAPHY
    # -------------------------------------------------------------------------
    def _audit_household_measures(
        self,
        core_week: list[dict[str, Any]],
        findings: list[LintFinding],
    ) -> float:
        score = 1.0

        for day in core_week:
            day_name = day.get("day_name", "Unknown Day")
            for meal in day.get("meals", []):
                slot = meal.get("slot", "Meal")
                for it in meal.get("items", []):
                    fam = str(it.get("familiar") or "")
                    name = str(it.get("food_name") or "")

                    # Double parentheses check
                    if "((" in fam or "))" in fam or "((" in name or "))" in name:
                        findings.append(LintFinding(
                            "RULE_8", "Household Measures & Typography", LintSeverity.ERROR,
                            f"Double nested parentheses found in '{name}': '{fam}' on {day_name} {slot}",
                            {"day": day_name, "slot": slot, "item": name, "familiar": fam}
                        ))
                        score = max(0.0, score - 0.3)
                    elif re.search(r"\(.*\(.*\).*\)", fam) or re.search(r"\(.*\(.*\).*\)", name):
                        findings.append(LintFinding(
                            "RULE_8", "Household Measures & Typography", LintSeverity.ERROR,
                            f"Nested parentheses found in '{name}': '{fam}' on {day_name} {slot}",
                            {"day": day_name, "slot": slot, "item": name, "familiar": fam}
                        ))
                        score = max(0.0, score - 0.3)

                    # Empty familiar measure check
                    if not fam.strip():
                        findings.append(LintFinding(
                            "RULE_8", "Household Measures & Typography", LintSeverity.WARNING,
                            f"Missing household familiar measure for '{name}' on {day_name} {slot}",
                            {"day": day_name, "slot": slot, "item": name}
                        ))
                        score = max(0.0, score - 0.05)

        return max(0.0, round(score, 2))

    # -------------------------------------------------------------------------
    # RULE 9: GROCERY PROCUREMENT CONSISTENCY
    # -------------------------------------------------------------------------
    def _audit_grocery_procurement(
        self,
        core_week: list[dict[str, Any]],
        grocery: Any,
        findings: list[LintFinding],
    ) -> float:
        score = 1.0
        items_list: list[dict[str, Any]] = []
        if isinstance(grocery, list):
            items_list = grocery
        elif isinstance(grocery, dict):
            if "items" in grocery and isinstance(grocery["items"], list):
                items_list = grocery["items"]
            else:
                for cat in grocery.get("categories") or grocery.get("aisles") or []:
                    items_list.extend(cat.get("items", []))

        if not items_list:
            findings.append(LintFinding(
                "RULE_9", "Grocery Procurement", LintSeverity.ERROR,
                "Weekly grocery shopping list is empty",
            ))
            return 0.0

        # Tally planned Injera vs Grocery Injera
        total_injera_planned = 0.0
        for day in core_week:
            for m in day.get("meals", []):
                for it in m.get("items", []):
                    if it.get("food_id") == "C001":
                        total_injera_planned += float(it.get("grams") or 0.0)
                    elif it.get("recipe_id") in ("R008", "R021"):
                        # Firfir recipe uses 1/3 prepared injera by weight (approx 60g in standard 180g portion)
                        total_injera_planned += round(float(it.get("grams") or 0.0) / 3.0 / 10.0) * 10.0

        grocery_injera_grams = 0.0
        for item in items_list:
            fid = str(item.get("food_id") or "")
            name = str(item.get("buy_item") or item.get("food_name") or "").lower()
            if fid == "C001" or "injera" in name:
                grocery_injera_grams += float(item.get("planned_grams") or item.get("total_grams") or item.get("grams") or 0.0)

        if total_injera_planned > 0 and grocery_injera_grams > 0:
            if abs(total_injera_planned - grocery_injera_grams) > 1.0:
                findings.append(LintFinding(
                    "RULE_9", "Grocery Procurement", LintSeverity.ERROR,
                    f"Injera weekly grocery mismatch: planned {total_injera_planned:.0f}g vs grocery {grocery_injera_grams:.0f}g",
                    {"planned": total_injera_planned, "grocery": grocery_injera_grams}
                ))
                score = max(0.0, score - 0.3)

        return max(0.0, round(score, 2))

    # -------------------------------------------------------------------------
    # RULE 10: PHYSICAL 15-PAGE BUDGET
    # -------------------------------------------------------------------------
    def _audit_physical_page_budget(
        self,
        plan: dict[str, Any],
        pdf_path: str | Path | None,
        findings: list[LintFinding],
    ) -> float:
        score = 1.0

        # If PDF path is provided and exists, verify exact physical page count
        if pdf_path:
            p = Path(pdf_path)
            if p.exists() and p.suffix.lower() == ".pdf":
                try:
                    import pypdf
                    reader = pypdf.PdfReader(str(p))
                    num_pages = len(reader.pages)
                    if num_pages != 15:
                        findings.append(LintFinding(
                            "RULE_10", "15-Page Budget", LintSeverity.ERROR,
                            f"Rendered physical PDF has {num_pages} pages; certified client standard requires EXACTLY 15 pages",
                            {"expected": 15, "actual": num_pages, "path": str(p)}
                        ))
                        return 0.0
                except ImportError:
                    pass

        # Verify core week structure satisfies 15-page layout
        core_week = plan.get("core_week") or []
        if len(core_week) != 7:
            findings.append(LintFinding(
                "RULE_10", "15-Page Budget", LintSeverity.ERROR,
                f"Core week contains {len(core_week)} days; requires exactly 7 days (Pages 4-10)",
                {"days": len(core_week)}
            ))
            score = max(0.0, score - 0.5)

        return max(0.0, round(score, 2))

    # -------------------------------------------------------------------------
    # SUMMARY MARKDOWN BUILDER
    # -------------------------------------------------------------------------
    def _build_summary_markdown(
        self,
        score: float,
        passed: bool,
        errors_count: int,
        warnings_count: int,
        rule_scores: dict[str, float],
        findings: list[LintFinding],
    ) -> str:
        status_icon = "✅ PASSED" if passed else "❌ FAILED"
        lines = [
            f"### 🛡️ Pre-Flight Meal Plan Audit Report: {score:.1f} / 10.0 · {status_icon}",
            f"- **Critical Errors:** {errors_count}",
            f"- **Practical Warnings:** {warnings_count}",
            "",
            "| Rule ID | Category | Score | Status |",
            "| --- | --- | --- | --- |",
        ]
        
        rule_titles = {
            "RULE_1_CALORIE_BOUNDS": "Calorie Bounds & Daily Macro Alignment",
            "RULE_2_PROTEIN_FLOORS": "Protein Floors & Muscle Preservation",
            "RULE_3_ORTHODOX_FASTING": "Orthodox Fasting Canonical Purity",
            "RULE_4_ALLERGIES_AND_DISLIKES": "Medical Safety & Allergen Exclusions",
            "RULE_5_LEGUME_CARB_REALISM": "Legume Stacking & Carbohydrate Realism",
            "RULE_6_OIL_AND_FAT_BALANCE": "Cooking Oil & Added Fat Balance",
            "RULE_7_KITCHEN_ROUNDING": "Kitchen Gram Rounding & Injera Increments",
            "RULE_8_HOUSEHOLD_MEASURES": "Household Measures & Nested Typography",
            "RULE_9_GROCERY_PROCUREMENT": "Grocery Aisles & Retail Packaging Sums",
            "RULE_10_PHYSICAL_PAGE_BUDGET": "Physical 15-Page Print Budget",
        }

        for r_id, r_score in rule_scores.items():
            title = rule_titles.get(r_id, r_id)
            icon = "✅" if r_score >= 0.95 else ("⚠️" if r_score >= 0.70 else "❌")
            lines.append(f"| `{r_id}` | {title} | `{r_score:.2f} / 1.0` | {icon} |")

        if findings:
            lines.append("")
            lines.append("#### 📋 Findings & Diagnostics:")
            for f in findings:
                icon = "❌" if f.severity == LintSeverity.ERROR else ("⚠️" if f.severity == LintSeverity.WARNING else "ℹ️")
                lines.append(f"- {icon} **[{f.rule_id} · {f.severity.value}]** {f.message}")

        return "\n".join(lines)
