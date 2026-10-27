import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
import config, asyncpg
from datetime import datetime, timezone, timedelta

async def verify_mapping():
    conn = await asyncpg.connect(config.settings.DATABASE_URL)
    cutoff = datetime.now(timezone.utc) - timedelta(days=56)
    
    # 1. Beginner Graduates mapping to Intermediate
    b_graduates = await conn.fetch('''
        SELECT 
            u.telegram_id, u.full_name, u.gender, u.language, u.frequency,
            p_old.id as old_pid, p_old.level as old_level,
            p_new.id as new_pid, p_new.title as new_title, p_new.level as new_level
        FROM payments pay
        JOIN products p_old ON pay.product_id = p_old.id
        JOIN users u ON pay.user_id = u.telegram_id
        LEFT JOIN products p_new ON 
            p_new.is_active = TRUE AND
            p_new.level = 'INTERMEDIATE' AND
            p_new.language = p_old.language AND
            p_new.gender = p_old.gender AND
            p_new.frequency = p_old.frequency
        WHERE pay.status = 'approved' 
          AND p_old.level = 'BEGINNER'
          AND COALESCE(pay.approved_at, pay.created_at) <= $1
    ''', cutoff)
    
    matched_b = [r for r in b_graduates if r['new_pid'] is not None]
    unmatched_b = [r for r in b_graduates if r['new_pid'] is None]
    print(f"Beginner Graduates: {len(b_graduates)} | Matched to Intermediate: {len(matched_b)} | Unmatched: {len(unmatched_b)}")
    if unmatched_b:
        print("Sample unmatched beginner:", dict(unmatched_b[0]))

    # 2. Intermediate Graduates mapping to Advanced
    i_graduates = await conn.fetch('''
        SELECT 
            u.telegram_id, u.full_name, u.gender, u.language, u.frequency,
            p_old.id as old_pid, p_old.level as old_level,
            p_new.id as new_pid, p_new.title as new_title, p_new.level as new_level
        FROM payments pay
        JOIN products p_old ON pay.product_id = p_old.id
        JOIN users u ON pay.user_id = u.telegram_id
        LEFT JOIN products p_new ON 
            p_new.is_active = TRUE AND
            p_new.level = 'ADVANCED' AND
            p_new.language = p_old.language AND
            p_new.gender = p_old.gender AND
            p_new.frequency = p_old.frequency
        WHERE pay.status = 'approved' 
          AND p_old.level = 'INTERMEDIATE'
          AND COALESCE(pay.approved_at, pay.created_at) <= $1
    ''', cutoff)
    
    matched_i = [r for r in i_graduates if r['new_pid'] is not None]
    unmatched_i = [r for r in i_graduates if r['new_pid'] is None]
    print(f"Intermediate Graduates: {len(i_graduates)} | Matched to Advanced: {len(matched_i)} | Unmatched: {len(unmatched_i)}")
    if unmatched_i:
        print("Sample unmatched intermediate:", dict(unmatched_i[0]))

    await conn.close()

if __name__ == "__main__":
    asyncio.run(verify_mapping())
