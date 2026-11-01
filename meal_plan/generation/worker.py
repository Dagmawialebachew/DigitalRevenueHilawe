from __future__ import annotations

import asyncio
import logging
import os
import socket

from aiogram import Bot

from database.db import Database
from meal_plan.generation.pipeline import process_generation_job
from meal_plan.review_repository import MealPlanReviewRepository
from meal_plan.runtime import generation_worker_interval_seconds

import time

logger = logging.getLogger(__name__)


def worker_identity() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


async def generation_worker_loop(bot: Bot, db: Database) -> None:
    pool = getattr(db, "_pool", None)
    if pool is None:
        raise RuntimeError("Database pool is not connected")
    repo = MealPlanReviewRepository(pool)
    worker_id = worker_identity()
    interval = generation_worker_interval_seconds()
    logger.info("Meal Plan generation worker started: %s", worker_id)
    last_sweep_time = 0.0
    while True:
        try:
            # Periodic self-healing sweep every 180 seconds
            now = time.monotonic()
            if now - last_sweep_time >= 180.0:
                last_sweep_time = now
                try:
                    await repo.sweep_stalled_generation_jobs()
                except Exception as sweep_err:
                    logger.warning("Generation worker stalled-job sweep error: %s", sweep_err)

            job = await repo.claim_generation_job(worker_id)
            if not job:
                await asyncio.sleep(interval)
                continue
            try:
                version_id = await process_generation_job(bot, db, repo, job)
                logger.info("Meal Plan generation job %s handed off as version %s", job["id"], version_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Meal Plan generation job %s failed", job["id"])
                await repo.fail_generation_job(job["id"], code=type(exc).__name__, message=str(exc))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Meal Plan generation worker loop error")
            await asyncio.sleep(max(interval, 3))
