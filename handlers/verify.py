"""
verify.py  —  Render-Optimized Edition (Character-Healed)
Target: < 3 seconds per transaction
"""

import os
import io
import asyncio
import re
import platform
import shutil
import time
from datetime import datetime, timezone

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
ABYSSINIA_SUFFIX = "53299555"

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
    img = enhancer.enhance(2.5)  # Slightly bumped to sharpen text boundaries

    # Vectorized fast thresholding
    img_array = np.array(img)
    threshold = np.mean(img_array) * 0.92
    binary_matrix = np.where(img_array > threshold, 255, 0).astype(np.uint8)
    
    return Image.fromarray(binary_matrix)

# ─────────────────────────────────────────────
#  SMART FAILOVER OCR WITH ENGINE WHITELISTING
# ─────────────────────────────────────────────
def _run_tesseract(img: Image.Image, psm: int) -> str:
    # Restrict character choices at runtime to completely block lowercase letters/garbage characters
    tess_config = f"--oem 3 --psm {psm} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:-/ "
    return pytesseract.image_to_string(img, config=tess_config)

async def _ocr_smart(img: Image.Image) -> str:
    loop = asyncio.get_running_loop()
    text = await loop.run_in_executor(None, _run_tesseract, img, 6)
    
    # Failover condition: Look for either a CBE ID or a 10-character Telebirr ID
    if not re.search(r"[A-Z0-9]{8,}", text):
        fallback_text = await loop.run_in_executor(None, _run_tesseract, img, 4)
        text = f"{text}\n{fallback_text}"
        
    return text

# ─────────────────────────────────────────────
#  ALGORITHMIC CHARACTER HEALING LAYER
# ─────────────────────────────────────────────
def _heal_transaction_string(ref_id: str | None) -> str | None:
    """
    Corrects structural OCR degradation. Swaps alphabetic confusion traps
    (O, I, L) into secure numeric values (0, 1) based on Ethiopian bank transaction structures.
    """
    if not ref_id:
        return None
    
    ref_id = ref_id.strip().upper()
    
    # Vector 1: Telebirr ID Healing (Format: D followed by 9 alphanumeric characters)
    if ref_id.startswith("D") and len(ref_id) == 10:
        body = ref_id[1:]
        body = body.replace("O", "0").replace("I", "1").replace("L", "1")
        return "D" + body
        
    # Vector 2: CBE ID Healing (Format: FT followed by alphanumeric sequence)
    if ref_id.startswith("FT"):
        body = ref_id[2:]
        body = body.replace("O", "0").replace("I", "1").replace("L", "1")
        return "FT" + body

    # Vector 3: Global fallback replacement for other providers
    # Safely swap inner elements while retaining potential alphabetic tracking markers
    return ref_id.replace("O", "0").replace("I", "1").replace("L", "1")

# ─────────────────────────────────────────────
#  EXTRACTION LOGIC
# ─────────────────────────────────────────────
def _detect_provider(up: str) -> str:
    if any(k in up for k in ("ABYSSINIA", "BOA")):
        return "Abyssinia"
    if any(k in up for k in ("COMMERCIAL BANK", "CBE", "BRECIEPT", "FT2")):
        return "CBE"
    if any(k in up for k in ("TELEBIRR", "ETHIO TELECOM", "TELE BIRR")) or re.search(r"\b(D[A-Z0-9]{9})\b", up):
        return "Telebirr"
    if "AWASH" in up:
        return "Awash"
    return "Unknown"

def _extract_cbe(up: str) -> str | None:
    m = re.search(r"F\s*T\s*([A-Z0-9]{8,12})", up)
    if m: return _heal_transaction_string(("FT" + m.group(1)).replace(" ", ""))
    m = re.search(r"(?:ID|TRANSACTION\s*ID)[:\s]+([A-Z0-9]{10,14})", up)
    if m: return _heal_transaction_string(m.group(1))
    m = re.search(r"\b(FT[A-Z0-9]{8,12})\b", up)
    return _heal_transaction_string(m.group(1)) if m else None

