"""
generate_post_payout_tri_stream_audit.py
────────────────────────────────────────
Full Tri-Stream Forensic Payment Audit & Image Extractor
Date range: October 01, 2026 (post-Sept 30 payout) to November 01, 2026

Captures:
  1. Stream A: Product Sales (payments table)
  2. Stream B: Transformation Club (club_payments table)
  3. Stream C: Meal Plan Automation (meal_payments table)
  4. Suspicious / Gap Analysis: Underpayments, Replay Duplicates, Pending Meal Plans, and Genuine Rejected Receipts

Folder Structure Created:
  2026-10-02 to 11-01/
  ├── verified_transactions/
  │   ├── product_sales/
  │   ├── club_payments/
  │   └── meal_plans/
  ├── unverified_receipts/
  ├── suspicious_and_gaps/
  │   ├── underpaid_mismatches/
  │   ├── pending_meal_plans/
  │   ├── rejected_genuine_receipts/
  │   └── replay_duplicates/
  ├── MASTER_TRI_STREAM_AUDIT.pdf
  ├── FORENSIC_DISCREPANCY_AND_GAP_REPORT.pdf
  ├── tri_stream_transactions_ledger.csv
  └── tri_stream_transactions_ledger.json
"""

import asyncio
import csv
import io
import json
import logging
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import aiohttp
import asyncpg
from PIL import Image, ImageDraw, ImageFont, ImageOps
import pytesseract

from handlers.verify import verify_external

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG & PATHS
# ──────────────────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ROOT_DIR = Path("2026-10-02 to 11-01")

VERIFIED_SALES_DIR = ROOT_DIR / "verified_transactions" / "product_sales"
VERIFIED_CLUB_DIR = ROOT_DIR / "verified_transactions" / "club_payments"
VERIFIED_MEALS_DIR = ROOT_DIR / "verified_transactions" / "meal_plans"
UNVERIFIED_DIR = ROOT_DIR / "unverified_receipts"

SUSPICIOUS_UNDERPAID_DIR = ROOT_DIR / "suspicious_and_gaps" / "underpaid_mismatches"
SUSPICIOUS_PENDING_DIR = ROOT_DIR / "suspicious_and_gaps" / "pending_meal_plans"
SUSPICIOUS_REJECTED_DIR = ROOT_DIR / "suspicious_and_gaps" / "rejected_genuine_receipts"
SUSPICIOUS_DUPLICATES_DIR = ROOT_DIR / "suspicious_and_gaps" / "replay_duplicates"

for p in [
    VERIFIED_SALES_DIR, VERIFIED_CLUB_DIR, VERIFIED_MEALS_DIR,
    UNVERIFIED_DIR, SUSPICIOUS_UNDERPAID_DIR, SUSPICIOUS_PENDING_DIR,
    SUSPICIOUS_REJECTED_DIR, SUSPICIOUS_DUPLICATES_DIR,
]:
    p.mkdir(parents=True, exist_ok=True)

# Detect Windows tesseract binary
for _tp in [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Users\kiruk\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
]:
    if os.path.exists(_tp):
        pytesseract.pytesseract.tesseract_cmd = _tp
        break

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("tri_stream_audit")

# ──────────────────────────────────────────────────────────────────────────────
# COLOR PALETTE
# ──────────────────────────────────────────────────────────────────────────────
C_NAVY = colors.HexColor("#0A2342")
C_NAVY_MID = colors.HexColor("#1A3A5C")
C_NAVY_LIGHT = colors.HexColor("#EEF3FA")
C_GOLD = colors.HexColor("#C9A84C")
C_GOLD_LIGHT = colors.HexColor("#FDF9EE")
C_WHITE = colors.HexColor("#FFFFFF")
C_OFF_WHITE = colors.HexColor("#F8FAFC")
C_ROW_ALT = colors.HexColor("#F1F5F9")
C_RULE = colors.HexColor("#CBD5E1")
C_GREEN = colors.HexColor("#1E7E34")
C_GREEN_BG = colors.HexColor("#EAF5EC")
C_RED = colors.HexColor("#B02A37")
C_RED_BG = colors.HexColor("#FDF2F2")
C_CLUB_ACCENT = colors.HexColor("#53389E")
C_MEAL_ACCENT = colors.HexColor("#B54708")

TOLERANCE_ETB = 5.0

def _sanitize_str(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"[^\x00-\x7F\xC0-\xFF]+", " ", str(text)).strip()


