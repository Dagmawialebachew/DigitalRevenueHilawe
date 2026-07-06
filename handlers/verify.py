"""
verify.py — Accuracy-First Edition
Fast path is still fast (~1 OCR pass on clean screenshots), but ambiguous
characters are no longer guessed — every plausible reading is generated
and checked against the real bank API, which is the only true source of
truth for what the reference ID actually is.
"""

import os
import io
import asyncio
import re
import platform
import shutil
import time
from datetime import datetime, timezone
from itertools import product

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
#  IN-MEMORY IMAGE PREPROCESSING (two variants: normal + aggressive)
# ─────────────────────────────────────────────
def _preprocess_variants(img_stream: io.BytesIO) -> list[Image.Image]:
    """Produces a couple of differently-processed versions of the image.
    Different receipts (screenshots, camera photos, low-contrast dark-mode
    apps, etc.) respond better to different preprocessing, so instead of
    betting everything on one fixed pipeline we keep two candidates ready
    and only reach for the second one if the first doesn't yield a
    confident read."""
    img_stream.seek(0)
    base = Image.open(img_stream).convert("L")
    w, h = base.size

    # Memory guard / upscaling for tiny screenshots
    if w > 1500:
        ratio = 1500 / w
        base = base.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
    elif w < 800:
        base = base.resize((w * 2, h * 2), Image.Resampling.BICUBIC)

    sharpened = base.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=2))

    variants = []
    for contrast in (2.2, 3.2):
        enhanced = ImageEnhance.Contrast(sharpened).enhance(contrast)
        arr = np.array(enhanced)
        threshold = np.mean(arr) * 0.92
        binary = np.where(arr > threshold, 255, 0).astype(np.uint8)
        variants.append(Image.fromarray(binary))

    return variants

# ─────────────────────────────────────────────
#  ESCALATING OCR (stop as soon as we get a confident structural match)
# ─────────────────────────────────────────────
def _run_tesseract(img: Image.Image, psm: int) -> str:
    tess_config = f"--oem 3 --psm {psm} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:-/ "
    return pytesseract.image_to_string(img, config=tess_config)

# A "confident" structural match: looks like a real CBE/Telebirr ID shape.
_STRICT_ID_RE = re.compile(r"\bFT[A-Z0-9]{8,12}\b|\bD[A-Z0-9]{9}\b")

async def _ocr_smart(images: list[Image.Image]) -> str:
    """Runs OCR passes in increasing order of effort, stopping the moment
    one of them yields a structurally-confident candidate. Clean
    screenshots resolve in a single pass; messy ones get up to 4."""
    loop = asyncio.get_running_loop()
    collected: list[str] = []

    passes = [
        (images[0], 6),
        (images[0], 4),
        (images[1], 6),
        (images[1], 11),
    ]

    for img, psm in passes:
        text = await loop.run_in_executor(None, _run_tesseract, img, psm)
        collected.append(text)
        combined_upper = "\n".join(collected).upper()
        if _STRICT_ID_RE.search(combined_upper):
            break

    return "\n".join(collected)

# ─────────────────────────────────────────────
#  CANDIDATE GENERATION (replaces blind character "healing")
# ─────────────────────────────────────────────
# Characters tesseract commonly confuses with each other. Note this is
# NOT a one-way mapping — a real ID can legitimately contain O, I, L, 0
# or 1, so we must not assume any single "corrected" direction is right.
_CONFUSABLE_GROUPS = {
    'O': ['O', '0'],
    '0': ['0', 'O'],
    'I': ['I', '1', 'L'],
    '1': ['1', 'I', 'L'],
    'L': ['L', '1', 'I'],
}

def generate_id_variants(raw: str, max_variants: int = 40) -> list[str]:
    """
    Returns an ordered list of plausible readings of an extracted ID.
    Instead of guessing which O/0/I/1/L is "correct", every plausible
    combination is generated (bounded, to avoid combinatorial blow-up) so
    the real bank API can confirm which one actually exists. The literal
    OCR reading is always tried first since it's most often correct.
    """
    raw = (raw or "").strip().upper()
    if not raw:
        return []

    ambiguous_positions = [i for i, c in enumerate(raw) if c in _CONFUSABLE_GROUPS]

    if not ambiguous_positions:
        return [raw]

    if len(ambiguous_positions) > 5:
        # Too many ambiguous characters to safely brute-force (would mean
        # dozens/hundreds of API calls). Fall back to the three most
        # sensible global readings instead of one blind guess.
        as_read = raw
        numerals_first = list(raw)
        letters_first = list(raw)
        for i in ambiguous_positions:
            c = raw[i]
            if c in ('O', '0'):
                numerals_first[i] = '0'
                letters_first[i] = 'O'
            else:  # I, 1, L
                numerals_first[i] = '1'
                letters_first[i] = 'I' if c != 'L' else 'L'
        candidates = [as_read, "".join(numerals_first), "".join(letters_first)]
    else:
        options_per_pos = [_CONFUSABLE_GROUPS[raw[i]] for i in ambiguous_positions]
        candidates = []
        for combo in product(*options_per_pos):
            chars = list(raw)
            for pos, val in zip(ambiguous_positions, combo):
                chars[pos] = val
            candidates.append("".join(chars))
        # Literal OCR reading first (most likely correct), rest after
        candidates.sort(key=lambda v: v != raw)

    seen = []
    for c in candidates:
        if c not in seen:
            seen.append(c)
    return seen[:max_variants]

