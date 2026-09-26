"""
forensic_stamp.py
─────────────────
Top 0.0001% Real-Time Forensic Verification & Visual Stamping Engine.

Executed BEFORE any payment proof is forwarded to admin channels:
1. Downloads proof image into memory (zero-disk clutter).
2. Runs OCR & pattern extraction for reference ID, provider, and amounts.
3. Checks for Transaction Reference (FT...) duplicate replays against the database.
4. Queries Veritas / bank gateways for live verification & settlement confirmation.
5. Reconciles registered price vs actual settled amount (underpayment detection).
6. Dynamically stamps a high-contrast visual audit banner directly onto the image.
7. Produces an executive Telegram caption with tap-to-copy reference and smart action buttons.
"""

from __future__ import annotations

import asyncio
import html
import io
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont
from aiogram import Bot, types
from aiogram.types import BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import Database
from handlers.verify import extract_local_data, verify_external, is_hilawe_receiver

logger = logging.getLogger("forensic_stamp")


def _sanitize_str(text: Any) -> str:
    """Sanitize strings for PIL TrueType rendering (stripping unprintable chars)."""
    if text is None:
        return ""
    s = str(text)
    return "".join(c for c in s if ord(c) < 65536 and c.isprintable() or c in (" ", "\n", "\t")).strip()


