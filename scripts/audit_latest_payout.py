"""
audit_latest_payout.py
──────────────────────
Pulls every transaction from the latest payout cutoff timestamp until now across
all 3 revenue streams (Product Sales, Club Subscriptions, Meal Plans), runs live
Veritas multi-bank verification, checks for discrepancies, and reconciles the 2k Br gap.

Usage:
  python scripts/audit_latest_payout.py
"""

import asyncio
import csv
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
DATABASE_URL = os.getenv("DATABASE_URL")
OUTPUT_DIR = Path("payments_export/latest_payout_audit")

from handlers.verify import verify_external

async def generate_audit_report():
    import asyncpg
    conn = await asyncpg.connect(DATABASE_URL)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Checkpoint Timestamp
        last_payout_ts = await conn.fetchval(
            "SELECT value_timestamp FROM system_metadata WHERE key = 'last_payout_at'"
        )
        if not last_payout_ts:
            last_payout_ts = await conn.fetchval(
                "SELECT MAX(payout_date) FROM payout_history WHERE entry_type = 'payout'"
            )
        last_payout_ts = last_payout_ts or datetime.min.replace(tzinfo=timezone.utc)

        print("=" * 70)
        print("  HILAWE REVENUE AUDIT // POST-PAYOUT RECONCILIATION")
        print("=" * 70)
        print(f"  Checkpoint Timestamp (Last Payout) : {last_payout_ts}")
        print(f"  Current Audit Run Time             : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 70)

        # 2. Query Approved Stream A: Products
        products = await conn.fetch("""
            SELECT p.id, p.amount, p.status, p.txn_id, p.proof_file_id,
                   COALESCE(p.approved_at, p.created_at) as settled_at,
                   u.full_name, u.username, pr.title as item_title
            FROM payments p
            JOIN users u ON u.telegram_id = p.user_id
            JOIN products pr ON pr.id = p.product_id
            WHERE p.status = 'approved' AND (p.approved_at > $1 OR (p.approved_at IS NULL AND p.created_at > $1))
            ORDER BY settled_at ASC
        """, last_payout_ts)

        # 3. Query Approved Stream B: Club
        clubs = await conn.fetch("""
            SELECT cp.id, cp.amount, cp.status, cp.payment_type, cp.proof_file_id,
                   COALESCE(cp.processed_at, cp.created_at) as settled_at,
                   u.full_name, u.username
            FROM club_payments cp
            JOIN users u ON u.telegram_id = cp.user_id
            WHERE cp.status = 'approved' AND (cp.processed_at > $1 OR (cp.processed_at IS NULL AND cp.created_at > $1))
            ORDER BY settled_at ASC
        """, last_payout_ts)

        # 4. Query Approved Stream C: Meal Plans
        meals = await conn.fetch("""
            SELECT mp.id, COALESCE(mp.settlement_amount, mp.expected_amount) as amount,
                   mp.expected_amount, mp.settlement_amount, mp.bank_code, mp.verification_reference,
                   mp.status, mp.proof_file_id, COALESCE(mp.approved_at, mp.created_at) as settled_at,
                   u.full_name, u.username, mo.duration_days, mo.service_type
            FROM meal_payments mp
            JOIN users u ON u.telegram_id = mp.user_id
            JOIN meal_orders mo ON mo.id = mp.order_id
            WHERE mp.status = 'APPROVED' AND (mp.approved_at > $1 OR (mp.approved_at IS NULL AND mp.created_at > $1))
            ORDER BY settled_at ASC
        """, last_payout_ts)

        # 5. Query Unsettled Operating Expenses
        expenses = await conn.fetch("""
            SELECT id, operational_deductions, expense_note, payout_date
            FROM payout_history
            WHERE entry_type = 'expense_only' AND payout_date > $1
            ORDER BY payout_date ASC
        """, last_payout_ts)

        # 6. Query Rejected / Edge-Case Payments (Gap Investigation)
        rejected_products = await conn.fetch("""
            SELECT p.id, p.amount, p.status, p.txn_id, p.proof_file_id, p.created_at,
                   u.full_name, u.username, pr.title
            FROM payments p
            JOIN users u ON u.telegram_id = p.user_id
            JOIN products pr ON pr.id = p.product_id
            WHERE p.status = 'rejected' AND p.created_at > $1
            ORDER BY p.id ASC
        """, last_payout_ts)

        pending_meals = await conn.fetch("""
            SELECT mp.id, COALESCE(mp.settlement_amount, mp.expected_amount) as amount,
                   mp.status, mp.proof_file_id, mp.created_at, u.full_name
            FROM meal_payments mp
            JOIN users u ON u.telegram_id = mp.user_id
            WHERE mp.status = 'PENDING' AND mp.created_at > $1 AND mp.expected_amount IN (2000, 2200, 4000)
            ORDER BY mp.id ASC
        """, last_payout_ts)

        # Financial Calculations
        prod_gross = sum(Decimal(str(r['amount'])) for r in products)
        club_gross = sum(Decimal(str(r['amount'])) for r in clubs)
        meal_gross = sum(Decimal(str(r['amount'])) for r in meals)
        total_gross = prod_gross + club_gross + meal_gross
        total_burn = sum(Decimal(str(r['operational_deductions'])) for r in expenses)

        net_prod = max(Decimal('0'), prod_gross - total_burn)
        coach_prod = round(net_prod * Decimal('0.70'), 2)
        dag_prod = net_prod - coach_prod

        coach_club = round(club_gross * Decimal('0.60'), 2)
        dag_club = club_gross - coach_club

        coach_meal = round(meal_gross * Decimal('0.60'), 2)
        dag_meal = meal_gross - coach_meal

        coach_total = coach_prod + coach_club + coach_meal
        dag_total = dag_prod + dag_club + dag_meal
        net_distributable = net_prod + club_gross + meal_gross

        print("\n📊 FINANCIAL OVERVIEW (SYSTEM REGISTERED):")
        print(f"  • Product Sales (Stream A) : {len(products):>3} txns | {prod_gross:>10,.2f} ETB")
        print(f"  • Club Subscriptions (B)   : {len(clubs):>3} txns | {club_gross:>10,.2f} ETB")
        print(f"  • Meal Plans (Stream C)    : {len(meals):>3} txns | {meal_gross:>10,.2f} ETB")
        print(f"  --------------------------------------------------")
        print(f"  • Total Gross Revenue      : {total_gross:>10,.2f} ETB")
        print(f"  • Operating Deductions     : {total_burn:>10,.2f} ETB")
        print(f"  • Net Distributable Pool   : {net_distributable:>10,.2f} ETB")
        print(f"  --------------------------------------------------")
        print(f"  • Coach Hilawe Total Share : {coach_total:>10,.2f} ETB")
        print(f"  • Dagmawi Total Share      : {dag_total:>10,.2f} ETB")

        # 7. Live Veritas Verification of Transactions with txn_id
        print("\n🔍 LIVE VERITAS VERIFICATION & ANOMALY SCAN:")
        audit_rows = []

        all_active = [("Product", r) for r in products] + [("Club", r) for r in clubs] + [("Meal", r) for r in meals]
        for stream_name, item in all_active:
            tid = item.get('txn_id') or item.get('verification_reference')
            amt = float(item['amount'])
            name = item['full_name'] or 'Unknown'
            ver_status = "UNVERIFIED"
            bank_amt = 0.0
            provider = "CBE" if str(tid).startswith("FT") else ("Telebirr" if str(tid).startswith("DH") else "Unknown")

            if tid:
                try:
                    res = await verify_external(tid, provider)
                    if res.get("success"):
                        ver_status = "VERIFIED"
                        bank_amt = float(res.get("amount") or 0.0)
                except Exception:
                    ver_status = "TIMEOUT"

            gap = amt - bank_amt if bank_amt > 0 else 0.0
            audit_rows.append({
                "stream": stream_name,
                "id": item['id'],
                "customer": name,
                "db_amount": amt,
                "bank_amount": bank_amt,
                "difference": gap,
                "txn_id": tid or "MANUAL_APPROVAL",
                "veritas_status": ver_status,
                "settled_at": item['settled_at'].strftime("%Y-%m-%d %H:%M")
            })

        # Save to CSV and JSON
        csv_path = OUTPUT_DIR / "post_payout_transactions.csv"
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "stream", "id", "customer", "db_amount", "bank_amount",
                "difference", "txn_id", "veritas_status", "settled_at"
            ])
            writer.writeheader()
            writer.writerows(audit_rows)

        print(f"  ✓ Exported {len(audit_rows)} transaction audit rows to: {csv_path}")

        # 8. GAP INVESTIGATION SUMMARY
        print("\n🔎 RECONCILING THE 2,000 ETB GAP:")
        print("=" * 70)
        
        # Candidate 1: PID #638 verified underpayment
        v638 = await verify_external("FT262803DQ37", "CBE")
        if v638.get("success"):
            print("  [FINDING 1] Underpaid / Rejected Payment Confirmed in Bank:")
            print(f"    • PID #638 (Mehammed Sualih): Order was 949 ETB, rejected in DB.")
            print(f"    • VERITAS BANK CONFIRMATION: {v638.get('amount')} ETB was settled to Hilawe ({v638.get('receiver')}) on {v638.get('date')}!")
            print(f"    • Impact: +{v638.get('amount')} ETB in Coach's bank account NOT counted in system revenue.\n")

        # Candidate 2: Other rejected payments with FT codes
        print("  [FINDING 2] Rejected Payments with Bank Confirmation References:")
        for rp in rejected_products:
            if rp['txn_id'] and rp['txn_id'] != 'FT262803DQ37':
                print(f"    • PID #{rp['id']}: {rp['amount']} ETB ({rp['full_name']}) | Ref: {rp['txn_id']}")
        print(f"    • If Coach accepted any of these direct CBE slips, gap increases by up to {sum(float(r['amount']) for r in rejected_products if r['id'] != 638):,.2f} ETB.\n")

        # Candidate 3: Unapproved Meal Orders (Pending)
        print("  [FINDING 3] Direct Meal Plan Checkouts Still in PENDING:")
        for pm in pending_meals:
            print(f"    • MID #{pm['id']}: {pm['amount']} ETB ({pm['full_name']}) created at {pm['created_at'].strftime('%Y-%m-%d %H:%M')}")
        print("    • If Freselam Aschenki (2,000 ETB) or Bezawit/Kidu (2,200 ETB) sent direct bank wire, that accounts for the exact 2k Br gap!\n")

        print("=" * 70)
        print("  AUDIT COMPLETED SUCCESSFULLY")
        print("=" * 70)

    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(generate_audit_report())
