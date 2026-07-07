"""
verify.py — Accuracy-First Edition
Rebuilt OCR pipeline specifically tuned for CBE mobile app receipts.
Key fixes:
  - Tighter ID boundary detection (stops at period/space/newline after ID)
  - 4↔A added to confusable groups (major source of CBE ID corruption)
  - Multi-region cropping: extracts text from the message block only,
    avoiding QR code noise bleeding into OCR output
  - Anchor-based extraction: finds "transaction ID:" label then grabs
    exactly what follows, instead of scanning the whole page
"""

import os
import io
import asyncio
import re
import platform
import shutil
import time
from datetime import datetime, timezone
from itertools import product as itertools_product

import numpy as np
import httpx
from PIL import Image, ImageEnhance, ImageFilter
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
#  CONFIG
# ─────────────────────────────────────────────
API_KEY          = settings.VERIFY_API_KEY
API_URL          = "https://verifyapi.leulzenebe.pro/verify"
CBE_SUFFIX       = "99533641"
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
#  IMAGE PREPROCESSING
# ─────────────────────────────────────────────
def _preprocess_variants(img_stream: io.BytesIO) -> list[Image.Image]:
    """
    Returns multiple preprocessed variants of the image.
    CBE receipts are white-background text on a light gray card — 
    high contrast binarization works well. We also produce a gentler
    variant for receipts that have already-high contrast text.
    """
    img_stream.seek(0)
    base = Image.open(img_stream).convert("L")
    w, h = base.size

    # Upscale small images, downscale huge ones
    if w > 1800:
        ratio = 1800 / w
        base = base.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
    elif w < 900:
        base = base.resize((w * 2, h * 2), Image.Resampling.BICUBIC)

    # Sharpen before thresholding
    sharpened = base.filter(ImageFilter.UnsharpMask(radius=1.5, percent=180, threshold=2))

    variants = []

    # Variant 1: Standard contrast — works for clean CBE app screenshots
    v1 = ImageEnhance.Contrast(sharpened).enhance(2.0)
    arr1 = np.array(v1)
    thresh1 = np.percentile(arr1, 55)  # adaptive threshold
    bin1 = np.where(arr1 > thresh1, 255, 0).astype(np.uint8)
    variants.append(Image.fromarray(bin1))

    # Variant 2: Aggressive contrast — for camera photos or dark-mode
    v2 = ImageEnhance.Contrast(sharpened).enhance(3.5)
    arr2 = np.array(v2)
    thresh2 = np.percentile(arr2, 45)
    bin2 = np.where(arr2 > thresh2, 255, 0).astype(np.uint8)
    variants.append(Image.fromarray(bin2))

    # Variant 3: Inverted aggressive — handles dark-background receipts
    inv = Image.fromarray(255 - bin2)
    variants.append(inv)

    return variants


def _crop_text_region(img_stream: io.BytesIO) -> Image.Image | None:
    """
    CBE receipts have a consistent layout: the transaction text block
    sits in the upper ~60% of the image. Cropping out the QR code at
    the bottom removes noise that can corrupt the ID extraction.
    """
    try:
        img_stream.seek(0)
        img = Image.open(img_stream).convert("L")
        w, h = img.size
        # Keep top 65% — this captures the full message text and excludes
        # the QR code which Tesseract sometimes misreads as alphanumerics
        cropped = img.crop((0, 0, w, int(h * 0.65)))
        return cropped
    except Exception:
        return None


# ─────────────────────────────────────────────
#  OCR ENGINE
# ─────────────────────────────────────────────
_TESS_CONFIG_TIGHT = "--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:- "
_TESS_CONFIG_BLOCK = "--oem 3 --psm 4 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:- "
_TESS_CONFIG_SPARSE = "--oem 3 --psm 11 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:- "

# Structural match — real CBE ID immediately after "transaction ID:" label
_STRICT_ID_RE = re.compile(r"\bFT[A-Z0-9]{8,12}\b|\bD[A-Z0-9]{9}\b")


def _run_tesseract(img: Image.Image, config: str) -> str:
    return pytesseract.image_to_string(img, config=config)


