"""Country/region vocabulary shared by Telegram entry and Mini App fallback."""

from __future__ import annotations

from meal_plan.constants import PRICING_REGIONS

COUNTRY_LABELS = {
    "ETHIOPIA": {"AM": "🇪🇹 ኢትዮጵያ", "EN": "🇪🇹 Ethiopia"},
    "UNITED_STATES": {"AM": "🇺🇸 ዩናይትድ ስቴትስ", "EN": "🇺🇸 United States"},
    "EUROPE": {"AM": "🇪🇺 አውሮፓ", "EN": "🇪🇺 Europe"},
    "UAE": {"AM": "🇦🇪 ዱባይ / UAE", "EN": "🇦🇪 Dubai / UAE"},
    "OTHER": {"AM": "🌍 ሌላ አገር", "EN": "🌍 Other"},
}


def normalize_region(value: str) -> str:
    region = (value or "").strip().upper()
    if region not in PRICING_REGIONS:
        raise ValueError("Unsupported country region")
    return region


def country_label(region: str, language: str, country_name: str | None = None) -> str:
    region = normalize_region(region)
    lang = language if language in {"AM", "EN"} else "AM"
    if region == "OTHER" and country_name:
        return f"🌍 {country_name.strip()}"
    return COUNTRY_LABELS[region][lang]


def validate_other_country_name(value: str) -> str:
    cleaned = " ".join((value or "").strip().split())
    if len(cleaned) < 2:
        raise ValueError("Country name is too short")
    if len(cleaned) > 80:
        raise ValueError("Country name is too long")
    if any(ord(ch) < 32 for ch in cleaned):
        raise ValueError("Country name contains invalid characters")
    return cleaned
