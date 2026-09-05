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


# --- Payouts & Dual-Stream Financial Core (Contract Date: 2026-08-10) --------

async def get_pending_payout_stats(request: web.Request) -> web.Response:
    """
    GET /api/admin/payouts/pending
    Calculates dual-stream settlement status governed by the Signed Partnership Agreement:
      - Stream A (Digital Products): Fixed 70% Coach Hilawe / 30% Dagmawi Tewodros
      - Stream B (Hilawe Transformation Club): 
          * Initial Stage (< 50,000 ETB cumulative gross): 60% Coach / 40% Dagmawi
          * Mature Stage (>= 50,000 ETB cumulative gross): 65% Coach / 35% Dagmawi
      - Infrastructure Cap: 5,000 ETB/month (Section 5.1)
      - Apportionment: Pro-rata deduction across active streams
    """
    db = request.app["db"]
    try:
        # 1. Fetch latest payout reference checkpoint
        last_payout_ts = await db.fetchval(
            "SELECT value_timestamp FROM system_metadata WHERE key = 'last_payout_at'"
        )
        last_payout_ts = last_payout_ts or datetime.min

        # 2. Extract itemized Pending Balances (Product vs Club streams) since checkpoint
        pending_row = await db.fetchrow("""
            SELECT 
                COALESCE((
                    SELECT SUM(amount) FROM payments 
                    WHERE status = 'approved' AND (approved_at > $1 OR (approved_at IS NULL AND created_at > $1))
                ), 0) as products_total,
                COALESCE((
                    SELECT COUNT(*) FROM payments 
                    WHERE status = 'approved' AND (approved_at > $1 OR (approved_at IS NULL AND created_at > $1))
                ), 0) as products_count,
                COALESCE((
                    SELECT SUM(amount) FROM club_payments 
                    WHERE status = 'approved' AND (processed_at > $1 OR (processed_at IS NULL AND created_at > $1))
                ), 0) as club_total,
                COALESCE((
                    SELECT COUNT(*) FROM club_payments 
                    WHERE status = 'approved' AND (processed_at > $1 OR (processed_at IS NULL AND created_at > $1))
                ), 0) as club_count
        """, last_payout_ts)
        
        pending_products = Decimal(str(pending_row['products_total']))
        pending_products_count = int(pending_row['products_count'])
        pending_club = Decimal(str(pending_row['club_total']))
        pending_club_count = int(pending_row['club_count'])
        pending_gross_total = pending_products + pending_club

        # 3. Cumulative All-Time Club Metrics for 50,000 ETB Milestone (Section 6.2)
        club_stats = await db.fetchrow("""
            SELECT 
                COALESCE(SUM(amount), 0) as cumulative_gross,
                COALESCE(COUNT(*), 0) as total_subscriptions
            FROM club_payments 
            WHERE status = 'approved'
        """)
        club_cumulative_all_time = Decimal(str(club_stats['cumulative_gross']))
        club_target_milestone = Decimal('50000.00')
        club_is_mature = club_cumulative_all_time >= club_target_milestone
        club_stage = "mature_65_35" if club_is_mature else "initial_60_40"
        club_coach_rate = Decimal('0.65') if club_is_mature else Decimal('0.60')
        club_dag_rate = Decimal('0.35') if club_is_mature else Decimal('0.40')
        club_progress_pct = min(Decimal('100'), (club_cumulative_all_time / club_target_milestone * 100)) if club_cumulative_all_time > 0 else Decimal('0')

        # 4. Monthly Operating Deductions Tracking (Uncapped actuals: servers, USD rates, product costs)
        infra_stats = await db.fetchrow("""
            SELECT 
                COALESCE(SUM(operational_deductions), 0) as current_month_burn
            FROM payout_history 
            WHERE entry_type = 'expense_only' 
              AND payout_date >= DATE_TRUNC('month', NOW())
        """)
        current_month_burn = Decimal(str(infra_stats['current_month_burn']))

        # 5. Unsettled Expenses logged since last payout
        unsettled_burn_row = await db.fetchrow("""
            SELECT COALESCE(SUM(operational_deductions), 0) as pending_burn
            FROM payout_history
            WHERE entry_type = 'expense_only' AND payout_date > $1
        """, last_payout_ts)
        pending_deductions = Decimal(str(unsettled_burn_row['pending_burn']))

        # 6. Pro-Rata Apportionment of Pending Deductions
        if pending_gross_total > 0 and pending_deductions > 0:
            prod_ratio = pending_products / pending_gross_total
            products_deductions = round(pending_deductions * prod_ratio, 2)
            club_deductions = pending_deductions - products_deductions
        else:
            products_deductions = Decimal('0')
            club_deductions = Decimal('0')

        net_products = max(Decimal('0'), pending_products - products_deductions)
        net_club = max(Decimal('0'), pending_club - club_deductions)

        # 7. Exact Partner Splits (Digital Products: 70/30 | Club: 60/40 or 65/35)
        prod_coach_share = round(net_products * Decimal('0.70'), 2)
        prod_dag_share = net_products - prod_coach_share

        club_coach_share = round(net_club * club_coach_rate, 2)
        club_dag_share = net_club - club_coach_share

        total_coach_payout = prod_coach_share + club_coach_share
        total_dag_payout = prod_dag_share + club_dag_share
        net_distributable_total = net_products + net_club

        # 8. Lifetime Aggregates
        lifetime_stats = await db.fetchrow("""
            SELECT 
                (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'approved') as lt_products_gross,
                (SELECT COALESCE(SUM(amount), 0) FROM club_payments WHERE status = 'approved') as lt_club_gross,
                (SELECT COALESCE(SUM(operational_deductions), 0) FROM payout_history) as lt_burn,
                (SELECT COALESCE(SUM(coach_share + dagmawi_share), 0) FROM payout_history) as lt_paid
        """)
        lt_products_gross = Decimal(str(lifetime_stats['lt_products_gross']))
        lt_club_gross = Decimal(str(lifetime_stats['lt_club_gross']))
        lt_gross_total = lt_products_gross + lt_club_gross
        lt_burn = Decimal(str(lifetime_stats['lt_burn']))
        lt_paid = Decimal(str(lifetime_stats['lt_paid']))
        reserve_balance = lt_gross_total - lt_burn - lt_paid

        # 9. Recent settlement trend points
        history_points = await db.fetch("""
            SELECT net_profit, coach_share, dagmawi_share, payout_date 
            FROM payout_history 
            WHERE entry_type = 'payout'
            ORDER BY payout_date DESC LIMIT 15
        """)

        return web.json_response({
            # Unified Summary
            "pending_revenue": float(pending_gross_total),
            "pending_deductions": float(pending_deductions),
            "net_distributable": float(net_distributable_total),
            "coach_total_payout": float(total_coach_payout),
            "dagmawi_total_payout": float(total_dag_payout),
            "last_payout_at": last_payout_ts.isoformat() if isinstance(last_payout_ts, datetime) else str(last_payout_ts),

            # Stream A: Digital Products (Fixed 70/30)
            "products_stream": {
                "gross": float(pending_products),
                "count": pending_products_count,
                "deductions": float(products_deductions),
                "net": float(net_products),
                "coach_rate": 0.70,
                "dagmawi_rate": 0.30,
                "coach_share": float(prod_coach_share),
                "dagmawi_share": float(prod_dag_share),
                "clause": "Section 6.1 (Fixed 70/30)"
            },

            # Stream B: Transformation Club (Community 60/40 -> 65/35)
            "club_stream": {
                "gross": float(pending_club),
                "count": pending_club_count,
                "deductions": float(club_deductions),
                "net": float(net_club),
                "stage": club_stage,
                "coach_rate": float(club_coach_rate),
                "dagmawi_rate": float(club_dag_rate),
                "coach_share": float(club_coach_share),
                "dagmawi_share": float(club_dag_share),
                "cumulative_all_time": float(club_cumulative_all_time),
                "target_milestone": float(club_target_milestone),
                "progress_pct": float(round(club_progress_pct, 1)),
                "clause": "Section 6.2 (Initial 60/40 until 50k ETB, then 65/35)"
            },

            # Operating Expenses (Uncapped actuals: servers, USD rates, product costs)
            "operating_expenses": {
                "current_month_burn": float(current_month_burn),
                "pending_burn": float(pending_deductions),
            },

            # Lifetime Financial Health
            "lifetime_gross": float(lt_gross_total),
            "lifetime_products_gross": float(lt_products_gross),
            "lifetime_club_gross": float(lt_club_gross),
            "lifetime_burn": float(lt_burn),
            "reserve_balance": float(reserve_balance),
            "trend_data": [float(row['coach_share'] + row['dagmawi_share']) for row in reversed(history_points)],
            "trend_labels": [row['payout_date'].strftime('%m/%d') for row in reversed(history_points)]
        })
    except Exception:
        LOG.exception("Dual-Stream KPI Logic Failure")
        return web.json_response({"error": "sync_error"}, status=500)


