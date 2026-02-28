import asyncio
import random
import logging
from datetime import datetime, timedelta
from database.db import Database

# --- CONFIGURATION ---
DSN = "postgresql://neondb_owner:npg_3nF9gpuImcYD@ep-wild-river-aikuskzc-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require" 
SAMPLE_PREFIX = "TST_" # Used to identify and "truncate" only test data

async def generate_dynamic_data():
    db = Database(DSN)
    await db.connect()
    
    print("🧹 [CLEANUP] Purging existing TST_ records...")
    async with db._pool.acquire() as conn:
        # We delete by prefix so we don't accidentally wipe your real manual data
        await conn.execute("DELETE FROM payments WHERE proof_file_id LIKE 'TST_%'")
        await conn.execute("DELETE FROM products WHERE telegram_file_id LIKE 'TST_%'")
        await conn.execute("DELETE FROM users WHERE username LIKE 'tst_%'")
    
    print("📦 [INJECT] Creating Dynamic Product Suite...")
    product_configs = [
        ("Alpha Signal Protocol", "EN", "Male", "Advanced", 7, 2500.00),
        ("Beta Flow Basic", "EN", "Both", "Beginner", 3, 750.00),
        ("Gamma Node Intermediate", "FR", "Female", "Intermediate", 5, 1200.00),
        ("Delta Sovereign Tier", "ES", "Both", "Advanced", 30, 9999.00)
    ]
    
    product_ids = []
    for p in product_configs:
        p_id = await db.create_product(p[0], p[1], p[2], p[3], p[4], p[5], f"{SAMPLE_PREFIX}{random.randint(100,999)}")
        product_ids.append(p_id)

    print("📈 [SIMULATE] Generating 30-Day Market Activity...")
    
    now = datetime.now()
    total_entries = 0
    
    # Simulate 30 days of history
    for day in range(30, -1, -1):
        current_date = now - timedelta(days=day)
        
        # DYNAMIC VOLUME: Weekends have lower volume, middle of month has a 'spike'
        is_weekend = current_date.weekday() >= 5
        base_volume = 15 if not is_weekend else 5
        
        # Add a "Spike" around 15 days ago for a better looking graph
        if 12 <= day <= 18:
            base_volume += random.randint(10, 25)
            
        daily_users = random.randint(base_volume - 3, base_volume + 10)

        for _ in range(daily_users):
            telegram_id = random.randint(1000000, 9999999)
            u_name = f"tst_node_{telegram_id}"
            
            # Create User with varying timestamps throughout the day
            timestamp = current_date.replace(hour=random.randint(0,23), minute=random.randint(0,59))
            
            await db.create_or_update_user(
                telegram_id,
                full_name=f"Dynamic Node {random.choice(['Ω', 'Σ', 'Δ', 'Ψ'])}",
                username=u_name,
                language=random.choice(['EN', 'FR', 'ES']),
                created_at=timestamp
            )

            # Create Payment
            # Probability: 70% Approved, 20% Pending, 10% Rejected
            status = random.choices(['approved', 'pending', 'rejected'], weights=[70, 20, 10])[0]
            prod_id = random.choice(product_ids)
            
            # Use raw query for payment to inject the specific historical timestamp
            query = """
                INSERT INTO payments (user_id, product_id, amount, status, created_at, proof_file_id)
                VALUES ($1, $2, (SELECT price FROM products WHERE id=$2), $3, $4, $5)
            """
            async with db._pool.acquire() as conn:
                await conn.execute(query, telegram_id, prod_id, status, timestamp, f"{SAMPLE_PREFIX}PROOFS")
            
            total_entries += 1

    print(f"✅ [SUCCESS] Injected {total_entries} signals across 30 days.")
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(generate_dynamic_data())