# ─────────────────────────────────────────────
#  EXTRACTION LOGIC (returns candidate lists, no guessing baked in)
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

def _extract_cbe(up: str) -> list[str]:
    candidates = []
    m = re.search(r"F\s*T\s*([A-Z0-9]{8,12})", up)
    if m:
        candidates.append(("FT" + m.group(1)).replace(" ", ""))
    m = re.search(r"(?:ID|TRANSACTION\s*ID)[:\s]+([A-Z0-9]{10,14})", up)
    if m:
        candidates.append(m.group(1))
    for m in re.finditer(r"\b(FT[A-Z0-9]{8,12})\b", up):
        candidates.append(m.group(1))
    seen = []
    for c in candidates:
        if c not in seen:
            seen.append(c)
    return seen

def _extract_telebirr(up: str, raw: str) -> list[str]:
    candidates = []
    for label in ("TRANSACTION NUMBER", "TRANSACTION NO", "INVOICE NO", "INVOICE NUMBER", "REF NO", "REFERENCE NO", "NUMBER"):
        m = re.search(rf"{label}[:\s#]+([A-Z0-9]{{8,14}})", up)
        if m:
            candidates.append(m.group(1))
    m = re.search(r"የግብይት\s*ቁጥር[:\s]+([A-Z0-9a-z]{8,14})", raw, re.UNICODE)
    if m:
        candidates.append(m.group(1).upper())
    for m in re.finditer(r"\b(D[A-Z0-9]{9})\b", up):
        candidates.append(m.group(1))
    seen = []
    for c in candidates:
        if c not in seen:
            seen.append(c)
    return seen

def _extract_amount_fallback(raw: str) -> str | None:
    amounts = re.findall(r"(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", raw)
    return max(amounts, key=lambda x: len(x.replace(",", ""))) if amounts else None

