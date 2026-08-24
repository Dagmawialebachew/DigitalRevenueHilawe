"""Coach Hilawe v1.3 ten-question nutrition safety gate.

The supplied Meal Planner OS defines exactly ten Yes/No safety checks. Any Yes
routes the client to Medical/Qualified Review; all No is Routine. This module
keeps that rule deterministic and separate from UI wording.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HealthFlag:
    code: str
    source_field: str
    label_en: str
    label_am: str


@dataclass(frozen=True)
class HealthGateResult:
    category: str
    flags: tuple[HealthFlag, ...]

    @property
    def requires_review(self) -> bool:
        return self.category == "MEDICAL_QUALIFIED_REVIEW"

    def codes(self) -> list[str]:
        return [flag.code for flag in self.flags]


# Mirrors the ten columns B:K in the v1.3 Health Gate sheet.
HEALTH_FLAGS: tuple[HealthFlag, ...] = (
    HealthFlag("UNDER_18", "age", "Under 18", "ዕድሜ ከ18 ዓመት በታች"),
    HealthFlag(
        "PREGNANCY_POSTPARTUM_LACTATING",
        "health_pregnancy_postpartum_lactating",
        "Pregnant / postpartum / lactating",
        "እርግዝና / ከወሊድ በኋላ / ጡት ማጥባት",
    ),
    HealthFlag("EATING_DISORDER_CONCERN", "health_eating_disorder_concern", "Eating-disorder concern", "የአመጋገብ ችግኝ ጥርጣሬ"),
    HealthFlag("KIDNEY_LIVER_DISEASE", "health_kidney_liver_disease", "Kidney / liver disease", "የኩላሊት / ጉበት በሽታ"),
    HealthFlag(
        "DIABETES_GLUCOSE_MEDICATION",
        "health_diabetes_or_glucose_medication",
        "Diabetes / glucose medication",
        "የስኳር በሽታ / የደም ስኳር መድሀኒት",
    ),
    HealthFlag("CLINICIAN_PRESCRIBED_DIET", "health_clinician_prescribed_diet", "Clinician-prescribed diet", "በሐኪም የታዘዘ የምግብ እቅድ"),
    HealthFlag("SEVERE_GI_CONDITION", "health_severe_gi_condition", "Severe GI symptoms / disease", "ከባድ የሆድ/አንጀት ምልክት ወይም በሽታ"),
    HealthFlag(
        "ANAPHYLACTIC_FOOD_ALLERGY",
        "health_anaphylactic_food_allergy",
        "Anaphylactic food allergy",
        "ከባድ አናፊላክሲስ የምግብ አለርጂ",
    ),
    HealthFlag("UNEXPLAINED_WEIGHT_CHANGE", "health_unexplained_weight_change", "Unexplained weight change", "ምክንያቱ ያልታወቀ የክብደት ለውጥ"),
    HealthFlag("OTHER_HEALTH_CHANGE", "health_other_important_change", "Other important health change", "ሌላ አስፈላጊ የጤና ለውጥ"),
)


def evaluate_health_gate(answers: dict[str, Any]) -> HealthGateResult:
    """Evaluate the exact Hilawe ten-question gate after Phase 3 completeness.

    Age derives the original workbook's ``Under 18`` Yes/No field. Every other
    flag maps directly to the questionnaire boolean. Missing booleans are an
    error here rather than silently treated as No.
    """
    try:
        age = int(answers["age"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Health gate requires a valid age") from exc

    triggered: list[HealthFlag] = []
    for flag in HEALTH_FLAGS:
        if flag.code == "UNDER_18":
            if age < 18:
                triggered.append(flag)
            continue
        if flag.source_field not in answers:
            raise ValueError(f"Health gate answer missing: {flag.source_field}")
        value = answers[flag.source_field]
        if not isinstance(value, bool):
            raise ValueError(f"Health gate answer must be Yes/No: {flag.source_field}")
        if value:
            triggered.append(flag)

    return HealthGateResult(
        category="MEDICAL_QUALIFIED_REVIEW" if triggered else "ROUTINE",
        flags=tuple(triggered),
    )


def localized_flag_labels(result: HealthGateResult, language: str) -> list[str]:
    use_am = str(language).upper() == "AM"
    return [flag.label_am if use_am else flag.label_en for flag in result.flags]