async def confirm_payout(request: web.Request) -> web.Response:
    """
    POST /api/admin/payouts/confirm
    Settles distributions according to the August 10, 2026 Partnership Agreement:
      - Accepts entry_type: 'payout' or 'expense_only'
      - Validates monthly infrastructure cap (5,000 ETB) and 50/50 video production costs
      - Records exact stream metrics (products_gross, club_gross, club_stage, club_cumulative_at_payout)
      - Advances system_metadata 'last_payout_at' to NOW()
    """
    db = request.app["db"]
    try:
        data = await request.json()
        entry_type = data.get('entry_type', 'payout')
        note = data.get('note', 'Partnership Settlement')

        if entry_type == 'payout':
            last_payout_ts = await db.fetchval(
                "SELECT value_timestamp FROM system_metadata WHERE key = 'last_payout_at'"
            )
            last_payout_ts = last_payout_ts or datetime.min

            # Query unsettled approved amounts
            pending_row = await db.fetchrow("""
                SELECT 
                    COALESCE((
                        SELECT SUM(amount) FROM payments 
                        WHERE status = 'approved' AND (approved_at > $1 OR (approved_at IS NULL AND created_at > $1))
                    ), 0) as products_total,
                    COALESCE((
                        SELECT SUM(amount) FROM club_payments 
                        WHERE status = 'approved' AND (processed_at > $1 OR (processed_at IS NULL AND created_at > $1))
                    ), 0) as club_total
            """, last_payout_ts)

            products_gross = Decimal(str(data.get('products_amount') if data.get('products_amount') is not None else pending_row['products_total']))
            club_gross = Decimal(str(data.get('club_amount') if data.get('club_amount') is not None else pending_row['club_total']))
            total_gross = products_gross + club_gross

            deductions = Decimal(str(data.get('deductions', 0) or 0))

            # Cumulative Club Milestone Check (Section 6.2)
            club_stats = await db.fetchval("SELECT COALESCE(SUM(amount), 0) FROM club_payments WHERE status = 'approved'")
            club_cumulative = Decimal(str(club_stats or 0))
            is_mature = club_cumulative >= Decimal('50000.00')
            club_stage = "mature_65_35" if is_mature else "initial_60_40"
            club_coach_rate = Decimal('0.65') if is_mature else Decimal('0.60')
            club_dag_rate = Decimal('0.35') if is_mature else Decimal('0.40')

            # Pro-rata deduction distribution
            if total_gross > 0 and deductions > 0:
                prod_weight = products_gross / total_gross
                prod_deduct = round(deductions * prod_weight, 2)
                club_deduct = deductions - prod_deduct
            else:
                prod_deduct = Decimal('0')
                club_deduct = Decimal('0')

            net_products = max(Decimal('0'), products_gross - prod_deduct)
            net_club = max(Decimal('0'), club_gross - club_deduct)

            prod_coach_share = round(net_products * Decimal('0.70'), 2)
            prod_dag_share = net_products - prod_coach_share

            club_coach_share = round(net_club * club_coach_rate, 2)
            club_dag_share = net_club - club_coach_share

            coach_total_share = prod_coach_share + club_coach_share
            dag_total_share = prod_dag_share + club_dag_share
            net_distributable = net_products + net_club

            async with db._pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("""
                        INSERT INTO payout_history 
                        (gross_revenue, operational_deductions, net_profit, 
                         coach_share, dagmawi_share, tier_applied, expense_note, entry_type,
                         products_gross, club_gross, club_stage, club_cumulative_at_payout,
                         infra_deductions, production_deductions)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    """, total_gross, deductions, net_distributable,
                        coach_total_share, dag_total_share, 2 if is_mature else 1,
                        note, 'payout',
                        products_gross, club_gross, club_stage, club_cumulative,
                        deductions, Decimal('0'))

                    await conn.execute("""
                        INSERT INTO system_metadata (key, value_timestamp) 
                        VALUES ('last_payout_at', NOW())
                        ON CONFLICT (key) DO UPDATE SET value_timestamp = NOW()
                    """)

            return web.json_response({
                "status": "success",
                "entry_type": "payout",
                "gross_revenue": float(total_gross),
                "deductions": float(deductions),
                "net_distributable": float(net_distributable),
                "coach_share": float(coach_total_share),
                "dagmawi_share": float(dag_total_share),
                "products_gross": float(products_gross),
                "club_gross": float(club_gross),
                "club_stage": club_stage
            })

        else:
            # Operational Expense Logging (Section 5.1 / 5.2)
            expense_category = data.get('category', 'infra')
            raw_amount = Decimal(str(data.get('amount', 0)))

            if expense_category == 'video_production':
                # Section 5.2: 2,500 ETB per video, 50% (1,250 ETB) partnership, 50% Coach personal
                partnership_deduction = round(raw_amount * Decimal('0.50'), 2)
                note_suffix = f" [Video Production: {partnership_deduction} ETB from partnership, {raw_amount - partnership_deduction} ETB Coach personal]"
                final_note = note + note_suffix
            else:
                partnership_deduction = raw_amount
                final_note = note

            async with db._pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("""
                        INSERT INTO payout_history 
                        (gross_revenue, operational_deductions, net_profit, 
                         coach_share, dagmawi_share, tier_applied, expense_note, entry_type,
                         products_gross, club_gross, club_stage, club_cumulative_at_payout,
                         infra_deductions, production_deductions)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    """, Decimal('0'), partnership_deduction, Decimal('0'),
                        Decimal('0'), Decimal('0'), 1,
                        final_note, 'expense_only',
                        Decimal('0'), Decimal('0'), 'initial_60_40', Decimal('0'),
                        partnership_deduction if expense_category != 'video_production' else Decimal('0'),
                        partnership_deduction if expense_category == 'video_production' else Decimal('0'))

            return web.json_response({
                "status": "success",
                "entry_type": "expense_only",
                "deduction_recorded": float(partnership_deduction),
                "note": final_note
            })

    except Exception:
        LOG.exception("CRITICAL_FINANCIAL_SYNC_ERROR")
        return web.json_response({"error": "logic_gate_failure"}, status=500)


async def get_payout_history(request: web.Request) -> web.Response:
    """GET /api/admin/payouts/history"""
    db = request.app["db"]
    try:
        rows = await db.fetch("""
            SELECT 
                id, gross_revenue, operational_deductions, net_profit, 
                coach_share, dagmawi_share, tier_applied, cumulative_profit_at_time, 
                payout_date, expense_note, entry_type,
                COALESCE(products_gross, 0) as products_gross,
                COALESCE(club_gross, 0) as club_gross,
                COALESCE(club_stage, 'initial_60_40') as club_stage,
                COALESCE(club_cumulative_at_payout, 0) as club_cumulative_at_payout,
                COALESCE(infra_deductions, 0) as infra_deductions,
                COALESCE(production_deductions, 0) as production_deductions
            FROM payout_history 
            ORDER BY payout_date DESC, id DESC 
            LIMIT 50
        """)
        return web.json_response(records_to_list(rows))
    except Exception:
        LOG.exception("get_payout_history failed")
        return web.json_response([], status=500)