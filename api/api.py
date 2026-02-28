from fastapi import FastAPI, Depends, HTTPException, Header, status
from typing import List, Optional
from pydantic import BaseModel
import asyncpg
import os
from datetime import datetime

app = FastAPI(title="DigitalRevenue Admin API")

# DB Connection Logic
async def get_db():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    try:
        yield conn
    finally:
        await conn.close()

# --- SCHEMAS ---
class DashboardStats(BaseModel):
    total_revenue: float
    pending_payments: int
    active_users: int
    conversion_rate: float

class PaymentUpdate(BaseModel):
    status: str # 'approved' or 'rejected'

# --- ENDPOINTS ---

@app.get("/api/admin/stats", response_model=DashboardStats)
async def get_admin_stats(db: asyncpg.Connection = Depends(get_db)):
    """Fetches high-level KPIs for the top-bar visuals."""
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
    return stats

@app.get("/api/admin/payments/recent")
async def get_recent_payments(db: asyncpg.Connection = Depends(get_db)):
    """Real-time feed of payment attempts."""
    rows = await db.fetch("""
        SELECT p.*, u.full_name, u.username, pr.title 
        FROM payments p
        JOIN users u ON p.user_id = u.telegram_id
        JOIN products pr ON p.product_id = pr.id
        ORDER BY p.created_at DESC LIMIT 10
    """)
    return [dict(r) for r in rows]

@app.post("/api/admin/payments/{payment_id}/verify")
async def verify_payment(payment_id: int, data: PaymentUpdate, db: asyncpg.Connection = Depends(get_db)):
    """The 'Approve/Reject' action for the admin."""
    result = await db.execute(
        "UPDATE payments SET status = $1 WHERE id = $2", 
        data.status, payment_id
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Payment not found")
    return {"status": "success", "message": f"Payment {data.status}"}

@app.get("/api/admin/users/growth")
async def get_user_growth(db: asyncpg.Connection = Depends(get_db)):
    """Data for the growth line chart."""
    rows = await db.fetch("""
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM users
        WHERE created_at > CURRENT_DATE - INTERVAL '14 days'
        GROUP BY DATE(created_at)
        ORDER BY date ASC
    """)
    return [dict(r) for r in rows]