def _extract_telebirr(up: str, raw: str) -> str | None:
    for label in ("TRANSACTION NUMBER", "TRANSACTION NO", "INVOICE NO", "INVOICE NUMBER", "REF NO", "REFERENCE NO", "NUMBER"):
        m = re.search(rf"{label}[:\s#]+([A-Z0-9]{{8,14}})", up)
        if m: return _heal_transaction_string(m.group(1))
    m = re.search(r"የግብይት\s*ቁጥር[:\s]+([A-Z0-9a-z]{8,14})", raw, re.UNICODE)
    if m: return _heal_transaction_string(m.group(1))
    
    # Strong fallback: Telebirr IDs follow the 10-character D-prefix format
    m = re.search(r"\b(D[A-Z0-9]{9})\b", up)
    if m: return _heal_transaction_string(m.group(1))
    return None

def _extract_amount_fallback(raw: str) -> str | None:
    amounts = re.findall(r"(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", raw)
    return max(amounts, key=lambda x: len(x.replace(",", ""))) if amounts else None

# ─────────────────────────────────────────────
#  PUBLIC EXPOSED HOOKS
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

    # Double-check array initialization for fuzzy variation retry
    variants = [reference.strip()]
    
    # If structural cleaning missed an option, prepare a soft variant list to run across hot pools
    inverted = reference.strip()
    if "0" in inverted or "1" in inverted:
        # Create a reverse mutation lookup just in case the API ledger contains anomalous data
        pass

    for url in endpoints:
        for ref_variant in variants:
            payload["reference"] = ref_variant
            try:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    print("\n" + "═"*50)
                    print(f"🔥 [API RAW RESPONSE | {provider}] 🔥")
                    print(f"REF: {ref_variant}")
                    print(f"URL: {url}")
                    print(data)
                    print("═"*50 + "\n")
                    return data
            except Exception as e:
                print(f"⚠️ Network error hitting {url} with ref {ref_variant}: {e}")
                continue

    return {"success": False, "error": "Endpoints unverified"}

def is_hilawe_receiver(raw: str, bank_data: dict) -> bool:
    """
    Bulletproof receiver validation checking both local OCR raw text 
    and structure-agnostic API responses (root level & nested payload).
    """
    if not bank_data:
        bank_data = {}

    # 1. Check local OCR text first
    if "HILAWE" in raw.upper():
        return True

    # 2. Extract values from the API root level
    root_receiver = (
        bank_data.get("receiver") or 
        bank_data.get("creditedPartyName") or 
        bank_data.get("credited_party_name") or 
        ""
    )

    # 3. Extract values from the nested 'data' payload (safeguard for varied endpoints)
    nested = bank_data.get("data") or {}
    nested_receiver = (
        nested.get("receiver") or 
        nested.get("creditedPartyName") or 
        nested.get("credited_party_name") or 
        ""
    )

    # 4. Consolidate and evaluate
    api_combined_names = f"{root_receiver} {nested_receiver}".upper()
    
    print(f"DEBUG [Receiver Audit]: Root='{root_receiver}' | Nested='{nested_receiver}'")
    return "HILAWE" in api_combined_names
# ─────────────────────────────────────────────
#  TEST ROUTERS
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

@router.message(PaymentStates.waiting_for_screenshot, F.photo)
async def handle_screenshot_test(message: types.Message, state: FSMContext, bot: Bot):
    start_time = time.perf_counter()
    status_msg = await message.answer("🔄 <b>Analyzing receipt...</b>", parse_mode="HTML")
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    img_stream = io.BytesIO()
    await bot.download_file(file.file_path, destination=img_stream)
    img_stream.seek(0)
    
    local = await extract_local_data(img_stream)
    
    if not local["ref"] or len(str(local["ref"])) < 8:
        await status_msg.edit_text(
            f"🤖 <b>AUDIT FAILED</b>\n⚠️ Could not extract valid ID.\n⏱️ <b>Process latency:</b> {time.perf_counter() - start_time:.2f}s",
            parse_mode="HTML"
        )
        await state.clear()
        return

    await status_msg.edit_text(f"📡 <b>Querying:</b> <code>{local['ref']}</code>...", parse_mode="HTML")
    bank_data = await verify_external(local["ref"], local["provider"])
    is_real = bank_data.get("success", False)
    total_elapsed = time.perf_counter() - start_time
    
    payer = bank_data.get("payer", "Unknown")
    receiver = bank_data.get("receiver", "N/A")
    amount = bank_data.get("amount", 0)
    
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

    is_hilawe = is_hilawe_receiver(local["raw_text"], bank_data)
    print('here is the name ', is_hilawe)
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

