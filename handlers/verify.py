#verify.py — OCR.space Edition
#Target: < 4 seconds per transaction

#Architecture:
# 1. API Authority:   Verify API is the source of truth for amounts/names.
# 2. OCR.space API:  REST-based, multi-part form data. Engine 2 enabled for optimal receipt parsing.
# 3. Memory Guard:    Downscales large screenshots before sending to OCR.space (speed + payload limit).
# 4. Dual HTTP Clients: Separate persistent clients for OCR.space API vs Verify API — no timeout bleed.
# 5. Graceful Fallback: Detailed error logging; empty string on OCR failure so flow continues.

#Env vars required:
# VERIFY_API_KEY   — your leulzenebe verify API key
# OCR_SPACE_API_KEY — your free API key from ocr.space
#"""

import io
import asyncio
import base64
import re
import time
from datetime import datetime, timezone

import httpx
from PIL import Image, ImageEnhance
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import settings


# ─────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────
VERIFY_API_KEY    = settings.VERIFY_API_KEY
VERIFY_URL        = "https://verifyapi.leulzenebe.pro/verify"
VERIFY_URL_TB     = "https://verifyapi.leulzenebe.pro/verify-telebirr/"
CBE_SUFFIX        = "99533641"

OCR_SPACE_API_KEY = getattr(settings, "OCR_SPACE_API_KEY", "helloworld")  # Fallback to public demo key if unconfigured
OCR_SPACE_URL     = "https://api.ocr.space/parse/image"

router = Router(name="verify")


# ─────────────────────────────────────────────
#  PERSISTENT HTTP CLIENTS  (two separate pools)
# ─────────────────────────────────────────────
_verify_client: httpx.AsyncClient | None = None
_ocr_client: httpx.AsyncClient | None = None


def get_verify_client() -> httpx.AsyncClient:
    """Persistent client for the Leulzenebe verify API — 10s timeout per attempt."""
    global _verify_client
    if _verify_client is None or _verify_client.is_closed:
        _verify_client = httpx.AsyncClient(
            # Changed read timeout to 10.0s for slow bank responses
            timeout=httpx.Timeout(connect=3.0, read=10.0, write=3.0, pool=1.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
            headers={
                "x-api-key": VERIFY_API_KEY,
                "Content-Type": "application/json",
            },
        )
    return _verify_client


def get_ocr_client() -> httpx.AsyncClient:
    """Persistent client for OCR.space REST — tuned read timeout for image processing."""
    global _ocr_client
    if _ocr_client is None or _ocr_client.is_closed:
        _ocr_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _ocr_client


# ─────────────────────────────────────────────
#  FSM STATES
# ─────────────────────────────────────────────
class PaymentStates(StatesGroup):
    waiting_for_screenshot = State()


# ─────────────────────────────────────────────
#  IMAGE PREPROCESSING
# ─────────────────────────────────────────────
def _preprocess_for_ocr(img_stream: io.BytesIO) -> bytes:
    """
    Lightweight preprocessing before sending to OCR.space.

    - Downscale oversized screenshots (cost guard, payload limit)
    - Upscale tiny screenshots (OCR struggles below ~600px wide)
    - Apply a mild contrast boost for washed-out Telebirr receipts
    - Re-encode as high-quality JPEG for the API payload
    """
    img = Image.open(img_stream).convert("RGB")
    w, h = img.size

    if w > 1400:
        ratio = 1400 / w
        img = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
    elif w < 600:
        ratio = 600 / w
        img = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.BICUBIC)

    img = ImageEnhance.Contrast(img).enhance(1.4)

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90)
    return out.getvalue()


# ─────────────────────────────────────────────
#  OCR.SPACE API OCR
# ─────────────────────────────────────────────
async def _ocr_space(image_bytes: bytes) -> str:
    """
    Sends image bytes to OCR.space API via multipart POST.
    Returns the full extracted text string, or empty string on any failure.
    """
    payload = {
    "apikey": OCR_SPACE_API_KEY,
    "language": "eng",
    "isOverlayRequired": "false",
    "OCREngine": "2",
    "scale": "false",  # Changed to false — PIL already handles resizing locally!
}
    files = {
        "file": ("receipt.jpg", image_bytes, "image/jpeg")
    }

    try:
        client = get_ocr_client()
        resp   = await client.post(OCR_SPACE_URL, data=payload, files=files)
        data   = resp.json()

        if data.get("IsErroredOnProcessing", False):
            print(f"⚠️ OCR.space API processing error: {data.get('ErrorMessage')}")
            return ""

        parsed_results = data.get("ParsedResults", [])
        if not parsed_results:
            return ""

        return parsed_results[0].get("ParsedText", "")

    except httpx.ReadTimeout:
        print("⚠️ OCR.space ReadTimeout — image may be too large or network is slow")
        return ""
    except Exception as e:
        print(f"⚠️ OCR.space error: {type(e).__name__}: {e}")
        return ""