async def _ocr_smart(images: list[Image.Image], cropped: Image.Image | None) -> str:
    """
    Runs OCR in escalating passes. Prioritizes the cropped text region
    (no QR noise) before falling back to the full image variants.
    Stops as soon as a structurally-confident CBE/Telebirr ID is found.
    """
    loop = asyncio.get_running_loop()
    collected: list[str] = []

    passes = []

    # Highest priority: cropped text region (no QR code noise)
    if cropped is not None:
        # Preprocess the crop the same way
        arr = np.array(cropped)
        thresh = np.percentile(arr, 55)
        binary_crop = Image.fromarray(np.where(arr > thresh, 255, 0).astype(np.uint8))
        passes.append((binary_crop, _TESS_CONFIG_TIGHT))
        passes.append((binary_crop, _TESS_CONFIG_BLOCK))

    # Full image fallbacks
    passes.append((images[0], _TESS_CONFIG_TIGHT))
    passes.append((images[0], _TESS_CONFIG_BLOCK))
    passes.append((images[1], _TESS_CONFIG_TIGHT))
    passes.append((images[2], _TESS_CONFIG_TIGHT))
    passes.append((images[1], _TESS_CONFIG_SPARSE))

    for img, config in passes:
        text = await loop.run_in_executor(None, _run_tesseract, img, config)
        collected.append(text)
        combined = "\n".join(collected).upper()
        if _STRICT_ID_RE.search(combined):
            break

    return "\n".join(collected)


# ─────────────────────────────────────────────
#  CBE ID EXTRACTION — ANCHOR-BASED
# ─────────────────────────────────────────────
# CBE transaction IDs always appear after "transaction ID:" in the receipt.
# By anchoring to that label we avoid accidentally grabbing other alphanumeric
# strings on the page (account numbers, amounts, etc.)
#
# The ID itself is always FT followed by exactly 10 alphanumeric characters.
# The ID is always terminated by a period, space, newline, or end of string.
# This tight boundary is what prevents phantom characters being appended.

_CBE_ANCHOR_RE = re.compile(
    r"TRANSACTION\s*ID\s*[:\s]+([A-Z0-9]{10,16}?)(?=[.\s\n]|$)",
    re.IGNORECASE
)

# Also match bare FT patterns as fallback, but with tight right boundary
_CBE_BARE_RE = re.compile(
    r"\b(FT[A-Z0-9]{8,12})(?=[.\s\n,;]|$)"
)

def _extract_cbe(up: str) -> list[str]:
    """
    Anchor-first extraction: look for 'transaction ID:' label then grab
    what immediately follows. Falls back to bare FT pattern scan only if
    anchor method finds nothing.
    """
    candidates = []

    # Method 1: Anchor on label (most reliable for CBE app receipts)
    for m in _CBE_ANCHOR_RE.finditer(up):
        val = m.group(1).strip().rstrip(".")
        # Ensure it starts with FT (sometimes the label match starts mid-ID)
        if val.startswith("FT") and len(val) >= 10:
            candidates.append(val)
        elif "FT" in val:
            # Extract from FT onwards
            idx = val.index("FT")
            candidates.append(val[idx:])

    # Method 2: Bare FT scan with tight boundary
    for m in _CBE_BARE_RE.finditer(up):
        val = m.group(1).strip().rstrip(".")
        if val not in candidates:
            candidates.append(val)

    # Deduplicate preserving order
    seen = []
    for c in candidates:
        c = c.rstrip(".")  # strip trailing period one more time
        if c and c not in seen:
            seen.append(c)
    return seen


# ─────────────────────────────────────────────
#  CANDIDATE GENERATION WITH CORRECT CONFUSABLES
# ─────────────────────────────────────────────
# Fixed: added 4↔A which is the primary failure mode in these CBE receipts.
# (Tesseract reads '4' as 'A' in certain fonts and contrast levels)
_CONFUSABLE_GROUPS: dict[str, list[str]] = {
    'O': ['O', '0'],
    '0': ['0', 'O'],
    'I': ['I', '1', 'L'],
    '1': ['1', 'I', 'L'],
    'L': ['L', '1', 'I'],
    'A': ['A', '4'],   # ← KEY FIX: Tesseract reads '4' as 'A' in CBE font
    '4': ['4', 'A'],   # ← KEY FIX: and vice versa
    'S': ['S', '5'],   # '5' sometimes read as 'S'
    '5': ['5', 'S'],
    'B': ['B', '8'],   # '8' sometimes read as 'B'
    '8': ['8', 'B'],
    'G': ['G', '6'],
    '6': ['6', 'G'],
}

