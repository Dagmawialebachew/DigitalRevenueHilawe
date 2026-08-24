"""Pure transition rules for meal-plan lifecycle entities.

Keeping transitions pure makes them easy to test. Persistence code performs an
atomic `UPDATE ... WHERE state = expected_state`, so two callbacks cannot both
win the same transition.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, TypeVar

from meal_plan.states import ActorRole, IntakeState, OrderState

S = TypeVar("S", bound=StrEnum)


class InvalidTransition(ValueError):
    pass


class UnauthorizedTransition(PermissionError):
    pass


@dataclass(frozen=True)
class TransitionRule:
    target: StrEnum
    actors: frozenset[ActorRole]


def _r(target: StrEnum, *actors: ActorRole) -> TransitionRule:
    return TransitionRule(target=target, actors=frozenset(actors))


INTAKE_TRANSITIONS: Mapping[IntakeState, tuple[TransitionRule, ...]] = {
    IntakeState.COUNTRY_REQUIRED: (
        _r(IntakeState.INTAKE_IN_PROGRESS, ActorRole.USER, ActorRole.SYSTEM),
        _r(IntakeState.CANCELLED, ActorRole.USER, ActorRole.ADMIN),
    ),
    IntakeState.INTAKE_IN_PROGRESS: (
        _r(IntakeState.HEALTH_REVIEW_REQUIRED, ActorRole.SYSTEM),
        _r(IntakeState.PROFILE_READY, ActorRole.SYSTEM),
        _r(IntakeState.CANCELLED, ActorRole.USER, ActorRole.ADMIN),
    ),
    IntakeState.HEALTH_REVIEW_REQUIRED: (
        _r(IntakeState.HEALTH_APPROVED, ActorRole.REVIEWER, ActorRole.ADMIN),
        _r(IntakeState.HEALTH_DECLINED, ActorRole.REVIEWER, ActorRole.ADMIN),
        _r(IntakeState.CANCELLED, ActorRole.ADMIN),
    ),
    IntakeState.HEALTH_APPROVED: (
        _r(IntakeState.PROFILE_READY, ActorRole.SYSTEM),
        _r(IntakeState.CANCELLED, ActorRole.ADMIN),
    ),
    IntakeState.PROFILE_READY: (
        _r(IntakeState.CHECKOUT_READY, ActorRole.USER, ActorRole.SYSTEM),
        _r(IntakeState.CANCELLED, ActorRole.USER, ActorRole.ADMIN),
    ),
    IntakeState.CHECKOUT_READY: (
        _r(IntakeState.CLOSED, ActorRole.SYSTEM),
        _r(IntakeState.CANCELLED, ActorRole.USER, ActorRole.ADMIN),
    ),
    IntakeState.HEALTH_DECLINED: (),
    IntakeState.CLOSED: (),
    IntakeState.CANCELLED: (),
}


ORDER_TRANSITIONS: Mapping[OrderState, tuple[TransitionRule, ...]] = {
    OrderState.CHECKOUT_READY: (
        _r(OrderState.AWAITING_PAYMENT, ActorRole.USER, ActorRole.SYSTEM),
        _r(OrderState.CANCELLED, ActorRole.USER, ActorRole.ADMIN),
    ),
    OrderState.AWAITING_PAYMENT: (
        _r(OrderState.PAYMENT_REVIEW, ActorRole.USER, ActorRole.SYSTEM),
        _r(OrderState.CANCELLED, ActorRole.USER, ActorRole.ADMIN),
    ),
    OrderState.PAYMENT_REVIEW: (
        _r(OrderState.PAYMENT_APPROVED, ActorRole.PAYMENT_VERIFIER, ActorRole.REVIEWER, ActorRole.ADMIN, ActorRole.SYSTEM),
        _r(OrderState.AWAITING_PAYMENT, ActorRole.PAYMENT_VERIFIER, ActorRole.REVIEWER, ActorRole.ADMIN, ActorRole.SYSTEM),
        _r(OrderState.CANCELLED, ActorRole.ADMIN),
    ),
    OrderState.PAYMENT_APPROVED: (
        _r(OrderState.GENERATION_QUEUED, ActorRole.SYSTEM, ActorRole.ADMIN),
        _r(OrderState.CANCELLED, ActorRole.ADMIN),
    ),
    OrderState.GENERATION_QUEUED: (
        _r(OrderState.GENERATING, ActorRole.WORKER),
        _r(OrderState.CANCELLED, ActorRole.ADMIN),
    ),
    OrderState.GENERATING: (
        _r(OrderState.REVIEW_PENDING, ActorRole.WORKER, ActorRole.SYSTEM),
        _r(OrderState.GENERATION_FAILED, ActorRole.WORKER, ActorRole.SYSTEM),
    ),
    OrderState.GENERATION_FAILED: (
        _r(OrderState.GENERATION_QUEUED, ActorRole.WORKER, ActorRole.SYSTEM, ActorRole.ADMIN),
        _r(OrderState.CANCELLED, ActorRole.ADMIN),
    ),
    OrderState.REVIEW_PENDING: (
        _r(OrderState.APPROVED, ActorRole.REVIEWER, ActorRole.ADMIN),
        _r(OrderState.CHANGES_REQUESTED, ActorRole.REVIEWER, ActorRole.ADMIN),
    ),
    OrderState.CHANGES_REQUESTED: (
        _r(OrderState.GENERATION_QUEUED, ActorRole.REVIEWER, ActorRole.ADMIN, ActorRole.SYSTEM),
        _r(OrderState.REVIEW_PENDING, ActorRole.REVIEWER, ActorRole.ADMIN, ActorRole.SYSTEM),
        _r(OrderState.CANCELLED, ActorRole.ADMIN),
    ),
    OrderState.APPROVED: (
        _r(OrderState.DELIVERY_PENDING, ActorRole.SYSTEM, ActorRole.REVIEWER, ActorRole.ADMIN),
    ),
    OrderState.DELIVERY_PENDING: (
        _r(OrderState.ACTIVE, ActorRole.SYSTEM),
        _r(OrderState.CANCELLED, ActorRole.ADMIN),
    ),
    OrderState.ACTIVE: (
        _r(OrderState.RENEWAL_DUE, ActorRole.SYSTEM),
        _r(OrderState.EXPIRED, ActorRole.SYSTEM),
        _r(OrderState.CANCELLED, ActorRole.ADMIN),
    ),
    OrderState.RENEWAL_DUE: (
        _r(OrderState.EXPIRED, ActorRole.SYSTEM),
        _r(OrderState.CANCELLED, ActorRole.ADMIN),
    ),
    OrderState.EXPIRED: (),
    OrderState.CANCELLED: (),
}


def _normalize(enum_type: type[S], value: S | str) -> S:
    return value if isinstance(value, enum_type) else enum_type(value)


def allowed_targets(entity: str, current: StrEnum | str) -> tuple[StrEnum, ...]:
    entity = entity.lower()
    if entity == "intake":
        state = _normalize(IntakeState, current)  # type: ignore[arg-type]
        return tuple(rule.target for rule in INTAKE_TRANSITIONS[state])
    if entity == "order":
        state = _normalize(OrderState, current)  # type: ignore[arg-type]
        return tuple(rule.target for rule in ORDER_TRANSITIONS[state])
    raise ValueError(f"Unknown state-machine entity: {entity}")


def require_transition(entity: str, current: StrEnum | str, target: StrEnum | str, actor: ActorRole | str) -> None:
    entity = entity.lower()
    actor = _normalize(ActorRole, actor)
    if entity == "intake":
        current_state = _normalize(IntakeState, current)  # type: ignore[arg-type]
        target_state = _normalize(IntakeState, target)  # type: ignore[arg-type]
        rules = INTAKE_TRANSITIONS[current_state]
    elif entity == "order":
        current_state = _normalize(OrderState, current)  # type: ignore[arg-type]
        target_state = _normalize(OrderState, target)  # type: ignore[arg-type]
        rules = ORDER_TRANSITIONS[current_state]
    else:
        raise ValueError(f"Unknown state-machine entity: {entity}")

    matching = next((rule for rule in rules if rule.target == target_state), None)
    if matching is None:
        raise InvalidTransition(f"{entity}: {current_state.value} -> {target_state.value} is not allowed")
    if actor not in matching.actors:
        raise UnauthorizedTransition(
            f"{actor.value} cannot perform {entity}: {current_state.value} -> {target_state.value}"
        )
