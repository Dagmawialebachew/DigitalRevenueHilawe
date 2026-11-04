import asyncio
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from database.db import Database
from scheduler.retarget_hot_unpaid_leads import get_hot_leads

async def inspect():
    db = Database(settings.DATABASE_URL)
    await db.connect()

    leads = await get_hot_leads(db)
    uids = [u['telegram_id'] for u in leads]
    print(f"Total leads from get_hot_leads: {len(uids)}")

    # 1. Did ANY of these 743 users have an approved payment in payments?
    p_approved = await db.fetch("""
        SELECT p.id, p.user_id, p.amount, p.status, p.created_at, p.approved_at, u.full_name
        FROM payments p
        JOIN users u ON u.telegram_id = p.user_id
        WHERE p.user_id = ANY($1) AND p.status = 'approved';
    """, uids)
    print(f"1. Leads with approved payments in payments: {len(p_approved)}")
    for p in p_approved:
        print(f"   ID: {p['id']}, User: {p['user_id']}, Name: {p['full_name']}, Amount: {p['amount']}, Status: {p['status']}")

    # 2. Did ANY of these 743 users have a pending payment in payments?
    p_pending = await db.fetch("""
        SELECT p.id, p.user_id, p.amount, p.status, p.created_at, u.full_name
        FROM payments p
        JOIN users u ON u.telegram_id = p.user_id
        WHERE p.user_id = ANY($1) AND p.status = 'pending';
    """, uids)
    print(f"\n2. Leads with PENDING payments in payments: {len(p_pending)}")
    for p in p_pending:
        print(f"   ID: {p['id']}, User: {p['user_id']}, Name: {p['full_name']}, Amount: {p['amount']}, Status: {p['status']}")

    # 3. Did ANY of these 743 users have a payment in club_payments?
    c_approved = await db.fetch("""
        SELECT cp.id, cp.user_id, cp.amount, cp.status, cp.created_at, u.full_name
        FROM club_payments cp
        JOIN users u ON u.telegram_id = cp.user_id
        WHERE cp.user_id = ANY($1);
    """, uids)
    print(f"\n3. Leads with records in club_payments: {len(c_approved)}")
    for cp in c_approved:
        print(f"   ID: {cp['id']}, User: {cp['user_id']}, Name: {cp['full_name']}, Amount: {cp['amount']}, Status: {cp['status']}")

    # 4. Did ANY of these 743 users have a payment in meal_payments?
    m_approved = await db.fetch("""
        SELECT mp.id, mp.user_id, mp.expected_amount, mp.status, mp.created_at, u.full_name
        FROM meal_payments mp
        JOIN users u ON u.telegram_id = mp.user_id
        WHERE mp.user_id = ANY($1);
    """, uids)
    print(f"\n4. Leads with records in meal_payments: {len(m_approved)}")
    for mp in m_approved:
        print(f"   ID: {mp['id']}, User: {mp['user_id']}, Name: {mp['full_name']}, Amount: {mp['expected_amount']}, Status: {mp['status']}")

    # 5. Check if any has_paid = true
    hp = await db.fetch("""
        SELECT telegram_id, full_name, has_paid FROM users WHERE telegram_id = ANY($1) AND has_paid = TRUE;
    """, uids)
    print(f"\n5. Leads with has_paid=TRUE: {len(hp)}")
    for u in hp:
        print(f"   User: {u['telegram_id']}, Name: {u['full_name']}, has_paid: {u['has_paid']}")

if __name__ == "__main__":
    asyncio.run(inspect())