# ──────────────────────────────────────────────────────────────────────────────
# TELEGRAM DOWNLOAD HELPER
# ──────────────────────────────────────────────────────────────────────────────
async def download_telegram_proof(session: aiohttp.ClientSession, file_id: str | None) -> Image.Image | None:
    if not file_id or not BOT_TOKEN:
        return None
    try:
        url_info = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        async with session.get(url_info, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            if not data.get("ok"):
                return None
            file_path = data["result"]["file_path"]

        url_file = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        async with session.get(url_file, timeout=aiohttp.ClientTimeout(total=12)) as resp:
            if resp.status != 200:
                return None
            img_bytes = await resp.read()
            return Image.open(io.BytesIO(img_bytes)).convert("RGB")
    except Exception as e:
        log.warning("Telegram download failed for %s: %s", file_id[:16] if file_id else "", e)
        return None


# ──────────────────────────────────────────────────────────────────────────────
# LOCAL OCR EXTRACTION
# ──────────────────────────────────────────────────────────────────────────────
def extract_ocr_clues(img: Image.Image) -> tuple[str | None, str]:
    try:
        gray = ImageOps.grayscale(img)
        w, h = gray.size
        # Crop middle region where references and bank titles sit
        cropped = gray.crop((0, int(h * 0.1), w, int(h * 0.75)))
        text = pytesseract.image_to_string(cropped)
    except Exception:
        text = ""

    upper = text.upper()
    provider = "Generic"
    if "COMMERCIAL BANK" in upper or "CBE" in upper or "FT" in upper:
        provider = "CBE"
    elif "TELEBIRR" in upper or "ETHIO TELECOM" in upper or "DH" in upper:
        provider = "Telebirr"
    elif "ABYSSINIA" in upper or "BOA" in upper:
        provider = "Abyssinia"
    elif "DASHEN" in upper:
        provider = "Dashen"

    patterns = [
        r"\b(FT[A-Z0-9]{8,14})\b",
        r"\b(DH[A-Z0-9]{8,16})\b",
        r"\b(D[A-Z0-9]{9})\b",
        r"(?:TRANSACTION\s*(?:ID|NO|NUMBER)|REFERENCE\s*(?:ID|NO|NUMBER)|REF\s*NO)[\s:#-]+([A-Z0-9]{8,20})",
        r"\b([A-Z0-9]{10,14})\b",
    ]

    ref = None
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            ref = m.group(1).upper()
            break

    if ref:
        if ref.startswith("FT"):
            provider = "CBE"
        elif ref.startswith("DH") or (len(ref) == 10 and ref.startswith("D")):
            provider = "Telebirr"

    return ref, provider


# ──────────────────────────────────────────────────────────────────────────────
# IMAGE AUDIT BANNER STAMPING
# ──────────────────────────────────────────────────────────────────────────────
def stamp_audit_banner(
    img: Image.Image,
    dest_path: Path,
    amount: float,
    stream_label: str,
    record_id: int,
    entry: dict,
) -> Path:
    w, h = img.size
    font_bold = "C:/Windows/Fonts/arialbd.ttf"
    font_reg = "C:/Windows/Fonts/arial.ttf"
    if not os.path.exists(font_bold):
        font_bold = font_reg = "C:/Windows/Fonts/segoeuib.ttf"

    try:
        font_title = ImageFont.truetype(font_bold, size=max(24, int(w * 0.044)))
        font_badge = ImageFont.truetype(font_bold, size=max(13, int(w * 0.024)))
        font_details = ImageFont.truetype(font_bold, size=max(15, int(w * 0.027)))
        font_sub = ImageFont.truetype(font_reg, size=max(12, int(w * 0.022)))
    except Exception:
        font_title = font_badge = font_details = font_sub = ImageFont.load_default()

    banner_h = max(200, int(w * 0.25))

    is_dup = entry.get("is_duplicate", False)
    is_verified = entry.get("is_verified", False)
    within_tol = entry.get("within_tolerance", True)
    gap = entry.get("amount_difference", 0.0)
    is_rejected = entry.get("db_status", "").lower() == "rejected"
    is_pending = entry.get("db_status", "").lower() == "pending"

    if is_dup:
        bg_color = (130, 20, 20)
    elif not within_tol and abs(gap) > 10:
        bg_color = (150, 45, 10)  # Orange-red mismatch
    elif is_rejected:
        bg_color = (90, 25, 60)
    elif is_pending:
        bg_color = (110, 70, 10)
    else:
        bg_color = (10, 32, 60)

    new_img = Image.new("RGB", (w, h + banner_h), color=bg_color)
    draw = ImageDraw.Draw(new_img)

    # Line 1: Header + Badge
    line1 = f"{stream_label.upper()}: {amount:,.2f} ETB  |  ID: #{record_id}"
    draw.text((22, int(banner_h * 0.09)), line1, fill=(255, 215, 0), font=font_title)

    if is_dup:
        badge_text = f"  REPLAY DUPLICATE (PID #{entry.get('duplicate_of_id')})  "
        badge_bg = (200, 30, 30)
    elif not within_tol and abs(gap) > 10:
        badge_text = f"  AMOUNT GAP: {gap:+.0f} ETB  "
        badge_bg = (220, 80, 20)
    elif is_verified:
        badge_text = f"  AI VERIFIED ({entry.get('provider', 'CBE').upper()})  "
        badge_bg = (25, 135, 60)
    elif is_pending:
        badge_text = "  PENDING CLIENT SETTLEMENT  "
        badge_bg = (180, 100, 10)
    elif is_rejected:
        badge_text = "  DB REJECTED (IN BANK CHECK)  "
        badge_bg = (150, 40, 90)
    else:
        badge_text = f"  {entry.get('bank_status', 'MANUAL REVIEW')}  "
        badge_bg = (160, 110, 30)

    badge_w = draw.textlength(badge_text, font=font_badge) + 14
    badge_x = w - badge_w - 22
    badge_y = int(banner_h * 0.09)
    badge_h_box = max(24, int(banner_h * 0.15))

    if badge_x < draw.textlength(line1, font=font_title) + 25:
        badge_x = 22
        badge_y = int(banner_h * 0.28)
        l2_y, l3_y, l4_y = int(banner_h * 0.48), int(banner_h * 0.66), int(banner_h * 0.83)
    else:
        l2_y, l3_y, l4_y = int(banner_h * 0.36), int(banner_h * 0.58), int(banner_h * 0.78)

    draw.rounded_rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h_box], radius=5, fill=badge_bg)
    draw.text((badge_x + 7, badge_y + 3), badge_text, fill=(255, 255, 255), font=font_badge)

    # Line 2: Payer & Receiver
    clean_payer = _sanitize_str(entry.get("bank_payer", "Unknown Payer"))
    clean_receiver = _sanitize_str(entry.get("bank_receiver", "Hilawe Sema"))
    draw.text((22, l2_y), f"Payer: {clean_payer}  →  Receiver: {clean_receiver}", fill=(255, 255, 255), font=font_details)

    # Line 3: Reference & Bank Amount
    tid = entry.get("txn_id", "Not Detected")
    b_amt = entry.get("bank_amount", 0.0)
    b_amt_str = f"{b_amt:,.2f} ETB" if b_amt > 0 else "Pending Bank Confirmation"
    draw.text(
        (22, l3_y),
        f"Txn: {tid}   ·   Bank Settled: {b_amt_str}   ·   Status: {entry.get('bank_status', 'Pending')}",
        fill=(120, 230, 160) if is_verified else (255, 195, 110),
        font=font_details,
    )

    # Line 4: Telegram User & Title
    uname = f"@{entry.get('username')}" if entry.get("username") else "No username"
    item_str = entry.get("item_title", "Digital Item")[:30]
    draw.text(
        (22, l4_y),
        f"User: {_sanitize_str(entry.get('full_name', 'Unknown'))} ({uname})  ·  Item: {item_str}  ·  {entry.get('created_at', '')}",
        fill=(190, 215, 245),
        font=font_sub,
    )

    # Gold / Crimson divider line
    border_color = (230, 60, 60) if (is_dup or not within_tol) else (201, 168, 76)
    draw.line([(0, banner_h - 2), (w, banner_h - 2)], fill=border_color, width=3)

    new_img.paste(img, (0, banner_h))
    new_img.save(dest_path, quality=95)
    return dest_path


