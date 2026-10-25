import asyncio
import os
import json
import sys
from dotenv import load_dotenv
import asyncpg

load_dotenv(r"d:\The hobby 2\DigitalRevenueHilawe\.env")
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    cols = await conn.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'meal_payments'")
    print("meal_payments columns:", [c['column_name'] for c in cols])
    
    rows = await conn.fetch("""
        SELECT p.id, p.order_id, p.status, p.bank_code, p.proof_file_id IS NOT NULL as has_proof,
               p.verification_reference, p.created_at, o.amount, o.currency, u.full_name, u.username, u.telegram_id
        FROM meal_payments p
        JOIN meal_orders o ON p.order_id = o.id
        LEFT JOIN users u ON o.user_id = u.telegram_id
        ORDER BY p.id DESC
    """)
    print("\nPayments count:", len(rows))
    for r in rows:
        print(f"Payment #{r['id']} | Order #{r['order_id']} | Status: {r['status']} | Bank: {r['bank_code']} | Proof: {r['has_proof']} | Ref: {r['verification_reference']} | User: {r['full_name']} (@{r['username']}, ID: {r['telegram_id']})")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
