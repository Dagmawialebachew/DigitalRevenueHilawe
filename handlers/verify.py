import os
import cv2
import re
import asyncio
import numpy as np
import httpx
from PIL import Image
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import settings

import pytesseract
import platform
import shutil

if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract") or "/usr/bin/tesseract"

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
API_KEY    = settings.VERIFY_API_KEY
API_URL    = "https://verifyapi.leulzenebe.pro/verify"
CBE_SUFFIX = "99533641"

router = Router(name="verify")

class PaymentStates(StatesGroup):
    waiting_for_screenshot = State()


# ─────────────────────────────────────────────
#  RECEIPT ARCHITECT v2  –  Fast & Accurate
# ─────────────────────────────────────────────
class ReceiptArchitect:

    # ── IMAGE PREPROCESSING ──────────────────────────────────────────────────
    def preprocess_image(self, image_path: str) -> str | None:
        img = cv2.imread(image_path)
        if img is None:
            return None

        h, w = img.shape[:2]

        # ① Upscale — 2× is enough and 33 % faster than 3×
        img = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # ② CLAHE — lifts dark-mode / low-contrast shots
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        gray  = clahe.apply(gray)

        # ③ Fast bilateral denoise (d=9 is lighter than d=11)
        gray = cv2.bilateralFilter(gray, 9, 75, 75)

        # ④ Otsu threshold
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        temp_path = f"temp_{os.path.basename(image_path)}"
        cv2.imwrite(temp_path, thresh)
        return temp_path

    # ── OCR (two-pass, parallel configs) ─────────────────────────────────────
    def _ocr(self, path: str) -> str:
        img = Image.open(path)
        # PSM 6 = single uniform block  |  PSM 4 = single column (catches table layouts)
        t6  = pytesseract.image_to_string(img, config="--oem 3 --psm 6")
        t4  = pytesseract.image_to_string(img, config="--oem 3 --psm 4")
        # Merge both passes — keeps the best of each
        return t6 + "\n" + t4

    # ── PROVIDER DETECTION ────────────────────────────────────────────────────
    @staticmethod
    def _detect_provider(text_up: str) -> str:
        if any(k in text_up for k in ("COMMERCIAL BANK", "CBE", "BRECIEPT.CBE", "FT2")):
            return "CBE"
        if any(k in text_up for k in ("TELEBIRR", "ETHIO TELECOM", "TELE BIRR",
                                       "TRANSACTION NUMBER", "INVOICE NO", "DDK", "DE6", "DE8", "DE9")):
            return "Telebirr"
        if "AWASH" in text_up:
            return "Awash"
        return "Unknown"

    # ── REFERENCE EXTRACTION ─────────────────────────────────────────────────
    @staticmethod
    def _extract_cbe_ref(text_up: str) -> str | None:
        # Pattern A — standard FT prefix (notification & web receipt)
        m = re.search(r"F\s*T\s*([A-Z0-9]{8,12})", text_up)
        if m:
            return ("FT" + m.group(1)).replace(" ", "")

        # Pattern B — after "ID:" label
        m = re.search(r"(?:ID|TRANSACTION\s*ID)[:\s]+([A-Z0-9]{10,14})", text_up)
        if m:
            return m.group(1).strip()

        # Pattern C — fallback: any FT-starting 10-14 char block
        m = re.search(r"\b(FT[A-Z0-9]{8,12})\b", text_up)
        return m.group(1) if m else None

    @staticmethod
    def _extract_telebirr_ref(text_up: str, raw: str) -> str | None:
        """
        Handles all Telebirr receipt layouts:
          • Simple success screen  → "Transaction Number: DE65L36GRH"
          • Telebirr app (Amharic) → "የግብይት ቁጥር: DE65L36GRH"
          • Full PDF receipt       → "Invoice No.: DDK22SFVU6"
        """

        # ── Layout 1: explicit English labels ────────────────────────
        for label in ("TRANSACTION NUMBER", "TRANSACTION NO", "INVOICE NO",
                      "INVOICE NUMBER", "REF NO", "REFERENCE NO"):
            pattern = rf"{re.escape(label)}[:\s#]+([A-Z0-9]{{8,14}})"
            m = re.search(pattern, text_up)
            if m:
                return m.group(1).strip()

        # ── Layout 2: Amharic label (የግብይት ቁጥር) ──────────────────
        # Amharic chars survive in raw_text even after uppercase
        m = re.search(r"የግብይት\s*ቁጥር[:\s]+([A-Z0-9a-z]{8,14})", raw, re.UNICODE)
        if m:
            return m.group(1).strip().upper()

        # ── Layout 3: greedy search – any dense DE/DDK block ─────────
        # Telebirr IDs start with DE or DDK
        m = re.search(r"\b((?:DE|DDK)[A-Z0-9]{6,12})\b", text_up)
        if m:
            return m.group(1).strip()

        # ── Layout 4: last-resort — any 8-14 alphanumeric block ──────
        # after known keywords
        for keyword in ("NUMBER", "NO", "INVOICE"):
            idx = text_up.find(keyword)
            if idx != -1:
                after = text_up[idx + len(keyword):idx + len(keyword) + 60]
                blocks = re.findall(r"[A-Z0-9]{8,14}", after)
                if blocks:
                    return blocks[0].strip()

        return None

    # ── AMOUNT EXTRACTION ─────────────────────────────────────────────────────
    @staticmethod
    def _extract_amount(raw: str) -> str | None:
        amounts = re.findall(r"(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", raw)
        if not amounts:
            return None
        return max(amounts, key=lambda x: len(x.replace(",", "")))

    # ── MAIN EXTRACTION ENTRY POINT ───────────────────────────────────────────
    def extract_local_data(self, image_path: str) -> dict:
        processed = self.preprocess_image(image_path)
        if not processed:
            return {"provider": "Error", "ref": None, "amount": None, "raw_text": ""}

        raw      = self._ocr(processed)
        text_up  = raw.upper()
        text_up  = re.sub(r'[^A-Z0-9\n\s:\-]', ' ', text_up)   # keep hyphens for "ETB-3641"

        if os.path.exists(processed):
            os.remove(processed)

        provider = self._detect_provider(text_up)
        ref      = None

        if provider == "CBE":
            ref = self._extract_cbe_ref(text_up)
        elif provider in ("Telebirr", "Unknown"):
            ref = self._extract_telebirr_ref(text_up, raw)
            if ref:
                provider = "Telebirr"

        amount = self._extract_amount(raw)

        print(f"[OCR] provider={provider} | ref={ref} | amount={amount}")
        return {"provider": provider, "ref": ref, "amount": amount, "raw_text": raw}

    # ── API VERIFICATION  (async, with timeout + retry) ───────────────────────
    async def verify_external(self, reference: str, provider: str) -> dict:
        payload = {"reference": reference.strip()}
        if provider == "CBE":
            payload["suffix"] = CBE_SUFFIX

        headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}

        endpoints = [API_URL]
        if provider == "Telebirr":
            endpoints.append("https://verifyapi.leulzenebe.pro/verify-telebirr/")

        async with httpx.AsyncClient(timeout=15.0) as client:
            for url in endpoints:
                try:
                    resp = await client.post(url, json=payload, headers=headers)
                    print(f"[API] {url} → {resp.status_code}")
                    if resp.status_code == 200:
                        return resp.json()
                except Exception as e:
                    print(f"[API] error → {e}")
        return {"success": False, "error": "All endpoints failed"}


