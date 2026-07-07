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
    Returns structured streams splitting Product Sales vs Club Subscriptions.
    """
    db = request.app["db"]
    try:
        days = int(request.query.get("days", 7))
    except ValueError:
        days = 7

    try:
        # Assumes db.get_revenue_history returns date, revenue_products, revenue_club, and new_users
        rows = await db.get_revenue_history(days=days)
        
        data = {
            "labels": [str(r["date"]) for r in rows],
            "revenue_products": [float(r.get("revenue_products", 0)) for r in rows],
            "revenue_club": [float(r.get("revenue_club", 0)) for r in rows],
            "users": [int(r["new_users"]) for r in rows],
            "days_limit": days
        }
        return web.json_response(data)
    except Exception:
        LOG.exception("get_revenue_stats failed")
        return web.json_response({
            "labels": [], "revenue_products": [], "revenue_club": [], "users": [], "days_limit": days
        }, status=500)


async def get_distribution_stats(request: web.Request) -> web.Response:
    """
    GET /api/admin/stats/distribution
    Returns counts for the status configuration donut chart.
    """
    db = request.app["db"]
    try:
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
    
    # --- Products (Analysis) ---
    app.router.add_get("/api/admin/products/top_sellers", get_top_sellers)
    app.router.add_get("/api/admin/products/lifecycle", get_product_lifecycle)
    app.router.add_get("/api/admin/products/price_distribution", get_price_distribution)
    app.router.add_get("/api/admin/revenue/products", get_revenue_by_products)

    # --- User Demographics ---
    app.router.add_get('/api/admin/stats/node-intelligence', get_node_intelligence)

    # --- CRUD Helper ---
    app.router.add_post("/api/products", handle_products_crud)
    app.router.add_patch("/api/products", handle_products_crud)
    app.router.add_delete("/api/products", handle_products_crud)
    
    # --- Testimonials ---
    app.router.add_get("/api/admin/testimonials", get_user_testimonials)
    app.router.add_get("/api/admin/testimonials/stats", get_testimonial_kpis)
    
    # --- Transaction & Payout Management ---
    app.router.add_get('/api/admin/payouts/pending', get_pending_payout_stats)
    app.router.add_get('/api/admin/payouts/history', get_payout_history)
    app.router.add_post("/api/admin/payouts/confirm", confirm_payout)


# --- Analysis & Secondary APIs ---------------------------------------------

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
    """Returns the complete User Intelligence Matrix in a single high-performance scan."""
    db = request.app["db"]
    try:
        record = await db.get_node_intelligence_matrix()
        return web.json_response(dict(record))
    except Exception:
        LOG.exception("get_node_intelligence matrix fetch failed")
        return web.json_response({
            "lang_en": 0, "lang_am": 0,
            "gen_male": 0, "gen_female": 0,
            "lvl_beginner": 0, "lvl_inter": 0, "lvl_adv": 0, "lvl_glute": 0,
            "freq_2_3": 0, "freq_3_4": 0, "freq_4_5": 0, "freq_everyday": 0
        })


async def get_payment_kpis(request: web.Request) -> web.Response:
    """GET /api/admin/payments/kpis - Now itemizing revenue channels"""
    db = request.app["db"]
    try:
        # Update your core DB method to return distinct gross tracking parameters
        record = await db.get_payment_kpis()
        return web.json_response(record_to_dict(record))
    except Exception:
        LOG.exception("get_payment_kpis failed")
        return web.json_response({
            "products_revenue": 0, 
            "club_revenue": 0, 
            "total_revenue": 0, 
            "pending_count": 0, 
            "avg_approval_time_minutes": 0, 
            "rejection_rate": 0
        })


# --- Product Lifecycle & Aggregations ---------------------------------------

async def get_product_lifecycle(request):
    db = request.app["db"]
    try:
        prod_id_raw = request.query.get('id')
        if not prod_id_raw:
             return web.json_response({"error": "product_id_required"}, status=400)
        
        prod_id = int(prod_id_raw)

        # 1. Fetch Product Metadata + Aggregates (Strictly targeting explicit guides via product_id match)
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
        
        product_data = dict(product_row)
        for key, value in product_data.items():
            if isinstance(value, Decimal):
                product_data[key] = float(value)

        return web.json_response({
            "product": product_data,
            "dates": [str(r['sales_date']) for r in chart_rows],
            "sales": [int(r['sales_count']) for r in chart_rows]
        })

    except ValueError:
        return web.json_response({"error": "invalid_product_id_format"}, status=400)
    except Exception as e:
        LOG.error(f"CRITICAL_SYSTEM_ERROR: {str(e)}") 
        return web.json_response({"error": "internal_uplink_failure"}, status=500)


async def handle_products_crud(request):
    db = request.app["db"]
    method = request.method
    
    try:
        if method == "POST":
            data = await request.json()
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
            await db.execute("UPDATE products SET is_active = FALSE WHERE id = $1", prod_id)
            return web.json_response({"status": "deactivated"})

    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


# --- Testimonials & Feedback -----------------------------------------------

async def get_testimonial_kpis(request: web.Request) -> web.Response:
    db = request.app["db"]
    try:
        query = """
            SELECT 
                COUNT(*) as total_responses,
                COUNT(DISTINCT user_id) as unique_users,
                AVG(rating_value) FILTER (WHERE question_id = 1) as avg_satisfaction
            FROM user_testimonials;
        """
        record = await db.fetchrow(query)
        
        unique_users = record['unique_users'] or 0
        participation_rate = round((unique_users / 600) * 100, 1) if unique_users > 0 else 0

        payload = {
            "total_feedback_points": record['total_responses'] or 0,
            "avg_rating": round(float(record['avg_satisfaction'] or 0), 1) if record['avg_satisfaction'] else 0,
            "participation_rate": f"{participation_rate}%",
            "active_respondents": unique_users
        }
        
        return web.json_response(payload)
    except Exception:
        LOG.exception("get_testimonial_kpis failed")
        return web.json_response({"error": "internal_error"}, status=500)
    
    
async def get_user_testimonials(request: web.Request) -> web.Response:
    """GET /api/admin/testimonials"""
    db = request.app["db"]
    bot = request.app["bot"] 
    try:
        query = """
            SELECT 
                u.telegram_id,
                u.full_name,
                u.username,
                u.language,
                JSON_AGG(JSON_BUILD_OBJECT(
                    'question_id', q.id,
                    'question_en', q.question_en,
                    'input_type', q.input_type,
                    'rating', ut.rating_value,
                    'text', ut.feedback_text,
                    'created_at', ut.created_at
                ) ORDER BY q.id ASC) as answers
            FROM users u
            JOIN user_testimonials ut ON u.telegram_id = ut.user_id
            JOIN testimonial_questions q ON ut.question_id = q.id
            GROUP BY u.telegram_id, u.full_name, u.username, u.language
            ORDER BY MAX(ut.created_at) DESC;
        """
        rows = await db.fetch(query)
        results = records_to_list(rows)

        for user in results:
            try:
                chat = await bot.get_chat(user['telegram_id'])
                user['live_name'] = chat.first_name or user['full_name']
            except Exception:
                user['live_name'] = user['full_name']

        return web.json_response(results)
    except Exception:
        LOG.exception("get_user_testimonials failed")
        return web.json_response({"error": "internal_error"}, status=500)


# --- Payouts & Separate Stream Financial Core -------------------------------

async def get_pending_payout_stats(request: web.Request) -> web.Response:
    """
    GET /api/admin/payouts/pending
    Calculates operational trends while distinguishing between product collections and recurring club runs.
    """
    db = request.app["db"]
    try:
        # 1. Fetch payout reference checkpoint
        last_payout_ts = await db.fetchval(
            "SELECT value_timestamp FROM system_metadata WHERE key = 'last_payout_at'"
        )
        last_payout_ts = last_payout_ts or datetime.min

        # 2. Extract itemized Pending Balances (Product vs Club streams)
        pending_row = await db.fetchrow("""
    SELECT 
        COALESCE((
            SELECT SUM(amount) FROM payments 
            WHERE status = 'approved' AND approved_at > $1
        ), 0) as products_total,
        COALESCE((
            SELECT SUM(amount) FROM club_payments 
            WHERE status = 'approved' AND processed_at > $1
        ), 0) as club_total
