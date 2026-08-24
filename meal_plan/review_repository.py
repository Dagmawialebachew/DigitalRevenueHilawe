from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from meal_plan.repository import ConcurrentUpdate, RecordNotFound
from meal_plan.followup_policy import decide_revision


class MealPlanReviewRepository:
    """Atomic persistence operations for generation, review, replacement and delivery.

    The Phase 1 schema already contains the required tables, so Phase 8 deliberately
    adds no schema migration. Every mutating operation locks the relevant order or
    version row and uses idempotency keys where retries are expected.
    """

    def __init__(self, pool):
        self.pool = pool

    async def claim_generation_job(self, worker_id: str):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                job = await conn.fetchrow(
                    """
                    WITH candidate AS (
                        SELECT id
                        FROM meal_generation_jobs
                        WHERE status='PENDING'
                        ORDER BY created_at, id
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE meal_generation_jobs j
                    SET status='RUNNING', stage='TARGETS', attempt_count=attempt_count+1,
                        locked_at=NOW(), locked_by=$1, started_at=COALESCE(started_at,NOW()), updated_at=NOW()
                    FROM candidate c
                    WHERE j.id=c.id
                    RETURNING j.*
                    """,
                    worker_id,
                )
                if not job:
                    return None
                order = await conn.fetchrow("SELECT * FROM meal_orders WHERE id=$1 FOR UPDATE", job["order_id"])
                if not order:
                    await conn.execute(
                        "UPDATE meal_generation_jobs SET status='FAILED',last_error_code='ORDER_NOT_FOUND',finished_at=NOW(),updated_at=NOW() WHERE id=$1",
                        job["id"],
                    )
                    return None
                if job["job_type"] == "REVISION":
                    # Follow-up revisions are generated in the background while the
                    # already-approved plan remains ACTIVE/RENEWAL_DUE for the client.
                    if order["state"] not in {"ACTIVE", "RENEWAL_DUE"}:
                        await conn.execute(
                            """
                            UPDATE meal_generation_jobs SET status='FAILED',last_error_code='ORDER_STATE_INVALID',
                                last_error_message=$2,finished_at=NOW(),updated_at=NOW()
                            WHERE id=$1
                            """,
                            job["id"], f"Revision cannot run while order state is {order['state']}",
                        )
                        return None
                elif order["state"] == "GENERATION_QUEUED":
                    order = await conn.fetchrow(
                        """
                        UPDATE meal_orders SET state='GENERATING',updated_at=NOW(),version=version+1
                        WHERE id=$1 AND state='GENERATION_QUEUED' RETURNING *
                        """,
                        order["id"],
                    )
                elif order["state"] != "GENERATING":
                    await conn.execute(
                        """
                        UPDATE meal_generation_jobs SET status='FAILED',last_error_code='ORDER_STATE_INVALID',
                            last_error_message=$2,finished_at=NOW(),updated_at=NOW()
                        WHERE id=$1
                        """,
                        job["id"], f"Order state is {order['state']}",
                    )
                    return None
                return job

    async def set_job_stage(self, job_id: int, stage: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE meal_generation_jobs SET stage=$2,updated_at=NOW() WHERE id=$1 AND status='RUNNING'",
                job_id, stage,
            )

    async def get_generation_context(self, job_id: int):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT j.*, o.public_id AS order_public_id, o.user_id, o.intake_id, o.state AS order_state,
                       o.duration_days, o.service_type, o.meals_per_day, o.start_date, o.ends_on,
                       o.region, o.country_name, o.currency, o.amount,
                       i.public_id AS intake_public_id, i.language, i.answers, i.nutrition_profile,
                       u.full_name, u.username
                FROM meal_generation_jobs j
                JOIN meal_orders o ON o.id=j.order_id
                JOIN meal_intakes i ON i.id=o.intake_id
                LEFT JOIN users u ON u.telegram_id=o.user_id
                WHERE j.id=$1
                """,
                job_id,
            )
            if not row:
                raise RecordNotFound("Generation job not found")
            return row

    async def create_generated_version(
        self,
        job_id: int,
        *,
        plan_json: dict[str, Any],
        engine_version: str,
        dataset_version: str,
        settings_version: str,
        generation_seed: str | None,
    ):
        payload = json.dumps(plan_json, ensure_ascii=False, separators=(",", ":"))
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                job = await conn.fetchrow("SELECT * FROM meal_generation_jobs WHERE id=$1 FOR UPDATE", job_id)
                if not job:
                    raise RecordNotFound("Generation job not found")
                if job["plan_version_id"]:
                    return await conn.fetchrow("SELECT * FROM meal_plan_versions WHERE id=$1", job["plan_version_id"])
                if job["status"] != "RUNNING":
                    raise ConcurrentUpdate("Generation job is no longer running")
                order = await conn.fetchrow("SELECT * FROM meal_orders WHERE id=$1 FOR UPDATE", job["order_id"])
                allowed_states = {"ACTIVE", "RENEWAL_DUE"} if job["job_type"] == "REVISION" else {"GENERATING"}
                if not order or order["state"] not in allowed_states:
                    raise ConcurrentUpdate("Order is no longer in a valid generation state")
                version_number = await conn.fetchval(
                    "SELECT COALESCE(MAX(version_number),0)+1 FROM meal_plan_versions WHERE order_id=$1",
                    order["id"],
                )
                source = "REVISION" if job["job_type"] == "REVISION" else "GENERATED"
                version = await conn.fetchrow(
                    """
                    INSERT INTO meal_plan_versions(
                        public_id,order_id,version_number,status,source,plan_json,detail_source,
                        engine_version,dataset_version,settings_version,generation_seed,generated_at
                    ) VALUES($1,$2,$3,'DRAFT',$4,$5::jsonb,'STRUCTURED',$6,$7,$8,$9,NOW())
                    RETURNING *
                    """,
                    uuid.uuid4(), order["id"], version_number, source, payload,
                    engine_version, dataset_version, settings_version, generation_seed,
                )
                await conn.execute(
                    "UPDATE meal_generation_jobs SET plan_version_id=$2,stage='DOCUMENTS',updated_at=NOW() WHERE id=$1",
                    job_id, version["id"],
                )
                if job["job_type"] == "REVISION":
                    job_payload = dict(job.get("payload") or {})
                    revision_request_id = job_payload.get("revision_request_id")
                    if revision_request_id:
                        await conn.execute(
                            """
                            UPDATE meal_revision_requests
                            SET status='IN_REVIEW',resulting_plan_version_id=$2,updated_at=NOW()
                            WHERE id=$1 AND status IN ('PENDING','GENERATION_QUEUED','IN_REVIEW')
                            """,
                            int(revision_request_id), version["id"],
                        )
                return version

    async def store_artifact(
        self,
        plan_version_id: int,
        *,
        artifact_type: str,
        storage_key: str,
        original_filename: str,
        content_sha256: str,
        byte_size: int,
        storage_backend: str = "LOCAL",
        telegram_file_id: str | None = None,
        created_by: int | None = None,
    ):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                INSERT INTO meal_plan_artifacts(
                    plan_version_id,artifact_type,storage_backend,storage_key,original_filename,
                    content_sha256,byte_size,telegram_file_id,created_by
                ) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT(plan_version_id,artifact_type) DO UPDATE SET
                    storage_backend=EXCLUDED.storage_backend,storage_key=EXCLUDED.storage_key,
                    original_filename=EXCLUDED.original_filename,content_sha256=EXCLUDED.content_sha256,
                    byte_size=EXCLUDED.byte_size,telegram_file_id=COALESCE(EXCLUDED.telegram_file_id,meal_plan_artifacts.telegram_file_id),
                    created_by=COALESCE(EXCLUDED.created_by,meal_plan_artifacts.created_by),created_at=NOW()
                RETURNING *
                """,
                plan_version_id, artifact_type, storage_backend, storage_key, original_filename,
                content_sha256, byte_size, telegram_file_id, created_by,
            )

    async def set_artifact_telegram_file_id(self, plan_version_id: int, artifact_type: str, telegram_file_id: str):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                UPDATE meal_plan_artifacts
                SET telegram_file_id=$3,
                    storage_backend=CASE
                        WHEN storage_backend='LOCAL' THEN 'LOCAL_TELEGRAM'
                        ELSE storage_backend
                    END
                WHERE plan_version_id=$1 AND artifact_type=$2 RETURNING *
                """,
                plan_version_id, artifact_type, telegram_file_id,
            )

    async def get_version(self, plan_version_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM meal_plan_versions WHERE id=$1", plan_version_id)

    async def get_version_by_review_message(self, review_chat_id: int, review_message_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT * FROM meal_plan_versions
                WHERE review_chat_id=$1 AND review_message_id=$2
                ORDER BY id DESC LIMIT 1
                """,
                review_chat_id, review_message_id,
            )

    async def get_review_context(self, plan_version_id: int):
        async with self.pool.acquire() as conn:
            version = await conn.fetchrow(
                """
                SELECT v.*, o.user_id,o.public_id AS order_public_id,o.state AS order_state,
                       o.duration_days,o.service_type,o.meals_per_day,o.start_date,o.ends_on,o.region,o.country_name,o.currency,o.amount,
                       i.language,i.answers,i.nutrition_profile,u.full_name,u.username
                FROM meal_plan_versions v
                JOIN meal_orders o ON o.id=v.order_id
                JOIN meal_intakes i ON i.id=o.intake_id
                LEFT JOIN users u ON u.telegram_id=o.user_id
                WHERE v.id=$1
                """,
                plan_version_id,
            )
            if not version:
                raise RecordNotFound("Plan version not found")
            artifacts = await conn.fetch(
                "SELECT * FROM meal_plan_artifacts WHERE plan_version_id=$1 ORDER BY artifact_type",
                plan_version_id,
            )
            return version, artifacts

    async def mark_review_handoff(self, plan_version_id: int, *, chat_id: int, message_id: int):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                version = await conn.fetchrow("SELECT * FROM meal_plan_versions WHERE id=$1 FOR UPDATE", plan_version_id)
                if not version:
                    raise RecordNotFound("Plan version not found")
                if version["status"] == "REVIEW_PENDING" and version["review_message_id"]:
                    return version
                if version["status"] != "DRAFT":
                    raise ConcurrentUpdate("Plan version is not ready for review handoff")
                order = await conn.fetchrow("SELECT * FROM meal_orders WHERE id=$1 FOR UPDATE", version["order_id"])
                version = await conn.fetchrow(
                    """
                    UPDATE meal_plan_versions
                    SET status='REVIEW_PENDING',review_chat_id=$2,review_message_id=$3,updated_at=NOW()
                    WHERE id=$1 AND status='DRAFT' RETURNING *
                    """,
                    plan_version_id, chat_id, message_id,
                )
                if order and order["state"] in {"GENERATING", "CHANGES_REQUESTED", "GENERATION_QUEUED"}:
                    await conn.execute(
                        "UPDATE meal_orders SET state='REVIEW_PENDING',updated_at=NOW(),version=version+1 WHERE id=$1",
                        order["id"],
                    )
                return version

    async def finish_generation_job(self, job_id: int, plan_version_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE meal_generation_jobs SET status='SUCCEEDED',stage='COMPLETE',plan_version_id=$2,
                    locked_at=NULL,locked_by=NULL,finished_at=NOW(),updated_at=NOW()
                WHERE id=$1 AND status='RUNNING'
                """,
                job_id, plan_version_id,
            )

    async def fail_generation_job(self, job_id: int, *, code: str, message: str):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                job = await conn.fetchrow("SELECT * FROM meal_generation_jobs WHERE id=$1 FOR UPDATE", job_id)
                if not job:
                    return
                await conn.execute(
                    """
                    UPDATE meal_generation_jobs SET status='FAILED',last_error_code=$2,last_error_message=$3,
                        locked_at=NULL,locked_by=NULL,finished_at=NOW(),updated_at=NOW()
                    WHERE id=$1
                    """,
                    job_id, code[:80], message[:2000],
                )
                await conn.execute(
                    """
                    UPDATE meal_orders SET state='GENERATION_FAILED',updated_at=NOW(),version=version+1
                    WHERE id=$1 AND state='GENERATING'
                    """,
                    job["order_id"],
                )

    async def record_review_action(self, plan_version_id: int, reviewer_id: int, action: str, *, notes: str | None = None, metadata: dict[str, Any] | None = None):
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                INSERT INTO meal_plan_reviews(plan_version_id,reviewer_telegram_id,action,notes,metadata)
                VALUES($1,$2,$3,$4,$5::jsonb) RETURNING id
                """,
                plan_version_id, reviewer_id, action, notes,
                json.dumps(metadata or {}, ensure_ascii=False, separators=(",", ":")),
            )

    async def approve_version(self, plan_version_id: int, reviewer_id: int):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                version = await conn.fetchrow("SELECT * FROM meal_plan_versions WHERE id=$1 FOR UPDATE", plan_version_id)
                if not version:
                    raise RecordNotFound("Plan version not found")
                order = await conn.fetchrow("SELECT * FROM meal_orders WHERE id=$1 FOR UPDATE", version["order_id"])
                if not order:
                    raise RecordNotFound("Order not found")
                if version["status"] in {"APPROVED", "DELIVERED"} and order["current_plan_version_id"] == version["id"]:
                    return version, order

                in_place_revision = order["state"] in {"ACTIVE", "RENEWAL_DUE"}
                if version["status"] != "REVIEW_PENDING":
                    raise ConcurrentUpdate("This plan version is no longer awaiting approval")
                if not in_place_revision and order["state"] != "REVIEW_PENDING":
                    raise ConcurrentUpdate("This plan version is no longer awaiting approval")

                artifact_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM meal_plan_artifacts WHERE plan_version_id=$1 AND artifact_type IN ('DOCX','PDF')",
                    plan_version_id,
                )
                if int(artifact_count or 0) != 2:
                    raise ConcurrentUpdate("Both DOCX and PDF artifacts are required before approval")

                previous_current = order.get("current_plan_version_id")
                version = await conn.fetchrow(
                    """
                    UPDATE meal_plan_versions SET status='APPROVED',approved_by=$2,approved_at=NOW(),updated_at=NOW()
                    WHERE id=$1 AND status='REVIEW_PENDING' RETURNING *
                    """,
                    plan_version_id, reviewer_id,
                )
                await conn.execute(
                    """
                    UPDATE meal_plan_versions SET status='SUPERSEDED',updated_at=NOW()
                    WHERE order_id=$1 AND id<>$2 AND status IN ('DRAFT','REVIEW_PENDING','CHANGES_REQUESTED')
                    """,
                    order["id"], plan_version_id,
                )

                if in_place_revision:
                    if previous_current and int(previous_current) != int(plan_version_id):
                        await conn.execute(
                            """
                            UPDATE meal_plan_versions SET status='SUPERSEDED',updated_at=NOW()
                            WHERE id=$1 AND status='DELIVERED'
                            """,
                            previous_current,
                        )
                    order = await conn.fetchrow(
                        """
                        UPDATE meal_orders SET current_plan_version_id=$2,approved_at=NOW(),updated_at=NOW(),version=version+1
                        WHERE id=$1 AND state IN ('ACTIVE','RENEWAL_DUE') RETURNING *
                        """,
                        order["id"], plan_version_id,
                    )
                else:
                    order = await conn.fetchrow(
                        """
                        UPDATE meal_orders SET state='APPROVED',current_plan_version_id=$2,
                            approved_at=COALESCE(approved_at,NOW()),updated_at=NOW(),version=version+1
                        WHERE id=$1 AND state='REVIEW_PENDING' RETURNING *
                        """,
                        order["id"], plan_version_id,
                    )
                await conn.execute(
                    """
                    INSERT INTO meal_plan_reviews(plan_version_id,reviewer_telegram_id,action,metadata)
                    VALUES($1,$2,'APPROVE',$3::jsonb)
                    """,
                    plan_version_id, reviewer_id,
                    json.dumps({"in_place_revision": in_place_revision}),
                )
                return version, order

    async def queue_regeneration(self, plan_version_id: int, reviewer_id: int):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                version = await conn.fetchrow("SELECT * FROM meal_plan_versions WHERE id=$1 FOR UPDATE", plan_version_id)
                if not version:
                    raise RecordNotFound("Plan version not found")
                order = await conn.fetchrow("SELECT * FROM meal_orders WHERE id=$1 FOR UPDATE", version["order_id"])
                if not order:
                    raise RecordNotFound("Order not found")
                in_place_revision = order["state"] in {"ACTIVE", "RENEWAL_DUE"}
                key = f"meal-order:{order['id']}:regenerate-after-v{version['version_number']}"
                if version["status"] == "CHANGES_REQUESTED":
                    job = await conn.fetchrow("SELECT * FROM meal_generation_jobs WHERE idempotency_key=$1", key)
                    if job:
                        return version, order, job
                if version["status"] != "REVIEW_PENDING":
                    raise ConcurrentUpdate("This version is no longer awaiting review")
                if not in_place_revision and order["state"] != "REVIEW_PENDING":
                    raise ConcurrentUpdate("This version is no longer awaiting review")

                await conn.execute(
                    "UPDATE meal_plan_versions SET status='CHANGES_REQUESTED',updated_at=NOW() WHERE id=$1",
                    plan_version_id,
                )
                if not in_place_revision:
                    order = await conn.fetchrow(
                        """
                        UPDATE meal_orders SET state='GENERATION_QUEUED',updated_at=NOW(),version=version+1
                        WHERE id=$1 AND state='REVIEW_PENDING' RETURNING *
                        """,
                        order["id"],
                    )
                    job_type = "REGENERATE"
                    payload = {"source_plan_version_id": plan_version_id, "requested_by": reviewer_id}
                else:
                    previous_job = await conn.fetchrow(
                        "SELECT payload FROM meal_generation_jobs WHERE plan_version_id=$1 ORDER BY id DESC LIMIT 1",
                        plan_version_id,
                    )
                    payload = dict(previous_job.get("payload") or {}) if previous_job else {}
                    if not isinstance(payload.get("revision"), dict):
                        revision_row = await conn.fetchrow(
                            """
                            SELECT r.id AS revision_request_id,c.id AS checkin_id,c.week_number,c.answers AS checkin_answers,
                                   i.answers AS baseline_answers
                            FROM meal_revision_requests r
                            JOIN meal_checkins c ON c.id=r.checkin_id
                            JOIN meal_orders ro ON ro.id=r.order_id
                            JOIN meal_intakes i ON i.id=ro.intake_id
                            WHERE r.order_id=$1 AND r.status IN ('IN_REVIEW','GENERATION_QUEUED')
                            ORDER BY r.id DESC LIMIT 1
                            """,
                            order["id"],
                        )
                        if revision_row:
                            checkin_answers = dict(revision_row.get("checkin_answers") or {})
                            decision = decide_revision(
                                baseline_answers=dict(revision_row.get("baseline_answers") or {}),
                                checkin_answers=checkin_answers,
                            )
                            payload.update({
                                "revision_request_id": revision_row["revision_request_id"],
                                "revision": {
                                    "checkin_id": revision_row["checkin_id"],
                                    "week_number": revision_row["week_number"],
                                    "kcal_delta": decision.kcal_delta,
                                    "reasons": list(decision.reasons),
                                    "answer_patch": decision.answer_patch,
                                    "current_weight_kg": checkin_answers.get("current_weight_kg"),
                                },
                            })
                    payload.update({"source_plan_version_id": plan_version_id, "requested_by": reviewer_id})
                    job_type = "REVISION"

                job = await conn.fetchrow(
                    """
                    INSERT INTO meal_generation_jobs(public_id,order_id,job_type,status,stage,idempotency_key,payload)
                    VALUES($1,$2,$3,'PENDING','QUEUED',$4,$5::jsonb)
                    ON CONFLICT(idempotency_key) DO UPDATE SET updated_at=meal_generation_jobs.updated_at
                    RETURNING *
                    """,
                    uuid.uuid4(), order["id"], job_type, key,
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                )
                await conn.execute(
                    """
                    INSERT INTO meal_plan_reviews(plan_version_id,reviewer_telegram_id,action,metadata)
                    VALUES($1,$2,'REGENERATE',$3::jsonb)
                    """,
                    plan_version_id, reviewer_id,
                    json.dumps({"generation_job_id": job["id"], "in_place_revision": in_place_revision}),
                )
                return version, order, job

    async def get_or_create_replacement_draft(self, source_version_id: int, reviewer_id: int):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                source = await conn.fetchrow("SELECT * FROM meal_plan_versions WHERE id=$1 FOR UPDATE", source_version_id)
                if not source:
                    raise RecordNotFound("Source plan version not found")
                if source["status"] not in {"REVIEW_PENDING", "CHANGES_REQUESTED"}:
                    raise ConcurrentUpdate("Source version is no longer replaceable")
                order = await conn.fetchrow("SELECT * FROM meal_orders WHERE id=$1 FOR UPDATE", source["order_id"])
                if not order or order["state"] not in {"REVIEW_PENDING", "ACTIVE", "RENEWAL_DUE"}:
                    raise ConcurrentUpdate("Order is no longer in Coach review")
                existing_replacement = await conn.fetchrow(
                    """
                    SELECT * FROM meal_plan_versions
                    WHERE order_id=$1 AND source='MANUAL_REPLACEMENT'
                      AND status IN ('DRAFT','REVIEW_PENDING')
                    ORDER BY version_number DESC LIMIT 1 FOR UPDATE
                    """,
                    order["id"],
                )
                if existing_replacement:
                    if existing_replacement["status"] == "REVIEW_PENDING":
                        raise ConcurrentUpdate("A replacement version is already waiting for Coach review")
                    if source["status"] == "REVIEW_PENDING":
                        await conn.execute("UPDATE meal_plan_versions SET status='CHANGES_REQUESTED',updated_at=NOW() WHERE id=$1", source_version_id)
                    return existing_replacement
                version_number = await conn.fetchval(
                    "SELECT COALESCE(MAX(version_number),0)+1 FROM meal_plan_versions WHERE order_id=$1",
                    order["id"],
                )
                draft = await conn.fetchrow(
                    """
                    INSERT INTO meal_plan_versions(
                        public_id,order_id,version_number,status,source,plan_json,detail_source,
                        engine_version,dataset_version,settings_version,generation_seed,generated_at
                    )
                    VALUES($1,$2,$3,'DRAFT','MANUAL_REPLACEMENT',$4,'DOCUMENT_OVERRIDE',$5,$6,$7,$8,NOW())
                    RETURNING *
                    """,
                    uuid.uuid4(), order["id"], version_number, source["plan_json"], source["engine_version"],
                    source["dataset_version"], source["settings_version"], source["generation_seed"],
                )
                if source["status"] == "REVIEW_PENDING":
                    await conn.execute("UPDATE meal_plan_versions SET status='CHANGES_REQUESTED',updated_at=NOW() WHERE id=$1", source_version_id)
                await conn.execute(
                    """
                    INSERT INTO meal_plan_reviews(plan_version_id,reviewer_telegram_id,action,metadata)
                    VALUES($1,$2,'REPLACE_FILES',$3::jsonb)
                    """,
                    source_version_id, reviewer_id,
                    json.dumps({"replacement_plan_version_id": draft["id"]}),
                )
                return draft

    async def replacement_ready(self, plan_version_id: int) -> bool:
        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM meal_plan_artifacts WHERE plan_version_id=$1 AND artifact_type IN ('DOCX','PDF')",
                plan_version_id,
            )
            return int(count or 0) == 2

    async def promote_replacement_for_review(self, replacement_version_id: int, *, source_version_id: int):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                replacement = await conn.fetchrow("SELECT * FROM meal_plan_versions WHERE id=$1 FOR UPDATE", replacement_version_id)
                if not replacement:
                    raise RecordNotFound("Replacement version not found")
                if replacement["status"] != "DRAFT":
                    return replacement
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM meal_plan_artifacts WHERE plan_version_id=$1 AND artifact_type IN ('DOCX','PDF')",
                    replacement_version_id,
                )
                if int(count or 0) != 2:
                    raise ConcurrentUpdate("Replacement review requires both DOCX and PDF")
                await conn.execute(
                    """
                    UPDATE meal_plan_versions SET status='CHANGES_REQUESTED',updated_at=NOW()
                    WHERE id=$1 AND status='REVIEW_PENDING'
                    """,
                    source_version_id,
                )
                return replacement

    async def prepare_delivery(self, plan_version_id: int):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                version = await conn.fetchrow("SELECT * FROM meal_plan_versions WHERE id=$1 FOR UPDATE", plan_version_id)
                if not version:
                    raise RecordNotFound("Plan version not found")
                order = await conn.fetchrow("SELECT * FROM meal_orders WHERE id=$1 FOR UPDATE", version["order_id"])
                if not order:
                    raise RecordNotFound("Order not found")
                if version["status"] == "DELIVERED" and order["state"] in {"ACTIVE", "RENEWAL_DUE"}:
                    deliveries = await conn.fetch("SELECT * FROM meal_deliveries WHERE plan_version_id=$1", plan_version_id)
                    return version, order, deliveries
                if version["status"] != "APPROVED" or order["current_plan_version_id"] != version["id"]:
                    raise ConcurrentUpdate("Only the approved current plan can be delivered")
                if order["state"] == "APPROVED":
                    order = await conn.fetchrow(
                        """
                        UPDATE meal_orders SET state='DELIVERY_PENDING',updated_at=NOW(),version=version+1
                        WHERE id=$1 AND state='APPROVED' RETURNING *
                        """,
                        order["id"],
                    )
                elif order["state"] not in {"ACTIVE", "RENEWAL_DUE", "DELIVERY_PENDING"}:
                    raise ConcurrentUpdate("Approved plan cannot be delivered from the current order state")
                for channel in ("TELEGRAM_DOCUMENT", "MINI_APP"):
                    await conn.execute(
                        """
                        INSERT INTO meal_deliveries(order_id,plan_version_id,channel,status,idempotency_key)
                        VALUES($1,$2,$3,'PENDING',$4)
                        ON CONFLICT(idempotency_key) DO NOTHING
                        """,
                        order["id"], plan_version_id, channel,
                        f"meal-order:{order['id']}:plan-v{version['version_number']}:{channel.lower()}",
                    )
                deliveries = await conn.fetch("SELECT * FROM meal_deliveries WHERE plan_version_id=$1", plan_version_id)
                return version, order, deliveries

    async def get_artifact(self, plan_version_id: int, artifact_type: str):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM meal_plan_artifacts WHERE plan_version_id=$1 AND artifact_type=$2",
                plan_version_id, artifact_type,
            )

    async def mark_delivery_sent(self, plan_version_id: int, channel: str, *, telegram_message_id: int | None = None):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                UPDATE meal_deliveries SET status='SENT',telegram_message_id=COALESCE($3,telegram_message_id),
                    error_message=NULL,sent_at=COALESCE(sent_at,NOW()),updated_at=NOW()
                WHERE plan_version_id=$1 AND channel=$2 RETURNING *
                """,
                plan_version_id, channel, telegram_message_id,
            )

    async def mark_delivery_failed(self, plan_version_id: int, channel: str, error_message: str):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                UPDATE meal_deliveries SET status='FAILED',error_message=$3,updated_at=NOW()
                WHERE plan_version_id=$1 AND channel=$2 RETURNING *
                """,
                plan_version_id, channel, error_message[:2000],
            )

    async def finalize_delivery(self, plan_version_id: int):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                version = await conn.fetchrow("SELECT * FROM meal_plan_versions WHERE id=$1 FOR UPDATE", plan_version_id)
                if not version:
                    raise RecordNotFound("Plan version not found")
                order = await conn.fetchrow("SELECT * FROM meal_orders WHERE id=$1 FOR UPDATE", version["order_id"])
                statuses = await conn.fetch(
                    "SELECT channel,status FROM meal_deliveries WHERE plan_version_id=$1",
                    plan_version_id,
                )
                by_channel = {row["channel"]: row["status"] for row in statuses}
                if by_channel.get("TELEGRAM_DOCUMENT") != "SENT" or by_channel.get("MINI_APP") != "SENT":
                    raise ConcurrentUpdate("Both Telegram and Mini App delivery channels must be ready")
                if version["status"] != "DELIVERED":
                    version = await conn.fetchrow(
                        """
                        UPDATE meal_plan_versions SET status='DELIVERED',delivered_at=COALESCE(delivered_at,NOW()),updated_at=NOW()
                        WHERE id=$1 AND status='APPROVED' RETURNING *
                        """,
                        plan_version_id,
                    )
                if order and order["state"] == "DELIVERY_PENDING":
                    order = await conn.fetchrow(
                        """
                        UPDATE meal_orders SET state='ACTIVE',activated_at=COALESCE(activated_at,NOW()),updated_at=NOW(),version=version+1
                        WHERE id=$1 AND state='DELIVERY_PENDING' RETURNING *
                        """,
                        order["id"],
                    )

                # A follow-up revision can be generated, reviewed and delivered while
                # the original plan remains ACTIVE. Resolve the latest open revision
                # request only after the replacement/revision is actually delivered.
                revision = await conn.fetchrow(
                    """
                    SELECT * FROM meal_revision_requests
                    WHERE order_id=$1 AND status IN ('IN_REVIEW','GENERATION_QUEUED')
                    ORDER BY id DESC LIMIT 1 FOR UPDATE
                    """,
                    version["order_id"],
                )
                if revision:
                    await conn.execute(
                        """
                        UPDATE meal_revision_requests
                        SET status='COMPLETED',resulting_plan_version_id=$2,resolved_at=NOW(),updated_at=NOW()
                        WHERE id=$1
                        """,
                        revision["id"], plan_version_id,
                    )
                    if revision.get("checkin_id"):
                        await conn.execute(
                            """
                            UPDATE meal_checkins
                            SET status='CLOSED',reviewed_at=COALESCE(reviewed_at,NOW()),updated_at=NOW()
                            WHERE id=$1 AND status IN ('SUBMITTED','REVIEW_REQUIRED')
                            """,
                            revision["checkin_id"],
                        )
                return version, order

    async def list_delivery_retry_versions(self, *, limit: int = 5) -> list[int]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT v.id
                FROM meal_plan_versions v
                JOIN meal_orders o ON o.current_plan_version_id=v.id
                LEFT JOIN meal_deliveries d ON d.plan_version_id=v.id
                WHERE v.status='APPROVED'
                  AND o.state IN ('APPROVED','DELIVERY_PENDING','ACTIVE','RENEWAL_DUE')
                  AND (d.id IS NULL OR d.status IN ('PENDING','FAILED'))
                ORDER BY v.id
                LIMIT $1
                """,
                limit,
            )
            return [int(row["id"]) for row in rows]

    async def get_current_plan_for_user(self, telegram_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT v.*,o.id AS order_id,o.public_id AS order_public_id,o.state AS order_state,o.user_id,
                       o.start_date,o.ends_on,o.service_type,o.duration_days,o.meals_per_day,
                       pdf.id AS pdf_artifact_id,pdf.storage_backend AS pdf_storage_backend,
                       pdf.storage_key AS pdf_storage_key,pdf.original_filename AS pdf_filename,
                       pdf.telegram_file_id AS pdf_telegram_file_id,
                       docx.id AS docx_artifact_id
                FROM meal_orders o
                JOIN meal_plan_versions v ON v.id=o.current_plan_version_id
                LEFT JOIN meal_plan_artifacts pdf ON pdf.plan_version_id=v.id AND pdf.artifact_type='PDF'
                LEFT JOIN meal_plan_artifacts docx ON docx.plan_version_id=v.id AND docx.artifact_type='DOCX'
                WHERE o.user_id=$1 AND o.state IN ('APPROVED','DELIVERY_PENDING','ACTIVE','RENEWAL_DUE')
                ORDER BY o.id DESC LIMIT 1
                """,
                telegram_id,
            )