def stamp_audit_banner_to_bytes(
    img: Image.Image,
    amount: float,
    pid: int,
    verdict_info: dict,
) -> io.BytesIO:
    """
    Stamps high-contrast, large-font audit banner onto image and returns BytesIO.
    Matches the forensic design of the Master Audit system.
    """
    # Ensure RGB
    if img.mode != "RGB":
        img = img.convert("RGB")

    w, h = img.size

    # Font setup
    font_path_bold = "C:/Windows/Fonts/arialbd.ttf"
    font_path_reg = "C:/Windows/Fonts/arial.ttf"
    if not os.path.exists(font_path_bold):
        font_path_bold = font_path_reg = "C:/Windows/Fonts/segoeuib.ttf"

    try:
        font_title = ImageFont.truetype(font_path_bold, size=max(24, int(w * 0.045)))
        font_badge = ImageFont.truetype(font_path_bold, size=max(13, int(w * 0.025)))
        font_details = ImageFont.truetype(font_path_bold, size=max(15, int(w * 0.027)))
        font_sub = ImageFont.truetype(font_path_reg, size=max(12, int(w * 0.023)))
    except Exception:
        font_title = font_badge = font_details = font_sub = ImageFont.load_default()

    banner_h = max(190, int(w * 0.24))

    is_dup = verdict_info.get("is_duplicate", False)
    is_underpaid = verdict_info.get("is_underpayment", False)
    is_verified = verdict_info.get("is_verified", False)
    gap = verdict_info.get("gap", 0.0)

    # Dynamic Background Palette
    if is_dup:
        bg_color = (120, 15, 15)   # Crimson red (Fraud / Replay)
    elif is_underpaid:
        bg_color = (135, 55, 10)   # Deep amber/orange (Underpayment)
    elif is_verified:
        bg_color = (10, 30, 58)    # Deep Navy (Verified)
    else:
        bg_color = (18, 28, 45)    # Slate Navy (Manual Review)

    new_img = Image.new("RGB", (w, h + banner_h), color=bg_color)
    draw = ImageDraw.Draw(new_img)

    # ── LINE 1: Registered Amount + Status Badge ──────────────────────────────
    stream_label = verdict_info.get("stream_label", "ORDER")
    line1_left = f"{stream_label}: {amount:,.2f} ETB   |   ID: #{pid}"
    title_color = (255, 80, 80) if is_dup else (255, 215, 0)
    draw.text((20, int(banner_h * 0.08)), line1_left, fill=title_color, font=font_title)

    # Badge configuration
    if is_dup:
        badge_text = f"  🚨 REPLAY DUPLICATE (PID #{verdict_info.get('duplicate_pid')})  "
        badge_bg = (195, 30, 30)
        badge_fg = (255, 255, 255)
    elif is_underpaid:
        badge_text = f"  ⚠️ UNDERPAYMENT ({gap:+.0f} ETB)  "
        badge_bg = (215, 85, 20)
        badge_fg = (255, 255, 255)
    elif is_verified:
        provider = verdict_info.get("provider", "BANK").upper()
        badge_text = f"  🟢 AI VERIFIED ({provider})  "
        badge_bg = (22, 138, 62)
        badge_fg = (255, 255, 255)
    else:
        status_label = verdict_info.get("bank_status", "MANUAL REVIEW").upper()
        badge_text = f"  🟡 {status_label}  "
        badge_bg = (175, 110, 20)
        badge_fg = (255, 255, 255)

    badge_w = draw.textlength(badge_text, font=font_badge) + 14
    badge_x = w - badge_w - 20
    badge_y = int(banner_h * 0.08)
    badge_height = max(24, int(banner_h * 0.15))

    # Responsive drop if screen is narrow
    if badge_x < draw.textlength(line1_left, font=font_title) + 26:
        badge_x = 20
        badge_y = int(banner_h * 0.28)
        line2_y = int(banner_h * 0.47)
        line3_y = int(banner_h * 0.65)
        line4_y = int(banner_h * 0.82)
    else:
        line2_y = int(banner_h * 0.36)
        line3_y = int(banner_h * 0.58)
        line4_y = int(banner_h * 0.78)

    draw.rounded_rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_height], radius=6, fill=badge_bg)
    draw.text((badge_x + 7, badge_y + 3), badge_text, fill=badge_fg, font=font_badge)

    # ── LINE 2: Bank Payer & Receiver ──────────────────────────────────────────
    clean_payer = _sanitize_str(verdict_info.get("payer", "Unknown Payer"))[:32]
    clean_receiver = _sanitize_str(verdict_info.get("receiver", "Hilawe Sema Melese"))[:32]
    line2 = f"Payer: {clean_payer}  →  Receiver: {clean_receiver}"
    draw.text((20, line2_y), line2, fill=(255, 255, 255), font=font_details)

    # ── LINE 3: Txn ID, Settled Amount, and Provider ───────────────────────────
    tid = verdict_info.get("txn_id", "Not Detected")
    b_amt = verdict_info.get("settled_amount", 0.0)
    b_amt_str = f"{b_amt:,.2f} ETB" if b_amt > 0 else "Confirmed"
    status_str = verdict_info.get("bank_status", "Completed")

    line3 = f"Txn: {tid}   ·   Settled: {b_amt_str}   ·   Status: {status_str}"
    line3_color = (255, 90, 90) if is_dup else ((255, 170, 70) if is_underpaid else ((120, 230, 160) if is_verified else (255, 195, 90)))
    draw.text((20, line3_y), line3, fill=line3_color, font=font_details)

    # ── LINE 4: Telegram User Details & Timestamp ──────────────────────────────
    clean_tg_name = _sanitize_str(verdict_info.get("user_name", "Unknown"))[:25]
    uname = f"@{verdict_info.get('username')}" if verdict_info.get("username") and verdict_info.get("username") != "No Username" else "No Username"
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    line4 = f"Telegram: {clean_tg_name} ({uname})   ·   {date_str}"
    draw.text((20, line4_y), line4, fill=(185, 210, 240), font=font_sub)

    # Bottom accent line
    border_color = (255, 70, 70) if is_dup else ((225, 90, 25) if is_underpaid else ((22, 138, 62) if is_verified else (201, 168, 76)))
    draw.line([(0, banner_h - 2), (w, banner_h - 2)], fill=border_color, width=3)

    # Paste original screenshot underneath banner
    new_img.paste(img, (0, banner_h))

    out_buf = io.BytesIO()
    new_img.save(out_buf, format="JPEG", quality=92)
    out_buf.seek(0)
    return out_buf


