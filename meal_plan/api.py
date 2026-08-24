"""aiohttp routes for the Coach Hilawe Meal Plan Mini App release candidate (Phase 10)."""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any

from aiohttp import web

from meal_plan.auth import TelegramInitDataError, validate_telegram_init_data
from meal_plan.checkout import parse_plan_configuration
from meal_plan.constants import LANGUAGES, ServiceType
from meal_plan.countries import country_label, normalize_region, validate_other_country_name
from meal_plan.health_gate import evaluate_health_gate, localized_flag_labels
from meal_plan.health_review import notify_health_review
from meal_plan.followup import send_followup_review
from meal_plan.followup_policy import CheckinValidationError, decide_revision, validate_checkin_answers
from meal_plan.followup_repository import MealPlanFollowUpRepository
from meal_plan.intake_validation import normalize_step, validate_answer_patch, validate_complete_assessment
from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.payment import bank_accounts, build_settlement, notify_payment_ready
from meal_plan.repository import ConcurrentUpdate
from meal_plan.repository_factory import get_meal_plan_repository
from meal_plan.review_repository import MealPlanReviewRepository
from meal_plan.plan_access import plan_payload, safe_local_pdf_path
from meal_plan.runtime import (
    business_timezone_name,
    followup_auto_revision_enabled,
    init_data_max_age_seconds,
    meal_plan_access_allowed,
    meal_plan_enabled,
)
from meal_plan.states import IntakeState, OrderState

logger = logging.getLogger(__name__)
# Compatibility note: the release-candidate health surface now reports Phase 10.


def _error(code: str, message: str, *, status: int = 400, details: Any = None) -> web.Response:
    body: dict[str, Any] = {"ok": False, "error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return web.json_response(body, status=status)


async def _json(request: web.Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text="Invalid JSON body") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="JSON body must be an object")
    return payload


async def _authenticate(request: web.Request, payload: dict[str, Any]):
    if not meal_plan_enabled():
        raise web.HTTPServiceUnavailable(text="Meal Plan feature is disabled")
    init_data = payload.get("init_data")
    if not isinstance(init_data, str):
        raise TelegramInitDataError("INIT_DATA_MISSING", "Telegram initData is required")
    bot = request.app["bot"]
    identity = validate_telegram_init_data(init_data, bot.token, max_age_seconds=init_data_max_age_seconds())
    if not meal_plan_access_allowed(identity.telegram_id):
        body = {
            "ok": False,
            "error": {
                "code": "MEAL_PLAN_COMING_SOON",
                "message": "Coach Hilawe Meal Plans are coming soon.",
            },
        }
        raise web.HTTPForbidden(text=json.dumps(body), content_type="application/json")
    return identity


async def _identity_user_intake(request: web.Request, payload: dict[str, Any]):
    identity = await _authenticate(request, payload)
    db = request.app["db"]
    user = await db.get_user(identity.telegram_id)
    if not user:
        raise PermissionError("USER_NOT_REGISTERED")
    lang = user.get("language") if user.get("language") in LANGUAGES else "AM"
    repo = get_meal_plan_repository(db)
    intake = await repo.create_or_resume_intake(identity.telegram_id, lang, source="MINI_APP")
    return identity, user, lang, repo, intake


def _money(row) -> dict[str, Any] | None:
    if not row:
        return None
    amount = row.get("amount")
    return {
        "id": row.get("id"),
        "currency": row.get("currency"),
        "amount": str(amount) if amount is not None else None,
        "label": row.get("label"),
    }




def _review_repo(db) -> MealPlanReviewRepository:
    pool = getattr(db, "_pool", None)
    if pool is None:
        raise RuntimeError("Database pool is not connected")
    return MealPlanReviewRepository(pool)


def _followup_repo(db) -> MealPlanFollowUpRepository:
    pool = getattr(db, "_pool", None)
    if pool is None:
        raise RuntimeError("Database pool is not connected")
    return MealPlanFollowUpRepository(pool)


def _business_today():
    try:
        tz = ZoneInfo(business_timezone_name())
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("Africa/Addis_Ababa")
    return datetime.now(tz).date()


