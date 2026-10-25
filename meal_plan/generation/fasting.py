from __future__ import annotations

from datetime import date
from typing import Any


class FastingCalendarRequired(ValueError):
    pass


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _verified_ranges(rows: tuple[dict[str, Any], ...], *, include_tsige: bool = False) -> list[tuple[date, date]]:
    result: list[tuple[date, date]] = []
    for row in rows:
        status = str(row.get("Verification Status") or row.get("verification_status") or "")
        if status != "Ready" and "VERIFIED" not in status.upper():
            continue
        rule_id = str(row.get("Rule ID") or row.get("rule_id") or "").upper()
        fast_name = str(row.get("Fast Name") or row.get("fast_name") or "").upper()
        if not include_tsige and ("TSIGE" in rule_id or "TSIGE" in fast_name or "ጽጌ" in fast_name):
            continue
        start = _parse_date(row.get("Start Date") or row.get("start_date"))
        end = _parse_date(row.get("End Date") or row.get("end_date"))
        if start and end:
            result.append((start, end))
    return result


def check_orthodox_fasting_season(date_obj: date, ranges: list[tuple[date, date]] | None = None) -> bool:
    """Check if date falls within a verified canonical Ethiopian Orthodox seasonal fast."""
    if ranges:
        if any(start <= date_obj <= end for start, end in ranges):
            return True

    month, day = date_obj.month, date_obj.day
    # Tsome Nebiyat (Advent): Nov 24/25 - Jan 6
    if (month == 11 and day >= 24) or (month == 12) or (month == 1 and day <= 6):
        return True
    # Tsome Filseta (Assumption): Aug 7 - Aug 22
    if month == 8 and 7 <= day <= 22:
        return True
    # Gahad of Timket: Jan 18
    if month == 1 and day == 18:
        return True
    return False


def is_day_fasting(date_obj: date, fasting_preference: str, ranges: list[tuple[date, date]] | None = None) -> bool:
    pref = str(fasting_preference or "NONE").upper().strip()
    if pref in ("NONE", "አይጾምም", ""):
        return False
    if pref in ("STRICT_LENT", "LENT", "ALWAYS"):
        return True

    # Wednesday (weekday == 2) and Friday (weekday == 4)
    is_wed_or_fri = date_obj.weekday() in (2, 4)
    if pref == "WED_FRI":
        return is_wed_or_fri

    if "SEASONAL" in pref or "WED_FRI_AND_SEASONAL" in pref:
        is_in_season = check_orthodox_fasting_season(date_obj, ranges)
        return is_wed_or_fri or is_in_season

    if "TSIGE" in pref or "ጽጌ" in pref:
        if ranges and any(start <= date_obj <= end for start, end in ranges):
            return True
        if (date_obj.month == 10 and date_obj.day >= 6) or (date_obj.month == 11 and date_obj.day <= 14):
            return True
        return is_wed_or_fri

    return False


def fasting_days_for_week(
    start_date: date,
    pattern: str,
    calendar_rows: tuple[dict[str, Any], ...],
) -> tuple[bool, ...]:
    return fasting_days_for_period(start_date, 7, pattern, calendar_rows)


def fasting_days_for_period(
    start_date: date,
    duration_days: int,
    pattern: str,
    calendar_rows: tuple[dict[str, Any], ...],
    *,
    verified_years: tuple[int, ...] | list[int] | None = None,
) -> tuple[bool, ...]:
    from datetime import timedelta

    if duration_days < 1:
        raise ValueError("Fasting period duration must be positive")
    normalized = str(pattern or "NONE").upper().strip()
    if normalized in {"LENT", "STRICT_LENT", "ALL_FASTING", "ALWAYS"}:
        return (True,) * duration_days
    if normalized in {"NONE", "አይጾምም", ""}:
        return (False,) * duration_days

    include_tsige = "TSIGE" in normalized or "ጽጌ" in normalized
    seasonal = "SEASONAL" in normalized or normalized in {"LENT", "FASTING"}
    ranges = _verified_ranges(calendar_rows, include_tsige=include_tsige)
    end_date = start_date + timedelta(days=duration_days - 1)
    if seasonal and verified_years is not None:
        required = set(range(start_date.year, end_date.year + 1))
        missing = sorted(required.difference(int(year) for year in verified_years))
        if missing:
            raise FastingCalendarRequired(
                "Seasonal Orthodox fasting calendar coverage is not verified for: "
                + ", ".join(str(year) for year in missing)
            )
    if seasonal and not ranges and not calendar_rows:
        raise FastingCalendarRequired(
            "Seasonal Orthodox fasting was selected, but the supplied Hilawe dataset has no verified annual dates. "
            "Add verified dates before generation; the engine will not guess them."
        )

    output: list[bool] = []
    for offset in range(duration_days):
        current = start_date + timedelta(days=offset)
        output.append(is_day_fasting(current, normalized, ranges))
    return tuple(output)