async def process_and_stamp_incoming_proof(
    bot: Bot,
    db: Database,
    proof_file_id: str,
    payment_id: int,
    stream: str,  # 'sales' or 'club'
    user_id: int,
    user_name: str,
    username: str | None,
    lang: str,
    expected_amount: float,
    item_title: str,
    extra_details: dict | None = None,
) -> Tuple[BufferedInputFile | str, str, types.InlineKeyboardMarkup]:
    """
    Full Forensic Verification & Stamping Pipeline.
    Returns (photo_object, caption_html, inline_markup).
    """
    start_time = time.perf_counter()
    extra = extra_details or {}
    stream_label = "PRODUCT SALE" if stream == "sales" else "CLUB SUBSCRIPTION"

    # Default fallback verdict structure
    verdict = {
        "stream_label": stream_label,
        "is_duplicate": False,
        "duplicate_pid": None,
        "is_underpayment": False,
        "is_verified": False,
        "gap": 0.0,
        "provider": "CBE",
        "payer": "Pending AI Check",
        "receiver": "Hilawe Sema Melese",
        "txn_id": "Not Detected",
        "settled_amount": 0.0,
        "bank_status": "Scanning",
        "user_name": user_name,
        "username": username or "No Username",
    }

    try:
        # 1. Download image into memory
        file_info = await bot.get_file(proof_file_id)
        img_buf = io.BytesIO()
        await bot.download_file(file_info.file_path, destination=img_buf)
        img_buf.seek(0)

        # 2. Extract OCR and Local Clues
        local_data = await extract_local_data(img_buf)
        ref_id = local_data.get("ref") if local_data else None
        provider = local_data.get("provider", "CBE") if local_data else "CBE"
        raw_text = local_data.get("raw_text", "") if local_data else ""

        verdict["provider"] = provider
        if ref_id:
            verdict["txn_id"] = ref_id

        # 3. Check for Transaction Reference Replay Duplicate in Database
        if ref_id and len(str(ref_id)) >= 6:
            dup_txn = await db.check_duplicate_txn_id(ref_id, exclude_id=payment_id, stream=stream)
            if dup_txn:
                verdict["is_duplicate"] = True
                verdict["duplicate_pid"] = dup_txn["id"]
                logger.warning(
                    "🚨 REPLAY DUPLICATE DETECTED: Incoming %s #%s reused txn_id %s from %s #%s!",
                    stream, payment_id, ref_id, dup_txn["stream"], dup_txn["id"]
                )

        # 4. Save detected Txn ID to the payment record
        if ref_id:
            await db.update_payment_txn_id(payment_id, ref_id, stream=stream)

        # 5. Live Bank Verification (if not already a confirmed duplicate)
        bank_data = {"success": False}
        is_real = False
        is_hilawe = False

        if ref_id and not verdict["is_duplicate"]:
            try:
                bank_data = await asyncio.wait_for(verify_external(ref_id, provider), timeout=12.0)
                is_real = bank_data.get("success", False)
                is_hilawe = is_hilawe_receiver(raw_text, bank_data)
            except Exception as e:
                logger.warning("Bank verification timeout or error for ref %s: %s", ref_id, e)
                bank_data = {"success": False, "status": "Gateway Timeout"}

        # 6. Parse Bank Results & Reconciliation
        settled_amt = 0.0
        if is_real:
            verdict["is_verified"] = True
            verdict["bank_status"] = "Verified & Settled"
            
            # Extract settled amount
            raw = bank_data.get("raw_response") or {}
            raw_data = raw.get("data") if isinstance(raw, dict) and isinstance(raw.get("data"), dict) else {}
            payer_val = bank_data.get("payer") or raw_data.get("payerName") or "Verified Payer"
            receiver_val = bank_data.get("receiver") or raw_data.get("creditedPartyName") or "Hilawe Sema Melese"
            
            verdict["payer"] = payer_val
            verdict["receiver"] = receiver_val

            amt_val = bank_data.get("amount") or raw_data.get("settledAmount") or raw.get("amount")
            if amt_val:
                try:
                    m = re.search(r"(\d+(?:\.\d+)?)", str(amt_val).replace(",", ""))
                    if m:
                        settled_amt = float(m.group(1))
                except Exception:
                    pass
        else:
            verdict["bank_status"] = bank_data.get("status") or ("Unverified Slip" if not ref_id else "API Lag / Manual Check")
            verdict["payer"] = user_name

        # Fallback local OCR amount if bank API didn't report exact figure
        if settled_amt == 0.0 and local_data.get("amount_fallback"):
            settled_amt = float(local_data["amount_fallback"])

        verdict["settled_amount"] = settled_amt

        # 7. Check for Underpayment / Financial Gap
        if settled_amt > 0:
            gap = settled_amt - expected_amount
            verdict["gap"] = gap
            if gap < -5.0:
                verdict["is_underpayment"] = True
                logger.warning(
                    "⚠️ UNDERPAYMENT DETECTED: Payment #%s registered at %.2f ETB, settled %.2f ETB (Gap: %.2f ETB)",
                    payment_id, expected_amount, settled_amt, gap
                )

        # 8. Stamp the Visual Banner onto Image
        img_buf.seek(0)
        with Image.open(img_buf) as pil_img:
            stamped_bytes_io = stamp_audit_banner_to_bytes(
                pil_img,
                amount=expected_amount,
                pid=payment_id,
                verdict_info=verdict,
            )

        photo_payload = BufferedInputFile(
            stamped_bytes_io.getvalue(),
            filename=f"audit_{stream}_{payment_id}.jpg"
        )

    except Exception as exc:
        logger.error("Error in forensic stamping pipeline for %s #%s: %s", stream, payment_id, exc, exc_info=True)
        # Safe fallback: send original proof photo without crashing
        photo_payload = proof_file_id

    elapsed = time.perf_counter() - start_time

    # 9. Build Executive Caption with Tap-to-Copy Reference & Risk Indicators
    caption = _build_executive_caption(
        stream=stream,
        stream_label=stream_label,
        payment_id=payment_id,
        user_id=user_id,
        user_name=user_name,
        username=username,
        lang=lang,
        item_title=item_title,
        expected_amount=expected_amount,
        verdict=verdict,
        elapsed=elapsed,
        extra=extra,
    )

    # 10. Build Smart Context-Aware Action Buttons
    keyboard = _build_smart_keyboard(
        stream=stream,
        payment_id=payment_id,
        user_id=user_id,
        verdict=verdict,
        extra=extra,
    )

    return photo_payload, caption, keyboard


