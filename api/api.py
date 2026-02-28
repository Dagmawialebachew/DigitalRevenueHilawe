# handlers/admin_api.py
from aiohttp import web
from typing import List, Dict, Any

# --- Admin API handlers using Database helper methods (Option 1) ---

async def get_admin_stats(request: web.Request) -> web.Response:
    """
    GET /api/admin/stats
    Uses Database.get_admin_stats() helper to return KPIs.
    """
    db = request.app["db"]
    stats = await db.get_admin_stats()
    return web.json_response(dict(stats or {}))


async def get_recent_payments(request: web.Request) -> web.Response:
    """
    GET /api/admin/payments/recent
    Uses Database.get_recent_payments() helper to return the 10 most recent payments.
    """
    db = request.app["db"]
    rows = await db.get_recent_payments(limit=10)
    return web.json_response([dict(r) for r in rows])


async def verify_payment(request: web.Request) -> web.Response:
    """
    POST /api/admin/payments/{payment_id}/verify
    Body: { "status": "approved" | "rejected" }
    - If approved: use Database.approve_payment to atomically approve and fetch product/user info.
    - If rejected: use Database.reject_payment helper.
    """
    db = request.app["db"]
    try:
        payment_id = int(request.match_info["payment_id"])
    except (KeyError, ValueError):
        return web.json_response({"error": "invalid payment_id"}, status=400)

    data = await request.json()
    status = (data.get("status") or "").lower()

    if status not in {"approved", "rejected"}:
        return web.json_response({"error": "invalid status"}, status=400)

    if status == "approved":
        result = await db.approve_payment(payment_id)
        if not result:
            return web.json_response({"error": "Payment not found"}, status=404)
        return web.json_response({
            "status": "success",
            "message": "Payment approved",
            "delivery": dict(result)
        })

    # status == 'rejected'
    ok = await db.reject_payment(payment_id)
    if not ok:
        return web.json_response({"error": "Payment not found"}, status=404)
    return web.json_response({"status": "success", "message": "Payment rejected"})


async def get_products(request: web.Request) -> web.Response:
    """
    GET /api/admin/products
    Uses Database.get_products() helper.
    """
    db = request.app["db"]
    # optional query params for pagination
    try:
        limit = int(request.query.get("limit", 100))
        offset = int(request.query.get("offset", 0))
    except ValueError:
        return web.json_response({"error": "invalid pagination parameters"}, status=400)

    rows = await db.get_products(limit=limit, offset=offset)
    return web.json_response([dict(r) for r in rows])


async def create_product(request: web.Request) -> web.Response:
    """
    POST /api/admin/products/create
    Body: { title, language, gender, level, frequency, price, file_id }
    Uses Database.create_product() helper.
    """
    db = request.app["db"]
    data = await request.json()

    required = ("title", "language", "gender", "level", "frequency", "price", "file_id")
    missing = [k for k in required if k not in data]
    if missing:
        return web.json_response({"error": f"missing fields: {', '.join(missing)}"}, status=400)

    try:
        product_id = await db.create_product(
            title=data["title"],
            language=data["language"],
            gender=data["gender"],
            level=data["level"],
            frequency=int(data["frequency"]),
            price=float(data["price"]),
            file_id=data["file_id"]
        )
    except Exception as e:
        # keep error message generic in production; log details server-side
        return web.json_response({"error": "failed to create product"}, status=500)

    return web.json_response({"status": "deployed", "id": product_id})


def setup_admin_routes(app: web.Application):
    """
    Register admin routes on the aiohttp app.
    """
    app.router.add_get("/api/admin/stats", get_admin_stats)
    app.router.add_get("/api/admin/payments/recent", get_recent_payments)
    app.router.add_post("/api/admin/payments/{payment_id}/verify", verify_payment)
    app.router.add_get("/api/admin/products", get_products)
    app.router.add_post("/api/admin/products/create", create_product)
