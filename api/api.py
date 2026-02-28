# handlers/admin_api.py
import logging
import time
from decimal import Decimal
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from aiohttp import web

LOG = logging.getLogger("admin_api")


# --- Utilities --------------------------------------------------------------

def record_to_dict(record):
    """Convert asyncpg.Record to dict with JSON-serializable values."""
    if record is None:
        return {}
    d = dict(record)
    for k, v in list(d.items()):
        if isinstance(v, Decimal):
            d[k] = float(v)   # convert Decimal -> float
        elif isinstance(v, datetime):
            d[k] = v.isoformat()  # convert datetime -> ISO string
        elif isinstance(v, bytes):
            d[k] = v.decode(errors="ignore")
    return d

def records_to_list(rows):
    return [record_to_dict(r) for r in rows]


# --- Lightweight in-memory cache for hot endpoints --------------------------
_STATS_TTL = 5

def _get_cached(app: web.Application, key: str, ttl: int):
    cache = app.get("admin_cache", {})
    entry = cache.get(key)
    if not entry:
        return None
    ts, payload = entry
    if (time.time() - ts) > ttl:
        cache.pop(key, None)
        app["admin_cache"] = cache
        return None
    return payload

def _set_cached(app: web.Application, key: str, payload: Any):
    cache = app.get("admin_cache", {})
    cache[key] = (time.time(), payload)
    app["admin_cache"] = cache


# --- Handlers ---------------------------------------------------------------

async def get_admin_stats(request: web.Request) -> web.Response:
    """GET /api/admin/stats - Basic KPIs"""
    db = request.app["db"]
    cached = _get_cached(request.app, "stats", _STATS_TTL)
    if cached is not None:
        return web.json_response(cached)

    try:
        stats_record = await db.get_admin_stats()
        payload = record_to_dict(stats_record)
        _set_cached(request.app, "stats", payload)
        return web.json_response(payload)
    except Exception:
        LOG.exception("get_admin_stats failed")
        return web.json_response({"error": "internal_server_error"}, status=500)


async def get_revenue_stats(request: web.Request) -> web.Response:
    """
    GET /api/admin/stats/revenue?days=7
    Returns time-series data for the line chart.
    """
    db = request.app["db"]
    try:
        days = int(request.query.get("days", 7))
    except ValueError:
        days = 7

    try:
        # Expected from DB: list of records with 'date' and 'value'
        rows = await db.get_revenue_history(days=days)
        return web.json_response(records_to_list(rows))
    except Exception:
        LOG.exception("get_revenue_stats failed")
        return web.json_response([], status=500)


async def get_distribution_stats(request: web.Request) -> web.Response:
    """
    GET /api/admin/stats/distribution
    Returns counts for the donut chart.
    """
    db = request.app["db"]
    try:
        # Expected from DB: record with 'pending', 'approved', 'rejected'
        record = await db.get_payment_distribution()
        return web.json_response(record_to_dict(record))
    except Exception:
        LOG.exception("get_distribution_stats failed")
        return web.json_response({"pending": 0, "approved": 0, "rejected": 0})


async def get_recent_payments(request: web.Request) -> web.Response:
    """GET /api/admin/payments/recent"""
    db = request.app["db"]
    try:
        limit = int(request.query.get("limit", 10))
        limit = max(1, min(limit, 200))
    except Exception:
        limit = 10

    try:
        rows = await db.get_recent_payments(limit=limit)
        return web.json_response(records_to_list(rows))
    except Exception:
        LOG.exception("get_recent_payments failed")
        return web.json_response({"error": "internal_server_error"}, status=500)


async def verify_payment(request: web.Request) -> web.Response:
    """POST /api/admin/payments/{payment_id}/verify"""
    db = request.app["db"]
    try:
        payment_id = int(request.match_info.get("payment_id"))
        data = await request.json()
        status = (data.get("status") or "").lower()
    except Exception:
        return web.json_response({"error": "bad_request"}, status=400)

    if status not in {"approved", "rejected"}:
        return web.json_response({"error": "invalid_status"}, status=400)

    try:
        if status == "approved":
            result = await db.approve_payment(payment_id)
            if not result:
                return web.json_response({"error": "not_found"}, status=404)
        else:
            ok = await db.reject_payment(payment_id)
            if not ok:
                return web.json_response({"error": "not_found"}, status=404)

        # Invalidate stats cache
        request.app.get("admin_cache", {}).pop("stats", None)
        return web.json_response({"status": "success"})
    except Exception:
        LOG.exception("verify_payment failed")
        return web.json_response({"error": "internal_error"}, status=500)


async def get_products(request: web.Request) -> web.Response:
    """GET /api/admin/products"""
    db = request.app["db"]
    try:
        limit = int(request.query.get("limit", 100))
        offset = int(request.query.get("offset", 0))
    except Exception:
        return web.json_response({"error": "invalid_pagination"}, status=400)

    try:
        rows = await db.get_products(limit=limit, offset=offset)
        return web.json_response(records_to_list(rows))
    except Exception:
        LOG.exception("get_products failed")
        return web.json_response({"error": "internal_error"}, status=500)


async def create_product(request: web.Request) -> web.Response:
    """POST /api/admin/products/create"""
    db = request.app["db"]
    try:
        p = await request.json()
        product_id = await db.create_product(
            title=p["title"], language=p["language"], gender=p["gender"],
            level=p["level"], frequency=int(p["frequency"]),
            price=float(p["price"]), file_id=p["file_id"]
        )
        return web.json_response({"status": "deployed", "id": product_id})
    except Exception:
        LOG.exception("create_product failed")
        return web.json_response({"error": "internal_server_error"}, status=500)


# --- Route registration ----------------------------------------------------

def setup_admin_routes(app: web.Application):
    """Register admin routes on the aiohttp app."""
    # Stats & Charts
    app.router.add_get("/api/admin/stats", get_admin_stats)
    app.router.add_get("/api/admin/stats/revenue", get_revenue_stats)
    app.router.add_get("/api/admin/stats/distribution", get_distribution_stats)
    
    # Payments
    app.router.add_get("/api/admin/payments/recent", get_recent_payments)
    app.router.add_post("/api/admin/payments/{payment_id}/verify", verify_payment)
    
    # Products
    app.router.add_get("/api/admin/products", get_products)
    app.router.add_post("/api/admin/products/create", create_product)