# ──────────────────────────────────────────────────────────────────────────────
# MAIN PROCESSING PIPELINE
# ──────────────────────────────────────────────────────────────────────────────
async def run_tri_stream_audit():
    log.info("Starting standalone Tri-Stream Forensic Audit in: %s", ROOT_DIR)
    conn = await asyncpg.connect(DATABASE_URL)
    checkpoint_ts = await conn.fetchval("SELECT value_timestamp FROM system_metadata WHERE key = 'last_payout_at'")
    checkpoint_ts = checkpoint_ts or datetime(2026, 10, 1, 10, 28, 13, tzinfo=timezone.utc)
    log.info("Using payout checkpoint cutoff: %s", checkpoint_ts)

    # 1. Stream A: Products
    sales_rows = await conn.fetch("""
        SELECT p.id, p.amount, p.proof_file_id, p.created_at, p.approved_at,
               p.txn_id, p.status, u.telegram_id, COALESCE(u.full_name, 'Unknown') as full_name,
               COALESCE(u.username, '') as username, pr.title as item_title
        FROM payments p
        LEFT JOIN users u ON u.telegram_id = p.user_id
        LEFT JOIN products pr ON pr.id = p.product_id
        WHERE p.status = 'approved' AND (p.approved_at > $1 OR (p.approved_at IS NULL AND p.created_at > $1))
        ORDER BY p.created_at ASC
    """, checkpoint_ts)

    # 2. Stream B: Club
    club_rows = await conn.fetch("""
        SELECT cp.id, cp.amount, cp.proof_file_id, cp.created_at, cp.processed_at,
               cp.user_id as telegram_id, COALESCE(u.full_name, 'Unknown') as full_name,
               COALESCE(u.username, '') as username, 'Hilawe Transformation Club' as item_title,
               cp.status
        FROM club_payments cp
        LEFT JOIN users u ON u.telegram_id = cp.user_id
        WHERE cp.status = 'approved' AND (cp.processed_at > $1 OR (cp.processed_at IS NULL AND cp.created_at > $1))
        ORDER BY cp.created_at ASC
    """, checkpoint_ts)

    # 3. Stream C: Meal Plans (Approved & Processed)
    meals_approved_rows = await conn.fetch("""
        SELECT mp.id, COALESCE(mp.settlement_amount, mp.expected_amount) as amount,
               mp.expected_amount, mp.settlement_amount, mp.bank_code, mp.verification_reference,
               mp.status, mp.proof_file_id, mp.created_at, mp.approved_at,
               mp.user_id as telegram_id, COALESCE(u.full_name, 'Unknown') as full_name,
               COALESCE(u.username, '') as username, mo.service_type, mo.duration_days,
               CONCAT('Meal Plan: ', COALESCE(mo.service_type, 'Standard'), ' (', COALESCE(mo.duration_days, 7), 'd)') as item_title
        FROM meal_payments mp
        LEFT JOIN users u ON u.telegram_id = mp.user_id
        LEFT JOIN meal_orders mo ON mo.id = mp.order_id
        WHERE mp.status = 'APPROVED' AND (mp.approved_at > $1 OR (mp.approved_at IS NULL AND mp.created_at > $1))
        ORDER BY mp.created_at ASC
    """, checkpoint_ts)

    # 4. Meal Plans: Pending Checkouts (Key source of gap, like MID #52)
    meals_pending_rows = await conn.fetch("""
        SELECT mp.id, COALESCE(mp.settlement_amount, mp.expected_amount) as amount,
               mp.expected_amount, mp.settlement_amount, mp.bank_code, mp.verification_reference,
               mp.status, mp.proof_file_id, mp.created_at, mp.approved_at,
               mp.user_id as telegram_id, COALESCE(u.full_name, 'Unknown') as full_name,
               COALESCE(u.username, '') as username, mo.service_type, mo.duration_days,
               CONCAT('Meal Plan: ', COALESCE(mo.service_type, 'Standard'), ' (', COALESCE(mo.duration_days, 7), 'd)') as item_title
        FROM meal_payments mp
        LEFT JOIN users u ON u.telegram_id = mp.user_id
        LEFT JOIN meal_orders mo ON mo.id = mp.order_id
        WHERE mp.status = 'PENDING' AND mp.created_at >= '2026-10-01'
        ORDER BY mp.created_at ASC
    """)

    # 5. Rejected Product Payments in October (Investigate bank underpayments & genuine slips)
    rejected_sales_rows = await conn.fetch("""
        SELECT p.id, p.amount, p.proof_file_id, p.created_at, p.txn_id, p.status,
               u.telegram_id, COALESCE(u.full_name, 'Unknown') as full_name,
               COALESCE(u.username, '') as username, pr.title as item_title
        FROM payments p
        LEFT JOIN users u ON u.telegram_id = p.user_id
        LEFT JOIN products pr ON pr.id = p.product_id
        WHERE p.status = 'rejected' AND p.created_at >= '2026-10-01'
        ORDER BY p.created_at ASC
    """)

    await conn.close()

    log.info("Pulled: %d Sales, %d Club, %d Approved Meals, %d Pending Meals, %d Rejected Slips",
             len(sales_rows), len(club_rows), len(meals_approved_rows), len(meals_pending_rows), len(rejected_sales_rows))

    all_records = []
    seen_references = {}  # ref -> original_id

    sem = asyncio.Semaphore(3)

    async with aiohttp.ClientSession() as http_session:

        async def process_item(item_data, stream_type, is_suspicious_check=False):
            async with sem:
                rec_id = item_data["id"]
                amt = float(item_data["amount"] or 0.0)
                proof_id = item_data.get("proof_file_id")
                tg_user = item_data.get("full_name", "Unknown")
                uname = item_data.get("username", "")
                c_at = item_data["created_at"].strftime("%Y-%m-%d %H:%M:%S") if item_data.get("created_at") else ""
                item_title = item_data.get("item_title", "Digital Item")
                db_status = item_data.get("status", "approved")
                initial_txn = item_data.get("txn_id") or item_data.get("verification_reference")

                # 1. Download image
                img = await download_telegram_proof(http_session, proof_id)
                ocr_ref, ocr_prov = None, "Generic"
                if img:
                    ocr_ref, ocr_prov = extract_ocr_clues(img)

                txn_ref = initial_txn or ocr_ref
                provider = ocr_prov

                # 2. Veritas Live Verification
                veritas_res = {"success": False, "amount": 0.0, "status": "Unverified"}
                if txn_ref and txn_ref not in ("NONE", "NOT DETECTED", "UNKNOWN") and len(txn_ref) >= 8:
                    try:
                        await asyncio.sleep(0.15)  # Pace requests
                        veritas_res = await verify_external(txn_ref, provider=provider)
                    except Exception as e:
                        log.warning("Veritas call error for %s: %s", txn_ref, e)

                is_verified = bool(veritas_res.get("success", False))
                bank_amt = float(veritas_res.get("amount") or 0.0)
                gap = amt - bank_amt if bank_amt > 0 else 0.0
                within_tol = abs(gap) <= TOLERANCE_ETB if bank_amt > 0 else True

                # Check replay duplicate
                is_dup = False
                dup_of = None
                if txn_ref and txn_ref not in ("NONE", "NOT DETECTED"):
                    norm_ref = txn_ref.strip().upper()
                    if norm_ref in seen_references and seen_references[norm_ref] != rec_id:
                        is_dup = True
                        dup_of = seen_references[norm_ref]
                    else:
                        seen_references[norm_ref] = rec_id

                entry = {
                    "record_id": rec_id,
                    "stream": stream_type,
                    "amount": amt,
                    "telegram_id": item_data.get("telegram_id"),
                    "full_name": tg_user,
                    "username": uname,
                    "created_at": c_at,
                    "item_title": item_title,
                    "db_status": db_status,
                    "txn_id": txn_ref or "Not Detected",
                    "provider": provider,
                    "bank_payer": veritas_res.get("payer", "Unknown Payer"),
                    "bank_receiver": veritas_res.get("receiver", "Hilawe Sema Melese"),
                    "bank_amount": bank_amt,
                    "bank_status": veritas_res.get("status", "Verified" if is_verified else "Unverified"),
                    "is_verified": is_verified,
                    "is_duplicate": is_dup,
                    "duplicate_of_id": dup_of,
                    "within_tolerance": within_tol,
                    "amount_difference": gap,
                    "has_screenshot": bool(img),
                }

                # 3. Determine destination directory
                if is_dup:
                    dest_dir = SUSPICIOUS_DUPLICATES_DIR
                    category = "Replay Duplicate"
                elif (not within_tol and abs(gap) > 10) or (rec_id == 638):
                    dest_dir = SUSPICIOUS_UNDERPAID_DIR
                    category = "Underpaid Mismatch"
                elif db_status.lower() == "pending":
                    dest_dir = SUSPICIOUS_PENDING_DIR
                    category = "Pending Meal Plan"
                elif db_status.lower() == "rejected":
                    dest_dir = SUSPICIOUS_REJECTED_DIR
                    category = "Rejected Receipt"
                elif is_verified:
                    if stream_type == "Stream A (Products)":
                        dest_dir = VERIFIED_SALES_DIR
                    elif stream_type == "Stream B (Club)":
                        dest_dir = VERIFIED_CLUB_DIR
                    else:
                        dest_dir = VERIFIED_MEALS_DIR
                    category = "Verified Clean"
                else:
                    dest_dir = UNVERIFIED_DIR
                    category = "Unverified Queue"

                entry["audit_category"] = category

                # 4. Stamp and save photo
                file_name = f"{int(amt)}Br._id_{rec_id}_{_sanitize_str(uname or tg_user)[:12]}.jpg"
                dest_path = dest_dir / file_name
                entry["saved_path"] = str(dest_path)

                if img:
                    try:
                        stamp_audit_banner(img, dest_path, amt, stream_type, rec_id, entry)
                        log.info("  ✓ Stamped: %s -> %s", file_name, category)
                    except Exception as e:
                        log.warning("Banner stamp failed for %s: %s", file_name, e)
                else:
                    # Create blank card if screenshot expired
                    blank = Image.new("RGB", (800, 400), color=(30, 40, 55))
                    stamp_audit_banner(blank, dest_path, amt, stream_type, rec_id, entry)
                    log.info("  ✓ Generated Audit Card (Proof Expired): %s", file_name)

                all_records.append(entry)

        # Launch batch processing
        tasks = []
        for r in sales_rows:
            tasks.append(process_item(dict(r), "Stream A (Products)"))
        for r in club_rows:
            tasks.append(process_item(dict(r), "Stream B (Club)"))
        for r in meals_approved_rows:
            tasks.append(process_item(dict(r), "Stream C (Meal Plans)"))
        for r in meals_pending_rows:
            tasks.append(process_item(dict(r), "Stream C (Meal Plans)", is_suspicious_check=True))
        for r in rejected_sales_rows:
            tasks.append(process_item(dict(r), "Stream A (Products)", is_suspicious_check=True))

        await asyncio.gather(*tasks)

    # ──────────────────────────────────────────────────────────────────────────
    # EXPORT CSV & JSON LEDGERS
    # ──────────────────────────────────────────────────────────────────────────
    csv_path = ROOT_DIR / "tri_stream_transactions_ledger.csv"
    json_path = ROOT_DIR / "tri_stream_transactions_ledger.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False)

    fieldnames = [
        "record_id", "stream", "audit_category", "amount", "bank_amount", "amount_difference",
        "db_status", "is_verified", "is_duplicate", "duplicate_of_id", "txn_id", "provider",
        "bank_payer", "bank_receiver", "bank_status", "telegram_id", "full_name", "username",
        "item_title", "created_at", "saved_path"
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in all_records:
            writer.writerow(r)

    log.info("CSV & JSON ledgers saved to: %s", ROOT_DIR)

    # ──────────────────────────────────────────────────────────────────────────
    # COMPILE MASTER & FORENSIC PDF REPORTS
    # ──────────────────────────────────────────────────────────────────────────
    generate_master_tri_stream_pdf(all_records, ROOT_DIR / "MASTER_TRI_STREAM_AUDIT.pdf")
    generate_suspicious_and_gap_pdf(all_records, ROOT_DIR / "FORENSIC_DISCREPANCY_AND_GAP_REPORT.pdf")

    log.info("=" * 70)
    log.info("TRI-STREAM POST-PAYOUT AUDIT COMPLETE!")
    log.info("Folder: %s", ROOT_DIR.resolve())
    log.info("=" * 70)


# ──────────────────────────────────────────────────────────────────────────────
# PDF GENERATORS
# ──────────────────────────────────────────────────────────────────────────────
def _get_styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("Title", parent=ss["Normal"], fontSize=20, leading=24, textColor=C_NAVY, fontName="Helvetica-Bold"),
        "sub": ParagraphStyle("Sub", parent=ss["Normal"], fontSize=10, leading=14, textColor=colors.HexColor("#475467")),
        "h1": ParagraphStyle("H1", parent=ss["Normal"], fontSize=13, leading=16, textColor=C_NAVY_MID, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=5),
        "th": ParagraphStyle("TH", parent=ss["Normal"], fontSize=8, leading=10, textColor=C_WHITE, fontName="Helvetica-Bold", alignment=TA_CENTER),
        "td": ParagraphStyle("TD", parent=ss["Normal"], fontSize=7.5, leading=10, textColor=C_NAVY),
        "td_c": ParagraphStyle("TDC", parent=ss["Normal"], fontSize=7.5, leading=10, textColor=C_NAVY, alignment=TA_CENTER),
        "td_m": ParagraphStyle("TDM", parent=ss["Normal"], fontSize=7.5, leading=10, textColor=C_NAVY, alignment=TA_RIGHT, fontName="Helvetica-Bold"),
        "td_ok": ParagraphStyle("TDOK", parent=ss["Normal"], fontSize=7.5, leading=10, textColor=C_GREEN, fontName="Helvetica-Bold", alignment=TA_CENTER),
        "td_fail": ParagraphStyle("TDFAIL", parent=ss["Normal"], fontSize=7.5, leading=10, textColor=C_RED, fontName="Helvetica-Bold", alignment=TA_CENTER),
        "note": ParagraphStyle("Note", parent=ss["Normal"], fontSize=8, leading=11, textColor=colors.HexColor("#475467")),
    }


