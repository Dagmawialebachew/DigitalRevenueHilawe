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
    # db.get_admin_stats returns an asyncpg.Record — convert to plain dict
    return web.json_response(dict(stats or {}))


async def get_recent_payments(request: web.Request) -> web.Response:
    """
    GET /api/admin/payments/recent
    Uses Database.get_pending_payments() helper (or a dedicated helper).
    Returns the 10 most recent payments (pending + approved + rejected).
    """
    db = request.app["db"]
    # If you want all recent payments (not only pending), use a direct query via helper if available.
    # We have get_pending_payments for pending; for recent regardless of status, use a small inline query
    # via the pool (safe because it's a single, simple read).
    rows = await db._pool.fetch("""
        SELECT p.id, p.amount, p.status, p.created_at, u.full_name, u.username, pr.title
        FROM payments p
        JOIN users u ON p.user_id = u.telegram_id
        JOIN products pr ON p.product_id = pr.id
        ORDER BY p.created_at DESC
        LIMIT 10
    """)
    return web.json_response([dict(r) for r in rows])


async def verify_payment(request: web.Request) -> web.Response:
    """
    POST /api/admin/payments/{payment_id}/verify
    Body: { "status": "approved" | "rejected" }
    - If approved: use Database.approve_payment to atomically approve and fetch product/user info.
    - If rejected: update status to 'rejected' and return success.
    """
    db = request.app["db"]
    payment_id = int(request.match_info["payment_id"])
    data = await request.json()
    status = (data.get("status") or "").lower()

    if status not in {"approved", "rejected"}:
        return web.json_response({"error": "invalid status"}, status=400)

    if status == "approved":
        # approve_payment updates status and returns product/user info (or None if not found)
        result = await db.approve_payment(payment_id)
        if not result:
            return web.json_response({"error": "Payment not found"}, status=404)

        # result is an asyncpg.Record with telegram_file_id, language, user_id
        return web.json_response({
            "status": "success",
            "message": "Payment approved",
            "delivery": dict(result)
        })

    # status == 'rejected'
    res = await db._pool.execute("UPDATE payments SET status = 'rejected' WHERE id = $1", payment_id)
    if res == "UPDATE 0":
        return web.json_response({"error": "Payment not found"}, status=404)
    return web.json_response({"status": "success", "message": "Payment rejected"})


async def get_products(request: web.Request) -> web.Response:
    """
    GET /api/admin/products
    Uses Database.get_all_products() helper.
    """
    db = request.app["db"]
    rows = await db.get_all_products(limit=100, offset=0)
    return web.json_response([dict(r) for r in rows])


async def create_product(request: web.Request) -> web.Response:
    """
    POST /api/admin/products/create
    Body: { title, language, gender, level, frequency, price, file_id }
    Uses Database.add_product() helper.
    """
    db = request.app["db"]
    data = await request.json()

    required = ("title", "language", "gender", "level", "frequency", "price", "file_id")
    missing = [k for k in required if k not in data]
    if missing:
        return web.json_response({"error": f"missing fields: {', '.join(missing)}"}, status=400)

    await db.add_product(
        title=data["title"],
        lang=data["language"],
        gender=data["gender"],
        level=data["level"],
        freq=int(data["frequency"]),
        price=float(data["price"]),
        file_id=data["file_id"]
    )
    return web.json_response({"status": "deployed"})


def setup_admin_routes(app: web.Application):
    """
    Register admin routes on the aiohttp app.
    """
    app.router.add_get("/api/admin/stats", get_admin_stats)
    app.router.add_get("/api/admin/payments/recent", get_recent_payments)
    app.router.add_post("/api/admin/payments/{payment_id}/verify", verify_payment)
    app.router.add_get("/api/admin/products", get_products)
    app.router.add_post("/api/admin/products/create", create_product)
