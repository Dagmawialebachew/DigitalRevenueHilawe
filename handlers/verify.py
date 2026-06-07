"""
verify.py  —  Render-Optimized Edition
Target: < 3 seconds per transaction

Speed & Architecture for Cloud (Render):
  1. API Authority: Always prioritizes exact amounts from the API over local OCR.
  2. Smart Failover OCR: Tries PSM 6 first. If it misses, falls back to PSM 4.
  3. Precision Binarization: Adjusted numpy thresholding to preserve light gray text (crucial for Telebirr receipts).
  4. Memory Guard: Downscales massive phone screenshots to prevent Out-Of-Memory crashes.
  5. Persistent Async HTTP: Warm connection pools for zero-latency API handshakes.
"""

import os
import io
import asyncio
import re
import platform
import shutil
import time

import numpy as np
import httpx
from PIL import Image, ImageEnhance
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import settings

import pytesseract

if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract") or "/usr/bin/tesseract"

# ─────────────────────────────────────────────
#  CONFIG & PERSISTENT CLIENT
# ─────────────────────────────────────────────
API_KEY    = settings.VERIFY_API_KEY
API_URL    = "https://verifyapi.leulzenebe.pro/verify"
CBE_SUFFIX = "99533641"
ABYSSINIA_SUFFIX = "53299555"  # <-- Add this line

router = Router(name="verify")

_http_client: httpx.AsyncClient | None = None

def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=3.0, read=10.0, write=3.0, pool=3.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
            headers={
                "x-api-key": API_KEY,
                "Content-Type": "application/json",
            },
        )
    return _http_client

class PaymentStates(StatesGroup):
    waiting_for_screenshot = State()

# ─────────────────────────────────────────────
#  IN-MEMORY IMAGE PREPROCESSING
# ─────────────────────────────────────────────
def _preprocess_in_memory(img_stream: io.BytesIO) -> Image.Image:
    """Processes image in RAM using PIL and numpy. Protects Render from OOM."""
    img = Image.open(img_stream).convert("L")
    w, h = img.size

    # Memory Guard
    if w > 1500:
        ratio = 1500 / w
        img = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
    elif w < 800:
        img = img.resize((w * 2, h * 2), Image.Resampling.BICUBIC)

    # Boost contrast before matrix conversion
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)

    # Vectorized fast thresholding
    # 0.92 multiplier ensures light gray text (Telebirr) isn't washed out into the white background
    img_array = np.array(img)
    threshold = np.mean(img_array) * 0.92
    binary_matrix = np.where(img_array > threshold, 255, 0).astype(np.uint8)
    
    return Image.fromarray(binary_matrix)

# ─────────────────────────────────────────────
#  SMART FAILOVER OCR
# ─────────────────────────────────────────────
def _run_tesseract(img: Image.Image, psm: int) -> str:
    return pytesseract.image_to_string(img, config=f"--oem 3 --psm {psm}")

async def _ocr_smart(img: Image.Image) -> str:
    loop = asyncio.get_running_loop()
    
    text = await loop.run_in_executor(None, _run_tesseract, img, 6)
    
    # Failover condition: Look for either a CBE ID or a 10-character Telebirr ID
    if not re.search(r"[A-Z0-9]{8,}", text):
        fallback_text = await loop.run_in_executor(None, _run_tesseract, img, 4)
        text = f"{text}\n{fallback_text}"
        
    return text

# ─────────────────────────────────────────────
#  EXTRACTION LOGIC
# ─────────────────────────────────────────────
def _detect_provider(up: str) -> str:
    if any(k in up for k in ("ABYSSINIA", "BOA")):
        return "Abyssinia"
    if any(k in up for k in ("COMMERCIAL BANK", "CBE", "BRECIEPT", "FT2")):
        return "CBE"
    # Added regex pattern to detect Telebirr IDs (starting with D, 10 chars) even if brand name is unreadable
    if any(k in up for k in ("TELEBIRR", "ETHIO TELECOM", "TELE BIRR")) or re.search(r"\b(D[A-Z0-9]{9})\b", up):
        return "Telebirr"
    if "AWASH" in up:
        return "Awash"
    return "Unknown"

def _extract_cbe(up: str) -> str | None:
    m = re.search(r"F\s*T\s*([A-Z0-9]{8,12})", up)
    if m: return ("FT" + m.group(1)).replace(" ", "")
    m = re.search(r"(?:ID|TRANSACTION\s*ID)[:\s]+([A-Z0-9]{10,14})", up)
    if m: return m.group(1).strip()
    m = re.search(r"\b(FT[A-Z0-9]{8,12})\b", up)
    return m.group(1) if m else None