def format_audit_report(local, bank_data, elapsed, is_real, is_hilawe):
    payer = bank_data.get("payer", "Unknown")
    receiver = bank_data.get("receiver", "N/A")
    amount = bank_data.get("amount", 0)
    
    time_display = "(Time unknown)"
    try:
        payment_time_str = bank_data.get("date")
        if payment_time_str:
            pay_dt = datetime.fromisoformat(payment_time_str.replace("Z", "+00:00"))
            total_minutes = int((datetime.now(timezone.utc) - pay_dt).total_seconds() / 60)
            if total_minutes < 60:
                time_display = f"({total_minutes}m ago)"
            elif total_minutes < 1440:
                hours = total_minutes // 60
                mins = total_minutes % 60
                time_display = f"({hours}h {mins}m ago)"
            else:
                days = total_minutes // 1440
                time_display = f"({days}d ago)"
    except Exception as e:
        print(f"Time parsing error: {e}")

    if is_real and is_hilawe:
        return (
            f"✅ <b>TRANSACTION VERIFIED</b>\n────────────────────\n"
            f"👤 <b>Payer:</b> <code>{payer}</code>\n"
            f"💰 <b>Amount:</b> {amount:,.2f} ETB\n"
            f"🏦 <b>Bank:</b> {local['provider']} {time_display}\n"
            f"🆔 <b>Ref ID:</b> <code>{local['ref']}</code>\n"
            f"🎯 <b>Receiver:</b> {receiver}\n\n"
            f"🟢 <b>Outcome:</b> Approved.\n⏱️ <b>Audit duration:</b> {elapsed:.2f}s"
        )
    else:
        fail_reason = "Receiver name mismatch" if is_real else "Invalid / Not found"
        return (
            f"🚨 <b>TRANSACTION REJECTED</b>\n────────────────────\n"
            f"❌ <b>Result:</b> {fail_reason}\n"
            f"👤 <b>Payer:</b> {payer} {time_display}\n"
            f"💰 <b>Amount:</b> {amount:,.2f} ETB\n"
            f"🆔 <b>Ref ID:</b> <code>{local['ref']}</code>\n\n"
            f"⚠️ <b>Protocol:</b> Do not release products.\n⏱️ <b>Audit duration:</b> {elapsed:.2f}s"
        )

@router.callback_query(F.data == "test_db_random")
async def test_batch_from_db(callback: types.CallbackQuery, bot: Bot, db):
    status_msg = await callback.message.answer("🔍 <b>Auditing recent payments...</b>", parse_mode="HTML")
    recent = await db.get_recent_payment_proofs(5)
    
    if not recent:
        return await status_msg.edit_text("❌ No recent payments found.")

    async def process_one(rec):
        try:
            start_time = time.perf_counter()
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
                    f"🤖 <b>API MATCH: SECURE & VALID ✅</b>\n────────────────────\n"
                    f"🟢 <b>Audit #{rec['id']}</b> • 100% authentic ledger match.\n\n"
                    f"📊 <b>{local['provider']}</b> • 🆔 <code>{local['ref']}</code> • 💰 <b>{display_amount} ETB</b>\n"
                    f"⏱️ <b>Speed:</b> {elapsed:.2f}s"
                )
            else:
                caption = (
                    f"🤖 <b>API MATCH: REJECTED / FAKE ALERT 🚨</b>\n────────────────────\n"
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