def _intake_payload(intake, lang: str) -> dict[str, Any]:
    region = intake.get("country_region")
    country = None
    if region:
        country = {
            "region": region,
            "name": intake.get("country_name"),
            "label": country_label(region, lang, intake.get("country_name")),
        }
    return {
        "public_id": str(intake["public_id"]),
        "state": intake["state"],
        "current_step": intake.get("current_step"),
        "version": intake.get("version", 1),
        "answers": dict(intake.get("answers") or {}),
        "nutrition_profile": dict(intake.get("nutrition_profile") or {}),
        "assessment_complete": bool(intake.get("completed_at")),
        "source": str(intake.get("source") or ""),
        "country_required": region is None,
        "country": country,
    }


async def meal_health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "meal-plan", "enabled": meal_plan_enabled(), "phase": 10})


async def bootstrap(request: web.Request) -> web.Response:
    try:
        payload = await _json(request)
        identity = await _authenticate(request, payload)
        db = request.app["db"]
        user = await db.get_user(identity.telegram_id)
        if not user:
            raise PermissionError("USER_NOT_REGISTERED")
        lang = user.get("language") if user.get("language") in LANGUAGES else "AM"
        repo = get_meal_plan_repository(db)
        followup_repo = _followup_repo(db)
    except TelegramInitDataError as exc:
        return _error(exc.code, str(exc), status=401)
    except PermissionError:
        return _error("USER_NOT_REGISTERED", "Open Coach Hilawe Bot and send /start before using the Meal Plan Mini App.", status=403)
    except web.HTTPException:
        raise

    open_intake = await repo.get_open_intake_for_user(identity.telegram_id)
    latest_order = await followup_repo.latest_order_for_user(identity.telegram_id)

    # Renewal intakes deliberately take precedence over the still-active expiring
    # order. They are fresh: only language is inherited; country/body/food/health
    # answers are collected again rather than silently copied from the old plan.
    if not open_intake and latest_order and latest_order["state"] == "EXPIRED":
        try:
            open_intake = await followup_repo.create_renewal_intake(
                telegram_id=identity.telegram_id,
                language=lang,
                source_order_id=latest_order["id"],
            )
        except ConcurrentUpdate as exc:
            logger.info("Expired-order renewal intake could not start yet: %s", exc)
        except Exception:
            logger.exception("Could not auto-start expired Meal Plan renewal intake")

    renewal_intake = bool(open_intake and str(open_intake.get("source") or "").startswith("RENEWAL:"))
    order = None if renewal_intake else await repo.get_current_order_for_user(identity.telegram_id)

    if order:
        intake = await repo.get_intake(order["intake_id"])
        payment = await repo.get_latest_payment_for_order(order["id"])
        payment_payload = None
        if payment:
            payment_payload = {
                "id": payment["id"],
                "status": payment["status"],
                "expected_amount": str(payment["expected_amount"]),
                "expected_currency": payment["expected_currency"],
                "settlement_amount": str(payment["settlement_amount"]) if payment.get("settlement_amount") is not None else None,
                "settlement_currency": payment.get("settlement_currency"),
                "proof_submitted": bool(payment.get("proof_file_id")),
                "verification": dict(payment.get("verification_payload") or {}),
            }
        current_plan = await _review_repo(db).get_current_plan_for_user(identity.telegram_id)
        due_checkin = await followup_repo.get_due_checkin_for_user(identity.telegram_id) if order["service_type"] == "FOLLOW_UP" else None
        checkins = await followup_repo.list_checkins_for_order(order["id"]) if order["service_type"] == "FOLLOW_UP" else []
        return web.json_response({
            "ok": True,
            "phase": 10,
            "user": {
                "telegram_id": identity.telegram_id,
                "first_name": identity.first_name,
                "username": identity.username,
                "language": lang,
            },
            "intake": _intake_payload(intake, lang),
            "health_review": None,
            "order": {
                "id": order["id"],
                "public_id": str(order["public_id"]),
                "state": order["state"],
                "duration_days": order["duration_days"],
                "service_type": order["service_type"],
                "meals_per_day": order["meals_per_day"],
                "start_date": order["start_date"].isoformat(),
                "ends_on": order["ends_on"].isoformat(),
                "currency": order["currency"],
                "amount": str(order["amount"]),
            },
            "payment": payment_payload,
            "plan": plan_payload(current_plan),
            "followup": {
                "enabled": order["service_type"] == "FOLLOW_UP",
                "due_checkin": None if not due_checkin else {
                    "id": due_checkin["id"],
                    "week_number": due_checkin["week_number"],
                    "status": due_checkin["status"],
                    "due_at": due_checkin["due_at"].isoformat(),
                    "submitted_at": due_checkin.get("submitted_at").isoformat() if due_checkin.get("submitted_at") else None,
                    "health_change": bool(due_checkin.get("health_change")),
                },
                "history": [{
                    "week_number": row["week_number"],
                    "status": row["status"],
                    "due_at": row["due_at"].isoformat(),
                    "submitted_at": row.get("submitted_at").isoformat() if row.get("submitted_at") else None,
                } for row in checkins],
            },
            "renewal": {
                "available": order["state"] == "RENEWAL_DUE",
                "days_remaining": max(0, (order["ends_on"] - _business_today()).days),
                "source_order_id": order["id"],
            },
            "payment_accounts": bank_accounts(),
        })

    intake = open_intake or await repo.create_or_resume_intake(identity.telegram_id, lang, source="MINI_APP")
    review = None
    if intake["state"] in {IntakeState.HEALTH_REVIEW_REQUIRED.value, IntakeState.HEALTH_APPROVED.value, IntakeState.HEALTH_DECLINED.value}:
        row = await repo.get_health_review_for_intake(intake["id"])
        if row:
            review = {
                "status": row["status"],
                "flags": list(row.get("flags") or []),
                "requested_at": row.get("requested_at").isoformat() if row.get("requested_at") else None,
                "resolved_at": row.get("resolved_at").isoformat() if row.get("resolved_at") else None,
            }

    return web.json_response({
        "ok": True,
        "phase": 10,
        "user": {
            "telegram_id": identity.telegram_id,
            "first_name": identity.first_name,
            "username": identity.username,
            "language": lang,
        },
        "intake": _intake_payload(intake, lang),
        "health_review": review,
        "order": None,
        "payment": None,
        "plan": None,
        "followup": {"enabled": False, "due_checkin": None, "history": []},
        "renewal": {
            "available": renewal_intake,
            "fresh_reassessment": renewal_intake,
            "source_order_id": latest_order["id"] if renewal_intake and latest_order else None,
        },
        "payment_accounts": bank_accounts(),
    })


