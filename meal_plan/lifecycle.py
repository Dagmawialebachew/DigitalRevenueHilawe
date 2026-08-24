from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from database.db import Database
from meal_plan.delivery import deliver_approved_plan
from meal_plan.followup_repository import MealPlanFollowUpRepository
from meal_plan.review_repository import MealPlanReviewRepository
from meal_plan.runtime import (
    business_timezone_name,
    checkin_hour,
    checkin_missed_after_hours,
    delivery_retry_limit,
    frontend_url,
    frontend_url_is_valid,
    lifecycle_interval_seconds,
    renewal_lead_days,
    stale_job_minutes,
)

logger = logging.getLogger(__name__)


def business_timezone() -> ZoneInfo:
    name = business_timezone_name()
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        logger.error("Invalid MEAL_PLAN_BUSINESS_TIMEZONE=%s; falling back to Africa/Addis_Ababa", name)
        return ZoneInfo("Africa/Addis_Ababa")


def _miniapp_markup(language: str) -> InlineKeyboardMarkup | None:
    url = frontend_url()
    if not frontend_url_is_valid(url):
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🥗 የMeal Plan ገጽ ክፈት" if language == "AM" else "🥗 Open Meal Plan",
            web_app=WebAppInfo(url=url),
        )
    ]])


async def _notify_checkin(bot: Bot, row) -> None:
    language = row.get("language") if row.get("language") in {"AM", "EN"} else "AM"
    week = int(row["week_number"])
    if language == "AM":
        text = (
            f"📊 <b>የ{week}ኛ ሳምንት Follow-Up ጊዜዎ ደርሷል።</b>\n\n"
            "አሁን ያለዎትን ክብደት፣ ፕላኑን ምን ያህል እንደተከተሉ፣ የረሃብ/ኃይል ሁኔታ እና ማንኛውንም አዲስ የጤና ለውጥ ያስገቡ።\n\n"
            "የጤና ለውጥ ካለ automation አይቀጥልም — Coach review ይጠይቃል።"
        )
    else:
        text = (
            f"📊 <b>Your Week {week} Follow-Up is ready.</b>\n\n"
            "Update your current weight, adherence, hunger/energy, and any new health changes.\n\n"
            "Any health change blocks automated revision and is routed to Coach review."
        )
    await bot.send_message(row["user_id"], text, parse_mode="HTML", reply_markup=_miniapp_markup(language))


async def _notify_renewal(bot: Bot, db: Database, order) -> None:
    user = await db.get_user(order["user_id"])
    language = (user.get("language") if user else None) or "AM"
    days = max(0, (order["ends_on"] - datetime.now(business_timezone()).date()).days)
    if language == "AM":
        text = (
            "🔄 <b>የMeal Plan እድሳት ጊዜ ቀርቧል።</b>\n\n"
            f"የአሁኑ ፕላንዎ በ{days} ቀን ውስጥ ይጠናቀቃል። ቀጣዩ ፕላን የዛሬን ክብደት፣ ግብ፣ ምግብ ምርጫ እና የጤና ለውጦች እንደገና በመፈተሽ ይዘጋጃል — የቀድሞ PDF በቀጥታ አይደገምም።"
        )
    else:
        text = (
            "🔄 <b>Your Meal Plan renewal window is open.</b>\n\n"
            f"Your current plan ends in {days} day(s). The next plan starts from a fresh update of your current weight, goal, food preferences and health changes — it is not a blind rebuy of the same PDF."
        )
    await bot.send_message(order["user_id"], text, parse_mode="HTML", reply_markup=_miniapp_markup(language))


async def _notify_expired(bot: Bot, db: Database, order) -> None:
    user = await db.get_user(order["user_id"])
    language = (user.get("language") if user else None) or "AM"
    text = (
        "⏳ <b>የአሁኑ Meal Plan ጊዜ ተጠናቋል።</b>\n\nMini App ክፈቱና በአዲስ መረጃዎ የቀጣዩን ፕላን ይጀምሩ።"
        if language == "AM" else
        "⏳ <b>Your current Meal Plan period has ended.</b>\n\nOpen the Mini App to start the next plan from your updated information."
    )
    await bot.send_message(order["user_id"], text, parse_mode="HTML", reply_markup=_miniapp_markup(language))