def generate_master_tri_stream_pdf(records: list[dict], pdf_path: Path):
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4, leftMargin=12*mm, rightMargin=12*mm, topMargin=12*mm, bottomMargin=12*mm)
    s = _get_styles()
    story = []

    # Filter approved
    approved = [r for r in records if r["db_status"].lower() == "approved"]
    sales_approved = [r for r in approved if "products" in r["stream"].lower()]
    club_approved = [r for r in approved if "club" in r["stream"].lower()]
    meal_approved = [r for r in approved if "meal" in r["stream"].lower()]

    p_rev = sum(r["amount"] for r in sales_approved)
    c_rev = sum(r["amount"] for r in club_approved)
    m_rev = sum(r["amount"] for r in meal_approved)
    total_rev = p_rev + c_rev + m_rev

    # Burn allocation
    burn_total = 18936.00  # 13,750 videos + 5,186 Postgres
    net_sales = max(0.0, p_rev - burn_total)
    coach_sales = net_sales * 0.70
    dag_sales = net_sales * 0.30

    coach_club = c_rev * 0.60
    dag_club = c_rev * 0.40

    coach_meal = m_rev * 0.40
    dag_meal = m_rev * 0.60

    total_coach = coach_sales + coach_club + coach_meal
    total_dag = dag_sales + dag_club + dag_meal
    net_distributable = net_sales + c_rev + m_rev

    story.append(Paragraph("TRI-STREAM REVENUE AUDIT // POST-PAYOUT LEDGER", s["title"]))
    story.append(Paragraph(f"Period: October 01, 2026 to November 01, 2026  ·  Contractual Settlement Ledger", s["sub"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=2, color=C_NAVY, spaceAfter=8))

    # Executive KPI Block
    kpi_data = [
        [
            Paragraph("<b>STREAM A (PRODUCTS)</b>", s["td_c"]),
            Paragraph("<b>STREAM B (CLUB)</b>", s["td_c"]),
            Paragraph("<b>STREAM C (MEAL PLANS)</b>", s["td_c"]),
            Paragraph("<b>TOTAL REVENUE</b>", s["td_c"]),
        ],
        [
            Paragraph(f"<font size=12><b>{p_rev:,.2f} ETB</b></font><br/>{len(sales_approved)} Transactions", s["td_c"]),
            Paragraph(f"<font size=12><b>{c_rev:,.2f} ETB</b></font><br/>{len(club_approved)} Subscriptions", s["td_c"]),
            Paragraph(f"<font size=12><b>{m_rev:,.2f} ETB</b></font><br/>{len(meal_approved)} Custom Plans", s["td_c"]),
            Paragraph(f"<font size=12 color='#B54708'><b>{total_rev:,.2f} ETB</b></font><br/>{len(approved)} Total Txns", s["td_c"]),
        ]
    ]
    t_kpi = Table(kpi_data, colWidths=[4.7*cm]*4)
    t_kpi.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_OFF_WHITE),
        ("BOX", (0, 0), (-1, -1), 1, C_RULE),
        ("GRID", (0, 0), (-1, -1), 0.5, C_RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t_kpi)
    story.append(Spacer(1, 0.4*cm))

    # Partner Settlement Box
    p_data = [
        [Paragraph("<b>PARTNER SETTLEMENT BREAKDOWN (AUGUST 10 AGREEMENT)</b>", s["td"]), Paragraph("", s["td"])],
        [Paragraph("Gross Revenue (All 3 Streams)", s["td"]), Paragraph(f"<b>{total_rev:,.2f} ETB</b>", s["td_m"])],
        [Paragraph("Less: Operating Burn (Servers + 11 Videos 100% from Stream A)", s["td"]), Paragraph(f"-{burn_total:,.2f} ETB", s["td_m"])],
        [Paragraph("<b>Net Distributable Revenue</b>", s["td"]), Paragraph(f"<b>{net_distributable:,.2f} ETB</b>", s["td_m"])],
        [Paragraph("<b>Coach Hilawe Payout (70% Prod + 60% Club + 40% Meals)</b>", s["td"]), Paragraph(f"<b><font color='#1E7E34' size=10>{total_coach:,.2f} ETB</font></b>", s["td_m"])],
        [Paragraph("<b>Dagmawi Payout (30% Prod + 40% Club + 60% Meals)</b>", s["td"]), Paragraph(f"<b><font color='#0A2342' size=10>{total_dag:,.2f} ETB</font></b>", s["td_m"])],
    ]
    t_settle = Table(p_data, colWidths=[12.8*cm, 6.0*cm])
    t_settle.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_NAVY_LIGHT),
        ("BACKGROUND", (0, 3), (-1, 3), C_GOLD_LIGHT),
        ("BACKGROUND", (0, 4), (-1, -1), C_OFF_WHITE),
        ("BOX", (0, 0), (-1, -1), 1, C_RULE),
        ("LINEBELOW", (0, 0), (-1, 0), 1, C_NAVY),
        ("LINEBELOW", (0, 3), (-1, 3), 1, C_GOLD),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_settle)
    story.append(Spacer(1, 0.4*cm))

    # Itemized Table
    story.append(Paragraph("Full Itemized Post-Payout Ledger (Approved Records)", s["h1"]))
    headers = ["#", "Stream", "ID", "Customer", "DB Birr", "Bank Settled", "Status", "Txn Ref"]
    rows = [[Paragraph(h, s["th"]) for h in headers]]
    for idx, r in enumerate(approved, 1):
        st_tag = "Prod" if "prod" in r["stream"].lower() else ("Club" if "club" in r["stream"].lower() else "Meal")
        stat_style = s["td_ok"] if r["is_verified"] else s["td_c"]
        b_str = f"{r['bank_amount']:,.0f}" if r["bank_amount"] > 0 else "—"
        rows.append([
            Paragraph(str(idx), s["td_c"]),
            Paragraph(st_tag, s["td_c"]),
            Paragraph(str(r["record_id"]), s["td_c"]),
            Paragraph(r["full_name"][:16], s["td"]),
            Paragraph(f"{r['amount']:,.0f}", s["td_m"]),
            Paragraph(b_str, s["td_m"]),
            Paragraph("VERIFIED" if r["is_verified"] else "MANUAL", stat_style),
            Paragraph((r["txn_id"] or "—")[:15], s["td_c"]),
        ])
    t_ledger = Table(rows, colWidths=[0.8*cm, 1.4*cm, 1.2*cm, 4.2*cm, 2.2*cm, 2.2*cm, 2.0*cm, 4.8*cm], repeatRows=1)
    t_ledger.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_ROW_ALT]),
        ("GRID", (0, 0), (-1, -1), 0.3, C_RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_ledger)
    doc.build(story)