async def save_country(request: web.Request) -> web.Response:
    try:
        payload = await _json(request)
        identity = await _authenticate(request, payload)
        region = normalize_region(str(payload.get("region") or ""))
    except TelegramInitDataError as exc:
        return _error(exc.code, str(exc), status=401)
    except ValueError as exc:
        return _error("COUNTRY_INVALID", str(exc), status=422)

    country_name = None
    if region == "OTHER":
        try:
            country_name = validate_other_country_name(str(payload.get("country_name") or ""))
        except ValueError as exc:
            return _error("COUNTRY_NAME_INVALID", str(exc), status=422)

    db = request.app["db"]
    user = await db.get_user(identity.telegram_id)
    if not user:
        return _error("USER_NOT_REGISTERED", "Please send /start to Coach Hilawe Bot first.", status=403)
    lang = user.get("language") if user.get("language") in LANGUAGES else "AM"
    repo = get_meal_plan_repository(db)
    intake = await repo.create_or_resume_intake(identity.telegram_id, lang, source="MINI_APP")
    intake = await repo.set_intake_country(intake["id"], identity.telegram_id, region, country_name=country_name)
    return web.json_response({
        "ok": True,
        "country": {"region": region, "name": country_name, "label": country_label(region, lang, country_name)},
        "intake_state": intake["state"],
    })


async def save_language(request: web.Request) -> web.Response:
    try:
        payload = await _json(request)
        identity = await _authenticate(request, payload)
    except TelegramInitDataError as exc:
        return _error(exc.code, str(exc), status=401)
    language = str(payload.get("language") or "").upper().strip()
    if language not in LANGUAGES:
        return _error("LANGUAGE_INVALID", "Language must be AM or EN", status=422)
    db = request.app["db"]
    user = await db.get_user(identity.telegram_id)
    if not user:
        return _error("USER_NOT_REGISTERED", "Please send /start to Coach Hilawe Bot first.", status=403)
    await db.create_or_update_user(identity.telegram_id, language=language)
    repo = get_meal_plan_repository(db)
    intake = await repo.get_open_intake_for_user(identity.telegram_id)
    if intake:
        await repo.set_intake_language(intake["id"], identity.telegram_id, language)
    return web.json_response({"ok": True, "language": language})


