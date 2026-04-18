# db.py
import asyncpg
import logging
from typing import Optional, Any, Dict, List
from asyncpg import Pool

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id BIGINT PRIMARY KEY,
    full_name TEXT,
    username TEXT,
    language VARCHAR(2) DEFAULT 'EN',
    gender VARCHAR(10),
    level VARCHAR(20),
    frequency INTEGER,
    onboarding_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    language VARCHAR(2) NOT NULL,
    gender VARCHAR(10) NOT NULL,
    level VARCHAR(20) NOT NULL,
    frequency INTEGER NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    telegram_file_id TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id),
    product_id INTEGER REFERENCES products(id),
    amount DECIMAL(10, 2),
    proof_file_id TEXT,
    status VARCHAR(20) DEFAULT 'pending', -- pending, approved, rejected
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


-- Add per-user deal fields and broadcasts table
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS deal_expires_at TIMESTAMP WITH TIME ZONE,
  ADD COLUMN IF NOT EXISTS deal_price DECIMAL(10,2);

CREATE TABLE IF NOT EXISTS broadcasts (
  id SERIAL PRIMARY KEY,
  name TEXT,
  target_filter TEXT,
  language VARCHAR(2),
  started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  expires_at TIMESTAMP WITH TIME ZONE,
  total_target INTEGER DEFAULT 0,
  sent_count INTEGER DEFAULT 0,
  failed_count INTEGER DEFAULT 0,
  admin_id BIGINT,
  cancelled BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Optional index for quick lookup of active deals
CREATE INDEX IF NOT EXISTS idx_users_deal_expires ON users (deal_expires_at) WHERE deal_expires_at IS NOT NULL;


-- Optimization Indexes
CREATE INDEX IF NOT EXISTS idx_products_filter ON products (language, gender, level, frequency) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_users_tid ON users (telegram_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments (status);
ALTER TABLE users ADD COLUMN IF NOT EXISTS goal TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS obstacle TEXT;

ALTER TABLE payments 
ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE users ADD COLUMN IF NOT EXISTS last_pitch_at TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS reminded BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS has_paid BOOLEAN DEFAULT FALSE;


-- Track the message we sent so we can edit it later
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_broadcast_msg_id BIGINT;

-- Store the product ID directly on the user for faster background processing
ALTER TABLE users ADD COLUMN IF NOT EXISTS matched_product_id INTEGER REFERENCES products(id);


-- Backfill existing approved rows with created_at
UPDATE payments 
SET approved_at = created_at 
WHERE status = 'approved' AND approved_at IS NULL;

-- Testimonial new sql migrations
CREATE TABLE IF NOT EXISTS testimonial_questions (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(50) UNIQUE NOT NULL, -- e.g., 'overall_satisfaction'
    question_en TEXT NOT NULL,
    question_am TEXT NOT NULL,
    input_type VARCHAR(20) DEFAULT 'rating', -- 'rating', 'emoji', 'text'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS user_testimonials (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    question_id INTEGER REFERENCES testimonial_questions(id),
    rating_value INTEGER, -- Store 1-5 stars or emoji index
    feedback_text TEXT,   -- Store the "Why" or "Transformation story"
    is_approved BOOLEAN DEFAULT FALSE, -- Admin toggle for API/Publicity
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraint: One answer per user per question
    CONSTRAINT unique_user_question UNIQUE (user_id, question_id)
);

CREATE TABLE IF NOT EXISTS testimonial_logs (
    question_id INTEGER,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS price_survey_results (
    user_id BIGINT PRIMARY KEY,
    selected_price INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Track every distribution made to Coach and Dagmawi
CREATE TABLE IF NOT EXISTS payout_history (
    id SERIAL PRIMARY KEY,
    gross_revenue DECIMAL(12, 2) NOT NULL,
    operational_deductions DECIMAL(12, 2) DEFAULT 0,
    net_profit DECIMAL(12, 2) NOT NULL,
    coach_share DECIMAL(12, 2) NOT NULL,
    dagmawi_share DECIMAL(12, 2) NOT NULL,
    tier_applied INTEGER DEFAULT 1,
    cumulative_profit_at_time DECIMAL(12, 2), -- To track the 500k milestone
    payout_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Simple table to store the last time a payout was "confirmed"
CREATE TABLE IF NOT EXISTS system_metadata (
    key TEXT PRIMARY KEY,
    value_timestamp TIMESTAMP WITH TIME ZONE,
    value_numeric DECIMAL(12, 2)
);

ALTER TABLE payout_history 
ADD COLUMN IF NOT EXISTS expense_note TEXT,
ADD COLUMN IF NOT EXISTS entry_type TEXT DEFAULT 'payout';

"""

class Database:
    
    
    def __init__(self, dsn: str):
        self.dsn = dsn
        self._pool: Optional[Pool] = None
        

    async def connect(self):
        if not self._pool:
            self._pool = await asyncpg.create_pool(
                self.dsn,
                min_size=1,
                max_size=10,
                statement_cache_size=0
            )
            logging.info("Connected to PostgreSQL")

    async def setup(self):
        async with self._pool.acquire() as conn:
            await conn.execute(SCHEMA_SQL)
            
    async def fetch(self, query, *args):
        async with self._pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query, *args):
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def execute(self, query, *args):
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetchval(self, query, *args):
        async with self._pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def get_user(self, telegram_id: int):
        return await self._pool.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)

    async def create_or_update_user(self, telegram_id, **kwargs):
    # This logic creates the user if they don't exist, or updates them if they do
        keys = kwargs.keys()
        values = list(kwargs.values())
        
        update_stmt = ", ".join([f"{k} = EXCLUDED.{k}" for k in keys])
        columns = ", ".join(keys)
        placeholders = ", ".join([f"${i+2}" for i in range(len(keys))])
        
        query = f"""
            INSERT INTO users (telegram_id, {columns}) 
            VALUES ($1, {placeholders})
            ON CONFLICT (telegram_id) 
            DO UPDATE SET {update_stmt}
        """
        await self._pool.execute(query, telegram_id, *values)
    # --- PRODUCT LOGIC ---
    async def match_product(self, language: str, level: str, frequency: int):
        query = """
            SELECT * FROM products 
            WHERE language = $1 
            AND level = $2 
            AND frequency = $3
            AND is_active = TRUE
            LIMIT 1
        """
        return await self._pool.fetchrow(query, language, level, frequency)

    async def add_product(self, title: str, lang: str, gender: str, level: str, freq: int, price: float, file_id: str):
        query = """
            INSERT INTO products (title, language, gender, level, frequency, price, telegram_file_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        await self._pool.execute(query, title, lang, gender, level, freq, price, file_id)

    # --- PAYMENT & ADMIN LOGIC ---
    async def create_payment(self, user_id: int, product_id: int, proof_id: str, amount: float):
        query = """
            INSERT INTO payments (user_id, product_id, proof_file_id, amount)
            VALUES ($1, $2, $3, $4) RETURNING id
        """
        return await self._pool.fetchval(query, user_id, product_id, proof_id, amount)

    async def get_admin_stats_bot(self):
        """Fetches elite-level business intelligence including pending tasks."""
        query = """
            SELECT 
                (SELECT count(*) FROM users) as users,
                (SELECT count(*) FROM payments WHERE status = 'approved') as sales,
                (SELECT sum(amount) FROM payments WHERE status = 'approved') as revenue,
                (SELECT count(*) FROM payments WHERE status = 'pending') as pending_count
        """
        return await self._pool.fetchrow(query)
    
    async def get_recent_payment_proofs(self, limit: int = 5) -> List[asyncpg.Record]:
        """Fetches the last N payments that have a proof_file_id for testing."""
        query = """
            SELECT p.id, p.proof_file_id, p.amount, u.full_name, pr.title
            FROM payments p
            JOIN users u ON p.user_id = u.telegram_id
            JOIN products pr ON p.product_id = pr.id
            WHERE p.proof_file_id IS NOT NULL
            ORDER BY p.created_at DESC
            LIMIT $1
        """
        return await self._pool.fetch(query, limit)

    async def approve_payment(self, payment_id: int) -> Optional[Dict]:
        """Approves payment and returns user_id + file_id for automated delivery."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Update status and set approved_at timestamp
                row = await conn.fetchrow("""
                    UPDATE payments 
                    SET status = 'approved',
                        approved_at = CURRENT_TIMESTAMP
                    WHERE id = $1 
                    RETURNING user_id, product_id
                """, payment_id)
                
                if not row:
                    return None
                
                # Get the PDF and User Language
                return await conn.fetchrow("""
                    SELECT p.telegram_file_id, u.language, u.telegram_id as user_id
                    FROM products p
                    JOIN users u ON u.telegram_id = $1
                    WHERE p.id = $2
                """, row['user_id'], row['product_id'])


    async def disconnect(self):
        if self._pool:
            await self._pool.close()
            
    
    async def get_user_language(self, telegram_id: int) -> str:
        """Return the user's language code (default 'EN')."""
        query = "SELECT language FROM users WHERE telegram_id = $1"
        row = await self._pool.fetchrow(query, telegram_id)
        if row and row["language"]:
            return row["language"]
        return "EN"
    
    async def get_ghost_users(self) -> List[asyncpg.Record]:
        query = """
            SELECT telegram_id AS user_id, language, level
            FROM users
            WHERE last_pitch_at < NOW() - INTERVAL '3 hours'
            AND last_pitch_at > NOW() - INTERVAL '6 hours'
            AND has_paid = FALSE
            AND reminded = FALSE
        """
        return await self._pool.fetch(query)

    
    async def get_pending_payments(self, limit: int = 5, offset: int = 0):
        query = """
            SELECT p.id, p.amount, p.created_at, u.username, u.full_name, pr.title 
            FROM payments p
            JOIN users u ON p.user_id = u.telegram_id
            JOIN products pr ON p.product_id = pr.id
            WHERE p.status = 'pending'
            ORDER BY p.created_at DESC
            LIMIT $1 OFFSET $2
        """
        return await self._pool.fetch(query, limit, offset)

    async def count_pending_payments(self):
        return await self._pool.fetchval("SELECT count(*) FROM payments WHERE status = 'pending'")
    
    
    async def get_all_products(self, limit: int = 10, offset: int = 0):
    # Change 'lang' to 'language' and 'telegram_file_id' if needed
        query = """
            SELECT id, title, price, is_active, language 
            FROM products 
            ORDER BY id DESC 
            LIMIT $1 OFFSET $2
        """
        return await self._pool.fetch(query, limit, offset)

    async def toggle_product_status(self, product_id: int):
        # Standard toggle logic
        return await self._pool.execute(
            "UPDATE products SET is_active = NOT is_active WHERE id = $1", 
            product_id
        )

    async def delete_product(self, product_id: int):
        return await self._pool.execute("DELETE FROM products WHERE id = $1", product_id)

    async def count_products(self):
        return await self._pool.fetchval("SELECT count(*) FROM products")
    async def get_recent_payments(self, limit: int = 10) -> List[Dict]:
        """
        Return the most recent payments (any status) with user and product info.
        """
        query = """
            SELECT p.id, p.amount, p.status, p.created_at,
                   u.full_name, u.username,
                   pr.title
            FROM payments p
            JOIN users u ON p.user_id = u.telegram_id
            JOIN products pr ON p.product_id = pr.id
            ORDER BY p.created_at DESC
            LIMIT $1
        """
        return await self._pool.fetch(query, limit)

    async def reject_payment(self, payment_id: int) -> bool:
        """
        Mark a payment as rejected. Returns True if updated, False if not found.
        """
        result = await self._pool.execute(
            "UPDATE payments SET status = 'rejected' WHERE id = $1",
            payment_id
        )
        return result != "UPDATE 0"

    async def get_products(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        Return products list for admin view.
        """
        query = """
            SELECT id, title, price, is_active, language, gender, level, frequency, created_at
            FROM products
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """
        return await self._pool.fetch(query, limit, offset)

    async def create_product(self, title: str, language: str, gender: str,
                             level: str, frequency: int, price: float, file_id: str) -> int:
        """
        Insert a new product and return its id.
        """
        query = """
            INSERT INTO products (title, language, gender, level, frequency, price, telegram_file_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """
        return await self._pool.fetchval(query, title, language, gender,
                                         level, frequency, price, file_id)
        
    
    # --- ANALYTICS HELPERS ---

    async def get_revenue_history(self, days: int = 7) -> List[asyncpg.Record]:
        """
        Aggregates daily revenue for the line chart.
        Returns rows with 'date' and 'value'.
        """
        query = """
            WITH date_series AS (
                SELECT generate_series(
                    CURRENT_DATE - ($1::int - 1) * INTERVAL '1 day',
                    CURRENT_DATE,
                    '1 day'::interval
                )::date AS day
            )
            SELECT 
                to_char(ds.day, 'MM/DD') as date,
                COALESCE(SUM(p.amount), 0) as value
            FROM date_series ds
            LEFT JOIN payments p ON ds.day = p.created_at::date AND p.status = 'approved'
            GROUP BY ds.day
            ORDER BY ds.day ASC
        """
        return await self._pool.fetch(query, days)

    async def get_payment_distribution(self) -> asyncpg.Record:
        """
        Counts payments by status for the donut chart.
        """
        query = """
            SELECT 
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'approved') as approved,
                COUNT(*) FILTER (WHERE status = 'rejected') as rejected
            FROM payments
        """
        return await self._pool.fetchrow(query)

    # --- UPDATED KPI HELPER ---
    
    async def get_admin_stats(self) -> asyncpg.Record:
        query = """
            SELECT 
                -- TOTAL NODES
                (SELECT count(*) FROM users) as active_users,
                
                -- PENDING SYNC
                (SELECT count(*) FROM payments WHERE status = 'pending') as pending_payments,
                
                -- TOTAL PROFIT
                (SELECT COALESCE(sum(amount), 0) FROM payments WHERE status = 'approved') as total_revenue,
                
                -- THE "PURITY" CONVERSION RATE (Users who bought / Total Users)
                (SELECT 
                    CASE 
                        WHEN (SELECT count(*) FROM users) = 0 THEN 0 
                        ELSE ROUND(
                            (COUNT(DISTINCT user_id)::numeric / 
                            (SELECT count(*) FROM users)::numeric) * 100, 1
                        )
                    END 
                FROM payments WHERE status = 'approved') as conversion_rate
        """
        return await self._pool.fetchrow(query)


    #New api for revenue targeting
    async def get_revenue_by_products(self) -> List[asyncpg.Record]:
        """
        Aggregates revenue and sales count per product, including language/gender/level/frequency.
        """
        query = """
            SELECT 
                pr.id as product_id,
                pr.title,
                pr.language,
                pr.gender,
                pr.level,
                pr.frequency,
                pr.price,
                COUNT(pay.id) FILTER (WHERE pay.status = 'approved') as sales_count,
                COALESCE(SUM(pay.amount) FILTER (WHERE pay.status = 'approved'), 0) as total_revenue
            FROM products pr
            LEFT JOIN payments pay ON pr.id = pay.product_id
            GROUP BY pr.id, pr.title, pr.language, pr.gender, pr.level, pr.frequency, pr.price
            ORDER BY total_revenue DESC
        """
        return await self._pool.fetch(query)

    async def get_users_by_language(self) -> asyncpg.Record:
            """Counts all registered users grouped by language."""
            query = """
                SELECT 
                    COUNT(*) FILTER (WHERE language = 'EN') as EN,
                    COUNT(*) FILTER (WHERE language = 'AM') as AM
                FROM users
            """
            return await self._pool.fetchrow(query)

    async def get_users_by_gender(self) -> asyncpg.Record:
            """Counts all registered users grouped by gender."""
            query = """
                SELECT 
                    COUNT(*) FILTER (WHERE gender = 'MALE') as MALE,
                    COUNT(*) FILTER (WHERE gender = 'FEMALE') as FEMALE
                FROM users
            """
            return await self._pool.fetchrow(query)

    async def get_users_by_level(self) -> asyncpg.Record:
            """Counts all registered users grouped by fitness level."""
            query = """
                SELECT 
                    COUNT(*) FILTER (WHERE level = 'BEGINNER') as BEGINNER,
                    COUNT(*) FILTER (WHERE level = 'INTERMEDIATE') as INTERMEDIATE,
                    COUNT(*) FILTER (WHERE level = 'ADVANCED') as ADVANCED,
                    COUNT(*) FILTER (WHERE level = 'GLUTE_FOCUSED') as GLUTE_FOCUSED
                FROM users
            """
            return await self._pool.fetchrow(query)
        
        
    async def get_node_intelligence_matrix(self) -> asyncpg.Record:
        query = """
            SELECT 
                -- Language (Case Insensitive)
                COUNT(*) FILTER (WHERE UPPER(language) = 'EN') as lang_en,
                COUNT(*) FILTER (WHERE UPPER(language) = 'AM') as lang_am,
                
                -- Gender (Case Insensitive)
                COUNT(*) FILTER (WHERE UPPER(gender) = 'MALE') as gen_male,
                COUNT(*) FILTER (WHERE UPPER(gender) = 'FEMALE') as gen_female,
                
                -- Level (Case Insensitive + Matches your specific VARCHAR values)
                COUNT(*) FILTER (WHERE UPPER(level) = 'BEGINNER') as lvl_beginner,
                COUNT(*) FILTER (WHERE UPPER(level) = 'INTERMEDIATE') as lvl_inter,
                COUNT(*) FILTER (WHERE UPPER(level) = 'ADVANCED') as lvl_adv,
                COUNT(*) FILTER (WHERE UPPER(level) = 'GLUTE_FOCUSED') as lvl_glute,
                
                -- Frequency (Integer Mapping)
                -- Mapping typical integer values to your UI labels
                COUNT(*) FILTER (WHERE frequency <= 3) as freq_2_3,
                COUNT(*) FILTER (WHERE frequency = 4) as freq_3_4,
                COUNT(*) FILTER (WHERE frequency = 5) as freq_4_5,
                COUNT(*) FILTER (WHERE frequency >= 6) as freq_everyday
            FROM users
        """
        return await self._pool.fetchrow(query)

    async def get_top_sellers(self, limit: int = 5):
        query = """
            SELECT 
                p.id as product_id, 
                p.title, 
                COUNT(pm.id) as sales_count,
                COALESCE(SUM(pm.amount), 0) as total_revenue
            FROM products p
            LEFT JOIN payments pm ON p.id = pm.product_id AND pm.status = 'approved'
            GROUP BY p.id, p.title
            ORDER BY total_revenue DESC
            LIMIT $1;
        """
        return await self._pool.fetch(query, limit)


    async def get_payment_kpis(self) -> asyncpg.Record:
        """
        Returns KPI metrics for payments tab.
        """
        query = """
            SELECT 
                COALESCE(SUM(amount) FILTER (WHERE status = 'approved'), 0) as total_revenue,
                COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
                COALESCE(AVG(EXTRACT(EPOCH FROM (approved_at - created_at)) / 60), 0) as avg_approval_time_minutes,
                CASE 
                    WHEN COUNT(*) = 0 THEN 0
                    ELSE ROUND((COUNT(*) FILTER (WHERE status = 'rejected')::numeric / COUNT(*)::numeric), 3)
                END as rejection_rate
            FROM payments
        """
        return await self._pool.fetchrow(query)
    
    
    async def create_product(self, data: Dict[str, Any]) -> int:
        query = """
            INSERT INTO products (title, language, gender, level, frequency, price, telegram_file_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """
        return await self._pool.fetchval(
            query, data['title'], data['language'], data['gender'], 
            data['level'], data['frequency'], data['price'], data['telegram_file_id']
        )

    async def update_product(self, prod_id: int, data: Dict[str, Any]):
        # Dynamically build update query based on provided fields
        keys = data.keys()
        set_clause = ", ".join([f"{k} = ${i+2}" for i, k in enumerate(keys)])
        values = [data[k] for k in keys]
        query = f"UPDATE products SET {set_clause} WHERE id = $1"
        await self._pool.execute(query, prod_id, *values)

    async def soft_delete_product(self, prod_id: int):
        query = "UPDATE products SET is_active = FALSE WHERE id = $1"
        await self._pool.execute(query, prod_id)
        
    
    # Use this for your main product fetch
    async def get_active_products_with_revenue(self):
        query = """
            SELECT 
                p.id as product_id, p.title, p.price, p.language, p.gender, p.frequency, p.telegram_file_id,
                COUNT(o.id) as sales_count,
                COALESCE(SUM(o.amount), 0) as total_revenue
            FROM products p
            LEFT JOIN orders o ON p.id = o.product_id AND o.status = 'COMPLETED'
            WHERE p.is_active = TRUE
            GROUP BY p.id
            ORDER BY total_revenue DESC
        """
        return await self._pool.fetch(query)
    from typing import List, Dict, Any
    from datetime import datetime, timedelta
    
    async def set_deal_for_targets(self, filter_sql: str, expires_at: datetime, price: float) -> int:
        """
        Set deal_expires_at and deal_price for users matching filter_sql.
        filter_sql should be a WHERE clause fragment like "has_paid = FALSE".
        Returns number of rows updated.
        """
        query = f"""
        UPDATE users
        SET deal_expires_at = $1, deal_price = $2
        WHERE {filter_sql}
        """
        result = await self._pool.execute(query, expires_at, price)
        # asyncpg returns a string like "UPDATE <n>"
        try:
            return int(result.split()[-1])
        except Exception:
            return 0

    async def fetch_broadcast_targets(self, filter_sql: str) -> List[Dict[str, Any]]:
        q = f"SELECT telegram_id, language FROM users WHERE {filter_sql}"
        rows = await self._pool.fetch(q)
        return [dict(r) for r in rows]

    async def create_broadcast(self, name: str, target_filter: str, language: str, expires_at: datetime, total_target: int, admin_id: int):
        return await self._pool.fetchrow(
            "INSERT INTO broadcasts (name, target_filter, language, expires_at, total_target, admin_id) VALUES ($1,$2,$3,$4,$5,$6) RETURNING id",
            name, target_filter, language, expires_at, total_target, admin_id
        )

    async def update_broadcast_stats(self, broadcast_id: int, sent: int, failed: int):
        await self._pool.execute("UPDATE broadcasts SET sent_count = $1, failed_count = $2 WHERE id = $3", sent, failed, broadcast_id)

