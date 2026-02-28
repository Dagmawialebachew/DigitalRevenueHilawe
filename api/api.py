from aiohttp import web

async def get_admin_stats(request: web.Request) -> web.Response:
    db = request.app["db"]
    stats = await db.fetchrow("""
        SELECT 
            COALESCE(SUM(amount) FILTER (WHERE status = 'approved'), 0) as total_revenue,
            COUNT(*) FILTER (WHERE status = 'pending') as pending_payments,
            (SELECT COUNT(*) FROM users) as active_users,
            ROUND(
                (COUNT(DISTINCT user_id) FILTER (WHERE status = 'approved'))::numeric / 
                NULLIF((SELECT COUNT(*) FROM users), 0) * 100, 2
            ) as conversion_rate
        FROM payments
    """)
    return web.json_response(dict(stats))

async def get_recent_payments(request: web.Request) -> web.Response:
    db = request.app["db"]
    rows = await db.fetch("""
        SELECT p.*, u.full_name, u.username, pr.title 
        FROM payments p
        JOIN users u ON p.user_id = u.telegram_id
        JOIN products pr ON p.product_id = pr.id
        ORDER BY p.created_at DESC LIMIT 10
    """)
    return web.json_response([dict(r) for r in rows])

async def verify_payment(request: web.Request) -> web.Response:
    db = request.app["db"]
    payment_id = int(request.match_info["payment_id"])
    data = await request.json()
    result = await db.execute("UPDATE payments SET status=$1 WHERE id=$2", data["status"], payment_id)
    if result == "UPDATE 0":
        return web.json_response({"error": "Payment not found"}, status=404)
    return web.json_response({"status": "success", "message": f"Payment {data['status']}"})

async def get_products(request: web.Request) -> web.Response:
    db = request.app["db"]
    rows = await db.fetch("SELECT * FROM products ORDER BY created_at DESC")
    return web.json_response([dict(r) for r in rows])

async def create_product(request: web.Request) -> web.Response:
    db = request.app["db"]
    data = await request.json()
    
    query = """
        INSERT INTO products (title, language, gender, level, frequency, price, telegram_file_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id
    """
    product_id = await db.fetchval(
        query, data['title'], data['language'], data['gender'], 
        data['level'], data['frequency'], float(data['price']), data['file_id']
    )
    return web.json_response({"status": "deployed", "id": product_id})


def setup_admin_routes(app: web.Application):
    app.router.add_get("/api/admin/stats", get_admin_stats)
    app.router.add_get("/api/admin/payments/recent", get_recent_payments)
    app.router.add_post("/api/admin/payments/{payment_id}/verify", verify_payment)
    app.router.add_get("/api/admin/products", get_products)
    app.router.add_post("/api/admin/products/create", create_product)