async def save_intake_answers(request: web.Request) -> web.Response:
    try:
        payload = await _json(request)
        _identity, _user, _lang, repo, intake = await _identity_user_intake(request, payload)
        if not intake.get("country_region"):
            return _error("COUNTRY_REQUIRED", "Choose your country before starting the assessment.", status=409)
        if intake["state"] != IntakeState.INTAKE_IN_PROGRESS.value or intake.get("completed_at"):
            return _error("INTAKE_LOCKED", "This assessment is not currently editable.", status=409)
        raw_answers = payload.get("answers")
        if not isinstance(raw_answers, dict):
            return _error("ANSWERS_INVALID", "answers must be an object", status=422)
        answers = validate_answer_patch(raw_answers)
        current_step = normalize_step(payload.get("current_step"))
    except TelegramInitDataError as exc:
        return _error(exc.code, str(exc), status=401)
    except PermissionError:
        return _error("USER_NOT_REGISTERED", "Please send /start to Coach Hilawe Bot first.", status=403)
    except ValueError as exc:
        return _error("INTAKE_VALIDATION_FAILED", str(exc), status=422)
    try:
        row = await repo.save_intake_answers(intake["id"], answers, current_step=current_step)
    except ConcurrentUpdate as exc:
        return _error("INTAKE_CONFLICT", str(exc), status=409)
    return web.json_response({"ok": True, "current_step": row.get("current_step"), "version": row.get("version"), "saved": answers})


async def _advance_completed_intake(request: web.Request, identity, lang: str, repo, intake):
    state = IntakeState(intake["state"])
    if state == IntakeState.HEALTH_REVIEW_REQUIRED:
        review = await repo.get_health_review_for_intake(intake["id"])
        return intake, {
            "outcome": "HEALTH_REVIEW_REQUIRED",
            "flags": list(review.get("flags") or []) if review else [],
        }
    if state in {IntakeState.PROFILE_READY, IntakeState.CHECKOUT_READY}:
        return intake, {"outcome": "PROFILE_READY", "nutrition_profile": dict(intake.get("nutrition_profile") or {})}
    if state == IntakeState.HEALTH_DECLINED:
        return intake, {"outcome": "HEALTH_DECLINED"}
    if state == IntakeState.HEALTH_APPROVED:
        profile = calculate_nutrition_profile(dict(intake.get("answers") or {})).to_dict()
        profile["health_gate"] = "MEDICAL_QUALIFIED_REVIEW_APPROVED"
        intake = await repo.store_nutrition_profile(intake["id"], expected_state=IntakeState.HEALTH_APPROVED, profile=profile)
        return intake, {"outcome": "PROFILE_READY", "nutrition_profile": profile}
    if state != IntakeState.INTAKE_IN_PROGRESS:
        return intake, {"outcome": state.value}

    answers = dict(intake.get("answers") or {})
    result = evaluate_health_gate(answers)
    if result.requires_review:
        summary = "; ".join(localized_flag_labels(result, "EN"))
        intake, _review = await repo.require_health_review(intake["id"], flags=result.codes(), summary=summary)
        try:
            await notify_health_review(request.app["bot"], intake=intake, identity=identity, language=lang, result=result)
        except Exception:
            logger.exception("Could not send health-review Telegram handoff; intake remains safely held")
        return intake, {"outcome": "HEALTH_REVIEW_REQUIRED", "flags": result.codes()}

    profile = calculate_nutrition_profile(answers).to_dict()
    profile["health_gate"] = "ROUTINE"
    intake = await repo.store_nutrition_profile(intake["id"], expected_state=IntakeState.INTAKE_IN_PROGRESS, profile=profile)
    return intake, {"outcome": "PROFILE_READY", "nutrition_profile": profile}


