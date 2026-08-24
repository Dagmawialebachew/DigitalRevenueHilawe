"""Verified fasting-calendar coverage and overlap policy."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Iterable


SEASONAL_PATTERNS = frozenset({"SEASONAL", "WED_FRI_AND_SEASONAL"})


class FastingCalendarCoverageRequired(ValueError):
    def __init__(self, missing_years: Iterable[int]):
        self.missing_years = tuple(sorted(set(int(year) for year in missing_years)))
        years = ", ".join(str(year) for year in self.missing_years)
        super().__init__(f"Verified seasonal fasting calendar coverage is missing for: {years}")


@dataclass(frozen=True)
class FastingSeasonOverlap:
    rule_id: str
    name: str
    start_date: date
    end_date: date
    overlap_start: date
    overlap_end: date
    overlap_days: int

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for key in ("start_date", "end_date", "overlap_start", "overlap_end"):
            value[key] = value[key].isoformat()
        return value


def seasonal_fasting_selected(pattern: Any) -> bool:
    return str(pattern or "NONE").upper() in SEASONAL_PATTERNS


def years_touched(start: date, end: date) -> tuple[int, ...]:
    if end < start:
        raise ValueError("Plan end date cannot be before its start date")
    return tuple(range(start.year, end.year + 1))


def missing_verified_years(start: date, end: date, coverage_rows: Iterable[Any]) -> tuple[int, ...]:
    verified = {
        int(row["calendar_year"])
        for row in coverage_rows
        if str(row["status"]) == "VERIFIED_COMPLETE"
    }
    return tuple(year for year in years_touched(start, end) if year not in verified)


def build_overlaps(start: date, end: date, rows: Iterable[Any]) -> tuple[FastingSeasonOverlap, ...]:
    overlaps: list[FastingSeasonOverlap] = []
    for row in rows:
        season_start = row["start_date"]
        season_end = row["end_date"]
        if not season_start or not season_end or season_start > end or season_end < start:
            continue
        overlap_start = max(start, season_start)
        overlap_end = min(end, season_end)
        overlaps.append(FastingSeasonOverlap(
            rule_id=str(row["rule_id"]),
            name=str(row["fast_name"]),
            start_date=season_start,
            end_date=season_end,
            overlap_start=overlap_start,
            overlap_end=overlap_end,
            overlap_days=(overlap_end - overlap_start).days + 1,
        ))
    return tuple(sorted(overlaps, key=lambda item: (item.start_date, item.rule_id)))
