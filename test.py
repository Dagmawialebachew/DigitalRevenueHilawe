import asyncio
from database.db import Database

# # --- CONFIGURATION ---
DSN = "postgresql://neondb_owner:npg_3nF9gpuImcYD@ep-wild-river-aikuskzc-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require" 

# async def wipe_database_completely():
#     db = Database(DSN)
#     await db.connect()
    
#     print("⚠️  [WARNING] Preparing to erase ALL data from the database...")
    
#     # We use TRUNCATE with CASCADE to handle foreign key dependencies 
#     # (e.g., deleting users will automatically clear their associated payments)
#     async with db._pool.acquire() as conn:
#         try:
#             # 1. Clear Payments first (usually has FKs to both users and products)
#             print("🧨 Clearing Payments...")
#             await conn.execute("TRUNCATE TABLE payments RESTART IDENTITY CASCADE")
            
#             # 2. Clear Products
#             print("🧨 Clearing Products...")
#             await conn.execute("TRUNCATE TABLE products RESTART IDENTITY CASCADE")
            
#             # 3. Clear Users
#             print("🧨 Clearing Users...")
#             await conn.execute("TRUNCATE TABLE users RESTART IDENTITY CASCADE")
            
#             print("✅ [SUCCESS] Database is now empty and ID counters are reset.")
            
#         except Exception as e:
#             print(f"❌ [ERROR] Cleanup failed: {e}")

#     await db.disconnect()

# if __name__ == "__main__":
#     # Final confirmation check
#     confirm = input("This will delete EVERYTHING. Type 'YES' to proceed: ")
#     if confirm == "YES":
#         asyncio.run(wipe_database_completely())
#     else:
#         print("Operation aborted.")