async def complete_assessment(request: web.Request) -> web.Response:
    try:
        payload = await _json(request)
        identity, _user, lang, repo, intake = await _identity_user_intake(request, payload)
    except TelegramInitDataError as exc:
        return _error(exc.code, str(exc), status=401)
    except PermissionError:
        return _error("USER_NOT_REGISTERED", "Please send /start to Coach Hilawe Bot first.", status=403)

    if not intake.get("country_region"):
        return _error("COUNTRY_REQUIRED", "Choose your country before completing the assessment.", status=409)

    if not intake.get("completed_at"):
        if intake["state"] != IntakeState.INTAKE_IN_PROGRESS.value:
            return _error("INTAKE_LOCKED", "This assessment is not currently editable.", status=409)
        answers = dict(intake.get("answers") or {})
        derived, missing = validate_complete_assessment(answers)
        if missing:
            return _error("ASSESSMENT_INCOMPLETE", "Please complete the remaining assessment questions.", status=422, details={"fields": missing})
        if derived:
            try:
                intake = await repo.save_intake_answers(intake["id"], derived, current_step="ASSESSMENT_COMPLETE")
            except ConcurrentUpdate as exc:
                return _error("INTAKE_CONFLICT", str(exc), status=409)
        try:
            intake = await repo.mark_assessment_complete(intake["id"], identity.telegram_id)
        except ConcurrentUpdate as exc:
            return _error("INTAKE_CONFLICT", str(exc), status=409)

    try:
        intake, result = await _advance_completed_intake(request, identity, lang, repo, intake)
    except (ValueError, ConcurrentUpdate) as exc:
        return _error("PROFILE_PREPARATION_FAILED", str(exc), status=409)

    return web.json_response({
        "ok": True,
        "state": intake["state"],
        "current_step": intake.get("current_step"),
        "version": intake.get("version"),
        "assessment_complete": True,
        **result,
    })


async def checkout_options(request: web.Request) -> web.Response:
    try:
        payload = await _json(request)
        _identity, _user, _lang, repo, intake = await _identity_user_intake(request, payload)
    except TelegramInitDataError as exc:
        return _error(exc.code, str(exc), status=401)
    except PermissionError:
        return _error("USER_NOT_REGISTERED", "Please send /start first.", status=403)

    if intake["state"] not in {IntakeState.PROFILE_READY.value, IntakeState.CHECKOUT_READY.value}:
        return _error("PROFILE_NOT_READY", "Your nutrition profile must be ready before configuring a plan.", status=409)

    region = intake.get("country_region")
    if region == "OTHER":
        return web.json_response({"ok": True, "pricing_mode": "MANUAL", "prices": [], "country_name": intake.get("country_name")})
    rows = await repo.get_active_prices_for_region(region)
    prices = [{
        "id": row["id"], "duration_days": row["duration_days"], "service_type": row["service_type"],
        "currency": row["currency"], "amount": str(row["amount"]), "label": row.get("label"),
    } for row in rows]
    return web.json_response({"ok": True, "pricing_mode": "AUTOMATIC", "prices": prices})


async def preview_checkout(request: web.Request) -> web.Response:
    try:
        payload = await _json(request)
        _identity, _user, _lang, repo, intake = await _identity_user_intake(request, payload)
        config = parse_plan_configuration(payload)
    except TelegramInitDataError as exc:
        return _error(exc.code, str(exc), status=401)
    except PermissionError:
        return _error("USER_NOT_REGISTERED", "Please send /start first.", status=403)
    except ValueError as exc:
        return _error("PLAN_CONFIGURATION_INVALID", str(exc), status=422)

    if intake["state"] not in {IntakeState.PROFILE_READY.value, IntakeState.CHECKOUT_READY.value}:
        return _error("PROFILE_NOT_READY", "Your nutrition profile must be ready before checkout.", status=409)

    config_payload = {
        "meals_per_day": config.meals_per_day,
        "start_date": config.start_date.isoformat(),
        "ends_on": config.ends_on.isoformat(),
        "duration_days": config.duration_days,
        "service_type": config.service_type.value,
    }
    region = intake["country_region"]

    if region == "OTHER":
        quote = await repo.create_or_get_pending_quote(
            intake["id"], country_name=intake.get("country_name") or "Other",
            duration_days=config.duration_days, service_type=config.service_type,
        )
        await repo.save_plan_configuration(intake["id"], configuration=config_payload, current_step="PRICING_REVIEW")
        if quote["status"] == "CONFIRMED":
            await repo.mark_checkout_ready(intake["id"])
            return web.json_response({
                "ok": True, "pricing_status": "READY", "configuration": config_payload,
                "price": _money(quote), "quote_id": quote["id"], "state": "CHECKOUT_READY",
            })
        return web.json_response({
            "ok": True, "pricing_status": "MANUAL_REVIEW_REQUIRED", "configuration": config_payload,
            "quote_id": quote["id"], "quote_public_id": str(quote["public_id"]), "state": intake["state"],
        })

    price = await repo.get_active_price(region, config.duration_days, config.service_type)
    await repo.save_plan_configuration(intake["id"], configuration=config_payload, current_step="CHECKOUT_PREVIEW")
    if not price:
        return web.json_response({
            "ok": True, "pricing_status": "NOT_CONFIGURED", "configuration": config_payload,
            "price": None, "state": intake["state"],
        })
    intake = await repo.mark_checkout_ready(intake["id"])
    return web.json_response({
        "ok": True, "pricing_status": "READY", "configuration": config_payload,
        "price": _money(price), "pricing_id": price["id"], "state": intake["state"],
    })