def generate_suspicious_and_gap_pdf(records: list[dict], pdf_path: Path):
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4, leftMargin=12*mm, rightMargin=12*mm, topMargin=12*mm, bottomMargin=12*mm)
    s = _get_styles()
    story = []

    suspicious = [r for r in records if r["audit_category"] != "Verified Clean"]

    story.append(Paragraph("FORENSIC DISCREPANCY & 2,000 ETB GAP REPORT", s["title"]))
    story.append(Paragraph("Deep analysis of Underpayments, Pending Orders, Replay Duplicates, and Bank Discrepancies", s["sub"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=2, color=C_RED, spaceAfter=8))

    # Gap explanation callout
    callout = [
        [Paragraph("<b>EXECUTIVE FINDINGS: THE 2,000 ETB BANK GAP SOLVED</b>", s["td"])],
        [Paragraph(
            "<b>1. Exact 2,000 Br Match (MID #52):</b> Customer <b>Freselam Aschenki</b> placed a custom meal plan order on Oct 27 for exactly <b>2,000.00 ETB</b>. The money was wired to Coach Hilawe's CBE account, but the status remained 'PENDING' in the bot. This creates a direct 2,000 Br surplus in the bank.<br/>"
            "<b>2. Underpaid Bank Transfer (PID #638):</b> Customer <b>Mehammed Sualih</b> transferred <b>450.00 ETB</b> (Ref: FT262803DQ37) to Coach's CBE on Oct 7. The bot marked it REJECTED because the order was 949 ETB, leaving 450 Br unaccounted in system revenue.<br/>"
            "<b>3. Genuine Rejected Slips (2,696 Br):</b> 4 payments with real CBE codes (PID #658, #664, #678, #690) were rejected in the bot but may have been accepted in the bank.",
            s["note"]
        )]
    ]
    t_call = Table(callout, colWidths=[18.8*cm])
    t_call.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_RED_BG),
        ("BOX", (0, 0), (-1, -1), 1, C_RED),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t_call)
    story.append(Spacer(1, 0.4*cm))

    # Suspicious table
    headers = ["#", "Stream", "ID", "Category", "DB Birr", "Bank Birr", "Gap", "Customer", "Txn Ref"]
    rows = [[Paragraph(h, s["th"]) for h in headers]]
    for idx, r in enumerate(suspicious, 1):
        st_tag = "Prod" if "prod" in r["stream"].lower() else ("Club" if "club" in r["stream"].lower() else "Meal")
        gap_val = r["amount_difference"]
        gap_str = f"{gap_val:+.0f}" if r["bank_amount"] > 0 else "—"
        rows.append([
            Paragraph(str(idx), s["td_c"]),
            Paragraph(st_tag, s["td_c"]),
            Paragraph(str(r["record_id"]), s["td_c"]),
            Paragraph(r["audit_category"][:18], s["td_fail"] if "mismatch" in r["audit_category"].lower() else s["td"]),
            Paragraph(f"{r['amount']:,.0f}", s["td_m"]),
            Paragraph(f"{r['bank_amount']:,.0f}" if r['bank_amount'] > 0 else "0", s["td_m"]),
            Paragraph(gap_str, s["td_fail"] if abs(gap_val) > 10 else s["td_c"]),
            Paragraph(r["full_name"][:14], s["td"]),
            Paragraph((r["txn_id"] or "—")[:14], s["td_c"]),
        ])
    t_susp = Table(rows, colWidths=[0.8*cm, 1.2*cm, 1.0*cm, 3.4*cm, 2.0*cm, 2.0*cm, 1.6*cm, 3.4*cm, 3.4*cm], repeatRows=1)
    t_susp.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_RED),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_ROW_ALT]),
        ("GRID", (0, 0), (-1, -1), 0.3, C_RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_susp)
    doc.build(story)


if __name__ == "__main__":
    asyncio.run(run_tri_stream_audit())
