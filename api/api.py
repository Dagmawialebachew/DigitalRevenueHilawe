# handlers/admin_api.py
import logging
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from aiohttp import web

LOG = logging.getLogger("admin_api")


# --- Utilities --------------------------------------------------------------

def record_to_dict(record: Optional[Any]) -> Dict[str, Any]:
    """Convert asyncpg.Record (or None) to a JSON-serializable dict."""
    if record is None:
        return {}
    d = dict(record)
    for k, v in list(d.items()):
        if isinstance(v, Decimal):
            # monetary / numeric fields -> float for JSON
            d[k] = float(v)
        elif isinstance(v, bytes):
            d[k] = v.decode(errors="ignore")
        # add other conversions here if needed (datetime -> isoformat, etc.)
    return d


def records_to_list(rows: Iterable[Any]) -> List[Dict[str, Any]]:
    return [record_to_dict(r) for r in rows]


# --- Lightweight in-memory cache for hot endpoints --------------------------
# Stored on app as app["admin_cache"] = {"stats": (timestamp, payload), ...}
# TTL in seconds
_STATS_TTL = 5


def _get_cached(app: web.Application, key: str, ttl: int):
    cache = app.get("admin_cache", {})
    entry = cache.get(key)
    if not entry:
        return None
    ts, payload = entry
    if (web.time.time() - ts) > ttl:
        # expired
        cache.pop(key, None)
        app["admin_cache"] = cache
        return None
    return payload


def _set_cached(app: web.Application, key: str, payload: Any):
    cache = app.get("admin_cache", {})
    cache[key] = (web.time.time(), payload)
    app["admin_cache"] = cache


# --- Handlers ---------------------------------------------------------------

async def get_admin_stats(request: web.Request) -> web.Response:
    """
    GET /api/admin/stats
    Uses Database.get_admin_stats() helper to return KPIs.
    Cached for a short TTL to reduce DB pressure from dashboard polling.
    """
    db = request.app["db"]

    # Try cache first
    cached = _get_cached(request.app, "stats", _STATS_TTL)
    if cached is not None:
        return web.json_response(cached)

    try:
        stats_record = await db.get_admin_stats()
        payload = record_to_dict(stats_record)
        _set_cached(request.app, "stats", payload)
        return web.json_response(payload)
    except Exception as e:
        LOG.exception("get_admin_stats failed")
        return web.json_response({"error": "internal_server_error"}, status=500)


async def get_recent_payments(request: web.Request) -> web.Response:
    """
    GET /api/admin/payments/recent
    Returns the most recent payments (limit query param supported).
    Uses Database.get_recent_payments helper.
    """
    db = request.app["db"]
    try:
        limit = int(request.query.get("limit", 10))
        if limit <= 0 or limit > 200:
            limit = 10
    except Exception:
        limit = 10

    try:
        rows = await db.get_recent_payments(limit=limit)
        return web.json_response(records_to_list(rows))
    except Exception:
        LOG.exception("get_recent_payments failed")
        return web.json_response({"error": "internal_server_error"}, status=500)


async def verify_payment(request: web.Request) -> web.Response:
    """
    POST /api/admin/payments/{payment_id}/verify
    Body: { "status": "approved" | "rejected" }
    - Approve: uses Database.approve_payment (atomic) and returns delivery info.
    - Reject: uses Database.reject_payment helper.
    """
    db = request.app["db"]
    try:
        payment_id = int(request.match_info.get("payment_id"))
    except Exception:
        return web.json_response({"error": "invalid_payment_id"}, status=400)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid_json"}, status=400)

    status = (data.get("status") or "").lower()
    if status not in {"approved", "rejected"}:
        return web.json_response({"error": "invalid_status"}, status=400)

    try:
        if status == "approved":
            result = await db.approve_payment(payment_id)
            if not result:
                return web.json_response({"error": "payment_not_found"}, status=404)

            # Clear stats cache so dashboard reflects new counts quickly
            request.app.get("admin_cache", {}).pop("stats", None)

            return web.json_response({
                "status": "success",
                "message": "payment_approved",
                "delivery": record_to_dict(result)
            })

        # rejected
        ok = await db.reject_payment(payment_id)
        if not ok:
            return web.json_response({"error": "payment_not_found"}, status=404)

        request.app.get("admin_cache", {}).pop("stats", None)
        return web.json_response({"status": "success", "message": "payment_rejected"})

    except Exception:
        LOG.exception("verify_payment failed for id=%s", payment_id)
        return web.json_response({"error": "internal_server_error"}, status=500)


async def get_products(request: web.Request) -> web.Response:
    """
    GET /api/admin/products
    Query params: limit, offset
    Uses Database.get_products helper.
    """
    db = request.app["db"]
    try:
        limit = int(request.query.get("limit", 100))
        offset = int(request.query.get("offset", 0))
        if limit < 1 or limit > 500:
            limit = 100
        if offset < 0:
            offset = 0
    except Exception:
        return web.json_response({"error": "invalid_pagination"}, status=400)

    try:
        rows = await db.get_products(limit=limit, offset=offset)
        return web.json_response(records_to_list(rows))
    except Exception:
        LOG.exception("get_products failed")
        return web.json_response({"error": "internal_server_error"}, status=500)


async def create_product(request: web.Request) -> web.Response:
    """
    POST /api/admin/products/create
    Body: { title, language, gender, level, frequency, price, file_id }
    Uses Database.create_product helper.
    """
    db = request.app["db"]
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"error": "invalid_json"}, status=400)

    required = ("title", "language", "gender", "level", "frequency", "price", "file_id")
    missing = [k for k in required if k not in payload]
    if missing:
        return web.json_response({"error": "missing_fields", "fields": missing}, status=400)

    try:
        product_id = await db.create_product(
            title=payload["title"],
            language=payload["language"],
            gender=payload["gender"],
            level=payload["level"],
            frequency=int(payload["frequency"]),
            price=float(payload["price"]),
            file_id=payload["file_id"]
        )
        # Invalidate product-related caches if you add any later
        return web.json_response({"status": "deployed", "id": product_id})
    except Exception:
        LOG.exception("create_product failed")
        return web.json_response({"error": "internal_server_error"}, status=500)


# --- Route registration ----------------------------------------------------

def setup_admin_routes(app: web.Application):
    """
    Register admin routes on the aiohttp app.
    """
    app.router.add_get("/api/admin/stats", get_admin_stats)
    app.router.add_get("/api/admin/payments/recent", get_recent_payments)
    app.router.add_post("/api/admin/payments/{payment_id}/verify", verify_payment)
    app.router.add_get("/api/admin/products", get_products)
    app.router.add_post("/api/admin/products/create", create_product)