async def start_payment(request: web.Request) -> web.Response:
    try:
        payload = await _json(request)
        identity = await _authenticate(request, payload)
        db = request.app["db"]
        user = await db.get_user(identity.telegram_id)
        if not user:
            raise PermissionError("USER_NOT_REGISTERED")
        lang = user.get("language") if user.get("language") in LANGUAGES else "AM"
        repo = get_meal_plan_repository(db)
        config = parse_plan_configuration(payload)
    except TelegramInitDataError as exc:
        return _error(exc.code, str(exc), status=401)
    except PermissionError:
        return _error("USER_NOT_REGISTERED", "Please send /start first.", status=403)
    except ValueError as exc:
        return _error("PAYMENT_CONFIGURATION_INVALID", str(exc), status=422)

    existing = await repo.get_current_order_for_user(identity.telegram_id)
    if existing:
        payment = await repo.get_latest_payment_for_order(existing["id"])
        return web.json_response({
            "ok": True, "already_started": True,
            "order": {
                "id": existing["id"], "public_id": str(existing["public_id"]), "state": existing["state"],
                "duration_days": existing["duration_days"], "service_type": existing["service_type"],
                "meals_per_day": existing["meals_per_day"], "start_date": existing["start_date"].isoformat(),
                "currency": existing["currency"], "amount": str(existing["amount"]),
            },
            "payment": ({
                "id": payment["id"], "status": payment["status"],
                "expected_amount": str(payment["expected_amount"]), "expected_currency": payment["expected_currency"],
                "settlement_amount": str(payment["settlement_amount"]) if payment.get("settlement_amount") is not None else None,
                "settlement_currency": payment.get("settlement_currency"),
            } if payment else None),
            "payment_accounts": bank_accounts(),
            "telegram_instruction_sent": False,
        })

    intake = await repo.get_open_intake_for_user(identity.telegram_id)
    if not intake or intake["state"] != IntakeState.CHECKOUT_READY.value:
        return _error("CHECKOUT_NOT_READY", "Prepare checkout before starting payment.", status=409)

    region = intake["country_region"]
    pricing_id = None
    quote_id = None
    price = None
    if region == "OTHER":
        quote = await repo.get_confirmed_quote(intake["id"], config.duration_days, config.service_type)
        if not quote:
            return _error("PRICE_REVIEW_REQUIRED", "Your country price must be confirmed before payment.", status=409)
        price = quote
        quote_id = quote["id"]
    else:
        price = await repo.get_active_price(region, config.duration_days, config.service_type)
        if not price:
            return _error("PRICE_NOT_CONFIGURED", "Pricing for this selection is not configured.", status=409)
        pricing_id = price["id"]

    try:
        settlement = build_settlement(price["amount"], price["currency"])
    except ValueError as exc:
        return _error("SETTLEMENT_NOT_CONFIGURED", str(exc), status=409)

    order = await repo.create_order_from_intake(
        intake["id"], identity.telegram_id,
        duration_days=config.duration_days, service_type=config.service_type,
        meals_per_day=config.meals_per_day, start_date=config.start_date, ends_on=config.ends_on,
        region=region, country_name=intake.get("country_name"), currency=price["currency"],
        amount=price["amount"], pricing_id=pricing_id, quote_id=quote_id,
    )
    payment = await repo.create_or_get_payment_attempt(
        order["id"], identity.telegram_id,
        expected_amount=settlement.expected_amount, expected_currency=settlement.expected_currency,
        settlement_amount=settlement.settlement_amount, settlement_currency=settlement.settlement_currency,
        exchange_rate=settlement.exchange_rate,
    )
    order = await repo.get_order(order["id"])

    try:
        await notify_payment_ready(request.app["bot"], user_id=identity.telegram_id, language=lang, payment=payment)
    except Exception:
        logger.exception("Could not send Meal Plan payment instruction message")

    await repo.append_audit_event(
        entity_type="meal_order", entity_id=str(order["id"]), event_type="PAYMENT_STARTED",
        actor_type="USER", actor_telegram_id=identity.telegram_id,
        payload={"payment_id": payment["id"], "expected_currency": payment["expected_currency"]},
    )
    return web.json_response({
        "ok": True,
        "order": {
            "id": order["id"], "public_id": str(order["public_id"]), "state": order["state"],
            "duration_days": order["duration_days"], "service_type": order["service_type"],
            "meals_per_day": order["meals_per_day"], "start_date": order["start_date"].isoformat(),
            "currency": order["currency"], "amount": str(order["amount"]),
        },
        "payment": {
            "id": payment["id"], "status": payment["status"],
            "expected_amount": str(payment["expected_amount"]), "expected_currency": payment["expected_currency"],
            "settlement_amount": str(payment["settlement_amount"]), "settlement_currency": payment["settlement_currency"],
        },
        "payment_accounts": bank_accounts(),
        "telegram_instruction_sent": True,
    })