def generate_id_variants(raw: str, max_variants: int = 64) -> list[str]:
    """
    Generates every plausible reading of an extracted ID by substituting
    visually confusable characters. The literal OCR reading is always
    tried first. The bank API is the only arbiter of which is correct.
    """
    raw = (raw or "").strip().upper().rstrip(".")
    if not raw:
        return []

    ambiguous_positions = [i for i, c in enumerate(raw) if c in _CONFUSABLE_GROUPS]

    if not ambiguous_positions:
        return [raw]

    if len(ambiguous_positions) > 6:
        # Too many to brute-force — produce 3 sensible readings
        as_read = raw
        numerals = list(raw)
        letters = list(raw)
        for i in ambiguous_positions:
            c = raw[i]
            if c in ('O', '0'):
                numerals[i] = '0'; letters[i] = 'O'
            elif c in ('A', '4'):
                numerals[i] = '4'; letters[i] = 'A'
            elif c in ('S', '5'):
                numerals[i] = '5'; letters[i] = 'S'
            elif c in ('B', '8'):
                numerals[i] = '8'; letters[i] = 'B'
            elif c in ('G', '6'):
                numerals[i] = '6'; letters[i] = 'G'
            else:  # I, 1, L
                numerals[i] = '1'; letters[i] = 'I'
        candidates = [as_read, "".join(numerals), "".join(letters)]
    else:
        options = [_CONFUSABLE_GROUPS[raw[i]] for i in ambiguous_positions]
        candidates = []
        for combo in itertools_product(*options):
            chars = list(raw)
            for pos, val in zip(ambiguous_positions, combo):
                chars[pos] = val
            candidates.append("".join(chars))
        # Literal reading first
        candidates.sort(key=lambda v: v != raw)

    seen: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.append(c)
    return seen[:max_variants]


# ─────────────────────────────────────────────
#  PROVIDER DETECTION
# ─────────────────────────────────────────────
def _detect_provider(up: str) -> str:
    if any(k in up for k in ("ABYSSINIA", "BOA")):
        return "Abyssinia"
    if any(k in up for k in ("COMMERCIAL BANK", "CBE", "BRECIEPT")) or re.search(r"\bFT[A-Z0-9]{8,12}\b", up):
        return "CBE"
    if any(k in up for k in ("TELEBIRR", "ETHIO TELECOM", "TELE BIRR")) or re.search(r"\b(D[A-Z0-9]{9})\b", up):
        return "Telebirr"
    if "AWASH" in up:
        return "Awash"
    return "Unknown"


# ─────────────────────────────────────────────
#  TELEBIRR EXTRACTION
# ─────────────────────────────────────────────
def _extract_telebirr(up: str, raw: str) -> list[str]:
    candidates = []
    for label in ("TRANSACTION NUMBER", "TRANSACTION NO", "INVOICE NO",
                  "INVOICE NUMBER", "REF NO", "REFERENCE NO", "NUMBER"):
        m = re.search(rf"{label}[:\s#]+([A-Z0-9]{{8,14}})(?=[.\s\n]|$)", up)
        if m:
            candidates.append(m.group(1).rstrip("."))
    m = re.search(r"የግብይት\s*ቁጥር[:\s]+([A-Z0-9a-z]{8,14})", raw, re.UNICODE)
    if m:
        candidates.append(m.group(1).upper().rstrip("."))
    for m in re.finditer(r"\b(D[A-Z0-9]{9})(?=[.\s\n]|$)", up):
        val = m.group(1).rstrip(".")
        if val not in candidates:
            candidates.append(val)
    seen = []
    for c in candidates:
        if c not in seen:
            seen.append(c)
    return seen


# ─────────────────────────────────────────────
#  AMOUNT FALLBACK
# ─────────────────────────────────────────────
def _extract_amount_fallback(raw: str) -> str | None:
    amounts = re.findall(r"(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", raw)
    return max(amounts, key=lambda x: len(x.replace(",", ""))) if amounts else None