async def run_lifecycle_cycle(bot: Bot, db: Database) -> dict[str, int]:
    pool = getattr(db, "_pool", None)
    if pool is None:
        raise RuntimeError("Database pool is not connected")
    repo = MealPlanFollowUpRepository(pool)
    review_repo = MealPlanReviewRepository(pool)
    tz = business_timezone()
    now_local = datetime.now(tz)
    now_utc = now_local.astimezone(timezone.utc)

    metrics: dict[str, int] = {
        "checkins_created": await repo.ensure_followup_checkins(business_tz=tz, checkin_hour=checkin_hour()),
        "checkins_due": await repo.promote_due_checkins(now_utc),
        "checkins_missed": 0,
        "renewal_due": 0,
        "expired": 0,
        "delivery_retries": 0,
        "stale_requeued": 0,
        "stale_failed": 0,
    }

    for row in await repo.due_checkins_needing_reminder(limit=25):
        try:
            await _notify_checkin(bot, row)
            await repo.append_audit(
                entity_type="CHECKIN", entity_id=str(row["id"]), event_type="CHECKIN_REMINDER_SENT",
                payload={"week_number": row["week_number"]},
            )
        except Exception:
            logger.exception("Could not send Meal Plan check-in reminder for checkin=%s", row["id"])

    missed_cutoff = now_utc - timedelta(hours=checkin_missed_after_hours())
    metrics["checkins_missed"] = await repo.mark_missed_checkins(missed_cutoff)

    renewal_orders = await repo.mark_orders_renewal_due(now_local.date(), renewal_lead_days())
    metrics["renewal_due"] = len(renewal_orders)
    for order in renewal_orders:
        if await repo.notification_needed(entity_type="ORDER", entity_id=str(order["id"]), event_type="RENEWAL_DUE_NOTIFIED"):
            try:
                await _notify_renewal(bot, db, order)
                await repo.append_audit(entity_type="ORDER", entity_id=str(order["id"]), event_type="RENEWAL_DUE_NOTIFIED")
            except Exception:
                logger.exception("Could not send Meal Plan renewal reminder for order=%s", order["id"])

    expired_orders = await repo.mark_orders_expired(now_local.date())
    metrics["expired"] = len(expired_orders)
    for order in expired_orders:
        if await repo.notification_needed(entity_type="ORDER", entity_id=str(order["id"]), event_type="EXPIRED_NOTIFIED"):
            try:
                await _notify_expired(bot, db, order)
                await repo.append_audit(entity_type="ORDER", entity_id=str(order["id"]), event_type="EXPIRED_NOTIFIED")
            except Exception:
                logger.exception("Could not send Meal Plan expiry notice for order=%s", order["id"])

    recovered = await repo.recover_stale_generation_jobs(
        now_utc - timedelta(minutes=stale_job_minutes()), limit=10,
    )
    metrics["stale_requeued"] = recovered["requeued"]
    metrics["stale_failed"] = recovered["failed"]

    for version_id in await review_repo.list_delivery_retry_versions(limit=delivery_retry_limit()):
        try:
            await deliver_approved_plan(bot, db, review_repo, int(version_id))
            metrics["delivery_retries"] += 1
        except Exception:
            logger.exception("Meal Plan delivery retry failed for version=%s", version_id)

    snapshot = await repo.operational_snapshot()
    logger.info("Meal Plan lifecycle cycle metrics=%s snapshot=%s", metrics, snapshot)
    return metrics


async def meal_plan_lifecycle_worker_loop(bot: Bot, db: Database) -> None:
    interval = lifecycle_interval_seconds()
    logger.info("Meal Plan lifecycle worker started; interval=%ss timezone=%s", interval, business_timezone().key)
    while True:
        try:
            await run_lifecycle_cycle(bot, db)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Meal Plan lifecycle worker cycle failed")
        await asyncio.sleep(interval)