async def submit_followup_checkin(request: web.Request) -> web.Response:
    try:
        payload = await _json(request)
        identity = await _authenticate(request, payload)
        answers = validate_checkin_answers(payload.get("answers") or {})
    except TelegramInitDataError as exc:
        return _error(exc.code, str(exc), status=401)
    except CheckinValidationError as exc:
        return _error("CHECKIN_VALIDATION_FAILED", str(exc), status=422)

    db = request.app["db"]
    user = await db.get_user(identity.telegram_id)
    if not user:
        return _error("USER_NOT_REGISTERED", "Please send /start to Coach Hilawe Bot first.", status=403)
    repo = _followup_repo(db)
    due = await repo.get_due_checkin_for_user(identity.telegram_id)
    if not due:
        return _error("CHECKIN_NOT_DUE", "There is no active weekly check-in to submit.", status=409)
    if due["status"] in {"SUBMITTED", "REVIEW_REQUIRED"}:
        return web.json_response({"ok": True, "already_submitted": True, "status": due["status"]})

    baseline_answers = dict(due.get("baseline_answers") or {})
    decision = decide_revision(baseline_answers=baseline_answers, checkin_answers=answers)
    try:
        checkin, revision, already = await repo.submit_checkin(
            checkin_id=due["id"],
            telegram_id=identity.telegram_id,
            answers=answers,
            decision=decision,
            auto_revision_enabled=followup_auto_revision_enabled(),
        )
    except PermissionError:
        return _error("CHECKIN_FORBIDDEN", "This check-in does not belong to you.", status=403)
    except (ConcurrentUpdate, ValueError) as exc:
        return _error("CHECKIN_CONFLICT", str(exc), status=409)

    review_required = checkin["status"] == "REVIEW_REQUIRED"
    if review_required:
        try:
            await send_followup_review(request.app["bot"], db, checkin["id"], decision.reasons)
        except Exception:
            logger.exception("Could not send follow-up human-review card; check-in remains safely held")

    return web.json_response({
        "ok": True,
        "already_submitted": already,
        "status": checkin["status"],
        "outcome": decision.action if followup_auto_revision_enabled() else ("HUMAN_REVIEW_REQUIRED" if decision.action == "QUEUE_REVISION" else decision.action),
        "kcal_delta": decision.kcal_delta if revision else 0,
        "reasons": list(decision.reasons),
        "revision_request_id": revision["id"] if revision else None,
    })