def _safe_amount(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


# ─────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────
async def extract_local_data(img_stream: io.BytesIO) -> dict:
    loop = asyncio.get_running_loop()

    # Run preprocessing and crop in parallel
    images, cropped = await asyncio.gather(
        loop.run_in_executor(None, _preprocess_variants, img_stream),
        loop.run_in_executor(None, _crop_text_region, img_stream),
    )

    raw = await _ocr_smart(images, cropped)

    # Clean to uppercase alphanumeric + punctuation for matching
    up = re.sub(r'[^A-Z0-9\n\s:.\-]', ' ', raw.upper())
    provider = _detect_provider(up)

    raw_candidates: list[str] = []
    if provider in ("CBE", "Abyssinia", "Unknown"):
        raw_candidates = _extract_cbe(up)
        if raw_candidates:
            provider = "CBE"
        elif provider == "Unknown":
            tb = _extract_telebirr(up, raw)
            if tb:
                provider = "Telebirr"
                raw_candidates = tb
    elif provider == "Telebirr":
        raw_candidates = _extract_telebirr(up, raw)

    # Expand each candidate into all plausible readings
    ref_candidates: list[str] = []
    for base in raw_candidates:
        for v in generate_id_variants(base):
            if v not in ref_candidates:
                ref_candidates.append(v)
    ref_candidates = ref_candidates[:80]

    print(f"[OCR] Provider: {provider}")
    print(f"[OCR] Raw candidates: {raw_candidates}")
    print(f"[OCR] All variants ({len(ref_candidates)}): {ref_candidates[:10]}...")

    return {
        "provider": provider,
        "ref": ref_candidates[0] if ref_candidates else None,
        "ref_candidates": ref_candidates,
        "amount_fallback": _extract_amount_fallback(raw),
        "raw_text": raw,
    }


async def verify_external(candidates: list[str], provider: str) -> dict:
    """
    Tries every plausible reading against the real bank API.
    Returns the first confirmed match. The bank is the source of truth.
    """
    client = get_http_client()
    if not candidates:
        return {"success": False, "error": "No candidate reference extracted"}

    endpoints = [API_URL]
    if provider == "Telebirr":
        endpoints.append("https://verifyapi.leulzenebe.pro/verify-telebirr/")
    elif provider == "Abyssinia":
        endpoints.append("https://verifyapi.leulzenebe.pro/verify-abyssinia")

    last_result = {"success": False, "error": "No matching transaction found"}

    for ref_variant in candidates:
        payload = {"reference": ref_variant}
        if provider in ("CBE", "Abyssinia"):
            payload["suffix"] = CBE_SUFFIX if provider == "CBE" else ABYSSINIA_SUFFIX

        for url in endpoints:
            try:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"[API] ref={ref_variant} matched={bool(data.get('success'))}")
                    if data.get("success"):
                        data["_matched_reference"] = ref_variant
                        return data
                    last_result = data
            except Exception as e:
                print(f"[API] Network error for ref={ref_variant}: {e}")
                continue

    return last_result


def is_hilawe_receiver(raw: str, bank_data: dict) -> bool:
    if not bank_data:
        bank_data = {}
    if "HILAWE" in raw.upper():
        return True
    root_receiver = (
        bank_data.get("receiver") or
        bank_data.get("creditedPartyName") or
        bank_data.get("credited_party_name") or ""
    )
    nested = bank_data.get("data") or {}
    nested_receiver = (
        nested.get("receiver") or
        nested.get("creditedPartyName") or
        nested.get("credited_party_name") or ""
    )
    api_combined = f"{root_receiver} {nested_receiver}".upper()
    print(f"[Receiver] Root='{root_receiver}' Nested='{nested_receiver}'")
    return "HILAWE" in api_combined