""", last_payout_ts)
        
        pending_products = Decimal(str(pending_row['products_total']))
        pending_club = Decimal(str(pending_row['club_total']))
        pending_revenue_total = pending_products + pending_club

        # 3. Calculate Itemized Lifetime KPIs
        stats = await db.fetchrow("""
    SELECT 
        (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'approved') as lt_products_gross,
        (SELECT COALESCE(SUM(amount), 0) FROM club_payments WHERE status = 'approved') as lt_club_gross,
        (SELECT COALESCE(SUM(operational_deductions), 0) FROM payout_history) as lt_burn,
        (SELECT COALESCE(SUM(coach_share + dagmawi_share), 0) FROM payout_history) as lt_paid
""")
        
        lt_products_gross = Decimal(str(stats['lt_products_gross']))
        lt_club_gross = Decimal(str(stats['lt_club_gross']))
        lt_gross_total = lt_products_gross + lt_club_gross
        lt_burn = Decimal(str(stats['lt_burn']))
        lt_paid = Decimal(str(stats['lt_paid']))

        # Compute accurate remaining cash reserves
        net_profit_to_date = lt_gross_total - lt_burn - lt_paid

        # 4. Tier System Verification (Based on combined cumulative efficiency volume)
        cumulative_efficiency_net = lt_gross_total - lt_burn
        tier_goal = Decimal('500000')
        current_tier = 2 if cumulative_efficiency_net >= tier_goal else 1
        tier_progress = min(Decimal('100'), (cumulative_efficiency_net / tier_goal * 100)) if cumulative_efficiency_net > 0 else Decimal('0')

        # 5. Profit Performance Efficiency
        efficiency = (cumulative_efficiency_net / lt_gross_total * 100) if lt_gross_total > 0 else 0

        # 6. Gather Historical Data Coordinates
        history_points = await db.fetch("""
            SELECT net_profit, payout_date 
            FROM payout_history 
            ORDER BY payout_date DESC LIMIT 15
        """)

        return web.json_response({
            "pending_revenue": float(pending_revenue_total),
            "pending_products_revenue": float(pending_products),
            "pending_club_revenue": float(pending_club),
            "cumulative_profit": float(net_profit_to_date), 
            "lifetime_gross": float(lt_gross_total),
            "lifetime_products_gross": float(lt_products_gross),
            "lifetime_club_gross": float(lt_club_gross),
            "lifetime_burn": float(lt_burn),
            "efficiency": float(round(efficiency, 1)),
            "current_tier": current_tier,
            "tier_progress": float(round(tier_progress, 1)),
            "trend_data": [float(row['net_profit']) for row in reversed(history_points)],
            "trend_labels": [row['payout_date'].strftime('%m/%d') for row in reversed(history_points)]
        })
    except Exception:
        LOG.exception("KPI Stats Logic Failure")
        return web.json_response({"error": "sync_error"}, status=500)


async def confirm_payout(request: web.Request) -> web.Response:
    """
    POST /api/admin/payouts/confirm
    Processes distributions while distinctly auditing product vs club cashflow properties.
    """
    db = request.app["db"]
    try:
        data = await request.json()
        entry_type = data.get('entry_type', 'payout')
        note = data.get('note', 'N/A')

        # Accept isolated incoming values or fallback safely to uniform values
        req_products = data.get('products_amount')
        req_club = data.get('club_amount')
        
        if req_products is not None or req_club is not None:
            products_amount = Decimal(str(req_products or 0))
            club_amount = Decimal(str(req_club or 0))
            total_gross_input = products_amount + club_amount
        else:
            total_gross_input = Decimal(str(data.get('amount', 0)))
            # If uniform amount came through, treat it as general distribution
            products_amount = total_gross_input 
            club_amount = Decimal('0')

        # 1. Access latest balancing context
        stats = await db.fetchrow("""
            SELECT 
                (SELECT net_profit FROM payout_history ORDER BY payout_date DESC, id DESC LIMIT 1) as last_balance,
                (SELECT COALESCE(SUM(gross_revenue), 0) FROM payout_history) as lifetime_gross
        """)
        
        current_balance = Decimal(str(stats['last_balance'] or 0))
        lifetime_gross = Decimal(str(stats['lifetime_gross'] or 0))

        # 2. Dynamic Profit Distribution Ratios
        tier = 2 if lifetime_gross >= 500000 else 1
        coach_ratio = Decimal('0.70') if tier == 2 else Decimal('0.60')
        dag_ratio = Decimal('0.30') if tier == 2 else Decimal('0.40')

        if entry_type == 'payout':
            deductions_val = data.get('deductions') or 0
            deductions = Decimal(str(deductions_val))
            
            gross_revenue = total_gross_input
            operational_deductions = deductions
            
            # Divide net distributable amounts via calculated tier weights
            distributable = gross_revenue - operational_deductions
            coach_share = max(Decimal('0'), distributable * coach_ratio)
            dag_share = max(Decimal('0'), distributable * dag_ratio)
            
            transaction_impact = -gross_revenue
        else:
            # Operational Expense
            gross_revenue = Decimal('0')
            products_amount = Decimal('0')
            club_amount = Decimal('0')
            operational_deductions = Decimal(str(data.get('amount', 0)))
            coach_share = Decimal('0')
            dag_share = Decimal('0')
            
            transaction_impact = -operational_deductions

        # 3. Calculate target ledger change
        new_running_balance = current_balance + transaction_impact

        # 4. Write verified state changes to storage
        # Note: If your payout_history table contains products_revenue and club_revenue columns, 
        # append them directly to your insert instruction below.
        async with db._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("""
                    INSERT INTO payout_history 
                    (gross_revenue, operational_deductions, net_profit, 
                     coach_share, dagmawi_share, tier_applied, expense_note, entry_type)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, gross_revenue, operational_deductions, new_running_balance, 
                    coach_share, dag_share, tier, note, entry_type)
                
                if entry_type == 'payout':
                    await conn.execute("""
                        INSERT INTO system_metadata (key, value_timestamp) 
                        VALUES ('last_payout_at', NOW())
                        ON CONFLICT (key) DO UPDATE SET value_timestamp = NOW()
                    """)

        return web.json_response({
            "status": "success", 
            "new_balance": str(new_running_balance),
            "impact": str(transaction_impact)
        })

    except Exception:
        LOG.exception("CRITICAL_FINANCIAL_SYNC_ERROR")
        return web.json_response({"error": "logic_gate_failure"}, status=500)


async def get_payout_history(request: web.Request) -> web.Response:
    """GET /api/admin/payouts/history"""
    db = request.app["db"]
    try:
        rows = await db.fetch("SELECT * FROM payout_history ORDER BY payout_date DESC LIMIT 50")
        return web.json_response(records_to_list(rows))
    except Exception:
        LOG.exception("get_payout_history failed")
        return web.json_response([], status=500)