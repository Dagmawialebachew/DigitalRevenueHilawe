"""Run the complete local/demo Meal Plan stack with explicit safety guards.

This runner is intentionally impossible to start unless MEAL_PLAN_DEMO_MODE=true.
It never configures a webhook and never deploys anything. Use --full when testing
the real Telegram Mini App journey; --full also requires an approved frontend
(public HTTPS or explicitly guarded loopback HTTP) plus both workers.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os

import aiohttp_cors
from aiohttp import web

from bot import bot, db, dp, run_meal_plan_migrations, set_commands
from config import settings
from meal_plan.api import setup_meal_plan_routes
from meal_plan.generation.worker import generation_worker_loop
from meal_plan.lifecycle import meal_plan_lifecycle_worker_loop
from meal_plan.release_gate import release_report
from meal_plan.runtime import (
    demo_bot_id,
    demo_mode,
    generation_worker_enabled,
    lifecycle_worker_enabled,
    meal_plan_enabled,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Coach Hilawe Meal Plan local demo stack")
    parser.add_argument("--full", action="store_true", help="Require an approved frontend + both workers before starting")
    return parser.parse_args()


async def _start_api() -> tuple[web.AppRunner, int]:
    app = web.Application()
    app["bot"] = bot
    app["db"] = db
    setup_meal_plan_routes(app)

    origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").strip()
    cors = aiohttp_cors.setup(
        app,
        defaults={
            origin: aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*",
            )
        },
    )
    for route in list(app.router.routes()):
        try:
            cors.add(route)
        except Exception:
            pass

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("MEAL_PLAN_DEMO_API_PORT", "8081"))
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    return runner, port


def _print_gate(full: bool) -> None:
    report = release_report("demo", full_demo=full)
    print("Coach Hilawe Meal Plan demo preflight")
    for item in report.findings:
        if item.status != "PASS" or item.code == "LOCAL_DEV_FRONTEND":
            print(f"[{item.status:5}] {item.code}: {item.message}")
    print(f"Preflight: {report.blockers} blocker(s), {report.warnings} warning(s)")
    if not report.ready:
        raise SystemExit("Demo preflight has blockers. Nothing was started.")


async def main(*, full: bool = False) -> None:
    if not demo_mode():
        raise SystemExit("Safety stop: set MEAL_PLAN_DEMO_MODE=true only in the demo environment before running this command.")
    if not meal_plan_enabled():
        raise SystemExit("Set MEAL_PLAN_ENABLED=true in the demo environment before running this command.")

    _print_gate(full)

    # Validate the bot identity before deleting any webhook or beginning polling.
    me = await bot.get_me()
    expected_bot_id = demo_bot_id()
    if expected_bot_id and int(me.id) != expected_bot_id:
        raise SystemExit(
            f"Safety stop: connected bot id {me.id} does not match MEAL_PLAN_DEMO_BOT_ID. No webhook was changed."
        )
    if expected_bot_id:
        logging.info("Demo bot identity guard passed: @%s (%s)", me.username or "unknown", me.id)
    else:
        logging.warning("MEAL_PLAN_DEMO_BOT_ID is not set; connected bot is @%s (%s)", me.username or "unknown", me.id)

    await db.connect()
    await db.setup()
    await run_meal_plan_migrations()
    await set_commands(bot, settings.ADMIN_IDS)

    # Safe only after the explicit demo-mode + optional bot-id guard above.
    await bot.delete_webhook(drop_pending_updates=True)

    runner, port = await _start_api()
    workers: list[asyncio.Task] = []
    if generation_worker_enabled():
        workers.append(asyncio.create_task(generation_worker_loop(bot, db), name="meal-plan-generation"))
        logging.info("Meal Plan generation worker enabled for local demo")
    else:
        logging.warning("Generation worker disabled; payment-to-review generation will not run")

    if lifecycle_worker_enabled():
        workers.append(asyncio.create_task(meal_plan_lifecycle_worker_loop(bot, db), name="meal-plan-lifecycle"))
        logging.info("Meal Plan lifecycle worker enabled for local demo")
    else:
        logging.warning("Lifecycle worker disabled; follow-up/renewal/recovery cycles will not run")

    logging.info("Meal Plan demo API listening on http://127.0.0.1:%s", port)
    logging.info("Demo bot polling started. Press Ctrl+C to stop.")

    try:
        await dp.start_polling(bot)
    finally:
        for task in workers:
            task.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        await runner.cleanup()
        await db.disconnect()
        await bot.session.close()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(main(full=args.full))
