"""Admin-only reset command for testing the Meal Plan engine from scratch.

This command resets ONLY the calling admin's meal-plan related records
(intakes, orders, payments, generation jobs, plan versions, reviews, checkins,
and FSM state) without touching any other user's data or legacy tables.
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import settings
from database.db import Database
from meal_plan.runtime import admin_ids

router = Router(name="meal_plan_admin_reset")
logger = logging.getLogger(__name__)


def is_admin_user(telegram_id: int | str | None) -> bool:
    """Return True if telegram_id is in configured settings.ADMIN_IDS or MEAL_PLAN_REVIEWER_IDS."""
    if telegram_id is None:
        return False
    try:
        uid = int(telegram_id)
    except (ValueError, TypeError):
        return False

    allowed_ids = set(settings.ADMIN_IDS) | set(admin_ids())
    return uid in allowed_ids


async def reset_user_meal_plan_data(pool: Any, user_id: int) -> dict[str, int]:
    """Reset all meal-plan data for a specific user without affecting others.

    Executes in a single atomic transaction:
    1. Gathers entity counts before deletion.
    2. Nullifies foreign key circular pointers (current_plan_version_id, etc.).
    3. Deletes child records (revisions, checkins, deliveries, reviews, artifacts).
    4. Deletes generation jobs and plan versions.
    5. Deletes meal payments, orders, quotes, health reviews, and intakes.
    6. Cleans user-specific meal audit events.
    """
    user_id = int(user_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            # 1. Count records prior to deletion for confirmation reporting
            intakes_count = (
                await conn.fetchval(
                    "SELECT COUNT(*) FROM meal_intakes WHERE user_id = $1", user_id
                )
                or 0
            )
            orders_count = (
                await conn.fetchval(
                    "SELECT COUNT(*) FROM meal_orders WHERE user_id = $1", user_id
                )
                or 0
            )
            payments_count = (
                await conn.fetchval(
                    "SELECT COUNT(*) FROM meal_payments WHERE user_id = $1", user_id
                )
                or 0
            )
            checkins_count = (
                await conn.fetchval(
                    "SELECT COUNT(*) FROM meal_checkins WHERE user_id = $1", user_id
                )
                or 0
            )

            # 2. Break circular / deferral references on orders and generation jobs
            await conn.execute(
                "UPDATE meal_orders SET current_plan_version_id = NULL WHERE user_id = $1",
                user_id,
            )
            await conn.execute(
                """
                UPDATE meal_revision_requests
                   SET resulting_plan_version_id = NULL
                 WHERE order_id IN (SELECT id FROM meal_orders WHERE user_id = $1)
                """,
                user_id,
            )
            await conn.execute(
                """
                UPDATE meal_generation_jobs
                   SET plan_version_id = NULL
                 WHERE order_id IN (SELECT id FROM meal_orders WHERE user_id = $1)
                """,
                user_id,
            )

            # 3. Delete revision requests, checkins, and deliveries
            await conn.execute(
                """
                DELETE FROM meal_revision_requests
                 WHERE order_id IN (SELECT id FROM meal_orders WHERE user_id = $1)
                """,
                user_id,
            )
            await conn.execute(
                "DELETE FROM meal_checkins WHERE user_id = $1",
                user_id,
            )
            await conn.execute(
                """
                DELETE FROM meal_deliveries
                 WHERE order_id IN (SELECT id FROM meal_orders WHERE user_id = $1)
                """,
                user_id,
            )

            # 4. Delete artifacts and reviews for all plan versions of this user's orders
            await conn.execute(
                """
                DELETE FROM meal_plan_reviews
                 WHERE plan_version_id IN (
                     SELECT v.id FROM meal_plan_versions v
                     JOIN meal_orders o ON v.order_id = o.id
                     WHERE o.user_id = $1
                 )
                """,
                user_id,
            )
            await conn.execute(
                """
                DELETE FROM meal_plan_artifacts
                 WHERE plan_version_id IN (
                     SELECT v.id FROM meal_plan_versions v
                     JOIN meal_orders o ON v.order_id = o.id
                     WHERE o.user_id = $1
                 )
                """,
                user_id,
            )

            # 5. Delete generation jobs and plan versions
            await conn.execute(
                """
                DELETE FROM meal_generation_jobs
                 WHERE order_id IN (SELECT id FROM meal_orders WHERE user_id = $1)
                """,
                user_id,
            )
            await conn.execute(
                """
                DELETE FROM meal_plan_versions
                 WHERE order_id IN (SELECT id FROM meal_orders WHERE user_id = $1)
                """,
                user_id,
            )

            # 6. Delete payments
            await conn.execute(
                """
                DELETE FROM meal_payments
                 WHERE user_id = $1
                    OR order_id IN (SELECT id FROM meal_orders WHERE user_id = $1)
                """,
                user_id,
            )

            # 7. Delete orders
            await conn.execute(
                "DELETE FROM meal_orders WHERE user_id = $1",
                user_id,
            )

            # 8. Delete quotes & health reviews
            await conn.execute(
                """
                DELETE FROM meal_quotes
                 WHERE intake_id IN (SELECT id FROM meal_intakes WHERE user_id = $1)
                """,
                user_id,
            )
            await conn.execute(
                """
                DELETE FROM meal_health_reviews
                 WHERE intake_id IN (SELECT id FROM meal_intakes WHERE user_id = $1)
                """,
                user_id,
            )

            # 9. Delete intakes
            await conn.execute(
                "DELETE FROM meal_intakes WHERE user_id = $1",
                user_id,
            )

            # 10. Clean user-specific meal audit events
            await conn.execute(
                """
                DELETE FROM meal_audit_events
                 WHERE actor_telegram_id = $1
                    OR (entity_type IN ('MEAL_INTAKE', 'MEAL_ORDER', 'MEAL_PAYMENT', 'MEAL_PLAN', 'USER') AND entity_id = $1::text)
                """,
                user_id,
            )

            return {
                "intakes": intakes_count,
                "orders": orders_count,
                "payments": payments_count,
                "checkins": checkins_count,
            }


@router.message(Command("reset", "reset_meal_plan"))
async def handle_admin_reset_command(
    message: types.Message, state: FSMContext, db: Database
) -> None:
    """Handle /reset command for authorized admins."""
    if not message.from_user:
        return

    admin_id = message.from_user.id
    if not is_admin_user(admin_id):
        logger.warning("Unauthorized /reset attempted by non-admin user_id=%s", admin_id)
        return

    # Target defaults to the calling admin themselves
    target_id = admin_id
    args = (message.text or "").strip().split()
    if len(args) > 1 and args[1].isdigit():
        target_id = int(args[1])

    pool = getattr(db, "_pool", None)
    if not pool:
        await message.answer("⚠️ Database connection pool is currently unavailable.")
        return

    try:
        # Clear FSM context if resetting self
        if target_id == admin_id:
            await state.clear()

        counts = await reset_user_meal_plan_data(pool, target_id)

        target_display = (
            f"Your account (<code>{admin_id}</code>)"
            if target_id == admin_id
            else f"User <code>{target_id}</code>"
        )

        reply_text = (
            f"🧹 <b>Meal Plan Test State Reset Complete!</b>\n\n"
            f"👤 <b>Target:</b> {target_display}\n"
            f"• <b>Intakes Cleared:</b> {counts['intakes']}\n"
            f"• <b>Orders Cleared:</b> {counts['orders']}\n"
            f"• <b>Payments Cleared:</b> {counts['payments']}\n"
            f"• <b>Check-Ins Cleared:</b> {counts['checkins']}\n"
            f"• <b>FSM Session:</b> Cleared ✅\n\n"
            f"<i>🔒 Safety Guarantee: Only meal plan records for this specific account were removed. "
            f"Other users' records and all general bot data remain completely untouched.</i>\n\n"
            f"👉 You can now test the flow from the very beginning by tapping <b>🥗 Meal Plan</b> or typing <b>/start</b>."
        )
        await message.answer(reply_text, parse_mode="HTML")
        logger.info(
            "Admin %s reset meal plan data for user %s: %s",
            admin_id,
            target_id,
            counts,
        )
    except Exception as exc:
        logger.exception("Failed to reset meal plan data for user %s: %s", target_id, exc)
        await message.answer(
            f"❌ <b>Reset Failed:</b> <code>{exc}</code>",
            parse_mode="HTML",
        )
