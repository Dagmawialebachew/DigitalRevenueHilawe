"""Pure payment/settlement rules for Meal Plan orders."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from meal_plan.runtime import payment_amount_tolerance, usd_settlement_mode, usd_to_etb_rate


@dataclass(frozen=True)
class Settlement:
    expected_amount: Decimal
    expected_currency: str
    settlement_amount: Decimal
    settlement_currency: str
    exchange_rate: Decimal | None


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_settlement(expected_amount: Decimal | str | int | float, expected_currency: str) -> Settlement:
    amount = _money(Decimal(str(expected_amount)))
    currency = expected_currency.upper().strip()
    if currency == "ETB":
        return Settlement(amount, "ETB", amount, "ETB", None)
    if currency != "USD":
        raise ValueError("Unsupported expected currency")

    if usd_settlement_mode() == "USD":
        return Settlement(amount, "USD", amount, "USD", None)

    rate = usd_to_etb_rate()
    if rate is None:
        raise ValueError("MEAL_PLAN_USD_TO_ETB_RATE is required when USD settlement mode is ETB")
    return Settlement(amount, "USD", _money(amount * rate), "ETB", rate)


def amount_matches(expected: Decimal | str | int | float, observed: object, *, tolerance: Decimal | None = None) -> bool:
    if observed is None:
        return False
    try:
        actual = Decimal(str(observed).replace(",", "").strip())
        target = Decimal(str(expected))
    except (InvalidOperation, ValueError, AttributeError):
        return False
    allowed = payment_amount_tolerance() if tolerance is None else tolerance
    return abs(actual - target) <= allowed