def _time_ago_display(bank_data: dict) -> str:
    try:
        payment_time_str = bank_data.get("date")
        if not payment_time_str:
            return "(Time unknown)"
        pay_dt = datetime.fromisoformat(payment_time_str.replace("Z", "+00:00"))
        total_seconds = int((datetime.now(timezone.utc) - pay_dt).total_seconds())
        if total_seconds <= 0:
            return "(Time unknown)"
        days, rem = divmod(total_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        if days > 0:
            return f"({days}d {hours}h ago)"
        if hours > 0:
            return f"({hours}h {minutes}m ago)"
        return f"({minutes}m ago)"
    except Exception as e:
        print(f"[Time] parse error: {e}")
        return "(Time unknown)"


# ─────────────────────────────────────────────
#  TELEGRAM HANDLERS
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

    if not local["ref_candidates"]:
        await status_msg.edit_text(
            f"🤖 <b>AUDIT FAILED</b>\n"
            f"⚠️ Could not extract a valid transaction ID.\n"
            f"Raw OCR preview: <code>{local['raw_text'][:200]}</code>\n"
            f"⏱️ {time.perf_counter() - start_time:.2f}s",
            parse_mode="HTML"
        )
        await state.clear()
        return

    alt_count = len(local["ref_candidates"]) - 1
    await status_msg.edit_text(
        f"📡 <b>Querying:</b> <code>{local['ref']}</code>"
        + (f" (+{alt_count} alt readings)" if alt_count > 0 else "")
        + f"\n<b>Provider:</b> {local['provider']}",
        parse_mode="HTML",
    )

    bank_data = await verify_external(local["ref_candidates"], local["provider"])
    is_real = bank_data.get("success", False)
    total_elapsed = time.perf_counter() - start_time

    matched_ref  = bank_data.get("_matched_reference") or local["ref"] or "N/A"
    payer        = bank_data.get("payer", "Unknown")
    receiver     = bank_data.get("receiver", "N/A")
    amount       = _safe_amount(bank_data.get("amount", 0))
    time_display = _time_ago_display(bank_data)
    is_hilawe    = is_hilawe_receiver(local["raw_text"], bank_data)

    if is_real and is_hilawe:
        report = (
            f"✅ <b>TRANSACTION VERIFIED</b>\n────────────────────\n"
            f"👤 <b>Payer:</b> <code>{payer}</code>\n"
            f"💰 <b>Amount:</b> {amount:,.2f} ETB\n"
            f"🏦 <b>Bank:</b> {local['provider']} {time_display}\n"
            f"🆔 <b>Ref ID:</b> <code>{matched_ref}</code>\n"
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
            f"🆔 <b>Ref ID tried:</b> <code>{matched_ref}</code>\n\n"
            f"⚠️ <b>Protocol:</b> Do not release.\n⏱️ <b>Audit:</b> {total_elapsed:.2f}s"
        )

    await status_msg.edit_text(report, parse_mode="HTML")
    await state.clear()


def format_audit_report(local, bank_data, elapsed, is_real, is_hilawe):
    matched_ref  = bank_data.get("_matched_reference") or local.get("ref") or "N/A"
    payer        = bank_data.get("payer", "Unknown")
    receiver     = bank_data.get("receiver", "N/A")
    amount       = _safe_amount(bank_data.get("amount", 0))
    time_display = _time_ago_display(bank_data)

    if is_real and is_hilawe:
        return (
            f"✅ <b>TRANSACTION VERIFIED</b>\n────────────────────\n"
            f"👤 <b>Payer:</b> <code>{payer}</code>\n"
            f"💰 <b>Amount:</b> {amount:,.2f} ETB\n"
            f"🏦 <b>Bank:</b> {local['provider']} {time_display}\n"
            f"🆔 <b>Ref ID:</b> <code>{matched_ref}</code>\n"
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
            f"🆔 <b>Ref ID tried:</b> <code>{matched_ref}</code>\n\n"
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

            local     = await extract_local_data(img_stream)
            bank_data = {}
            is_real   = False

            if local["ref_candidates"]:
                bank_data = await verify_external(local["ref_candidates"], local["provider"])
                is_real   = bank_data.get("success", False)

            is_hilawe   = is_hilawe_receiver(local["raw_text"], bank_data)
            matched_ref = bank_data.get("_matched_reference") or local["ref"] or "N/A"
            api_amount  = bank_data.get("data", {}).get("amount") if isinstance(bank_data.get("data"), dict) else None
            display_amt = f"{_safe_amount(api_amount):,.2f}" if api_amount else (local["amount_fallback"] or "?")
            elapsed     = time.perf_counter() - start_time

            if is_real and is_hilawe:
                caption = (
                    f"🤖 <b>API MATCH: SECURE & VALID ✅</b>\n────────────────────\n"
                    f"🟢 <b>Audit #{rec['id']}</b> • Authentic ledger match.\n\n"
                    f"📊 <b>{local['provider']}</b> • 🆔 <code>{matched_ref}</code> • 💰 <b>{display_amt} ETB</b>\n"
                    f"⏱️ <b>Speed:</b> {elapsed:.2f}s"
                )
            else:
                caption = (
                    f"🤖 <b>API MATCH: REJECTED 🚨</b>\n────────────────────\n"
                    f"🔴 <b>Audit #{rec['id']}</b> • No bank match.\n\n"
                    f"📊 <b>{local['provider']}</b> • 🆔 <code>{matched_ref}</code> • 💰 <b>{display_amt} ETB</b>\n"
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
                f"⚠️ <b>Error on #{rec['id']}:</b> <code>{e}</code>", parse_mode="HTML"
            )

    await asyncio.gather(*[process_one(r) for r in recent])
    await status_msg.delete()