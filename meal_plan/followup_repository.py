from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from meal_plan.followup_policy import RevisionDecision
from meal_plan.repository import ConcurrentUpdate, RecordNotFound


class MealPlanFollowUpRepository:
    def __init__(self, pool):
        self.pool = pool

    async def ensure_followup_checkins(self, *, business_tz, checkin_hour: int) -> int:
        """Create the four weekly check-ins for eligible 30-day FOLLOW_UP orders.

        Unique(order_id, week_number) makes this safe to run on every lifecycle tick.
        """
        async with self.pool.acquire() as conn:
            orders = await conn.fetch(
                """
                SELECT id,user_id,start_date
                FROM meal_orders
                WHERE service_type='FOLLOW_UP' AND duration_days=30
                  AND state IN ('ACTIVE','RENEWAL_DUE')
                """
            )
            created = 0
            for order in orders:
                for week in range(1, 5):
                    local_due_date = order["start_date"] + timedelta(days=week * 7 - 1)
                    local_due = datetime(
                        local_due_date.year, local_due_date.month, local_due_date.day,
                        checkin_hour, 0, 0, tzinfo=business_tz,
                    )
                    status = await conn.execute(
                        """
                        INSERT INTO meal_checkins(order_id,user_id,week_number,status,due_at)
                        VALUES($1,$2,$3,'SCHEDULED',$4)
                        ON CONFLICT(order_id,week_number) DO NOTHING
                        """,
                        order["id"], order["user_id"], week, local_due,
                    )
                    if status.endswith("1"):
                        created += 1
            return created

    async def promote_due_checkins(self, now: datetime) -> int:
        async with self.pool.acquire() as conn:
            status = await conn.execute(
                """
                UPDATE meal_checkins
                SET status='DUE',updated_at=NOW()
                WHERE status='SCHEDULED' AND due_at <= $1
                """,
                now,
            )
            try:
                return int(status.split()[-1])
            except (ValueError, IndexError):
                return 0

    async def due_checkins_needing_reminder(self, *, limit: int = 25):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT c.*,o.public_id AS order_public_id,o.ends_on,o.state AS order_state,
                       u.language,u.full_name
                FROM meal_checkins c
                JOIN meal_orders o ON o.id=c.order_id
                LEFT JOIN users u ON u.telegram_id=c.user_id
                WHERE c.status='DUE'
                  AND NOT EXISTS (
                    SELECT 1 FROM meal_audit_events a
                    WHERE a.entity_type='CHECKIN' AND a.entity_id=c.id::text
                      AND a.event_type='CHECKIN_REMINDER_SENT'
                  )
                ORDER BY c.due_at,c.id
                LIMIT $1
                """,
                limit,
            )

    async def append_audit(
        self,
        *,
        entity_type: str,
        entity_id: str,
        event_type: str,
        actor_type: str = "SYSTEM",
        actor_telegram_id: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                INSERT INTO meal_audit_events(entity_type,entity_id,event_type,actor_type,actor_telegram_id,payload)
                VALUES($1,$2,$3,$4,$5,$6::jsonb) RETURNING id
                """,
                entity_type, entity_id, event_type, actor_type, actor_telegram_id,
                json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":")),
            )

    async def mark_missed_checkins(self, cutoff: datetime) -> int:
        async with self.pool.acquire() as conn:
            status = await conn.execute(
                """
                UPDATE meal_checkins
                SET status='MISSED',updated_at=NOW()
                WHERE status='DUE' AND due_at < $1
                """,
                cutoff,
            )
            try:
                return int(status.split()[-1])
            except (ValueError, IndexError):
                return 0

    async def get_due_checkin_for_user(self, telegram_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT c.*,o.service_type,o.state AS order_state,o.ends_on,
                       i.answers AS baseline_answers,i.nutrition_profile
                FROM meal_checkins c
                JOIN meal_orders o ON o.id=c.order_id
                JOIN meal_intakes i ON i.id=o.intake_id
                WHERE c.user_id=$1 AND c.status IN ('DUE','REVIEW_REQUIRED','SUBMITTED')
                  AND o.state IN ('ACTIVE','RENEWAL_DUE')
                ORDER BY c.week_number DESC,c.id DESC LIMIT 1
                """,
                telegram_id,
            )

    async def list_checkins_for_order(self, order_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT id,week_number,status,due_at,submitted_at,health_change,answers
                FROM meal_checkins WHERE order_id=$1 ORDER BY week_number
                """,
                order_id,
            )

    async def submit_checkin(
        self,
        *,
        checkin_id: int,
        telegram_id: int,
        answers: dict[str, Any],
        decision: RevisionDecision,
        auto_revision_enabled: bool,
    ):
        answers_json = json.dumps(answers, ensure_ascii=False, separators=(",", ":"))
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                checkin = await conn.fetchrow(
                    "SELECT * FROM meal_checkins WHERE id=$1 FOR UPDATE",
                    checkin_id,
                )
                if not checkin:
                    raise RecordNotFound("Check-in not found")
                if checkin["user_id"] != telegram_id:
                    raise PermissionError("Check-in does not belong to this user")
                if checkin["status"] in {"CLOSED", "MISSED"}:
                    raise ConcurrentUpdate("This check-in is already closed")
                if checkin["status"] in {"SUBMITTED", "REVIEW_REQUIRED"}:
                    revision = await conn.fetchrow(
                        "SELECT * FROM meal_revision_requests WHERE checkin_id=$1 ORDER BY id DESC LIMIT 1",
                        checkin_id,
                    )
                    return checkin, revision, True
                if checkin["status"] != "DUE":
                    raise ConcurrentUpdate("This check-in is not due yet")

                order = await conn.fetchrow("SELECT * FROM meal_orders WHERE id=$1 FOR UPDATE", checkin["order_id"])
                if not order or order["state"] not in {"ACTIVE", "RENEWAL_DUE"}:
                    raise ConcurrentUpdate("The Meal Plan is not active")

                if decision.action == "HEALTH_REVIEW_REQUIRED":
                    new_status = "REVIEW_REQUIRED"
                elif decision.action == "QUEUE_REVISION" and auto_revision_enabled:
                    new_status = "SUBMITTED"
                elif decision.action == "QUEUE_REVISION":
                    new_status = "REVIEW_REQUIRED"
                else:
                    new_status = "CLOSED"

                checkin = await conn.fetchrow(
                    """
                    UPDATE meal_checkins
                    SET status=$3,answers=$4::jsonb,health_change=$5,submitted_at=NOW(),
                        reviewed_at=CASE WHEN $3='CLOSED' THEN NOW() ELSE reviewed_at END,
                        updated_at=NOW()
                    WHERE id=$1 AND user_id=$2 AND status='DUE'
                    RETURNING *
                    """,
                    checkin_id, telegram_id, new_status, answers_json, bool(answers.get("health_change")),
                )
                if not checkin:
                    raise ConcurrentUpdate("Check-in changed while it was being submitted")

                revision = None
                if decision.action == "QUEUE_REVISION" and auto_revision_enabled:
                    revision = await conn.fetchrow(
                        """
                        INSERT INTO meal_revision_requests(order_id,checkin_id,status,reason,requested_by)
                        VALUES($1,$2,'GENERATION_QUEUED',$3,$4)
                        ON CONFLICT DO NOTHING
                        RETURNING *
                        """,
                        order["id"], checkin_id, "; ".join(decision.reasons), telegram_id,
                    )
                    if revision is None:
                        revision = await conn.fetchrow(
                            "SELECT * FROM meal_revision_requests WHERE checkin_id=$1 ORDER BY id DESC LIMIT 1",
                            checkin_id,
                        )
                    key = f"meal-order:{order['id']}:followup-week-{checkin['week_number']}:revision"
                    payload = {
                        "revision_request_id": revision["id"],
                        "revision": {
                            "checkin_id": checkin_id,
                            "week_number": checkin["week_number"],
                            "kcal_delta": decision.kcal_delta,
                            "reasons": list(decision.reasons),
                            "answer_patch": decision.answer_patch,
                            "current_weight_kg": answers.get("current_weight_kg"),
                        },
                    }
                    await conn.execute(
                        """
                        INSERT INTO meal_generation_jobs(public_id,order_id,job_type,status,stage,idempotency_key,payload)
                        VALUES($1,$2,'REVISION','PENDING','QUEUED',$3,$4::jsonb)
                        ON CONFLICT(idempotency_key) DO NOTHING
                        """,
                        uuid.uuid4(), order["id"], key,
                        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    )

                await conn.execute(
                    """
                    INSERT INTO meal_audit_events(entity_type,entity_id,event_type,actor_type,actor_telegram_id,payload)
                    VALUES('CHECKIN',$1,'CHECKIN_SUBMITTED','USER',$2,$3::jsonb)
                    """,
                    str(checkin_id), telegram_id,
                    json.dumps(decision.to_payload(), ensure_ascii=False, separators=(",", ":")),
                )
                return checkin, revision, False

    async def mark_orders_renewal_due(self, today: date, lead_days: int):
        threshold = today + timedelta(days=lead_days)
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                """
                UPDATE meal_orders
                SET state='RENEWAL_DUE',updated_at=NOW(),version=version+1
                WHERE state='ACTIVE' AND ends_on <= $1 AND ends_on >= $2
                RETURNING *
                """,
                threshold, today,
            )

    async def mark_orders_expired(self, today: date):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                """
                UPDATE meal_orders
                SET state='EXPIRED',expired_at=COALESCE(expired_at,NOW()),updated_at=NOW(),version=version+1
                WHERE state IN ('ACTIVE','RENEWAL_DUE') AND ends_on < $1
                RETURNING *
                """,
                today,
            )

    async def notification_needed(self, *, entity_type: str, entity_id: str, event_type: str) -> bool:
        async with self.pool.acquire() as conn:
            exists = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM meal_audit_events
                    WHERE entity_type=$1 AND entity_id=$2 AND event_type=$3
                )
                """,
                entity_type, entity_id, event_type,
            )
            return not bool(exists)

    async def latest_order_for_user(self, telegram_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM meal_orders WHERE user_id=$1 ORDER BY id DESC LIMIT 1",
                telegram_id,
            )

    async def create_renewal_intake(self, *, telegram_id: int, language: str, source_order_id: int):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                order = await conn.fetchrow(
                    "SELECT * FROM meal_orders WHERE id=$1 AND user_id=$2 FOR UPDATE",
                    source_order_id, telegram_id,
                )
                if not order:
                    raise RecordNotFound("Previous Meal Plan order not found")
                if order["state"] not in {"RENEWAL_DUE", "EXPIRED"}:
                    raise ConcurrentUpdate("Renewal is not available for this order yet")
                existing = await conn.fetchrow(
                    "SELECT * FROM meal_intakes WHERE user_id=$1 AND closed_at IS NULL ORDER BY id DESC LIMIT 1 FOR UPDATE",
                    telegram_id,
                )
                if existing:
                    return existing
                intake = await conn.fetchrow(
                    """
                    INSERT INTO meal_intakes(public_id,user_id,language,state,source,current_step)
                    VALUES($1,$2,$3,'COUNTRY_REQUIRED',$4,'WELCOME') RETURNING *
                    """,
                    uuid.uuid4(), telegram_id, language if language in {"AM", "EN"} else "AM",
                    f"RENEWAL:{source_order_id}",
                )
                await conn.execute(
                    """
                    INSERT INTO meal_audit_events(entity_type,entity_id,event_type,actor_type,actor_telegram_id,payload)
                    VALUES('ORDER',$1,'RENEWAL_INTAKE_STARTED','USER',$2,$3::jsonb)
                    """,
                    str(source_order_id), telegram_id,
                    json.dumps({"renewal_intake_id": intake["id"]}),
                )
                return intake

    async def recover_stale_generation_jobs(self, cutoff: datetime, *, limit: int = 10) -> dict[str, int]:
        requeued = 0
        failed = 0
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                jobs = await conn.fetch(
                    """
                    SELECT * FROM meal_generation_jobs
                    WHERE status='RUNNING' AND locked_at IS NOT NULL AND locked_at < $1
                    ORDER BY locked_at LIMIT $2
                    FOR UPDATE SKIP LOCKED
                    """,
                    cutoff, limit,
                )
                for job in jobs:
                    if job["attempt_count"] < job["max_attempts"]:
                        await conn.execute(
                            """
                            UPDATE meal_generation_jobs
                            SET status='PENDING',stage='QUEUED',locked_at=NULL,locked_by=NULL,
                                last_error_code='STALE_WORKER_RECOVERY',
                                last_error_message='Recovered stale RUNNING job after worker interruption',updated_at=NOW()
                            WHERE id=$1
                            """,
                            job["id"],
                        )
                        if job["job_type"] != "REVISION":
                            await conn.execute(
                                """
                                UPDATE meal_orders SET state='GENERATION_QUEUED',updated_at=NOW(),version=version+1
                                WHERE id=$1 AND state='GENERATING'
                                """,
                                job["order_id"],
                            )
                        requeued += 1
                    else:
                        await conn.execute(
                            """
                            UPDATE meal_generation_jobs
                            SET status='FAILED',locked_at=NULL,locked_by=NULL,finished_at=NOW(),
                                last_error_code='STALE_MAX_ATTEMPTS',
                                last_error_message='Stale generation job exhausted retry limit',updated_at=NOW()
                            WHERE id=$1
                            """,
                            job["id"],
                        )
                        if job["job_type"] != "REVISION":
                            await conn.execute(
                                """
                                UPDATE meal_orders SET state='GENERATION_FAILED',updated_at=NOW(),version=version+1
                                WHERE id=$1 AND state='GENERATING'
                                """,
                                job["order_id"],
                            )
                        failed += 1
        return {"requeued": requeued, "failed": failed}

    async def operational_snapshot(self) -> dict[str, int]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                  (SELECT COUNT(*) FROM meal_orders WHERE state IN ('ACTIVE','RENEWAL_DUE')) AS active_orders,
                  (SELECT COUNT(*) FROM meal_generation_jobs WHERE status='PENDING') AS queued_jobs,
                  (SELECT COUNT(*) FROM meal_generation_jobs WHERE status='RUNNING') AS running_jobs,
                  (SELECT COUNT(*) FROM meal_plan_versions WHERE status='REVIEW_PENDING') AS review_pending,
                  (SELECT COUNT(*) FROM meal_deliveries WHERE status='FAILED') AS failed_deliveries,
                  (SELECT COUNT(*) FROM meal_checkins WHERE status='DUE') AS due_checkins,
                  (SELECT COUNT(*) FROM meal_checkins WHERE status='REVIEW_REQUIRED') AS checkins_review_required
                """
            )
            return {key: int(row[key] or 0) for key in row.keys()}

    async def get_checkin_review_context(self, checkin_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT c.*,o.public_id AS order_public_id,o.service_type,o.state AS order_state,
                       i.answers AS baseline_answers,u.full_name,u.username
                FROM meal_checkins c
                JOIN meal_orders o ON o.id=c.order_id
                JOIN meal_intakes i ON i.id=o.intake_id
                LEFT JOIN users u ON u.telegram_id=c.user_id
                WHERE c.id=$1
                """,
                checkin_id,
            )

    async def close_review_checkin(self, checkin_id: int, reviewer_id: int, *, notes: str | None = None):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow("SELECT * FROM meal_checkins WHERE id=$1 FOR UPDATE", checkin_id)
                if not row:
                    raise RecordNotFound("Check-in not found")
                if row["status"] == "CLOSED":
                    return row
                if row["status"] != "REVIEW_REQUIRED":
                    raise ConcurrentUpdate("This check-in is not awaiting human review")
                row = await conn.fetchrow(
                    """
                    UPDATE meal_checkins SET status='CLOSED',reviewed_at=NOW(),reviewed_by=$2,updated_at=NOW()
                    WHERE id=$1 AND status='REVIEW_REQUIRED' RETURNING *
                    """,
                    checkin_id, reviewer_id,
                )
                await conn.execute(
                    """
                    INSERT INTO meal_audit_events(entity_type,entity_id,event_type,actor_type,actor_telegram_id,payload)
                    VALUES('CHECKIN',$1,'CHECKIN_REVIEW_CLOSED','REVIEWER',$2,$3::jsonb)
                    """,
                    str(checkin_id), reviewer_id,
                    json.dumps({"notes": notes or ""}, ensure_ascii=False),
                )
                return row
