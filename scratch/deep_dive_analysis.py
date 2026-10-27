import asyncio
import os
import sys
import json
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
import config
import asyncpg

async def deep_dive():
    conn = await asyncpg.connect(config.settings.DATABASE_URL)
    
    print("=" * 60)
    print("DEEP DIVE: WORKOUT GRADUATES & MEAL PLAN FUNNEL")
    print("=" * 60)
    
    # 1. 8-week workout graduates
    cutoff = datetime.now(timezone.utc) - timedelta(days=56)
    
    # Get all distinct users with approved workout payment <= cutoff
    graduates = await conn.fetch("""
        SELECT 
            u.telegram_id,
            u.full_name,
            u.username,
            u.gender,
            u.language,
            p.id as product_id,
            p.title,
            p.level,
            pay.amount as paid_amount,
            COALESCE(pay.approved_at, pay.created_at) as completed_start_date
        FROM payments pay
        JOIN products p ON pay.product_id = p.id
        JOIN users u ON pay.user_id = u.telegram_id
        WHERE pay.status = 'approved'
          AND COALESCE(pay.approved_at, pay.created_at) <= $1
        ORDER BY completed_start_date ASC
    """, cutoff)
    
    print(f"Total Graduate Records (8+ weeks): {len(graduates)}")
    
    # Map users to their latest level
    user_latest_level = {}
    for g in graduates:
        uid = g['telegram_id']
        # If user has multiple, take the latest
        user_latest_level[uid] = g

    print(f"Unique Graduate Users: {len(user_latest_level)}")
    
    level_counts = {}
    for g in user_latest_level.values():
        lvl = g['level']
        level_counts[lvl] = level_counts.get(lvl, 0) + 1
        
    print("\nUnique Graduates by Workout Level:")
    for lvl, cnt in level_counts.items():
        print(f"  {lvl:<15}: {cnt} users")
        
    # Check overlap with meal_orders
    grad_ids = list(user_latest_level.keys())
    mp_orders = await conn.fetch("""
        SELECT mo.id, mo.user_id, mo.state, mo.amount, mo.currency, mo.duration_days, mo.created_at
        FROM meal_orders mo
    """)
    mp_user_map = {}
    for mo in mp_orders:
        mp_user_map[mo['user_id']] = mo
        
    # How many graduates created a meal order?
    grad_with_mp = [uid for uid in grad_ids if uid in mp_user_map]
    print(f"\nOf {len(grad_ids)} graduates, how many entered Meal Plan checkout? {len(grad_with_mp)}")
    for uid in grad_with_mp:
        mo = mp_user_map[uid]
        u = user_latest_level[uid]
        print(f"  User {uid} ({u['full_name']}) | Level: {u['level']} | MP State: {mo['state']} | Amt: {mo['amount']} {mo['currency']}")

    # Who are the 40 people in meal_orders awaiting payment?
    print("\n--- BREAKDOWN OF THE 40+ MEAL PLAN ABANDONED ORDERS ---")
    awaiting_users = await conn.fetch("""
        SELECT mo.id, mo.user_id, mo.state, mo.amount, mo.currency, mo.duration_days, mo.region, mo.created_at,
               u.full_name, u.username, u.gender,
               (SELECT count(*) FROM payments p WHERE p.user_id = mo.user_id AND p.status = 'approved') as past_workout_buys,
               (SELECT count(*) FROM club_payments cp WHERE cp.user_id = mo.user_id AND cp.status = 'approved') as past_club_buys
        FROM meal_orders mo
        JOIN users u ON mo.user_id = u.telegram_id
        WHERE mo.state = 'AWAITING_PAYMENT'
        ORDER BY mo.created_at DESC
    """)
    
    past_buyers_abandoned = 0
    cold_abandoned = 0
    for au in awaiting_users:
        is_past_buyer = (au['past_workout_buys'] > 0 or au['past_club_buys'] > 0)
        if is_past_buyer:
            past_buyers_abandoned += 1
        else:
            cold_abandoned += 1
            
    print(f"Total Awaiting Payment Orders: {len(awaiting_users)}")
    print(f"  From Existing Paying Customers (Warm): {past_buyers_abandoned}")
    print(f"  From Cold / New Leads: {cold_abandoned}")
    
    # 8. Check why they dropped off - let's see meal_payments details for awaiting orders
    proof_submitted = await conn.fetch("""
        SELECT count(*) FROM meal_payments 
        WHERE status = 'PENDING' AND proof_file_id IS NOT NULL AND proof_file_id != ''
    """)
    proof_empty = await conn.fetch("""
        SELECT count(*) FROM meal_payments 
        WHERE status = 'PENDING' AND (proof_file_id IS NULL OR proof_file_id = '')
    """)
    print(f"\nPending payments with Proof Uploaded: {proof_submitted[0]['count']}")
    print(f"Pending payments with NO Proof Uploaded (Abandoned Checkout at bank screen): {proof_empty[0]['count']}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(deep_dive())