def _build_executive_caption(
    stream: str,
    stream_label: str,
    payment_id: int,
    user_id: int,
    user_name: str,
    username: str | None,
    lang: str,
    item_title: str,
    expected_amount: float,
    verdict: dict,
    elapsed: float,
    extra: dict,
) -> str:
    """Builds an executive-level Telegram HTML audit card."""
    is_dup = verdict.get("is_duplicate", False)
    is_underpaid = verdict.get("is_underpayment", False)
    is_verified = verdict.get("is_verified", False)
    provider = verdict.get("provider", "CBE").upper()
    ref_id = verdict.get("txn_id", "Not Detected")
    gap = verdict.get("gap", 0.0)
    settled = verdict.get("settled_amount", 0.0)

    # ── RISK SEVERITY HEADER ──────────────────────────────────────────
    if is_dup:
        header = (
            f"🚨 <b>CRITICAL FRAUD ALERT — REPLAY DUPLICATE</b>\n"
            f"⚠️ <i>Receipt reference already claimed in PID #{verdict.get('duplicate_pid')}!</i>\n"
        )
    elif is_underpaid:
        header = (
            f"⚠️ <b>FINANCIAL ALERT — UNDERPAYMENT DETECTED</b>\n"
            f"🚨 <i>Customer paid {settled:,.0f} ETB instead of {expected_amount:,.0f} ETB!</i>\n"
        )
    elif is_verified:
        header = (
            f"🟢 <b>AI AUDIT: 100% VERIFIED & SETTLED</b>\n"
            f"✓ <i>Direct bank settlement confirmed with {provider}.</i>\n"
        )
    else:
        header = (
            f"🟡 <b>AI AUDIT: MANUAL STATEMENT REVIEW REQUIRED</b>\n"
            f"ℹ️ <i>Visual receipt scanned; gateway lag or custom bank.</i>\n"
        )

    # User & Handle
    clean_user = html.escape(user_name)
    uname_str = html.escape(f"@{username}") if username and username != "No Username" else "<i>No username</i>"
    lang_badge = "🇺🇸 English" if lang == "EN" else "🇪🇹 አማርኛ"

    # Amount & Reconciliation text
    if is_underpaid:
        amt_line = f"💰 <b>Amount:</b> Expected <code>{expected_amount:,.2f} ETB</code>  |  <b>Paid:</b> <code>{settled:,.2f} ETB</code>  (<b>{gap:+.0f} ETB GAP ❌</b>)"
    elif settled > 0 and abs(gap) <= 5.0:
        amt_line = f"💰 <b>Amount:</b> <code>{settled:,.2f} ETB</code> (Full Match ✓)"
    else:
        amt_line = f"💰 <b>Expected:</b> <code>{expected_amount:,.2f} ETB</code>"

    # Ref representation (tap to copy)
    ref_display = f"<code>{html.escape(ref_id)}</code>" if ref_id != "Not Detected" else "<i>Unreadable Slip</i>"

    # Stream-specific lines
    if stream == "club":
        payment_type = extra.get("payment_type", "new").upper()
        prev_payments = extra.get("previous_payments", 0)
        stream_extra = (
            f"👑 <b>Club Type:</b> <code>{payment_type}</code>  |  "
            f"Past Subs: <code>{prev_payments}</code>\n"
        )
    else:
        stream_extra = f"📦 <b>Target Plan:</b> {html.escape(item_title)}\n"

    caption = (
        f"{header}"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Customer:</b> {clean_user}  ({uname_str})\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>  ·  {lang_badge}\n"
        f"{stream_extra}"
        f"{amt_line}\n"
        f"🎫 <b>Payment ID:</b> <code>#{payment_id}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 <b>Bank:</b> <b>{provider}</b>\n"
        f"🔖 <b>Txn Reference:</b> {ref_display}\n"
        f"👤 <b>Bank Payer:</b> {html.escape(verdict.get('payer', 'N/A'))}\n"
        f"🎯 <b>Credited To:</b> {html.escape(verdict.get('receiver', 'Hilawe Sema Melese'))}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱️ <i>Audited in {elapsed:.2f}s  ·  Anti-Replay Shield Active 🛡️</i>"
    )

    return caption


