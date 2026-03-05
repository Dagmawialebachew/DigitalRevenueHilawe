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
    # --- Dashboard & Stats ---
    app.router.add_get("/api/admin/stats", get_admin_stats)
    app.router.add_get("/api/admin/stats/revenue", get_revenue_stats)
    app.router.add_get("/api/admin/stats/distribution", get_distribution_stats)

    # --- Payments ---
    app.router.add_get("/api/admin/payments/recent", get_recent_payments)
    app.router.add_get("/api/admin/payments/kpis", get_payment_kpis)
    app.router.add_post("/api/admin/payments/{payment_id}/verify", verify_payment)

    # --- Products (Core) ---
    app.router.add_get("/api/admin/products", get_products)
    app.router.add_post("/api/admin/products/create", create_product)
    
    # --- Products (Analysis) ---
    app.router.add_get("/api/admin/products/top_sellers", get_top_sellers)
    app.router.add_get("/api/admin/products/lifecycle", get_product_lifecycle)
    app.router.add_get("/api/admin/products/price_distribution", get_price_distribution)
    app.router.add_get("/api/admin/revenue/products", get_revenue_by_products)

    # --- User Demographics ---
    app.router.add_get('/api/admin/stats/node-intelligence', get_node_intelligence)

    # --- CRUD Helper (For the specific Mint Modal actions) ---
    # We use explicit methods instead of a wildcard to avoid 404/500 confusion
    app.router.add_post("/api/products", handle_products_crud)
    app.router.add_patch("/api/products", handle_products_crud)
    app.router.add_delete("/api/products", handle_products_crud)
    
# New API

async def get_revenue_by_products(request: web.Request) -> web.Response:
    """GET /api/admin/revenue/products"""
    db = request.app["db"]
    try:
        rows = await db.get_revenue_by_products()
        return web.json_response(records_to_list(rows))
    except Exception:
        LOG.exception("get_revenue_by_products failed")
        return web.json_response({"error": "internal_error"}, status=500)


async def get_top_sellers(request: web.Request) -> web.Response:
    """GET /api/admin/products/top_sellers"""
    db = request.app["db"]
    try:
        limit = int(request.query.get("limit", 10))
        rows = await db.get_top_sellers(limit=limit)
        return web.json_response(records_to_list(rows))
    except Exception:
        LOG.exception("get_top_sellers failed")
        return web.json_response({"error": "internal_error"}, status=500)

async def get_price_distribution(request: web.Request) -> web.Response:
    """GET /api/admin/products/price_distribution"""
    db = request.app["db"]
    try:
        rows = await db.get_price_distribution()
        return web.json_response(records_to_list(rows))
    except Exception:
        LOG.exception("get_price_distribution failed")
        return web.json_response({"error": "internal_error"}, status=500)

async def get_node_intelligence(request: web.Request) -> web.Response:
    """
    Returns the complete User Intelligence Matrix (Lang, Gender, Level, Freq)
    in a single high-performance scan.
    """
    db = request.app["db"]
    try:
        # Call the single-scan DB method we just created
        record = await db.get_node_intelligence_matrix()
        
        # Convert the asyncpg Record to a dictionary and send
        return web.json_response(dict(record))
    except Exception:
        LOG.exception("get_node_intelligence matrix fetch failed")
        # Return a safe fallback so the frontend doesn't crash
        return web.json_response({
            "lang_en": 0, "lang_am": 0,
            "gen_male": 0, "gen_female": 0,
            "lvl_beginner": 0, "lvl_inter": 0, "lvl_adv": 0, "lvl_glute": 0,
            "freq_2_3": 0, "freq_3_4": 0, "freq_4_5": 0, "freq_everyday": 0
        })



async def get_payment_kpis(request: web.Request) -> web.Response:
    """GET /api/admin/payments/kpis"""
    db = request.app["db"]
    try:
        record = await db.get_payment_kpis()
        return web.json_response(record_to_dict(record))
    except Exception:
        LOG.exception("get_payment_kpis failed")
        return web.json_response({"total_revenue": 0, "pending_count": 0, "avg_approval_time_minutes": 0, "rejection_rate": 0})



# --- PRODUCT CRUD HANDLERS ---

async def create_product(request: web.Request) -> web.Response:
    """POST /api/admin/products"""
    db = request.app["db"]
    data = await request.json()
    try:
        # data: {title, language, gender, level, frequency, price, telegram_file_id}
        new_id = await db.create_product(data)
        return web.json_response({"status": "created", "id": new_id}, status=201)
    except Exception:
        LOG.exception("create_product failed")
        return web.json_response({"error": "creation_failed"}, status=500)