# ─────────────────────────────────────────────
#  RECEIVER MATCH  (HILAWE check)
# ─────────────────────────────────────────────
def _is_hilawe(local_raw: str, bank_data: dict) -> bool:
    data = bank_data.get("data", {})
    api_name = str(
        data.get("receiver") or data.get("creditedPartyName") or
        data.get("credited_party_name") or ""
    ).upper()
    return "HILAWE" in local_raw.upper() or "HILAWE" in api_name


# ─────────────────────────────────────────────
#  HANDLERS
# ─────────────────────────────────────────────
def get_verifier_menu():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📸 Upload Screenshot", callback_data="test_upload"))
    builder.row(types.InlineKeyboardButton(text="🎲 Test Batch (DB)", callback_data="test_db_random"))
    return builder.as_markup()


@router.callback_query(F.data == "test_upload")
async def start_upload_test(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🎯 *Ready!* Send me the receipt screenshot.")
    await state.set_state(PaymentStates.waiting_for_screenshot)


@router.message(PaymentStates.waiting_for_screenshot, F.photo)
async def handle_screenshot_test(message: types.Message, state: FSMContext, bot: Bot):
    status_msg = await message.answer("🔄 <b>Scanning receipt…</b>", parse_mode="HTML")

    # ── Download ──────────────────────────────────────────────────────────────
    photo     = message.photo[-1]
    file      = await bot.get_file(photo.file_id)
    os.makedirs("downloads", exist_ok=True)
    file_path = f"downloads/{photo.file_id}.png"
    await bot.download_file(file.file_path, file_path)

    # ── OCR + API in parallel ─────────────────────────────────────────────────
    architect = ReceiptArchitect()
    local     = architect.extract_local_data(file_path)

    if os.path.exists(file_path):
        os.remove(file_path)

    if not local["ref"] or len(str(local["ref"])) < 8:
        await status_msg.edit_text(
            "⚠️ <b>Could not read a valid transaction ID.</b>\n"
            "Please send a clearer screenshot (full receipt, good lighting).",
            parse_mode="HTML"
        )
        await state.clear()
        return

    await status_msg.edit_text(
        f"📡 <b>Verifying</b> <code>{local['ref']}</code> with bank…",
        parse_mode="HTML"
    )

    bank_data = await architect.verify_external(local["ref"], local["provider"])

    # ── Decision ──────────────────────────────────────────────────────────────
    is_real   = bank_data.get("success", False)
    is_hilawe = _is_hilawe(local["raw_text"], bank_data)

    report = (
        "🧐 <b>VERIFICATION VERDICT</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"🏦 <b>Bank:</b> <i>{local['provider']}</i>\n"
        f"🆔 <b>Ref:</b> <code>{local['ref']}</code>\n"
        f"💰 <b>Amount:</b> {local['amount'] or '—'} ETB\n"
        f"✅ <b>Bank Verified:</b> {'<b>YES</b>' if is_real else '<b>NO</b>'}\n"
        f"👤 <b>Receiver:</b> {'<u>HILAWE ✔</u>' if is_hilawe else '<i>NOT MATCHED</i>'}\n"
        "━━━━━━━━━━━━━━━\n"
    )
    report += (
        "🟢 <b>RESULT: TRANSACTION VALIDATED ✅</b>"
        if is_real and is_hilawe else
        "🔴 <b>RESULT: REJECTED — MANUAL REVIEW ❌</b>"
    )

    await status_msg.edit_text(report, parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "test_db_random")
async def test_batch_from_db(callback: types.CallbackQuery, bot: Bot, db):
    status_msg = await callback.message.answer("🔍 <b>Fetching last 5 payments…</b>", parse_mode="HTML")
    recent = await db.get_recent_payment_proofs(5)

    if not recent:
        return await status_msg.edit_text("❌ No payments found in DB.")

    architect = ReceiptArchitect()
    os.makedirs("downloads", exist_ok=True)

    # ── Process all receipts concurrently ─────────────────────────────────────
    async def process_one(rec):
        try:
            file      = await bot.get_file(rec["proof_file_id"])
            path      = f"downloads/stress_{rec['id']}.png"
            await bot.download_file(file.file_path, path)

            local = architect.extract_local_data(path)
            if os.path.exists(path):
                os.remove(path)

            bank_data = {}
            is_real   = False
            if local["ref"]:
                bank_data = await architect.verify_external(local["ref"], local["provider"])
                is_real   = bank_data.get("success", False)

            is_hilawe = _is_hilawe(local["raw_text"], bank_data)

            caption = (
                f"📑 <b>AUDIT #{rec['id']}</b>\n"
                "━━━━━━━━━━━━━━━\n"
                f"🏦 <b>Bank:</b> {local['provider']}\n"
                f"🆔 <b>Ref:</b> <code>{local['ref'] or 'NOT DETECTED'}</code>\n"
                f"💰 <b>Amount:</b> {local['amount'] or '?'} ETB\n"
                f"✅ <b>Verified:</b> {'YES' if is_real else 'NO'}\n"
                f"👤 <b>Target:</b> {'✅ HILAWE' if is_hilawe else '❌ NOT FOUND'}\n"
                "━━━━━━━━━━━━━━━\n"
                f"🏁 {'🟢 VALID' if is_real and is_hilawe else '🔴 FLAG'}"
            )

            await bot.send_photo(
                chat_id=callback.from_user.id,
                photo=rec["proof_file_id"],
                caption=caption,
                parse_mode="HTML"
            )
        except Exception as e:
            await callback.message.answer(
                f"⚠️ <b>Error ID {rec['id']}:</b> <code>{e}</code>",
                parse_mode="HTML"
            )

    # Run all receipts concurrently for maximum speed
    await asyncio.gather(*[process_one(r) for r in recent])
    await status_msg.delete()