def _extract_telebirr(up: str, raw: str) -> str | None:
    for label in ("TRANSACTION NUMBER", "TRANSACTION NO", "INVOICE NO", "INVOICE NUMBER", "REF NO", "REFERENCE NO", "NUMBER"):
        m = re.search(rf"{label}[:\s#]+([A-Z0-9]{{8,14}})", up)
        if m: return m.group(1).strip()
    m = re.search(r"የግብይት\s*ቁጥር[:\s]+([A-Z0-9a-z]{8,14})", raw, re.UNICODE)
    if m: return m.group(1).strip().upper()
    
    # Strong fallback: Telebirr IDs heavily follow the 10-character D-prefix format
    m = re.search(r"\b(D[A-Z0-9]{9})\b", up)
    if m: return m.group(1).strip()
    return None

def _extract_amount_fallback(raw: str) -> str | None:
    # Used strictly as a fallback if the API fails to return the exact amount
    amounts = re.findall(r"(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", raw)
    return max(amounts, key=lambda x: len(x.replace(",", ""))) if amounts else None

# ─────────────────────────────────────────────
#  PUBLIC EXPOSED HOOKS (Imported by payment.py)
# ─────────────────────────────────────────────
async def extract_local_data(img_stream: io.BytesIO) -> dict:
    loop = asyncio.get_running_loop()

    processed_img = await loop.run_in_executor(None, _preprocess_in_memory, img_stream)
    raw = await _ocr_smart(processed_img)

    up = re.sub(r'[^A-Z0-9\n\s:\-]', ' ', raw.upper())
    provider = _detect_provider(up)
    ref = None

    if provider in ("CBE", "Abyssinia"):
        ref = _extract_cbe(up)
    elif provider in ("Telebirr", "Unknown"):
        ref = _extract_telebirr(up, raw)
        if ref: provider = "Telebirr"

    amount_fallback = _extract_amount_fallback(raw)
    return {"provider": provider, "ref": ref, "amount_fallback": amount_fallback, "raw_text": raw}

async def verify_external(reference: str, provider: str) -> dict:
    client  = get_http_client()
    payload = {"reference": reference.strip()}
    
    if provider == "CBE": 
        payload["suffix"] = CBE_SUFFIX
    elif provider == "Abyssinia":
        payload["suffix"] = ABYSSINIA_SUFFIX

    endpoints = [API_URL]
    if provider == "Telebirr":
        endpoints.append("https://verifyapi.leulzenebe.pro/verify-telebirr/")
    elif provider == "Abyssinia":
        endpoints.append("https://verifyapi.leulzenebe.pro/verify-abyssinia")

    for url in endpoints:
        try:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                
                print("\n" + "═"*50)
                print(f"🔥 [API RAW RESPONSE | {provider}] 🔥")
                print(f"REF: {reference}")
                print(f"URL: {url}")
                print(data)
                print("═"*50 + "\n")
                
                return data
        except Exception as e:
            print(f"⚠️ Network error hitting {url}: {e}")
            continue

    return {"success": False, "error": "Endpoints unverified"}


def is_hilawe_receiver(raw: str, bank_data: dict) -> bool:
    """Synced name: This is perfectly matched to the import in payment.py"""
    data = bank_data.get("data", {})
    api_name = str(
        data.get("receiver") or data.get("creditedPartyName") or data.get("credited_party_name") or ""
    ).upper()
    return "HILAWE" in raw.upper() or "HILAWE" in api_name

# ─────────────────────────────────────────────
#  TEST ROUTERS (Isolated manual verifier UI)
# ─────────────────────────────────────────────
def get_verifier_menu():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📸 Upload Screenshot", callback_data="test_upload"))
    builder.row(types.InlineKeyboardButton(text="📋 Test Batch (DB)", callback_data="test_db_random"))
    return builder.as_markup()