def _safe_amount(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0

# ─────────────────────────────────────────────
#  PUBLIC EXPOSED HOOKS
# ─────────────────────────────────────────────
async def extract_local_data(img_stream: io.BytesIO) -> dict:
    loop = asyncio.get_running_loop()

    images = await loop.run_in_executor(None, _preprocess_variants, img_stream)
    raw = await _ocr_smart(images)

    up = re.sub(r'[^A-Z0-9\n\s:\-]', ' ', raw.upper())
    provider = _detect_provider(up)

    raw_candidates: list[str] = []
    if provider in ("CBE", "Abyssinia"):
        raw_candidates = _extract_cbe(up)
    elif provider in ("Telebirr", "Unknown"):
        tb = _extract_telebirr(up, raw)
        if tb:
            provider = "Telebirr"
            raw_candidates = tb
        elif provider == "Unknown":
            # last-resort attempt in case it's actually a CBE receipt that
            # didn't contain any of the provider keywords
            fallback = _extract_cbe(up)
            if fallback:
                provider = "CBE"
                raw_candidates = fallback

    # Expand each raw candidate into every plausible reading, and let the
    # bank API (in verify_external) decide which one is real.
    ref_candidates: list[str] = []
    for base in raw_candidates:
        for v in generate_id_variants(base):
            if v not in ref_candidates:
                ref_candidates.append(v)
    ref_candidates = ref_candidates[:60]  # hard cap on API calls per receipt

    amount_fallback = _extract_amount_fallback(raw)
    return {
        "provider": provider,
        "ref": ref_candidates[0] if ref_candidates else None,
        "ref_candidates": ref_candidates,
        "amount_fallback": amount_fallback,
        "raw_text": raw,
    }

async def verify_external(candidates: list[str], provider: str) -> dict:
    """Tries every plausible reading of the reference ID against the real
    bank API and returns the first one that the bank actually confirms.
    This is what makes the system self-correcting against OCR ambiguity:
    we don't have to be sure which reading is right, the bank tells us."""
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
        if provider == "CBE":
            payload["suffix"] = CBE_SUFFIX
        elif provider == "Abyssinia":
            payload["suffix"] = ABYSSINIA_SUFFIX

        for url in endpoints:
            try:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    print("\n" + "═"*50)
                    print(f"🔥 [API RAW RESPONSE | {provider}] 🔥")
                    print(f"REF: {ref_variant}")
                    print(f"URL: {url}")
                    print(f"MATCH: {bool(data.get('success'))}")
                    print("═"*50 + "\n")
                    if data.get("success"):
                        data["_matched_reference"] = ref_variant
                        return data
                    last_result = data
            except Exception as e:
                print(f"⚠️ Network error hitting {url} with ref {ref_variant}: {e}")
                continue

    return last_result

def is_hilawe_receiver(raw: str, bank_data: dict) -> bool:
    """
    Bulletproof receiver validation checking both local OCR raw text
    and structure-agnostic API responses (root level & nested payload).
    """
    if not bank_data:
        bank_data = {}

    if "HILAWE" in raw.upper():
        return True

    root_receiver = (
        bank_data.get("receiver") or
        bank_data.get("creditedPartyName") or
        bank_data.get("credited_party_name") or
        ""
    )

    nested = bank_data.get("data") or {}
    nested_receiver = (
        nested.get("receiver") or
        nested.get("creditedPartyName") or
        nested.get("credited_party_name") or
        ""
    )

    api_combined_names = f"{root_receiver} {nested_receiver}".upper()

    print(f"DEBUG [Receiver Audit]: Root='{root_receiver}' | Nested='{nested_receiver}'")
    return "HILAWE" in api_combined_names

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
        print(f"Time parsing error: {e}")
        return "(Time unknown)"

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

    if not local["ref_candidates"]:
        await status_msg.edit_text(
            f"🤖 <b>AUDIT FAILED</b>\n⚠️ Could not extract a valid ID from the screenshot.\n⏱️ <b>Process latency:</b> {time.perf_counter() - start_time:.2f}s",
            parse_mode="HTML"
        )
        await state.clear()
        return

    await status_msg.edit_text(
        f"📡 <b>Querying:</b> <code>{local['ref']}</code>"
        + (f" (+{len(local['ref_candidates']) - 1} alt readings)" if len(local["ref_candidates"]) > 1 else "")
        + "...",
        parse_mode="HTML",
    )
    bank_data = await verify_external(local["ref_candidates"], local["provider"])
    is_real = bank_data.get("success", False)
    total_elapsed = time.perf_counter() - start_time

    matched_ref = bank_data.get("_matched_reference") or local["ref"] or "N/A"
    payer = bank_data.get("payer", "Unknown")
    receiver = bank_data.get("receiver", "N/A")
    amount = _safe_amount(bank_data.get("amount", 0))
    time_display = _time_ago_display(bank_data)

    is_hilawe = is_hilawe_receiver(local["raw_text"], bank_data)

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
    matched_ref = bank_data.get("_matched_reference") or local.get("ref") or "N/A"
    payer = bank_data.get("payer", "Unknown")
    receiver = bank_data.get("receiver", "N/A")
    amount = _safe_amount(bank_data.get("amount", 0))
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

            local = await extract_local_data(img_stream)
            bank_data = {}
            is_real = False

            if local["ref_candidates"]:
                bank_data = await verify_external(local["ref_candidates"], local["provider"])
                is_real = bank_data.get("success", False)

            is_hilawe = is_hilawe_receiver(local["raw_text"], bank_data)
            matched_ref = bank_data.get("_matched_reference") or local["ref"] or "N/A"
            api_amount = bank_data.get("data", {}).get("amount") if isinstance(bank_data.get("data"), dict) else None
            display_amount = f"{_safe_amount(api_amount):,.2f}" if api_amount else (local['amount_fallback'] or "?")
            elapsed = time.perf_counter() - start_time

            if is_real and is_hilawe:
                caption = (
                    f"🤖 <b>API MATCH: SECURE & VALID ✅</b>\n────────────────────\n"
                    f"🟢 <b>Audit #{rec['id']}</b> • 100% authentic ledger match.\n\n"
                    f"📊 <b>{local['provider']}</b> • 🆔 <code>{matched_ref}</code> • 💰 <b>{display_amount} ETB</b>\n"
                    f"⏱️ <b>Speed:</b> {elapsed:.2f}s"
                )
            else:
                caption = (
                    f"🤖 <b>API MATCH: REJECTED / FAKE ALERT 🚨</b>\n────────────────────\n"
                    f"🔴 <b>Audit #{rec['id']}</b> • Fraud guard triggered. No bank match.\n\n"
                    f"📊 <b>{local['provider']}</b> • 🆔 <code>{matched_ref}</code> • 💰 <b>{display_amount} ETB</b>\n"
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