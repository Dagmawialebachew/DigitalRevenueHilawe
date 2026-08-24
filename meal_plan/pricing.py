"""Pricing contract helpers.

Actual amounts live in PostgreSQL. This module validates keys so neither React
nor Telegram handlers invent unsupported price combinations.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from meal_plan.constants import PLAN_DURATIONS_DAYS, PRICING_REGIONS, ServiceType, service_type_allowed

SUPPORTED_CURRENCIES = ("ETB", "USD")


@dataclass(frozen=True)
class PriceKey:
    region: str
    duration_days: int
    service_type: ServiceType

    @classmethod
    def build(cls, region: str, duration_days: int, service_type: ServiceType | str) -> "PriceKey":
        region = region.upper().strip()
        service = ServiceType(service_type)
        if region not in PRICING_REGIONS:
            raise ValueError(f"Unsupported pricing region: {region}")
        if duration_days not in PLAN_DURATIONS_DAYS:
            raise ValueError(f"Unsupported duration: {duration_days}")
        if not service_type_allowed(duration_days, service):
            raise ValueError("FOLLOW_UP is only available for the 30-day plan")
        return cls(region=region, duration_days=duration_days, service_type=service)


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    @classmethod
    def build(cls, amount: Decimal | str | int | float, currency: str) -> "Money":
        value = Decimal(str(amount))
        currency = currency.upper().strip()
        if value < 0:
            raise ValueError("Price cannot be negative")
        if currency not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Unsupported currency: {currency}")
        return cls(amount=value, currency=currency)


def requires_manual_quote(region: str) -> bool:
    return region.upper().strip() == "OTHER"
