"""Persistence boundary for meal-plan lifecycle data.

This repository is intentionally not wired to handlers in Phase 1. It accepts an
asyncpg-compatible pool directly. A later integration phase will construct it
from the application database pool. SQL updates include expected state/version
checks so retries and Telegram double-clicks cannot silently overwrite state.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from meal_plan.constants import LANGUAGES, MEAL_COUNTS, PRICING_REGIONS, ServiceType, service_type_allowed
from meal_plan.pricing import PriceKey, SUPPORTED_CURRENCIES
from meal_plan.state_machine import require_transition
from meal_plan.states import ActorRole, IntakeState, OrderState


class ConnectionLike(Protocol):
    async def fetchrow(self, query: str, *args: Any): ...
    async def fetch(self, query: str, *args: Any): ...
    async def execute(self, query: str, *args: Any): ...
    async def fetchval(self, query: str, *args: Any): ...
    def transaction(self): ...


class AcquireContext(Protocol):
    async def __aenter__(self) -> ConnectionLike: ...
    async def __aexit__(self, exc_type, exc, tb): ...


class PoolLike(Protocol):
    def acquire(self) -> AcquireContext: ...


class ConcurrentUpdate(RuntimeError):
    pass


class RecordNotFound(LookupError):
    pass


class MealPlanRepository:
    def __init__(self, pool: PoolLike):
        self.pool = pool

    async def get_intake(self, intake_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM meal_intakes WHERE id = $1", intake_id)

    async def get_open_intake_for_user(self, telegram_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT * FROM meal_intakes
                WHERE user_id = $1 AND closed_at IS NULL
                ORDER BY id DESC
                LIMIT 1
                """,
                telegram_id,
            )

    async def create_or_resume_intake(
        self,
        telegram_id: int,
        language: str,
        *,
        country_region: str | None = None,
        country_name: str | None = None,
        source: str = "BOT_MENU",
    ):
        language = language.upper().strip()
        if language not in LANGUAGES:
            language = "AM"
        if country_region is not None:
            country_region = country_region.upper().strip()
            if country_region not in PRICING_REGIONS:
                raise ValueError(f"Unsupported region: {country_region}")
        state = IntakeState.INTAKE_IN_PROGRESS if country_region else IntakeState.COUNTRY_REQUIRED

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                existing = await conn.fetchrow(
                    """
                    SELECT * FROM meal_intakes
                    WHERE user_id = $1 AND closed_at IS NULL
                    ORDER BY id DESC
                    LIMIT 1
                    FOR UPDATE
                    """,
                    telegram_id,
                )
                if existing:
                    return existing

                return await conn.fetchrow(
                    """
                    INSERT INTO meal_intakes(
                        public_id, user_id, language, country_region, country_name,
                        state, source
                    )
                    VALUES($1, $2, $3, $4, $5, $6, $7)
                    RETURNING *
                    """,
                    uuid.uuid4(), telegram_id, language, country_region, country_name,
                    state.value, source,
                )

    async def set_intake_country(
        self,
        intake_id: int,
        telegram_id: int,
        region: str,
        *,
        country_name: str | None = None,
    ):
        region = region.upper().strip()
        if region not in PRICING_REGIONS:
            raise ValueError(f"Unsupported region: {region}")
        if region != "OTHER":
            country_name = None

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE meal_intakes
                SET country_region = $3,
                    country_name = $4,
                    state = CASE
                        WHEN state = 'COUNTRY_REQUIRED' THEN 'INTAKE_IN_PROGRESS'
                        ELSE state
                    END,
                    current_step = COALESCE(current_step, 'WELCOME'),
                    version = version + 1,
                    last_saved_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                  AND user_id = $2
                  AND closed_at IS NULL
                  AND state IN ('COUNTRY_REQUIRED','INTAKE_IN_PROGRESS')
                RETURNING *
                """,
                intake_id, telegram_id, region, country_name,
            )
            if row is None:
                raise ConcurrentUpdate("Intake country can no longer be changed")
            return row

    async def set_intake_language(self, intake_id: int, telegram_id: int, language: str):
        language = language.upper().strip()
        if language not in LANGUAGES:
            raise ValueError("Unsupported language")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE meal_intakes
                SET language = $3,
                    version = version + 1,
                    updated_at = NOW()
                WHERE id = $1 AND user_id = $2 AND closed_at IS NULL
                RETURNING *
                """,
                intake_id, telegram_id, language,
            )
            if row is None:
                raise ConcurrentUpdate("Open intake was not found")
            return row

    async def save_intake_answers(
        self,
        intake_id: int,
        answer_patch: dict[str, Any],
        *,
        current_step: str | None = None,
        expected_version: int | None = None,
    ):
        if not answer_patch:
            raise ValueError("answer_patch cannot be empty")
        payload = json.dumps(answer_patch, separators=(",", ":"), ensure_ascii=False)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE meal_intakes
                SET answers = answers || $2::jsonb,
                    current_step = COALESCE($3, current_step),
                    version = version + 1,
                    last_saved_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                  AND closed_at IS NULL
                  AND ($4::integer IS NULL OR version = $4)
                RETURNING *
                """,
                intake_id, payload, current_step, expected_version,
            )
            if row is None:
                raise ConcurrentUpdate("Intake was closed, missing, or updated by another request")
            return row

    async def mark_assessment_complete(self, intake_id: int, telegram_id: int):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE meal_intakes
                SET current_step = 'ASSESSMENT_COMPLETE',
                    completed_at = COALESCE(completed_at, NOW()),
                    last_saved_at = NOW(),
                    updated_at = NOW(),
                    version = version + 1
                WHERE id = $1
                  AND user_id = $2
                  AND closed_at IS NULL
                  AND state = 'INTAKE_IN_PROGRESS'
                RETURNING *
                """,
                intake_id, telegram_id,
            )
            if row is None:
                raise ConcurrentUpdate("Assessment can no longer be completed")
            return row

    async def transition_intake(
        self,
        intake_id: int,
        current: IntakeState | str,
        target: IntakeState | str,
        actor: ActorRole | str,
    ):
        current = IntakeState(current)
        target = IntakeState(target)
        require_transition("intake", current, target, actor)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE meal_intakes
                SET state = $3,
                    closed_at = CASE WHEN $3 IN ('CLOSED','CANCELLED','HEALTH_DECLINED') THEN NOW() ELSE closed_at END,
                    updated_at = NOW(),
                    version = version + 1
                WHERE id = $1 AND state = $2
                RETURNING *
                """,
                intake_id, current.value, target.value,
            )
            if row is None:
                raise ConcurrentUpdate(f"Intake is no longer in expected state {current.value}")
            return row

    async def get_health_review_for_intake(self, intake_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM meal_health_reviews WHERE intake_id=$1",
                intake_id,
            )

    async def require_health_review(
        self,
        intake_id: int,
        *,
        flags: list[str],
        summary: str,
    ):
        flags_json = json.dumps(flags, separators=(",", ":"), ensure_ascii=False)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                intake = await conn.fetchrow(
                    "SELECT * FROM meal_intakes WHERE id=$1 FOR UPDATE",
                    intake_id,
                )
                if not intake:
                    raise RecordNotFound("Intake not found")
                if intake["state"] == IntakeState.HEALTH_REVIEW_REQUIRED.value:
                    review = await conn.fetchrow(
                        "SELECT * FROM meal_health_reviews WHERE intake_id=$1", intake_id
                    )
                    return intake, review
                if intake["state"] != IntakeState.INTAKE_IN_PROGRESS.value:
                    raise ConcurrentUpdate("Intake is not ready for health-gate evaluation")

                review = await conn.fetchrow(
                    """
                    INSERT INTO meal_health_reviews(intake_id, status, flags, summary)
                    VALUES($1, 'PENDING', $2::jsonb, $3)
                    ON CONFLICT (intake_id) DO UPDATE SET
                        status='PENDING', flags=EXCLUDED.flags, summary=EXCLUDED.summary,
                        reviewer_telegram_id=NULL, decision_notes=NULL, resolved_at=NULL, updated_at=NOW()
                    RETURNING *
                    """,
                    intake_id, flags_json, summary,
                )
                intake = await conn.fetchrow(
                    """
                    UPDATE meal_intakes
                    SET state='HEALTH_REVIEW_REQUIRED', current_step='HEALTH_REVIEW_REQUIRED',
                        updated_at=NOW(), version=version+1
                    WHERE id=$1 AND state='INTAKE_IN_PROGRESS'
                    RETURNING *
                    """,
                    intake_id,
                )
                if intake is None:
                    raise ConcurrentUpdate("Health-review transition lost a concurrent update")
                return intake, review

    async def store_nutrition_profile(
        self,
        intake_id: int,
        *,
        expected_state: IntakeState | str,
        profile: dict[str, Any],
        target_state: IntakeState | str = IntakeState.PROFILE_READY,
    ):
        current = IntakeState(expected_state)
        target = IntakeState(target_state)
        require_transition("intake", current, target, ActorRole.SYSTEM)
        payload = json.dumps(profile, separators=(",", ":"), ensure_ascii=False)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE meal_intakes
                SET nutrition_profile=$3::jsonb, state=$4, current_step='PROFILE_READY',
                    updated_at=NOW(), version=version+1
                WHERE id=$1 AND state=$2 AND closed_at IS NULL
                RETURNING *
                """,
                intake_id, current.value, payload, target.value,
            )
            if row is None:
                raise ConcurrentUpdate(f"Intake is no longer in expected state {current.value}")
            return row

    async def approve_health_review(
        self,
        intake_id: int,
        reviewer_telegram_id: int,
        *,
        notes: str | None = None,
    ):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                intake = await conn.fetchrow(
                    "SELECT * FROM meal_intakes WHERE id=$1 FOR UPDATE", intake_id
                )
                if not intake:
                    raise RecordNotFound("Intake not found")
                if intake["state"] == IntakeState.HEALTH_APPROVED.value:
                    return intake
                if intake["state"] != IntakeState.HEALTH_REVIEW_REQUIRED.value:
                    raise ConcurrentUpdate("Health review is no longer pending")
                review = await conn.fetchrow(
                    "SELECT * FROM meal_health_reviews WHERE intake_id=$1 FOR UPDATE", intake_id
                )
                if not review or review["status"] != "PENDING":
                    raise ConcurrentUpdate("Health review is no longer pending")
                await conn.execute(
                    """
                    UPDATE meal_health_reviews
                    SET status='APPROVED', reviewer_telegram_id=$2, decision_notes=$3,
                        resolved_at=NOW(), updated_at=NOW()
                    WHERE intake_id=$1
                    """,
                    intake_id, reviewer_telegram_id, notes,
                )
                return await conn.fetchrow(
                    """
                    UPDATE meal_intakes
                    SET state='HEALTH_APPROVED', current_step='HEALTH_APPROVED',
                        updated_at=NOW(), version=version+1
                    WHERE id=$1 AND state='HEALTH_REVIEW_REQUIRED'
                    RETURNING *
                    """,
                    intake_id,
                )

    async def decline_health_review(
        self,
        intake_id: int,
        reviewer_telegram_id: int,
        *,
        notes: str | None = None,
    ):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                intake = await conn.fetchrow(
                    "SELECT * FROM meal_intakes WHERE id=$1 FOR UPDATE", intake_id
                )
                if not intake:
                    raise RecordNotFound("Intake not found")
                if intake["state"] != IntakeState.HEALTH_REVIEW_REQUIRED.value:
                    raise ConcurrentUpdate("Health review is no longer pending")
                await conn.execute(
                    """
                    UPDATE meal_health_reviews
                    SET status='DECLINED', reviewer_telegram_id=$2, decision_notes=$3,
                        resolved_at=NOW(), updated_at=NOW()
                    WHERE intake_id=$1 AND status='PENDING'
                    """,
                    intake_id, reviewer_telegram_id, notes,
                )
                return await conn.fetchrow(
                    """
                    UPDATE meal_intakes
                    SET state='HEALTH_DECLINED', current_step='HEALTH_DECLINED',
                        closed_at=NOW(), updated_at=NOW(), version=version+1
                    WHERE id=$1 AND state='HEALTH_REVIEW_REQUIRED'
                    RETURNING *
                    """,
                    intake_id,
                )

    async def save_plan_configuration(
        self,
        intake_id: int,
        *,
        configuration: dict[str, Any],
        current_step: str,
    ):
        patch = json.dumps({"plan_configuration": configuration}, separators=(",", ":"), ensure_ascii=False)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE meal_intakes
                SET answers=answers || $2::jsonb, current_step=$3, updated_at=NOW(),
                    last_saved_at=NOW(), version=version+1
                WHERE id=$1 AND state IN ('PROFILE_READY','CHECKOUT_READY') AND closed_at IS NULL
                RETURNING *
                """,
                intake_id, patch, current_step,
            )
            if row is None:
                raise ConcurrentUpdate("Plan configuration can no longer be changed")
            return row

    async def mark_checkout_ready(self, intake_id: int):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE meal_intakes
                SET state='CHECKOUT_READY', current_step='CHECKOUT_READY', updated_at=NOW(), version=version+1
                WHERE id=$1 AND state IN ('PROFILE_READY','CHECKOUT_READY') AND closed_at IS NULL
                RETURNING *
                """,
                intake_id,
            )
            if row is None:
                raise ConcurrentUpdate("Intake is not ready for checkout")
            return row

    async def get_active_prices_for_region(self, region: str):
        region = region.upper().strip()
        if region not in PRICING_REGIONS:
            raise ValueError("Unsupported region")
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT DISTINCT ON (duration_days, service_type) *
                FROM meal_pricing
                WHERE region=$1 AND is_active=TRUE AND effective_from <= NOW()
                  AND (effective_to IS NULL OR effective_to > NOW())
                ORDER BY duration_days, service_type, effective_from DESC, id DESC
                """,
                region,
            )

    async def get_fasting_calendar_window(self, start_date: date, end_date: date):
        """Return verified year coverage and annual occurrences overlapping a plan."""
        if end_date < start_date:
            raise ValueError("Plan end date cannot be before its start date")
        years = list(range(start_date.year, end_date.year + 1))
        async with self.pool.acquire() as conn:
            coverage = await conn.fetch(
                """
                SELECT calendar_year,status,source_name,source_url,verified_at
                FROM nutrition_fasting_calendar_coverage
                WHERE calendar_year = ANY($1::int[])
                ORDER BY calendar_year
                """,
                years,
            )
            seasons = await conn.fetch(
                """
                SELECT rule_id,fast_name,start_date,end_date,verified_for_year,notes
                FROM nutrition_fasting_calendar
                WHERE verification_status='VERIFIED_RULESET'
                  AND start_date IS NOT NULL AND end_date IS NOT NULL
                  AND start_date <= $2 AND end_date >= $1
                ORDER BY start_date,rule_id
                """,
                start_date, end_date,
            )
        return coverage, seasons

    async def create_or_get_pending_quote(
        self,
        intake_id: int,
        *,
        country_name: str,
        duration_days: int,
        service_type: ServiceType | str,
    ):
        service = ServiceType(service_type)
        if not service_type_allowed(duration_days, service):
            raise ValueError("Invalid duration/service combination")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                existing = await conn.fetchrow(
                    """
                    SELECT * FROM meal_quotes
                    WHERE intake_id=$1 AND duration_days=$2 AND service_type=$3
                      AND status IN ('PENDING','CONFIRMED')
                    ORDER BY id DESC LIMIT 1 FOR UPDATE
                    """,
                    intake_id, duration_days, service.value,
                )
                if existing:
                    return existing
                return await conn.fetchrow(
                    """
                    INSERT INTO meal_quotes(public_id, intake_id, region, country_name, duration_days, service_type)
                    VALUES($1,$2,'OTHER',$3,$4,$5)
                    RETURNING *
                    """,
                    uuid.uuid4(), intake_id, country_name, duration_days, service.value,
                )

    async def set_price(
        self,
        *,
        region: str,
        duration_days: int,
        service_type: ServiceType | str,
        currency: str,
        amount: Decimal | str | int | float,
        created_by: int | None = None,
        label: str | None = None,
    ):
        key = PriceKey.build(region, duration_days, service_type)
        currency = currency.upper().strip()
        if currency not in SUPPORTED_CURRENCIES:
            raise ValueError("Unsupported currency")
        money = Decimal(str(amount))
        if money < 0:
            raise ValueError("Price cannot be negative")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE meal_pricing SET is_active=FALSE, effective_to=NOW()
                    WHERE region=$1 AND duration_days=$2 AND service_type=$3 AND is_active=TRUE
                    """,
                    key.region, key.duration_days, key.service_type.value,
                )
                return await conn.fetchrow(
                    """
                    INSERT INTO meal_pricing(region,duration_days,service_type,currency,amount,label,created_by)
                    VALUES($1,$2,$3,$4,$5,$6,$7)
                    RETURNING *
                    """,
                    key.region, key.duration_days, key.service_type.value, currency, money, label, created_by,
                )

    async def confirm_quote(
        self,
        quote_id: int,
        *,
        currency: str,
        amount: Decimal | str | int | float,
        set_by: int,
    ):
        currency = currency.upper().strip()
        if currency not in SUPPORTED_CURRENCIES:
            raise ValueError("Unsupported currency")
        money = Decimal(str(amount))
        if money < 0:
            raise ValueError("Price cannot be negative")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE meal_quotes
                SET currency=$2, amount=$3, status='CONFIRMED', set_by=$4, confirmed_at=NOW(), updated_at=NOW()
                WHERE id=$1 AND status='PENDING'
                RETURNING *
                """,
                quote_id, currency, money, set_by,
            )
            if row is None:
                raise ConcurrentUpdate("Quote is no longer pending")
            return row

    async def get_active_price(self, region: str, duration_days: int, service_type: ServiceType | str):
        key = PriceKey.build(region, duration_days, service_type)
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT * FROM meal_pricing
                WHERE region = $1
                  AND duration_days = $2
                  AND service_type = $3
                  AND is_active = TRUE
                  AND effective_from <= NOW()
                  AND (effective_to IS NULL OR effective_to > NOW())
                ORDER BY effective_from DESC, id DESC
                LIMIT 1
                """,
                key.region, key.duration_days, key.service_type.value,
            )

    async def create_order_from_intake(
        self,
        intake_id: int,
        telegram_id: int,
        *,
        duration_days: int,
        service_type: ServiceType | str,
        meals_per_day: int,
        start_date: date,
        ends_on: date,
        region: str,
        country_name: str | None,
        currency: str,
        amount: Decimal | str | int | float,
        pricing_id: int | None = None,
        quote_id: int | None = None,
    ):
        service = ServiceType(service_type)
        if not service_type_allowed(duration_days, service):
            raise ValueError("Invalid duration/service combination")
        if meals_per_day not in MEAL_COUNTS:
            raise ValueError("meals_per_day must be 3, 4, or 5")
        region = region.upper().strip()
        if region not in PRICING_REGIONS:
            raise ValueError("Unsupported region")
        amount = Decimal(str(amount))
        if amount < 0:
            raise ValueError("amount cannot be negative")
        currency = currency.upper().strip()
        if currency not in SUPPORTED_CURRENCIES:
            raise ValueError("Unsupported currency")
        if ends_on < start_date:
            raise ValueError("ends_on cannot be before start_date")

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                intake = await conn.fetchrow(
                    "SELECT * FROM meal_intakes WHERE id=$1 FOR UPDATE",
                    intake_id,
                )
                if not intake:
                    raise RecordNotFound("Intake not found")
                if intake["user_id"] != telegram_id:
                    raise PermissionError("Intake does not belong to user")
                if intake["state"] != IntakeState.CHECKOUT_READY.value:
                    raise ConcurrentUpdate("Intake is not checkout-ready")

                order = await conn.fetchrow(
                    """
                    INSERT INTO meal_orders(
                        public_id, user_id, intake_id, state, duration_days, service_type,
                        meals_per_day, start_date, ends_on, region, country_name,
                        currency, amount, pricing_id, quote_id
                    )
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
                    RETURNING *
                    """,
                    uuid.uuid4(), telegram_id, intake_id, OrderState.CHECKOUT_READY.value,
                    duration_days, service.value, meals_per_day, start_date, ends_on,
                    region, country_name, currency, amount, pricing_id, quote_id,
                )
                await conn.execute(
                    """
                    UPDATE meal_intakes
                    SET state='CLOSED', closed_at=NOW(), updated_at=NOW(), version=version+1
                    WHERE id=$1 AND state='CHECKOUT_READY'
                    """,
                    intake_id,
                )
                return order

    async def get_order(self, order_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM meal_orders WHERE id=$1", order_id)

    async def transition_order(
        self,
        order_id: int,
        current: OrderState | str,
        target: OrderState | str,
        actor: ActorRole | str,
    ):
        current = OrderState(current)
        target = OrderState(target)
        require_transition("order", current, target, actor)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE meal_orders
                SET state=$3, updated_at=NOW(), version=version+1,
                    paid_at = CASE WHEN $3='PAYMENT_APPROVED' AND paid_at IS NULL THEN NOW() ELSE paid_at END,
                    approved_at = CASE WHEN $3='APPROVED' AND approved_at IS NULL THEN NOW() ELSE approved_at END,
                    activated_at = CASE WHEN $3='ACTIVE' AND activated_at IS NULL THEN NOW() ELSE activated_at END,
                    expired_at = CASE WHEN $3='EXPIRED' AND expired_at IS NULL THEN NOW() ELSE expired_at END,
                    cancelled_at = CASE WHEN $3='CANCELLED' AND cancelled_at IS NULL THEN NOW() ELSE cancelled_at END
                WHERE id=$1 AND state=$2
                RETURNING *
                """,
                order_id, current.value, target.value,
            )
            if row is None:
                raise ConcurrentUpdate(f"Order is no longer in expected state {current.value}")
            return row

    async def append_audit_event(
        self,
        *,
        entity_type: str,
        entity_id: str,
        event_type: str,
        actor_type: str,
        actor_telegram_id: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> int:
        payload_json = json.dumps(payload or {}, separators=(",", ":"), ensure_ascii=False)
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                INSERT INTO meal_audit_events(
                    entity_type, entity_id, event_type, actor_type,
                    actor_telegram_id, payload
                )
                VALUES($1,$2,$3,$4,$5,$6::jsonb)
                RETURNING id
                """,
                entity_type, entity_id, event_type, actor_type, actor_telegram_id, payload_json,
            )

    async def get_current_order_for_user(self, telegram_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT * FROM meal_orders
                WHERE user_id=$1 AND state NOT IN ('EXPIRED','CANCELLED')
                ORDER BY id DESC
                LIMIT 1
                """,
                telegram_id,
            )

    async def get_order_for_user(self, order_id: int, telegram_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM meal_orders WHERE id=$1 AND user_id=$2",
                order_id, telegram_id,
            )

    async def get_latest_payment_for_order(self, order_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM meal_payments WHERE order_id=$1 ORDER BY id DESC LIMIT 1",
                order_id,
            )

    async def get_payment_for_user(self, payment_id: int, telegram_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM meal_payments WHERE id=$1 AND user_id=$2",
                payment_id, telegram_id,
            )

    async def get_confirmed_quote(self, intake_id: int, duration_days: int, service_type: ServiceType | str):
        service = ServiceType(service_type)
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT * FROM meal_quotes
                WHERE intake_id=$1 AND duration_days=$2 AND service_type=$3 AND status='CONFIRMED'
                  AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY confirmed_at DESC NULLS LAST, id DESC
                LIMIT 1
                """,
                intake_id, duration_days, service.value,
            )

    async def create_order_from_intake(
        self,
        intake_id: int,
        telegram_id: int,
        *,
        duration_days: int,
        service_type: ServiceType | str,
        meals_per_day: int,
        start_date: date,
        ends_on: date,
        region: str,
        country_name: str | None,
        currency: str,
        amount: Decimal | str | int | float,
        pricing_id: int | None = None,
        quote_id: int | None = None,
    ):
        """Create the order once; retries return the existing intake-scoped order."""
        service = ServiceType(service_type)
        if not service_type_allowed(duration_days, service):
            raise ValueError("Invalid duration/service combination")
        if meals_per_day not in MEAL_COUNTS:
            raise ValueError("meals_per_day must be 3, 4, or 5")
        region = region.upper().strip()
        if region not in PRICING_REGIONS:
            raise ValueError("Unsupported region")
        amount = Decimal(str(amount))
        if amount < 0:
            raise ValueError("amount cannot be negative")
        currency = currency.upper().strip()
        if currency not in SUPPORTED_CURRENCIES:
            raise ValueError("Unsupported currency")
        if ends_on < start_date:
            raise ValueError("ends_on cannot be before start_date")

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                existing = await conn.fetchrow(
                    "SELECT * FROM meal_orders WHERE intake_id=$1 FOR UPDATE",
                    intake_id,
                )
                if existing:
                    if existing["user_id"] != telegram_id:
                        raise PermissionError("Order does not belong to user")
                    return existing

                intake = await conn.fetchrow(
                    "SELECT * FROM meal_intakes WHERE id=$1 FOR UPDATE",
                    intake_id,
                )
                if not intake:
                    raise RecordNotFound("Intake not found")
                if intake["user_id"] != telegram_id:
                    raise PermissionError("Intake does not belong to user")
                if intake["state"] != IntakeState.CHECKOUT_READY.value:
                    raise ConcurrentUpdate("Intake is not checkout-ready")

                order = await conn.fetchrow(
                    """
                    INSERT INTO meal_orders(
                        public_id, user_id, intake_id, state, duration_days, service_type,
                        meals_per_day, start_date, ends_on, region, country_name,
                        currency, amount, pricing_id, quote_id
                    )
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
                    RETURNING *
                    """,
                    uuid.uuid4(), telegram_id, intake_id, OrderState.CHECKOUT_READY.value,
                    duration_days, service.value, meals_per_day, start_date, ends_on,
                    region, country_name, currency, amount, pricing_id, quote_id,
                )
                await conn.execute(
                    """
                    UPDATE meal_intakes
                    SET state='CLOSED', closed_at=NOW(), updated_at=NOW(), version=version+1
                    WHERE id=$1 AND state='CHECKOUT_READY'
                    """,
                    intake_id,
                )
                return order

    async def create_or_get_payment_attempt(
        self,
        order_id: int,
        telegram_id: int,
        *,
        expected_amount: Decimal | str | int | float,
        expected_currency: str,
        settlement_amount: Decimal | str | int | float,
        settlement_currency: str,
        exchange_rate: Decimal | None,
    ):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                order = await conn.fetchrow("SELECT * FROM meal_orders WHERE id=$1 FOR UPDATE", order_id)
                if not order:
                    raise RecordNotFound("Order not found")
                if order["user_id"] != telegram_id:
                    raise PermissionError("Order does not belong to user")
                if order["state"] not in {OrderState.CHECKOUT_READY.value, OrderState.AWAITING_PAYMENT.value}:
                    latest = await conn.fetchrow(
                        "SELECT * FROM meal_payments WHERE order_id=$1 ORDER BY id DESC LIMIT 1",
                        order_id,
                    )
                    if latest and latest["status"] in {"PENDING", "VERIFYING", "APPROVED"}:
                        return latest
                    raise ConcurrentUpdate("Order is not accepting a payment")

                existing = await conn.fetchrow(
                    """
                    SELECT * FROM meal_payments
                    WHERE order_id=$1 AND status IN ('PENDING','VERIFYING')
                    ORDER BY id DESC LIMIT 1 FOR UPDATE
                    """,
                    order_id,
                )
                if existing:
                    return existing

                attempt_number = await conn.fetchval(
                    "SELECT COUNT(*) + 1 FROM meal_payments WHERE order_id=$1",
                    order_id,
                )
                payment = await conn.fetchrow(
                    """
                    INSERT INTO meal_payments(
                        order_id,user_id,expected_amount,expected_currency,
                        settlement_amount,settlement_currency,exchange_rate,status,idempotency_key
                    )
                    VALUES($1,$2,$3,$4,$5,$6,$7,'PENDING',$8)
                    RETURNING *
                    """,
                    order_id, telegram_id, Decimal(str(expected_amount)), expected_currency,
                    Decimal(str(settlement_amount)), settlement_currency, exchange_rate,
                    f"meal-order:{order_id}:attempt:{attempt_number}",
                )
                if order["state"] == OrderState.CHECKOUT_READY.value:
                    await conn.execute(
                        "UPDATE meal_orders SET state='AWAITING_PAYMENT', updated_at=NOW(), version=version+1 WHERE id=$1 AND state='CHECKOUT_READY'",
                        order_id,
                    )
                return payment

    async def create_retry_payment(self, order_id: int, telegram_id: int):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                order = await conn.fetchrow("SELECT * FROM meal_orders WHERE id=$1 FOR UPDATE", order_id)
                if not order:
                    raise RecordNotFound("Order not found")
                if order["user_id"] != telegram_id:
                    raise PermissionError("Order does not belong to user")
                if order["state"] != OrderState.AWAITING_PAYMENT.value:
                    raise ConcurrentUpdate("Order is not waiting for another payment receipt")
                open_payment = await conn.fetchrow(
                    "SELECT * FROM meal_payments WHERE order_id=$1 AND status IN ('PENDING','VERIFYING') ORDER BY id DESC LIMIT 1",
                    order_id,
                )
                if open_payment:
                    return open_payment
                previous = await conn.fetchrow(
                    "SELECT * FROM meal_payments WHERE order_id=$1 ORDER BY id DESC LIMIT 1",
                    order_id,
                )
                if not previous:
                    raise RecordNotFound("Previous payment attempt not found")
                attempt_number = await conn.fetchval("SELECT COUNT(*) + 1 FROM meal_payments WHERE order_id=$1", order_id)
                return await conn.fetchrow(
                    """
                    INSERT INTO meal_payments(
                        order_id,user_id,expected_amount,expected_currency,settlement_amount,
                        settlement_currency,exchange_rate,status,idempotency_key
                    ) VALUES($1,$2,$3,$4,$5,$6,$7,'PENDING',$8)
                    RETURNING *
                    """,
                    order_id, telegram_id, previous["expected_amount"], previous["expected_currency"],
                    previous["settlement_amount"], previous["settlement_currency"], previous["exchange_rate"],
                    f"meal-order:{order_id}:attempt:{attempt_number}",
                )

    async def submit_payment_proof(self, payment_id: int, telegram_id: int, proof_file_id: str):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                payment = await conn.fetchrow("SELECT * FROM meal_payments WHERE id=$1 FOR UPDATE", payment_id)
                if not payment:
                    raise RecordNotFound("Payment attempt not found")
                if payment["user_id"] != telegram_id:
                    raise PermissionError("Payment attempt does not belong to user")
                if payment["status"] == "VERIFYING" and payment["proof_file_id"] == proof_file_id:
                    order = await conn.fetchrow("SELECT * FROM meal_orders WHERE id=$1", payment["order_id"])
                    return payment, order
                if payment["status"] != "PENDING":
                    raise ConcurrentUpdate("Payment attempt is no longer accepting a receipt")
                order = await conn.fetchrow("SELECT * FROM meal_orders WHERE id=$1 FOR UPDATE", payment["order_id"])
                if not order or order["state"] != OrderState.AWAITING_PAYMENT.value:
                    raise ConcurrentUpdate("Order is no longer awaiting payment")
                payment = await conn.fetchrow(
                    """
                    UPDATE meal_payments
                    SET proof_file_id=$2,status='VERIFYING',updated_at=NOW()
                    WHERE id=$1 AND status='PENDING'
                    RETURNING *
                    """,
                    payment_id, proof_file_id,
                )
                order = await conn.fetchrow(
                    """
                    UPDATE meal_orders SET state='PAYMENT_REVIEW',updated_at=NOW(),version=version+1
                    WHERE id=$1 AND state='AWAITING_PAYMENT'
                    RETURNING *
                    """,
                    order["id"],
                )
                return payment, order

    async def store_payment_verification(self, payment_id: int, *, reference: str | None, payload: dict[str, Any]):
        payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                UPDATE meal_payments
                SET verification_reference=$2, verification_payload=$3::jsonb, updated_at=NOW()
                WHERE id=$1 AND status='VERIFYING'
                RETURNING *
                """,
                payment_id, reference, payload_json,
            )

    async def approve_payment_and_queue_generation(self, payment_id: int, *, processed_by: int | None):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                payment = await conn.fetchrow("SELECT * FROM meal_payments WHERE id=$1 FOR UPDATE", payment_id)
                if not payment:
                    raise RecordNotFound("Payment not found")
                order = await conn.fetchrow("SELECT * FROM meal_orders WHERE id=$1 FOR UPDATE", payment["order_id"])
                if not order:
                    raise RecordNotFound("Order not found")

                if payment["status"] == "APPROVED" and order["state"] in {
                    OrderState.PAYMENT_APPROVED.value, OrderState.GENERATION_QUEUED.value,
                    OrderState.GENERATING.value, OrderState.REVIEW_PENDING.value,
                    OrderState.CHANGES_REQUESTED.value, OrderState.APPROVED.value,
                    OrderState.DELIVERY_PENDING.value, OrderState.ACTIVE.value,
                }:
                    job = await conn.fetchrow(
                        "SELECT * FROM meal_generation_jobs WHERE order_id=$1 AND job_type='INITIAL' ORDER BY id DESC LIMIT 1",
                        order["id"],
                    )
                    return {"payment": payment, "order": order, "job": job}

                if payment["status"] != "VERIFYING" or order["state"] != OrderState.PAYMENT_REVIEW.value:
                    raise ConcurrentUpdate("Payment is no longer awaiting approval")

                payment = await conn.fetchrow(
                    """
                    UPDATE meal_payments SET status='APPROVED',processed_by=$2,approved_at=NOW(),updated_at=NOW()
                    WHERE id=$1 AND status='VERIFYING' RETURNING *
                    """,
                    payment_id, processed_by,
                )
                order = await conn.fetchrow(
                    """
                    UPDATE meal_orders
                    SET state='GENERATION_QUEUED',paid_at=COALESCE(paid_at,NOW()),updated_at=NOW(),version=version+1
                    WHERE id=$1 AND state='PAYMENT_REVIEW'
                    RETURNING *
                    """,
                    order["id"],
                )
                job = await conn.fetchrow(
                    """
                    INSERT INTO meal_generation_jobs(public_id,order_id,job_type,status,stage,idempotency_key,payload)
                    VALUES($1,$2,'INITIAL','PENDING','QUEUED',$3,'{}'::jsonb)
                    ON CONFLICT (idempotency_key) DO UPDATE SET updated_at=meal_generation_jobs.updated_at
                    RETURNING *
                    """,
                    uuid.uuid4(), order["id"], f"meal-order:{order['id']}:initial-generation",
                )
                return {"payment": payment, "order": order, "job": job}

    async def reject_payment_for_retry(self, payment_id: int, *, processed_by: int | None):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                payment = await conn.fetchrow("SELECT * FROM meal_payments WHERE id=$1 FOR UPDATE", payment_id)
                if not payment:
                    raise RecordNotFound("Payment not found")
                order = await conn.fetchrow("SELECT * FROM meal_orders WHERE id=$1 FOR UPDATE", payment["order_id"])
                if not order:
                    raise RecordNotFound("Order not found")
                if payment["status"] == "REJECTED" and order["state"] == OrderState.AWAITING_PAYMENT.value:
                    return {"payment": payment, "order": order}
                if payment["status"] != "VERIFYING" or order["state"] != OrderState.PAYMENT_REVIEW.value:
                    raise ConcurrentUpdate("Payment is no longer awaiting review")
                payment = await conn.fetchrow(
                    """
                    UPDATE meal_payments SET status='REJECTED',processed_by=$2,rejected_at=NOW(),updated_at=NOW()
                    WHERE id=$1 AND status='VERIFYING' RETURNING *
                    """,
                    payment_id, processed_by,
                )
                order = await conn.fetchrow(
                    """
                    UPDATE meal_orders SET state='AWAITING_PAYMENT',updated_at=NOW(),version=version+1
                    WHERE id=$1 AND state='PAYMENT_REVIEW' RETURNING *
                    """,
                    order["id"],
                )
                return {"payment": payment, "order": order}