@router.callback_query(F.data == "test_upload")
async def start_upload_test(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 <b>Ready.</b> Please send the receipt screenshot.", parse_mode="HTML")
    await state.set_state(PaymentStates.waiting_for_screenshot)

from datetime import datetime, timezone
import re
@router.message(PaymentStates.waiting_for_screenshot, F.photo)
async def handle_screenshot_test(message: types.Message, state: FSMContext, bot: Bot):
    start_time = time.perf_counter()
    status_msg = await message.answer("🔄 <b>Analyzing receipt...</b>", parse_mode="HTML")
    
    # 1. Download & Image Extraction
    t0 = time.perf_counter()
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    img_stream = io.BytesIO()
    await bot.download_file(file.file_path, destination=img_stream)
    img_stream.seek(0)
    download_time = time.perf_counter() - t0
    
    t1 = time.perf_counter()
    local = await extract_local_data(img_stream)
    ocr_time = time.perf_counter() - t1
    
    # 2. Safety Check (Abort early if no ref found to save time)
    if not local["ref"] or len(str(local["ref"])) < 8:
        await status_msg.edit_text(
            f"🤖 <b>AUDIT FAILED</b>\n"
            f"⚠️ Could not extract valid ID.\n"
            f"⏱️ <b>Process latency:</b> {time.perf_counter() - start_time:.2f}s",
            parse_mode="HTML"
        )
        await state.clear()
        return

    # 3. API Verification
    await status_msg.edit_text(f"📡 <b>Querying:</b> <code>{local['ref']}</code>...", parse_mode="HTML")
    t2 = time.perf_counter()
    bank_data = await verify_external(local["ref"], local["provider"])
    api_time = time.perf_counter() - t2
    is_real = bank_data.get("success", False)
    
    # Log performance
    total_elapsed = time.perf_counter() - start_time
    print(f"DEBUG: Dwn:{download_time:.2f}s | OCR:{ocr_time:.2f}s | API:{api_time:.2f}s | Total:{total_elapsed:.2f}s")
    
    # 4. Data Parsing
    payer = bank_data.get("payer", "Unknown")
    receiver = bank_data.get("receiver", "N/A")
    amount = bank_data.get("amount", 0)
    
    # Integrated Time Calculation
    time_display = "(Time unknown)"
    try:
        payment_time_str = bank_data.get("date")
        if payment_time_str:
            pay_dt = datetime.fromisoformat(payment_time_str.replace("Z", "+00:00"))
            total_seconds = int((datetime.now(timezone.utc) - pay_dt).total_seconds())
            if total_seconds > 0:
                days, rem = divmod(total_seconds, 86400)
                hours, rem = divmod(rem, 3600)
                minutes, _ = divmod(rem, 60)
                if days > 0: time_display = f"({days}d {hours}h ago)"
                elif hours > 0: time_display = f"({hours}h {minutes}m ago)"
                else: time_display = f"({minutes}m ago)"
    except Exception as e:
        print(f"Time parsing error: {e}")

    # 5. Final Report Construction
    is_hilawe = is_hilawe_receiver(local["raw_text"], bank_data)
    if is_real and is_hilawe:
        report = (
            f"✅ <b>TRANSACTION VERIFIED</b>\n────────────────────\n"
            f"👤 <b>Payer:</b> <code>{payer}</code>\n"
            f"💰 <b>Amount:</b> {amount:,.2f} ETB\n"
            f"🏦 <b>Bank:</b> {local['provider']} {time_display}\n"
            f"🆔 <b>Ref ID:</b> <code>{local['ref']}</code>\n"
            f"🎯 <b>Receiver:</b> {receiver}\n\n"
            f"🟢 <b>Outcome:</b> Approved.\n⏱️ <b>Audit:</b> {total_elapsed:.2f}s"
        )
    else:
        fail_reason = "Receiver name mismatch" if is_real else "Invalid / Not found"
        report = (
            f"🚨 <b>TRANSACTION REJECTED</b>\n────────────────────\n"
            f"❌ <b>Result:</b> {fail_reason}\n"
            f"👤 <b>Payer:</b> {payer} {time_display}\n"
            f"💰 <b>Amount:</b> {amount:,.2f} ETB\n"
            f"🆔 <b>Ref ID:</b> <code>{local['ref']}</code>\n\n"
            f"⚠️ <b>Protocol:</b> Do not release.\n⏱️ <b>Audit:</b> {total_elapsed:.2f}s"
        )

    await status_msg.edit_text(report, parse_mode="HTML")
    await state.clear()
    
from datetime import datetime, timezone

def format_audit_report(local, bank_data, elapsed, is_real, is_hilawe):
    # Parsing
    data = bank_data
    payer = data.get("payer", "Unknown")
    receiver = data.get("receiver", "N/A")
    amount = data.get("amount", 0)
    
    # Time Calculation
    time_display = "(Time unknown)"
    try:
        payment_time_str = data.get("date")
        if payment_time_str:
            pay_dt = datetime.fromisoformat(payment_time_str.replace("Z", "+00:00"))
            total_minutes = int((datetime.now(timezone.utc) - pay_dt).total_seconds() / 60)
            
            # Logic: Convert total minutes into readable format
            if total_minutes < 60:
                time_display = f"({total_minutes}m ago)"
            elif total_minutes < 1440: # Less than 24 hours
                hours = total_minutes // 60
                mins = total_minutes % 60
                time_display = f"({hours}h {mins}m ago)"
            else: # 24 hours or more
                days = total_minutes // 1440
                time_display = f"({days}d ago)"
    except Exception as e:
        print(f"Time parsing error: {e}")
    # Construct
    if is_real and is_hilawe:
        return (
            f"✅ <b>TRANSACTION VERIFIED</b>\n"
            f"────────────────────\n"
            f"👤 <b>Payer:</b> <code>{payer}</code>\n"
            f"💰 <b>Amount:</b> {amount:,.2f} ETB\n"
            f"🏦 <b>Bank:</b> {local['provider']} {time_display}\n"
            f"🆔 <b>Ref ID:</b> <code>{local['ref']}</code>\n"
            f"🎯 <b>Receiver:</b> {receiver}\n\n"
            f"🟢 <b>Outcome:</b> Approved.\n"
            f"⏱️ <b>Audit duration:</b> {elapsed:.2f}s"
        )
    else:
        fail_reason = "Receiver name mismatch" if is_real else "Invalid / Not found"
        return (
            f"🚨 <b>TRANSACTION REJECTED</b>\n"
            f"────────────────────\n"
            f"❌ <b>Result:</b> {fail_reason}\n"
            f"👤 <b>Payer:</b> {payer} {time_display}\n"
            f"💰 <b>Amount:</b> {amount:,.2f} ETB\n"
            f"🆔 <b>Ref ID:</b> <code>{local['ref']}</code>\n\n"
            f"⚠️ <b>Protocol:</b> Do not release products.\n"
            f"⏱️ <b>Audit duration:</b> {elapsed:.2f}s"
        )
        
@router.callback_query(F.data == "test_db_random")
async def test_batch_from_db(callback: types.CallbackQuery, bot: Bot, db):
    status_msg = await callback.message.answer("🔍 <b>Auditing recent payments...</b>", parse_mode="HTML")
    recent = await db.get_recent_payment_proofs(5)
    
    if not recent:
        return await status_msg.edit_text("❌ No recent payments found.")

    async def process_one(rec):
        start_time = time.perf_counter()
        t0 = time.perf_counter()
        file = await bot.get_file(rec["proof_file_id"])
        await bot.download_file(file.file_path, destination=img_stream)
        print(f"DEBUG: Download took {time.perf_counter() - t0:.2f}s")
        
        # Measure OCR
        t1 = time.perf_counter()
        local = await extract_local_data(img_stream)
        print(f"DEBUG: OCR took {time.perf_counter() - t1:.2f}s")
        
        # Measure API
        t2 = time.perf_counter()
        bank_data = await verify_external(local["ref"], local["provider"])
        print(f"DEBUG: API Call took {time.perf_counter() - t2:.2f}s")
        try:
            file = await bot.get_file(rec["proof_file_id"])
            img_stream = io.BytesIO()
            await bot.download_file(file.file_path, destination=img_stream)
            img_stream.seek(0)

            local = await extract_local_data(img_stream)
            bank_data = {}
            is_real = False

            if local["ref"]:
                bank_data = await verify_external(local["ref"], local["provider"])
                is_real = bank_data.get("success", False)

            is_hilawe = is_hilawe_receiver(local["raw_text"], bank_data)
            
            api_amount = bank_data.get("data", {}).get("amount")
            display_amount = f"{float(api_amount):,.2f}" if api_amount else (local['amount_fallback'] or "?")

            elapsed = time.perf_counter() - start_time

            if is_real and is_hilawe:
                caption = (
                    f"🤖 <b>API MATCH: SECURE & VALID ✅</b>\n"
                    f"────────────────────\n"
                    f"🟢 <b>Audit #{rec['id']}</b> • 100% authentic ledger match.\n\n"
                    f"📊 <b>{local['provider']}</b> • 🆔 <code>{local['ref']}</code> • 💰 <b>{display_amount} ETB</b>\n"
                    f"⏱️ <b>Speed:</b> {elapsed:.2f}s"
                )
            else:
                caption = (
                    f"🤖 <b>API MATCH: REJECTED / FAKE ALERT 🚨</b>\n"
                    f"────────────────────\n"
                    f"🔴 <b>Audit #{rec['id']}</b> • Fraud guard triggered. No bank match.\n\n"
                    f"📊 <b>{local['provider']}</b> • 🆔 <code>{local['ref'] or 'N/A'}</code> • 💰 <b>{display_amount} ETB</b>\n"
                    f"⏱️ <b>Speed:</b> {elapsed:.2f}s"
                )

            await bot.send_photo(
                chat_id=callback.from_user.id,
                photo=rec["proof_file_id"],
                caption=caption,
                parse_mode="HTML",
            )
        except Exception as e:
            await callback.message.answer(f"⚠️ <b>Error on #{rec['id']}:</b> <code>{e}</code>", parse_mode="HTML")

    await asyncio.gather(*[process_one(r) for r in recent])
    await status_msg.delete()