async def start_renewal(request: web.Request) -> web.Response:
    try:
        payload = await _json(request)
        identity = await _authenticate(request, payload)
    except TelegramInitDataError as exc:
        return _error(exc.code, str(exc), status=401)
    db = request.app["db"]
    user = await db.get_user(identity.telegram_id)
    if not user:
        return _error("USER_NOT_REGISTERED", "Please send /start to Coach Hilawe Bot first.", status=403)
    lang = user.get("language") if user.get("language") in LANGUAGES else "AM"
    repo = _followup_repo(db)
    latest = await repo.latest_order_for_user(identity.telegram_id)
    if not latest or latest["state"] not in {"RENEWAL_DUE", "EXPIRED"}:
        return _error("RENEWAL_NOT_AVAILABLE", "Renewal is not available for this plan yet.", status=409)
    try:
        intake = await repo.create_renewal_intake(
            telegram_id=identity.telegram_id,
            language=lang,
            source_order_id=latest["id"],
        )
    except (ConcurrentUpdate, ValueError) as exc:
        return _error("RENEWAL_CONFLICT", str(exc), status=409)
    return web.json_response({
        "ok": True,
        "fresh_reassessment": True,
        "source_order_id": latest["id"],
        "intake": _intake_payload(intake, lang),
    })


async def download_approved_pdf(request: web.Request) -> web.StreamResponse:
    try:
        payload = await _json(request)
        identity = await _authenticate(request, payload)
    except TelegramInitDataError as exc:
        return _error(exc.code, str(exc), status=401)
    db = request.app["db"]
    user = await db.get_user(identity.telegram_id)
    if not user:
        return _error("USER_NOT_REGISTERED", "Please send /start to Coach Hilawe Bot first.", status=403)
    plan = await _review_repo(db).get_current_plan_for_user(identity.telegram_id)
    if not plan or plan.get("status") not in {"APPROVED", "DELIVERED"}:
        return _error("PLAN_NOT_READY", "Your approved Meal Plan is not available yet.", status=409)
    filename = Path(str(plan.get("pdf_filename") or "meal-plan.pdf")).name
    path = safe_local_pdf_path(str(plan.get("pdf_storage_key") or ""))
    if path is not None:
        response = web.FileResponse(path)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.headers["Cache-Control"] = "private, no-store"
        return response

    # Render/local disks are not durable. Once a review artifact has been uploaded
    # to Telegram we persist its reusable file_id and can recover the approved PDF
    # even after a local-disk restart. The short-lived Telegram file path itself is
    # never stored; it is resolved fresh for each authenticated download.
    telegram_file_id = str(plan.get("pdf_telegram_file_id") or "").strip()
    if not telegram_file_id:
        return _error("PDF_NOT_AVAILABLE", "The approved PDF is not available in durable storage.", status=409)
    try:
        telegram_file = await request.app["bot"].get_file(telegram_file_id)
        if not telegram_file.file_path:
            raise RuntimeError("Telegram did not return a file path")
        buffer = io.BytesIO()
        await request.app["bot"].download_file(telegram_file.file_path, destination=buffer)
        body = buffer.getvalue()
        if not body.startswith(b"%PDF"):
            raise RuntimeError("Recovered artifact is not a PDF")
    except Exception:
        logger.exception("Approved Meal Plan PDF recovery from Telegram failed for user %s", identity.telegram_id)
        return _error("PDF_TEMPORARILY_UNAVAILABLE", "The approved PDF is temporarily unavailable. Please try again.", status=503)
    response = web.Response(body=body, content_type="application/pdf")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Cache-Control"] = "private, no-store"
    return response


def setup_meal_plan_routes(app: web.Application) -> None:
    app.router.add_get("/api/meal/health", meal_health)
    app.router.add_post("/api/meal/bootstrap", bootstrap)
    app.router.add_post("/api/meal/country", save_country)
    app.router.add_post("/api/meal/language", save_language)
    app.router.add_post("/api/meal/intake/answers", save_intake_answers)
    app.router.add_post("/api/meal/intake/complete", complete_assessment)
    app.router.add_post("/api/meal/checkout/options", checkout_options)
    app.router.add_post("/api/meal/checkout/preview", preview_checkout)
    app.router.add_post("/api/meal/payment/start", start_payment)
    app.router.add_post("/api/meal/followup/checkin", submit_followup_checkin)
    app.router.add_post("/api/meal/renewal/start", start_renewal)
    app.router.add_post("/api/meal/plan/pdf", download_approved_pdf)