# ─────────────────────────────────────────────
#  PROVIDER DETECTION
# ─────────────────────────────────────────────
def _detect_provider(up: str) -> str:
    if any(k in up for k in ("COMMERCIAL BANK", "CBE", "BRECIEPT", "FT2")):
        return "CBE"
    if any(k in up for k in ("TELEBIRR", "ETHIO TELECOM", "TELE BIRR")) or re.search(r"\b(D[A-Z0-9]{9})\b", up):
        return "Telebirr"
    if "AWASH" in up:
        return "Awash"
    return "Unknown"


# ─────────────────────────────────────────────
#  REFERENCE ID EXTRACTION
# ─────────────────────────────────────────────
def _extract_cbe(up: str) -> str | None:
    m = re.search(r"F\s*T\s*([A-Z0-9]{8,12})", up)
    if m: return ("FT" + m.group(1)).replace(" ", "")
    m = re.search(r"(?:ID|TRANSACTION\s*ID)[:\s]+([A-Z0-9]{10,14})", up)
    if m: return m.group(1).strip()
    m = re.search(r"\b(FT[A-Z0-9]{8,12})\b", up)
    return m.group(1) if m else None


def _extract_telebirr(up: str, raw: str) -> str | None:
    for label in (
        "TRANSACTION NUMBER", "TRANSACTION NO", "INVOICE NO",
        "INVOICE NUMBER", "REF NO", "REFERENCE NO", "NUMBER",
    ):
        m = re.search(rf"{label}[:\s#]+([A-Z0-9]{{8,14}})", up)
        if m: return m.group(1).strip()

    # Amharic label — OCR Engine reads Ethiopic script reliably
    m = re.search(r"የግብይት\s*ቁጥር[:\s]+([A-Z0-9a-z]{8,14})", raw, re.UNICODE)
    if m: return m.group(1).strip().upper()

    # D-prefix fallback: Telebirr IDs are consistently D + 9 alphanumeric chars
    m = re.search(r"\b(D[A-Z0-9]{9})\b", up)
    if m: return m.group(1).strip()
    return None


def _extract_amount_fallback(raw: str) -> str | None:
    """Last-resort amount extraction from raw OCR text if Verify API returns nothing."""
    amounts = re.findall(r"(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", raw)
    return max(amounts, key=lambda x: len(x.replace(",", ""))) if amounts else None


# ─────────────────────────────────────────────
#  PUBLIC HOOKS  (imported by payment.py)
# ─────────────────────────────────────────────
async def extract_local_data(img_stream: io.BytesIO) -> dict:
    """
    Full OCR pipeline: preprocess → OCR.space → extract provider/ref/amount.
    Returns the exact same dict shape as the original version — payment.py unchanged.
    """
    loop = asyncio.get_running_loop()

    # PIL preprocessing is CPU-bound — run in thread pool
    image_bytes = await loop.run_in_executor(None, _preprocess_for_ocr, img_stream)

    # OCR.space OCR — async REST call
    raw = await _ocr_space(image_bytes)

    # Sanitize: strip non-alphanumeric for regex safety, keep Ethiopic in `raw`
    up       = re.sub(r'[^A-Z0-9\n\s:\-]', ' ', raw.upper())
    provider = _detect_provider(up)
    ref      = None

    if provider == "CBE":
        ref = _extract_cbe(up)
    elif provider in ("Telebirr", "Unknown"):
        ref = _extract_telebirr(up, raw)
        if ref:
            provider = "Telebirr"

    return {
        "provider":        provider,
        "ref":             ref,
        "amount_fallback": _extract_amount_fallback(raw),
        "raw_text":        raw,
    }