async def update_product(request: web.Request) -> web.Response:
    """PATCH /api/admin/products/{id}"""
    db = request.app["db"]
    prod_id = int(request.match_info['id'])
    data = await request.json()
    try:
        await db.update_product(prod_id, data)
        return web.json_response({"status": "updated"})
    except Exception:
        LOG.exception("update_product failed")
        return web.json_response({"error": "update_failed"}, status=500)

async def delete_product(request: web.Request) -> web.Response:
    """DELETE /api/admin/products/{id}"""
    db = request.app["db"]
    prod_id = int(request.match_info['id'])
    try:
        # We perform a soft delete by setting is_active = FALSE
        await db.soft_delete_product(prod_id)
        return web.json_response({"status": "deactivated"})
    except Exception:
        LOG.exception("delete_product failed")
        return web.json_response({"error": "delete_failed"}, status=500)
    
 

async def get_product_lifecycle(request):
    db = request.app["db"]
    try:
        prod_id_raw = request.query.get('id')
        if not prod_id_raw:
             return web.json_response({"error": "product_id_required"}, status=400)
        
        prod_id = int(prod_id_raw)

        # 1. Fetch Product Metadata + Aggregates
        product_query = """
            SELECT 
                p.id as product_id, p.title, p.price, p.language, 
                p.telegram_file_id, p.gender, p.frequency,
                COALESCE(SUM(pm.amount), 0) as total_revenue,
                COUNT(pm.id) as sales_count
            FROM products p
            LEFT JOIN payments pm ON p.id = pm.product_id AND pm.status = 'approved'
            WHERE p.id = $1
            GROUP BY p.id;
        """
        product_row = await db.fetchrow(product_query, prod_id)
        
        if not product_row:
            return web.json_response({"error": "product_not_found"}, status=404)

        # 2. Fetch Lifecycle Data (14-Day Series)
        chart_query = """
            SELECT 
                CAST(days.day AS DATE) as sales_date,
                COUNT(p.id) as sales_count
            FROM (
                SELECT generate_series(
                    CURRENT_DATE - INTERVAL '13 days', 
                    CURRENT_DATE, 
                    '1 day'::interval
                ) AS day
            ) AS days
            LEFT JOIN payments p ON DATE_TRUNC('day', p.created_at) = days.day 
                AND p.product_id = $1 
                AND p.status = 'approved'
            GROUP BY days.day
            ORDER BY days.day ASC;
        """
        chart_rows = await db.fetch(chart_query, prod_id)
        
        # 3. Data Sanitization (Fixing the Decimal Error)
        # We convert the record to a dict and cast Decimals to floats/ints
        product_data = dict(product_row)
        for key, value in product_data.items():
            if isinstance(value, Decimal):
                product_data[key] = float(value)

        # 4. Final Fusion
        return web.json_response({
            "product": product_data,
            "dates": [str(r['sales_date']) for r in chart_rows],
            "sales": [int(r['sales_count']) for r in chart_rows]
        })

    except ValueError:
        return web.json_response({"error": "invalid_product_id_format"}, status=400)
    except Exception as e:
        # LOG is assumed to be your logger instance
        print(f"CRITICAL_SYSTEM_ERROR: {str(e)}") 
        return web.json_response({"error": "internal_uplink_failure"}, status=500)

async def handle_products_crud(request):
    db = request.app["db"]
    method = request.method
    
    try:
        if method == "POST":
            data = await request.json()
            # Expects: title, price, language, gender, frequency, telegram_file_id
            query = """
                INSERT INTO products (title, price, language, gender, frequency, telegram_file_id, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, TRUE) RETURNING id
            """
            new_id = await db.fetchval(query, data['title'], float(data['price']), 
                                     data['language'], data.get('gender', 'ALL'), 
                                     int(data.get('frequency', 3)), data['telegram_file_id'])
            return web.json_response({"status": "created", "id": new_id})

        elif method == "PATCH":
            prod_id = int(request.query.get('id'))
            data = await request.json()
            query = """
                UPDATE products 
                SET title=$1, price=$2, language=$3, telegram_file_id=$4
                WHERE id=$5
            """
            await db.execute(query, data['title'], float(data['price']), 
                           data['language'], data['telegram_file_id'], prod_id)
            return web.json_response({"status": "updated"})

        elif method == "DELETE":
            prod_id = int(request.query.get('id'))
            # SOFT DELETE: Keep data for revenue stats but hide from store
            await db.execute("UPDATE products SET is_active = FALSE WHERE id = $1", prod_id)
            return web.json_response({"status": "deactivated"})

    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)