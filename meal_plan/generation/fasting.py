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


def _verified_ranges(rows: tuple[dict[str, Any], ...]) -> list[tuple[date, date]]:
    result: list[tuple[date, date]] = []
    for row in rows:
        status = str(row.get("Verification Status") or "")
        if status != "Ready" and "VERIFIED" not in status.upper():
            continue
        start = _parse_date(row.get("Start Date"))
        end = _parse_date(row.get("End Date"))
        if start and end:
            result.append((start, end))
    return result


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
    normalized = str(pattern or "NONE").upper()
    seasonal = normalized in {"SEASONAL", "WED_FRI_AND_SEASONAL"}
    ranges = _verified_ranges(calendar_rows)
    end_date = start_date + timedelta(days=duration_days - 1)
    if seasonal and verified_years is not None:
        required = set(range(start_date.year, end_date.year + 1))
        missing = sorted(required.difference(int(year) for year in verified_years))
        if missing:
            raise FastingCalendarRequired(
                "Seasonal Orthodox fasting calendar coverage is not verified for: "
                + ", ".join(str(year) for year in missing)
            )
    if seasonal and not ranges:
        raise FastingCalendarRequired(
            "Seasonal Orthodox fasting was selected, but the supplied Hilawe dataset has no verified annual dates. "
            "Add verified dates before generation; the engine will not guess them."
        )

    output: list[bool] = []
    for offset in range(duration_days):
        current = start_date + timedelta(days=offset)
        weekly = normalized in {"WED_FRI", "WED_FRI_AND_SEASONAL"} and current.weekday() in {2, 4}
        annual = seasonal and any(a <= current <= b for a, b in ranges)
        output.append(bool(weekly or annual))
    return tuple(output)