async def verify_external(reference: str, provider: str, max_attempts: int = 3) -> dict:
    """Hits the Leulzenebe verify API with retries (up to 30s total budget)."""
    client  = get_verify_client()
    payload = {"reference": reference.strip()}
    if provider == "CBE":
        payload["suffix"] = CBE_SUFFIX

    endpoints = [VERIFY_URL]
    if provider == "Telebirr":
        endpoints.append(VERIFY_URL_TB)

    for attempt in range(1, max_attempts + 1):
        for url in endpoints:
            try:
                print(f"🔄 [VERIFY ATTEMPT {attempt}/{max_attempts}] Requesting {url}...")
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        print(f"🔥 [VERIFY API MATCH] REF: {reference}")
                        return data
            except httpx.ReadTimeout:
                print(f"⚠️ [Attempt {attempt}] ReadTimeout (10s) on {url}")
            except Exception as e:
                print(f"⚠️ [Attempt {attempt}] Error on {url}: {type(e).__name__}: {e}")

        # Pause 1 second before retrying if attempts remain
        if attempt < max_attempts:
            await asyncio.sleep(1.0)

    return {"success": False, "error": "Bank verification server timed out after 30 seconds."}

def is_hilawe_receiver(raw: str, bank_data: dict) -> bool:
    """Checks OCR text and API response for Hilawe as the credited receiver."""
    data     = bank_data.get("data", {})
    api_name = str(
        data.get("receiver") or
        data.get("creditedPartyName") or
        data.get("credited_party_name") or ""
    ).upper()
    return "HILAWE" in raw.upper() or "HILAWE" in api_name


