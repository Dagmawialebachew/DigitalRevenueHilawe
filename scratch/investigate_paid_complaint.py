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

async def main():
    db = Database(settings.DATABASE_URL)
    await db.connect()

    leads = await get_hot_leads(db)
    uids = [u['telegram_id'] for u in leads]
    print(f"Total leads in hot leads list: {len(uids)}")

    # 1. Any record in payments table for these uids?
    all_p = await db.fetch("""
        SELECT p.id, p.user_id, p.amount, p.status, p.created_at, p.approved_at, u.full_name, u.username
        FROM payments p
        JOIN users u ON u.telegram_id = p.user_id
        WHERE p.user_id = ANY($1)
        ORDER BY p.created_at DESC;
    """, uids)
    print(f"\n--- Records in PAYMENTS table for cohort ({len(all_p)} found) ---")
    for p in all_p:
        print(f"  Payment ID: {p['id']} | User: {p['user_id']} ({p['full_name']} / @{p['username']}) | Amount: {p['amount']} | Status: {p['status']} | Created: {p['created_at']}")

    # 2. Any record in meal_payments table?
    all_mp = await db.fetch("""
        SELECT mp.id, mp.user_id, mp.expected_amount, mp.status, mp.created_at, mp.approved_at, u.full_name, u.username
        FROM meal_payments mp
        JOIN users u ON u.telegram_id = mp.user_id
        WHERE mp.user_id = ANY($1)
        ORDER BY mp.created_at DESC;
    """, uids)
    print(f"\n--- Records in MEAL_PAYMENTS table for cohort ({len(all_mp)} found) ---")
    for mp in all_mp:
        print(f"  Meal Payment ID: {mp['id']} | User: {mp['user_id']} ({mp['full_name']} / @{mp['username']}) | Amount: {mp['expected_amount']} | Status: {mp['status']} | Created: {mp['created_at']}")

    # 3. Any record in club_payments table?
    all_cp = await db.fetch("""
        SELECT cp.id, cp.user_id, cp.amount, cp.status, cp.created_at, u.full_name, u.username
        FROM club_payments cp
        JOIN users u ON u.telegram_id = cp.user_id
        WHERE cp.user_id = ANY($1)
        ORDER BY cp.created_at DESC;
    """, uids)
    print(f"\n--- Records in CLUB_PAYMENTS table for cohort ({len(all_cp)} found) ---")
    for cp in all_cp:
        print(f"  Club Payment ID: {cp['id']} | User: {cp['user_id']} ({cp['full_name']} / @{cp['username']}) | Amount: {cp['amount']} | Status: {cp['status']} | Created: {cp['created_at']}")

    # 4. Check if any user who has an APPROVED payment anywhere in the DB received the broadcast today!
    # Remember retarget_incomplete_onboarding or retarget_hot_unpaid_leads.
    # What was the message ID range for the hot leads broadcast?
    # Let's inspect max last_broadcast_msg_id in users table
    print("\n--- Approved payers who have last_broadcast_msg_id updated TODAY ---")
    today_approved = await db.fetch("""
        SELECT u.telegram_id, u.full_name, u.username, u.has_paid, u.last_broadcast_msg_id, p.id as payment_id, p.amount, p.status, p.approved_at
        FROM users u
        JOIN payments p ON p.user_id = u.telegram_id
        WHERE p.status = 'approved' AND u.last_broadcast_msg_id IS NOT NULL
        ORDER BY p.approved_at DESC NULLS LAST;
    """)
    print(f"Total approved users with broadcast ID: {len(today_approved)}")
    for u in today_approved[:15]:
        print(f"  User: {u['telegram_id']} ({u['full_name']}) | MsgID: {u['last_broadcast_msg_id']} | Payment: #{u['payment_id']} ({u['amount']} ETB) Approved: {u['approved_at']}")

    # 5. Let's check users who paid today or yesterday (Nov 1, 2, 3) across the whole bot
    print("\n--- ALL Payments submitted on Nov 1, 2, 3 across the entire bot ---")
    recent_all = await db.fetch("""
        SELECT p.id, p.user_id, p.amount, p.status, p.created_at, p.approved_at, u.full_name, u.username, u.has_paid, u.last_broadcast_msg_id
        FROM payments p
        LEFT JOIN users u ON u.telegram_id = p.user_id
        WHERE p.created_at >= '2026-11-01 00:00:00'
        ORDER BY p.created_at DESC;
    """)
    for r in recent_all:
        print(f"  #{r['id']}: User {r['user_id']} ({r['full_name']}) | Status: {r['status']} | Amount: {r['amount']} | Created: {r['created_at']} | Approved: {r['approved_at']} | has_paid: {r['has_paid']} | BroadcastMsgID: {r['last_broadcast_msg_id']}")

    await db.close()

if __name__ == "__main__":
    asyncio.run(main())