def _build_smart_keyboard(
    stream: str,
    payment_id: int,
    user_id: int,
    verdict: dict,
    extra: dict,
) -> types.InlineKeyboardMarkup:
    """Builds smart inline action buttons tailored to verification risk level."""
    builder = InlineKeyboardBuilder()
    is_dup = verdict.get("is_duplicate", False)
    is_underpaid = verdict.get("is_underpayment", False)

    if stream == "sales":
        if is_dup:
            builder.button(text="🚨 REJECT DUPLICATE (FRAUD)", callback_data=f"reject_{payment_id}")
            builder.button(text="⚠️ FORCE APPROVE (OVERRIDE)", callback_data=f"approve_{payment_id}")
        elif is_underpaid:
            builder.button(text="⚠️ REJECT UNDERPAYMENT", callback_data=f"reject_{payment_id}")
            builder.button(text="✅ APPROVE PARTIAL AMOUNT", callback_data=f"approve_{payment_id}")
        else:
            builder.button(text="✅ APPROVE & DELIVER PDF", callback_data=f"approve_{payment_id}")
            builder.button(text="❌ REJECT / FAKE", callback_data=f"reject_{payment_id}")
    else:  # Club stream
        is_renewal = extra.get("is_renewal", False)
        approve_cb = f"club_approve_{payment_id}"
        reject_cb = f"club_reject_{payment_id}"

        if is_dup:
            builder.button(text="🚨 REJECT DUPLICATE (FRAUD)", callback_data=reject_cb)
            builder.button(text="⚠️ FORCE APPROVE", callback_data=approve_cb)
        elif is_underpaid:
            builder.button(text="⚠️ REJECT UNDERPAYMENT", callback_data=reject_cb)
            builder.button(text="✅ ACCEPT & GRANT ENTRY", callback_data=approve_cb)
        else:
            label = "✅ APPROVE RENEWAL (+30 DAYS)" if is_renewal else "✅ APPROVE CLUB ENTRY"
            builder.button(text=label, callback_data=approve_cb)
            if is_renewal:
                builder.button(text="🧾 VIEW MEMBER HISTORY", callback_data=f"club_history_{user_id}")
            builder.button(text="❌ REJECT RECEIPT", callback_data=reject_cb)

    builder.adjust(1)
    return builder.as_markup()