# ─────────────────────────────────────────────
#  TIME FORMATTER  (shared utility)
# ─────────────────────────────────────────────
def _format_time_ago(date_str: str | None) -> str:
    if not date_str:
        return "(Time unknown)"
    try:
        pay_dt        = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        total_seconds = int((datetime.now(timezone.utc) - pay_dt).total_seconds())
        if total_seconds <= 0:
            return "(just now)"
        days, rem  = divmod(total_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        if days > 0:  return f"({days}d {hours}h ago)"
        if hours > 0: return f"({hours}h {minutes}m ago)"
        return f"({minutes}m ago)"
    except Exception as e:
        print(f"⚠️ Time parsing error: {e}")
        return "(Time unknown)"


# ─────────────────────────────────────────────
#  REPORT FORMATTER
# ─────────────────────────────────────────────
def format_audit_report(
    local: dict,
    bank_data: dict,
    elapsed: float,
    is_real: bool,
    is_hilawe: bool,
) -> str:
    payer        = bank_data.get("payer", "Unknown")
    receiver     = bank_data.get("receiver", "N/A")
    amount       = bank_data.get("amount", 0)
    time_display = _format_time_ago(bank_data.get("date"))

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


# ─────────────────────────────────────────────
#  TEST ROUTER — manual verifier UI
# ─────────────────────────────────────────────
def get_verifier_menu():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📸 Upload Screenshot", callback_data="test_upload"))
    builder.row(types.InlineKeyboardButton(text="📋 Test Batch (DB)",   callback_data="test_db_random"))
    return builder.as_markup()


@router.callback_query(F.data == "test_upload")
async def start_upload_test(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📝 <b>Ready.</b> Send the receipt screenshot now.",
        parse_mode="HTML",
    )
    await state.set_state(PaymentStates.waiting_for_screenshot)


@router.message(PaymentStates.waiting_for_screenshot, F.photo)
async def handle_screenshot_test(message: types.Message, state: FSMContext, bot: Bot):
    start_time = time.perf_counter()
    status_msg = await message.answer("🔄 <b>Analyzing receipt...</b>", parse_mode="HTML")

    # ── 1. Download ────────────────────────────────────────────────────────────
    t0         = time.perf_counter()
    photo = message.photo[-2] if len(message.photo) > 1 else message.photo[-1]
    file       = await bot.get_file(photo.file_id)
    img_stream = io.BytesIO()
    await bot.download_file(file.file_path, destination=img_stream)
    img_stream.seek(0)
    t_download = time.perf_counter() - t0

    # ── 2. OCR ─────────────────────────────────────────────────────────────────
    t1    = time.perf_counter()
    local = await extract_local_data(img_stream)
    t_ocr = time.perf_counter() - t1

    # ── 3. Abort if no ref extracted ───────────────────────────────────────────
    if not local["ref"] or len(str(local["ref"])) < 8:
        await status_msg.edit_text(
            f"🤖 <b>AUDIT FAILED</b>\n"
            f"────────────────────\n"
            f"⚠️ Could not extract a valid transaction ID.\n\n"
            f"<b>Raw OCR preview:</b>\n<code>{local['raw_text'][:400]}</code>\n\n"
            f"⏱️ <b>Elapsed:</b> {time.perf_counter() - start_time:.2f}s",
            parse_mode="HTML",
        )
        await state.clear()
        return

    # ── 4. Verify ──────────────────────────────────────────────────────────────
    await status_msg.edit_text(
        f"📡 <b>Querying bank ledger:</b> <code>{local['ref']}</code>...\n"
        f"<i>Connecting to {local['provider']} (may take up to 30s)...</i>",
        parse_mode="HTML",
    )
    t2        = time.perf_counter()
    bank_data = await verify_external(local["ref"], local["provider"])
    t_api     = time.perf_counter() - t2
    is_real   = bank_data.get("success", False)
    

    # Handle Server / Bank Timeout specifically
    if bank_data.get("error") and "timed out" in bank_data.get("error", "").lower():
        await status_msg.edit_text(
            f"⏳ <b>BANK NETWORK DELAY</b>\n"
            f"────────────────────\n"
            f"🆔 <b>Ref ID Extracted:</b> <code>{local['ref']}</code>\n"
            f"🏦 <b>Provider:</b> {local['provider']}\n\n"
            f"⚠️ The bank verification server is taking too long to respond.\n"
            f"Please tap <b>Upload Screenshot</b> to try again in a few seconds.",
            parse_mode="HTML",
        )
        await state.clear()
        return

    total = time.perf_counter() - start_time
    print(f"⏱️  Dwn:{t_download:.2f}s | OCR:{t_ocr:.2f}s | API:{t_api:.2f}s | Total:{total:.2f}s")

    # ── 5. Report ──────────────────────────────────────────────────────────────
    is_hilawe = is_hilawe_receiver(local["raw_text"], bank_data)
    report    = format_audit_report(local, bank_data, total, is_real, is_hilawe)
    await status_msg.edit_text(report, parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "test_db_random")
async def test_batch_from_db(callback: types.CallbackQuery, bot: Bot, db):
    status_msg = await callback.message.answer(
        "🔍 <b>Auditing recent payments...</b>",
        parse_mode="HTML",
    )
    recent = await db.get_recent_payment_proofs(5)

    if not recent:
        return await status_msg.edit_text("❌ No recent payments found.")

    async def process_one(rec):
        start_time = time.perf_counter()
        try:
            img_stream = io.BytesIO()
            file       = await bot.get_file(rec["proof_file_id"])
            await bot.download_file(file.file_path, destination=img_stream)
            img_stream.seek(0)

            local     = await extract_local_data(img_stream)
            bank_data = {}
            is_real   = False

            if local["ref"]:
                bank_data = await verify_external(local["ref"], local["provider"])
                is_real   = bank_data.get("success", False)

            is_hilawe      = is_hilawe_receiver(local["raw_text"], bank_data)
            api_amount     = bank_data.get("data", {}).get("amount")
            display_amount = f"{float(api_amount):,.2f}" if api_amount else (local["amount_fallback"] or "?")
            elapsed        = time.perf_counter() - start_time

            if is_real and is_hilawe:
                caption = (
                    f"🤖 <b>API MATCH: SECURE & VALID ✅</b>\n"
                    f"────────────────────\n"
                    f"🟢 <b>Audit #{rec['id']}</b> — 100% authentic ledger match.\n\n"
                    f"📊 <b>{local['provider']}</b> · "
                    f"🆔 <code>{local['ref']}</code> · "
                    f"💰 <b>{display_amount} ETB</b>\n"
                    f"⏱️ <b>Speed:</b> {elapsed:.2f}s"
                )
            else:
                caption = (
                    f"🤖 <b>API MATCH: REJECTED 🚨</b>\n"
                    f"────────────────────\n"
                    f"🔴 <b>Audit #{rec['id']}</b> — Fraud guard triggered. No bank match.\n\n"
                    f"📊 <b>{local['provider']}</b> · "
                    f"🆔 <code>{local['ref'] or 'N/A'}</code> · "
                    f"💰 <b>{display_amount} ETB</b>\n"
                    f"⏱️ <b>Speed:</b> {elapsed:.2f}s"
                )

            await bot.send_photo(
                chat_id=callback.from_user.id,
                photo=rec["proof_file_id"],
                caption=caption,
                parse_mode="HTML",
            )
        except Exception as e:
            await callback.message.answer(
                f"⚠️ <b>Error on #{rec['id']}:</b> <code>{e}</code>",
                parse_mode="HTML",
            )

    await asyncio.gather(*[process_one(r) for r in recent])
    await status_msg.delete()