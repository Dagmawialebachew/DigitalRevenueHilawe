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

-- Optimization Indexes
CREATE INDEX IF NOT EXISTS idx_products_filter ON products (language, gender, level, frequency) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_users_tid ON users (telegram_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments (status);
ALTER TABLE users ADD COLUMN IF NOT EXISTS goal TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS obstacle TEXT;
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

    async def get_admin_stats(self):
        """Fetches elite-level business intelligence including pending tasks."""
        query = """
            SELECT 
                (SELECT count(*) FROM users) as users,
                (SELECT count(*) FROM payments WHERE status = 'approved') as sales,
                (SELECT sum(amount) FROM payments WHERE status = 'approved') as revenue,
                (SELECT count(*) FROM payments WHERE status = 'pending') as pending_count
        """
        return await self._pool.fetchrow(query)

    async def approve_payment(self, payment_id: int) -> Optional[Dict]:
        """Approves payment and returns user_id + file_id for automated delivery."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Update status
                row = await conn.fetchrow("""
                    UPDATE payments SET status = 'approved' 
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
